"""P19: read-only compatibility assessment of an operator-held SEC capture ZIP.

No SEC requests, model calls, audit DB, file writes, raw original disclosure,
source-origin authentication, or implicit operator selection. P13 preview and
the actual reread ZIP must fingerprint-match before reporting capabilities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .ixbrl_revenue_review import review_inline_annual_revenue
from .kuodra_offline_preflight import (
    inspect_saved_capture_periods, _candidate_needle_receipts,
)
from .local_sec_packet import _json_object, _MAX_FILE_BYTES
from .sec_capture_bundle import _read_checked_capture_bundle
from .sec_companyfacts import verify_sec_annual_revenue


_KEYS = ("submissions", "companyfacts", "original_filing")


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.saved-capture-compatibility.v1",
        "status": "blocked",
        "reason_code": reason,
        "mode": "READ_ONLY_LOCAL_UNTRUSTED",
        "issuer_cik_self_reported": None,
        "accession_self_reported": None,
        "as_of_self_reported": None,
        "source_sha256": None,
        "fiscal_pair_count": 0,
        "period_checks": [],
        "original_strict_utf8": False,
        "locally_verified_candidate_count": 0,
        "text_candidates_disclosed": False,
        "inline_review_is_optional": True,
        "operator_selection_required": True,
        "model_proposal_required": True,
        "audit_consent_required": True,
        "automatic_execution": False,
        "audit_written": False,
        "network_calls": 0,
        "live_model_called": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "financial_facts_authenticated": False,
        "trade_executed": False,
    }


def inspect_saved_capture_compatibility(
    bundle_path: str | Path,
) -> dict[str, Any]:
    """Diagnose a local capture without recommending dates, evidence or trades.

    The strict iXBRL XHTML context review is supplemental: ordinary SEC HTML
    frequently will NOT match its constrained profile, which does not make
    an otherwise viable CompanyFacts fiscal pair invalid.
    """
    if not isinstance(bundle_path, (str, Path)) or not str(bundle_path).strip():
        return _base("INVALID_LOCAL_CAPTURE_PATH")
    try:
        path = Path(bundle_path).expanduser()
        preview = inspect_saved_capture_periods(path)
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            RecursionError, RuntimeError):
        return _base("LOCAL_PREFLIGHT_UNAVAILABLE")
    if (preview.get("status") != "review_candidates_available"
            or not isinstance(preview.get("period_candidates"), list)
            or not preview["period_candidates"]):
        return _base(str(preview.get("reason_code") or "NO_PERIOD_CANDIDATES"))
    try:
        integrity, raws, receipt = _read_checked_capture_bundle(path)
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            RecursionError, RuntimeError):
        return _base("CAPTURE_RECHECK_FAILED")
    if (integrity.get("status") != "bundle_integrity_pass_origin_unverified"
            or not isinstance(raws, Mapping)
            or not isinstance(receipt, Mapping)
            or receipt.get("issuer_cik") != preview.get("issuer_cik_self_reported")
            or receipt.get("accession") != preview.get("accession_self_reported")
            or receipt.get("observed_utc_day") != preview.get("as_of_self_reported")
            or not isinstance(preview.get("source_sha256"), Mapping)
            or any(type(raws.get(k)) is not bytes
                   or hashlib.sha256(raws[k]).hexdigest() !=
                   preview["source_sha256"].get(k) for k in _KEYS)):
        return _base("CAPTURE_CHANGED_SINCE_PREFLIGHT")
    try:
        companyfacts = _json_object(raws["companyfacts"], limit=_MAX_FILE_BYTES)
        original = raws["original_filing"]
        periods = []
        for pair in preview["period_candidates"]:
            verdict = verify_sec_annual_revenue(
                companyfacts, cik=receipt["issuer_cik"],
                accession=receipt["accession"],
                current_end=pair["current_end"],
                prior_end=pair["prior_end"],
                as_of=receipt["observed_utc_day"],
            )
            if (verdict.get("status") != "calculated_unverified"
                    or verdict.get("revenue_concept") != pair["revenue_concept"]
                    or verdict.get("filing_date") != pair["filing_date"]):
                return _base("FISCAL_VERIFICATION_CHANGED_SINCE_PREVIEW")
            inline = review_inline_annual_revenue(
                original, companyfacts=companyfacts,
                verdict=verdict, cik=receipt["issuer_cik"],
            )
            if (inline.get("source_authenticated") is not False
                    or inline.get("financial_facts_authenticated") is not False):
                return _base("INVALID_INLINE_SOURCE_AUTHENTICATION")
            periods.append({
                "current_end": pair["current_end"],
                "prior_end": pair["prior_end"],
                "revenue_concept": pair["revenue_concept"],
                "inline_xbrl_structural_status": inline["status"],
                "inline_xbrl_reason_code": inline["reason_code"],
                "inline_xbrl_not_required_for_operator_selection": True,
            })
        try:
            original.decode("utf-8")
            strict_utf8 = True
        except UnicodeDecodeError:
            strict_utf8 = False
        # Explicit snippet disclosure is NOT inherited from P13. Only the
        # COUNT of safely verified eligible candidates is emitted. This count
        # is not proof that a useful operator-chosen financial quote exists.
        count = len(_candidate_needle_receipts(original)) if strict_utf8 else 0
    except (ValueError, KeyError, TypeError, OverflowError,
            RecursionError, RuntimeError, MemoryError):
        return _base("LOCAL_COMPATIBILITY_INSPECTION_FAILED")
    result = _base(
        "OPERATOR_MUST_SELECT_PERIOD_AND_ORIGINAL_TEXT"
        if strict_utf8 else "ORIGINAL_NOT_STRICT_UTF8_FOR_SOURCE_ANCHOR"
    )
    result.update(
        status="operator_review_required" if strict_utf8 else "blocked",
        issuer_cik_self_reported=receipt["issuer_cik"],
        accession_self_reported=receipt["accession"],
        as_of_self_reported=receipt["observed_utc_day"],
        source_sha256=dict(preview["source_sha256"]),
        fiscal_pair_count=len(periods),
        period_checks=periods,
        original_strict_utf8=strict_utf8,
        locally_verified_candidate_count=count,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect a local saved SEC ZIP; no API, model, SQLite or raw text output."
    )
    parser.add_argument("--capture-zip", required=True, type=Path)
    args = parser.parse_args(argv)
    result = inspect_saved_capture_compatibility(args.capture_zip)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "operator_review_required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
