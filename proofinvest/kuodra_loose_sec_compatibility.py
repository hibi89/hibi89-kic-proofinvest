"""P20: SEC-shaped loose local 3-file compatibility, WITHOUT inventing a receipt.

The user may already have submissions.json, companyfacts.json and a 10-K HTML.
This CLI reads the exact files offline, never uploads/stores/converts them, and
does not claim their origin, collection time, legal rights or that the HTML is
the actual SEC filing for the supplied accession. No SQLite, API or model.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from disclosure_lightning.core import index_submissions, parse_day, MAX_JSON_BYTES
from disclosure_lightning.originals import MAX_FILING_BYTES
from .ixbrl_revenue_review import review_inline_annual_revenue
from .dei_identity_review import review_embedded_dei_identity
from .kuodra_offline_preflight import _candidate_needle_receipts
from .local_sec_packet import _json_object, _read_regular_local, _MAX_FILE_BYTES
from .sec_companyfacts import REVENUE_TAGS, MAX_ROWS, _date, verify_sec_annual_revenue
from .dl_bridge import filing_available_at_observation
from .kuodra_history import index_pinned_history

_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACC = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
_MAX_ENDS = 64
_MAX_PAIRS = 80
_MAX_DISPLAY = 5


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.loose-local-sec-compatibility.v1",
        "status": "blocked",
        "reason_code": reason,
        "mode": "READ_ONLY_THREE_LOOSE_LOCAL_FILES_UNVERIFIED",
        "issuer_cik_operator_supplied": None,
        "accession_operator_supplied": None,
        "as_of_operator_supplied": None,
        "collected_at_operator_supplied_not_authenticated": None,
        "filing_source_uri_in_submissions_not_fetched": None,
        "source_sha256": None,
        "period_candidates": [],
        "candidates_truncated": False,
        "original_strict_utf8": False,
        "embedded_dei_identity": None,
        "eligible_original_text_candidate_count": 0,
        "original_text_disclosed": False,
        "original_filing_belongs_to_accession_verified": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "financial_facts_authenticated": False,
        "revenue_is_structural_unverified": True,
        "operator_must_select_period_and_needle": True,
        "audit_written": False,
        "model_called": False,
        "network_calls": 0,
        "trade_executed": False,
        "production_verified": False,
    }


def inspect_loose_sec_files(
    *, submissions_path: str | Path, companyfacts_path: str | Path,
    original_path: str | Path, cik: str, accession: str,
    as_of: str, collected_at: str,
) -> dict[str, Any]:
    """Review existing operator-supplied files, without inventing SEC provenance.

    The claimed observation timestamp must be explicit and must NOT be
    interpreted as verified transport metadata. This output never allows
    execution or local audit persistence.
    """
    if (type(cik) is not str or _CIK.fullmatch(cik) is None
            or cik == "0000000000" or type(accession) is not str
            or _ACC.fullmatch(accession) is None
            or type(as_of) is not str or type(collected_at) is not str):
        return _result("INVALID_OPERATOR_IDENTITY_OR_DATE")
    try:
        parse_day(as_of)
        paths = (submissions_path, companyfacts_path, original_path)
        if any(not isinstance(x, (str, Path)) or not str(x).strip() for x in paths):
            return _result("INVALID_INPUT_FILE_PATH")
        normalized = [Path(x).expanduser().resolve(strict=False) for x in paths]
        if len(set(normalized)) != 3:
            return _result("SOURCE_INPUT_PATH_COLLISION")
        submissions_raw = _read_regular_local(Path(paths[0]).expanduser(), MAX_JSON_BYTES)
        facts_raw = _read_regular_local(Path(paths[1]).expanduser(), _MAX_FILE_BYTES)
        original = _read_regular_local(Path(paths[2]).expanduser(), MAX_FILING_BYTES)
    except (OSError, ValueError, TypeError, RecursionError, RuntimeError):
        return _result("INPUT_FILES_MISSING_UNSAFE_OR_OVERSIZED")
    return inspect_loose_sec_bytes(
        submissions_json=submissions_raw,
        companyfacts_json=facts_raw,
        original_filing=original,
        cik=cik, accession=accession, as_of=as_of, collected_at=collected_at,
    )


def inspect_loose_sec_bytes(
    *, submissions_json: bytes, companyfacts_json: bytes,
    original_filing: bytes, cik: str, accession: str, as_of: str,
    collected_at: str, show_local_needle_candidates: bool = False,
    history_page_json: bytes | None = None, history_page_name: str | None = None,
) -> dict[str, Any]:
    """Bounded read-only three-source discovery without temporary raw-file IO.

    Reuses the exact historical CLI period/filing/DEI/XBRL gates.
    Actual literal text candidates are omitted unless explicitly requested.
    """
    if type(show_local_needle_candidates) is not bool:
        raise ValueError("INVALID_EXPLICIT_LOCAL_TEXT_DISCLOSURE_FLAG")
    if (type(cik) is not str or _CIK.fullmatch(cik) is None
            or cik == "0000000000" or type(accession) is not str
            or _ACC.fullmatch(accession) is None
            or type(as_of) is not str or type(collected_at) is not str):
        return _result("INVALID_OPERATOR_IDENTITY_OR_DATE")
    try:
        parse_day(as_of)
    except ValueError:
        return _result("INPUT_FILES_MISSING_UNSAFE_OR_OVERSIZED")
    if (type(submissions_json) is not bytes or not 0 < len(submissions_json) <= MAX_JSON_BYTES
            or type(companyfacts_json) is not bytes or not 0 < len(companyfacts_json) <= _MAX_FILE_BYTES
            or type(original_filing) is not bytes or not 0 < len(original_filing) <= MAX_FILING_BYTES):
        return _result("INPUT_FILES_MISSING_UNSAFE_OR_OVERSIZED")
    if (history_page_json is None) != (history_page_name is None):
        return _result("HISTORY_PAGE_AND_NAME_REQUIRED_TOGETHER")
    if history_page_json is not None and (
            type(history_page_json) is not bytes
            or not 0 < len(history_page_json) <= MAX_JSON_BYTES):
        return _result("HISTORY_PAGE_MISSING_OR_OVERSIZED")
    submissions_raw, facts_raw, original = (
        submissions_json, companyfacts_json, original_filing,
    )
    try:
        index = (
            index_submissions(
                submissions_raw, cik=cik, as_of=as_of,
                forms=frozenset({"10-K"}), provenance="OFFLINE_UNVERIFIED",
                collected_at=collected_at,
            ) if history_page_json is None else
            index_pinned_history(
                base_raw=submissions_raw, history_raw=history_page_json,
                page_name=history_page_name, cik=cik, as_of=as_of,
                collected_at=collected_at,
            )
        )
        target = [f for f in index["filings"]
                  if f.get("accession") == accession and f.get("form") == "10-K"]
        if len(target) != 1 or not isinstance(target[0].get("source_uri"), str):
            return _result("TARGET_10K_NOT_IN_SAVED_SOURCE_INDEX")
        if not filing_available_at_observation(index, target[0]):
            return _result("FILING_NOT_AVAILABLE_AT_OBSERVATION")
        facts = _json_object(facts_raw, limit=_MAX_FILE_BYTES)
    except (ValueError, KeyError, TypeError, OverflowError, RecursionError):
        return _result("SUBMISSIONS_OR_COMPANYFACTS_FORMAT_INVALID")
    root = facts.get("facts")
    gaap = root.get("us-gaap") if isinstance(root, Mapping) else None
    if not isinstance(gaap, Mapping):
        return _result("NO_US_GAAP_REVENUE_FACTS")
    ends: set[date] = set()
    for name in REVENUE_TAGS:
        concept = gaap.get(name)
        if concept is None:
            continue
        units = concept.get("units") if isinstance(concept, Mapping) else None
        rows = units.get("USD") if isinstance(units, Mapping) else None
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            return _result("REVENUE_ROWS_MISSING_OR_OVERSIZED")
        for row in rows:
            if not isinstance(row, Mapping):
                return _result("INVALID_REVENUE_RECORD")
            if row.get("accn") != accession or row.get("form") != "10-K":
                continue
            start, end, filed = (_date(row.get(k)) for k in ("start","end","filed"))
            if (start is None or end is None or filed is None
                    or not start < end <= filed <= parse_day(as_of)
                    or not 330 <= (end-start).days <= 380
                    or type(row.get("val")) is not int):
                return _result("INVALID_TARGET_REVENUE_RECORD")
            ends.add(end)
            if len(ends) > _MAX_ENDS:
                return _result("TOO_MANY_FISCAL_PERIODS")
    if len(ends) < 2:
        return _result("NO_TWO_ANNUAL_PERIOD_ENDS")
    pairs = [(current, prior)
             for current in sorted(ends, reverse=True)
             for prior in sorted(ends, reverse=True)
             if prior < current and 330 <= (current-prior).days <= 380]
    if len(pairs) > _MAX_PAIRS:
        return _result("TOO_MANY_ANNUAL_PAIRS")
    approved: list[dict[str, Any]] = []
    for current, prior in pairs:
        verdict = verify_sec_annual_revenue(
            facts, cik=cik, accession=accession, as_of=as_of,
            current_end=current.isoformat(), prior_end=prior.isoformat(),
        )
        if verdict["status"] != "calculated_unverified":
            continue
        if verdict["filing_date"] != target[0]["filed_at"]:
            return _result("FILING_DATE_COMPANYFACTS_SUBMISSIONS_MISMATCH")
        xbrl = review_inline_annual_revenue(
            original, companyfacts=facts, verdict=verdict, cik=cik,
        )
        if (xbrl.get("source_authenticated") is not False
                or xbrl.get("financial_facts_authenticated") is not False):
            return _result("ILLEGAL_PROVENANCE_UPGRADE")
        approved.append({
            "current_end": current.isoformat(),
            "prior_end": prior.isoformat(),
            "growth_pct_unverified": verdict["growth_pct"],
            "revenue_concept": verdict["revenue_concept"],
            "filing_date": verdict["filing_date"],
            "optional_ixbrl_status": xbrl["status"],
            "optional_ixbrl_reason": xbrl["reason_code"],
        })
    if not approved:
        return _result("ANNUAL_REVENUE_PAIR_UNAVAILABLE_OR_AMBIGUOUS")
    try:
        original.decode("utf-8")
        utf8 = True
    except UnicodeDecodeError:
        utf8 = False
    dei_identity = review_embedded_dei_identity(original, cik=cik)
    if dei_identity["status"] in ("conflict", "ambiguous"):
        blocked = _result("ORIGINAL_DEI_SELF_CLAIM_CONFLICT_OR_AMBIGUOUS")
        blocked["embedded_dei_identity"] = dei_identity
        return blocked
    needle_candidates = _candidate_needle_receipts(original) if utf8 else []
    candidate_count = len(needle_candidates)
    out = _result(
        "MANUAL_PERIOD_NEEDLE_REVIEW_REQUIRED"
        if utf8 else "ORIGINAL_NOT_STRICT_UTF8_FOR_TEXT_EVIDENCE"
    )
    out.update(
        status="operator_review_required" if utf8 else "blocked",
        issuer_cik_operator_supplied=cik,
        accession_operator_supplied=accession,
        as_of_operator_supplied=as_of,
        collected_at_operator_supplied_not_authenticated=index["collected_at"],
        filing_source_uri_in_submissions_not_fetched=target[0]["source_uri"],
        source_sha256={
            **{
                "submissions": hashlib.sha256(submissions_raw).hexdigest(),
                "companyfacts": hashlib.sha256(facts_raw).hexdigest(),
                "original_filing": hashlib.sha256(original).hexdigest(),
            },
            **({
                "history_page": hashlib.sha256(history_page_json).hexdigest(),
            } if history_page_json is not None else {}),
        },
        period_candidates=approved[:_MAX_DISPLAY],
        candidates_truncated=len(approved) > _MAX_DISPLAY,
        original_strict_utf8=utf8,
        embedded_dei_identity=dei_identity,
        eligible_original_text_candidate_count=candidate_count,
    )
    if show_local_needle_candidates:
        # Explicit operator consent: these strings come from untrusted local
        # original bytes and must only be shown inside the loopback UI.
        out["local_needle_candidates"] = needle_candidates
    return out




def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline/read-only inspect three already-owned local SEC-shaped files"
    )
    for name in ("submissions", "companyfacts", "original"):
        parser.add_argument("--"+name, required=True, type=Path)
    for name in ("cik", "accession", "as-of", "collected-at"):
        parser.add_argument("--"+name, required=True)
    args = parser.parse_args(argv)
    report = inspect_loose_sec_files(
        submissions_path=args.submissions, companyfacts_path=args.companyfacts,
        original_path=args.original, cik=args.cik, accession=args.accession,
        as_of=args.as_of, collected_at=args.collected_at,
    )
    print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "operator_review_required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
