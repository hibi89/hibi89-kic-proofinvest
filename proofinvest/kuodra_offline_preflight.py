"""KUODRA P10: safe, read-only SEC-capture annual-period discovery.

Offline only. This tool does NOT write SQLite, invoke SEC/LLMs, authenticate
local provenance or choose an evidentiary original-text anchor. The operator
must still review and explicitly select the intended period and needle.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any, Mapping

from disclosure_lightning.core import index_submissions
from .kuodra_capture_replay import _capture_instant
from .local_sec_packet import _json_object, _MAX_FILE_BYTES
from .sec_capture_bundle import _read_checked_capture_bundle
from .sec_companyfacts import MAX_AMOUNT, MAX_ROWS, REVENUE_TAGS, _date, verify_sec_annual_revenue

_MAX_PERIOD_ENDS = 64
_MAX_CANDIDATE_PAIRS = 80
_MAX_RETURNED = 5


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.saved-sec-capture-preflight.v1",
        "status": "blocked",
        "reason_code": reason,
        "mode": "READ_ONLY_UNTRUSTED_CAPTURE_OFFLINE",
        "issuer_cik_self_reported": None,
        "accession_self_reported": None,
        "as_of_self_reported": None,
        "source_sha256": None,
        "period_candidates": [],
        "candidates_truncated": False,
        "selected_period": None,
        "operator_must_confirm": [
            "issuer_cik", "accession", "as_of",
            "current_end", "prior_end", "needle",
            "requested_intent", "audit_db", "run_id",
            "explicit_local_audit_persistence_consent",
        ],
        "audit_written": False,
        "network_calls": 0,
        "live_model_called": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "trade_executed": False,
    }


def inspect_saved_capture_periods(bundle_path: str | Path) -> dict[str, Any]:
    """List at most five operator-review candidates from one locally verified ZIP.

    Reuses the actual annual revenue verifier to avoid proposing combinations
    that are not accepted by the Guard replay. Only the manifest's self-
    reported capture day is used; no present-day backdating or remote fetch.
    """
    result = _result("CAPTURE_ZIP_UNVERIFIABLE")
    verdict, raws, receipt = _read_checked_capture_bundle(
        Path(bundle_path).expanduser()
    )
    if (verdict.get("status") != "bundle_integrity_pass_origin_unverified"
            or verdict.get("local_bytes_and_manifest_match") is not True
            or not isinstance(raws, Mapping)
            or not isinstance(receipt, Mapping)
            or receipt.get("capture_bytes_persisted") is not False):
        return result
    day, cik, accession = (receipt.get(k) for k in
                           ("observed_utc_day", "issuer_cik", "accession"))
    instants = [
        _capture_instant(receipt.get(k), day)
        for k in ("submissions_observed_at_utc",
                  "companyfacts_observed_at_utc",
                  "original_observed_at_utc")
    ]
    if (not isinstance(day, str) or _date(day) is None
            or any(item is None for item in instants)
            or instants != sorted(instants)):
        result["reason_code"] = "CAPTURE_OBSERVATION_CLOCK_INVALID"
        return result
    try:
        indexed = index_submissions(
            raws["submissions"], cik=cik, as_of=day,
            forms=frozenset({"10-K"}), provenance="OFFLINE_UNVERIFIED",
            collected_at=receipt["submissions_observed_at_utc"],
        )
        filing = [row for row in indexed["filings"]
                  if row.get("accession") == accession and row.get("form") == "10-K"]
        if len(filing) != 1:
            result["reason_code"] = "TARGET_10K_NOT_IN_SAVED_SUBMISSIONS_AS_OF"
            return result
        companyfacts = _json_object(raws["companyfacts"], limit=_MAX_FILE_BYTES)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        result["reason_code"] = "CAPTURE_SUBMISSIONS_OR_FACTS_INVALID"
        return result

    facts = companyfacts.get("facts")
    gaap = facts.get("us-gaap") if isinstance(facts, Mapping) else None
    if not isinstance(gaap, Mapping):
        result["reason_code"] = "US_GAAP_ANNUAL_FACTS_UNAVAILABLE"
        return result
    ends: set[date] = set()
    for concept in REVENUE_TAGS:
        tag = gaap.get(concept)
        if tag is None:
            continue
        units = tag.get("units") if isinstance(tag, Mapping) else None
        rows = units.get("USD") if isinstance(units, Mapping) else None
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            result["reason_code"] = "UNBOUNDED_OR_INVALID_REVENUE_CONCEPT"
            return result
        for row in rows:
            if not isinstance(row, Mapping):
                result["reason_code"] = "INVALID_REVENUE_FACT_RECORD"
                return result
            if row.get("accn") != accession or row.get("form") != "10-K":
                continue
            start, end, filed = (_date(row.get(k)) for k in
                                 ("start", "end", "filed"))
            if (start is None or end is None or filed is None
                    or not start < end <= filed <= _date(day)
                    or not 330 <= (end - start).days <= 380
                    or type(row.get("val")) is not int
                    or not 0 <= row["val"] <= MAX_AMOUNT):
                result["reason_code"] = "INVALID_TARGET_ANNUAL_FACT"
                return result
            ends.add(end)
            if len(ends) > _MAX_PERIOD_ENDS:
                result["reason_code"] = "TOO_MANY_ANNUAL_PERIODS"
                return result
    if len(ends) < 2:
        result["reason_code"] = "NO_CONSECUTIVE_ANNUAL_PERIODS"
        return result

    pairs = [
        (current, prior)
        for current in sorted(ends, reverse=True)
        for prior in sorted(ends, reverse=True)
        if prior < current and 330 <= (current-prior).days <= 380
    ]
    if not pairs or len(pairs) > _MAX_CANDIDATE_PAIRS:
        result["reason_code"] = (
            "TOO_MANY_FISCAL_PERIOD_PAIRS" if pairs else
            "NO_CONSECUTIVE_ANNUAL_PERIODS"
        )
        return result
    accepted = []
    for current, prior in pairs:
        verification = verify_sec_annual_revenue(
            companyfacts, cik=cik, accession=accession,
            current_end=current.isoformat(),
            prior_end=prior.isoformat(), as_of=day,
        )
        if verification["status"] != "calculated_unverified":
            continue
        accepted.append({
            "current_end": current.isoformat(),
            "prior_end": prior.isoformat(),
            "growth_pct_unverified": verification["growth_pct"],
            "revenue_concept": verification["revenue_concept"],
            "filing_date": verification["filing_date"],
        })
    result.update(
        issuer_cik_self_reported=cik,
        accession_self_reported=accession,
        as_of_self_reported=day,
        source_sha256=dict(receipt["raw_response_sha256"]),
    )
    if not accepted:
        result["reason_code"] = "NO_VERIFIABLE_REVENUE_PERIOD_PAIR"
        return result
    result.update(
        status="review_candidates_available",
        reason_code="OPERATOR_REVIEW_REQUIRED_NO_EXECUTION",
        period_candidates=accepted[:_MAX_RETURNED],
        candidates_truncated=len(accepted) > _MAX_RETURNED,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only local SEC ZIP preflight; zero DB/network/LLM writes."
    )
    parser.add_argument("--capture-zip", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = inspect_saved_capture_periods(args.capture_zip)
    except (OSError, TypeError, KeyError, ValueError,
            OverflowError, RecursionError):
        report = _result("CAPTURE_ZIP_PREVIEW_FAILED")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["status"] == "review_candidates_available" else 2


if __name__ == "__main__":
    raise SystemExit(main())
