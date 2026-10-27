"""KIC offline review packet from arbitrary caller-provided SEC-shaped files.

No HTTP, outside source verification, private data upload, LLM, or trades.
Uses the canonical DL SQLite original-byte archive in a temporary directory.
Input files (including honest SEC downloads) remain UNAUTHENTICATED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from disclosure_lightning.core import (
    MAX_JSON_BYTES, index_submissions, save_index,
)
from disclosure_lightning.originals import (
    MAX_FILING_BYTES, locate_original, persist_original,
)
from proofinvest.dl_bridge import (
    assess_dl_sec_handoff, assess_dl_original_handoff,
)
from proofinvest.dl_source_span import anchored_source_span
from proofinvest.sec_companyfacts import verify_sec_annual_revenue
from proofinvest.numeric_literal_anchor import find_numeric_literals_in_html_text

_MAX_CLAIM_BYTES = 400
_MAX_FILE_BYTES = 8_000_000
_CIK = re.compile(r"[0-9]{10}\Z", flags=re.ASCII)
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", flags=re.ASCII)


def _json_object(raw: bytes, *, limit: int) -> dict[str, Any]:
    if type(raw) is not bytes or not 0 < len(raw) <= limit:
        raise ValueError("LOCAL_JSON_INPUT_MISSING_OR_OVERSIZED")

    def no_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, val in pairs:
            if key in out:
                raise ValueError("DUPLICATE_JSON_KEY")
            out[key] = val
        return out

    def no_nonfinite(token: str) -> None:
        raise ValueError("NONFINITE_JSON_NUMBER")

    try:
        payload = json.loads(
            raw.decode("utf-8-sig"), object_pairs_hook=no_duplicate,
            parse_constant=no_nonfinite,
        )
    except (UnicodeDecodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_LOCAL_JSON") from exc
    if type(payload) is not dict:
        raise ValueError("EXPECTED_LOCAL_JSON_OBJECT")
    return payload


def _read_regular_local(path: Path, limit: int) -> bytes:
    """Read bounded files, refusing symlinks, nonregular files, and size races."""
    location = Path(path)
    if location.is_symlink():
        raise ValueError("LOCAL_SYMLINK_INPUT_REJECTED")
    fd = os.open(location, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as file:
        info = os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
            raise ValueError("LOCAL_FILE_NOT_REGULAR_OR_BOUNDED")
        data = file.read(limit + 1)
    if not 0 < len(data) <= limit or len(data) != info.st_size:
        raise ValueError("LOCAL_FILE_CHANGED_OR_OVERSIZED")
    return data


def build_local_sec_review_packet(
    *, submissions_json: bytes, companyfacts_json: bytes,
    original_filing: bytes, cik: str, accession: str, as_of: str,
    collected_at: str, current_end: str, prior_end: str,
    needle: str, claimed_growth_pct: str | None = None,
) -> dict[str, Any]:
    """Join locally supplied untrusted files; reject mismatched/uncertain chains.

    A locally saved receipt is NOT a proof the original issuer filed the content.
    The phrase position is NOT financial-value verification.
    """
    if (not isinstance(cik, str) or _CIK.fullmatch(cik) is None
            or cik == "0000000000"
            or not isinstance(accession, str)
            or _ACCESSION.fullmatch(accession) is None
            or accession[:10] != cik):
        raise ValueError("INVALID_CIK_ACCESSION_TARGET")
    _json_object(submissions_json, limit=MAX_JSON_BYTES)
    facts = _json_object(companyfacts_json, limit=_MAX_FILE_BYTES)
    if type(original_filing) is not bytes or not 0 < len(original_filing) <= MAX_FILING_BYTES:
        raise ValueError("ORIGINAL_FILE_MISSING_OR_OVERSIZED")
    # Disallow oversized free-form user strings and do not copy them to output.
    if claimed_growth_pct is not None and (
            not isinstance(claimed_growth_pct, str)
            or len(claimed_growth_pct) > _MAX_CLAIM_BYTES):
        raise ValueError("INVALID_CLAIM")

    # DL verifies UTC collected_at <= as_of, per-filing date and pinned URL.
    index = index_submissions(
        submissions_json, cik=cik, as_of=as_of,
        forms=frozenset({"10-K"}), provenance="OFFLINE_UNVERIFIED",
        collected_at=collected_at,
    )
    # A filing absent as-of is unavailable, never guessed or substituted.
    candidates = [record for record in index["filings"]
                  if record.get("accession") == accession]
    if len(candidates) != 1 or candidates[0].get("form") != "10-K":
        raise ValueError("FILING_UNAVAILABLE_AT_AS_OF")

    verdict = verify_sec_annual_revenue(
        facts, cik=cik, accession=accession,
        current_end=current_end, prior_end=prior_end,
        as_of=as_of, claimed_growth_pct=claimed_growth_pct,
    )
    if verdict.get("status") not in ("calculated_unverified", "conflict"):
        raise ValueError("NUMERIC_UNAVAILABLE:" + str(verdict.get("reason_code")))
    if (verdict.get("authenticated_external_source") is not False
            or verdict.get("live_api_called") is not False
            or verdict.get("source_rights_verified") is not False):
        raise ValueError("FORGED_FINANCIAL_AUTHENTICATION")

    link = assess_dl_sec_handoff(index, verdict)
    if (link.get("status") != "linked_metadata_only"
            or link.get("trace_linked") is not True
            or link.get("authenticated_external_source") is not False
            or link.get("live_api_called") is not False):
        raise ValueError("FILING_METADATA_VERDICT_MISMATCH")

    with TemporaryDirectory(prefix="proofinvest-offline-review-") as directory:
        db_path = Path(directory) / "evidence.sqlite3"
        inserted = save_index(db_path, submissions_json, index)
        receipt = locate_original(db_path, cik=cik, accession=accession)
        original_receipt = persist_original(
            db_path=db_path, receipt=receipt, raw=original_filing,
            kind="application/octet-stream", origin="OFFLINE_FILE_UNVERIFIED",
        )
        span = anchored_source_span(
            db_path=db_path, cik=cik, accession=accession,
            sha256=original_receipt["filing_sha256"], needle=needle,
        )
        crosslink = assess_dl_original_handoff(link, span)

    if (crosslink.get("status") != "linked_untrusted_original_span_for_review"
            or crosslink.get("span_metadata_linked") is not True
            or crosslink.get("authenticated_external_source") is not False
            or crosslink.get("numeric_facts_authenticated") is not False
            or crosslink.get("live_api_called") is not False
            or original_receipt.get("authenticated_external_source") is not False
            or original_receipt.get("original_filing_retrieved") is not False
            or original_receipt.get("status") != "SAVED"
            or inserted.get("new_filings", 0) < 1):
        raise ValueError("ORIGINAL_CROSSLINK_UNAVAILABLE")

    if (span.get("filing_sha256") != hashlib.sha256(original_filing).hexdigest()
            or index["source_sha256"] != hashlib.sha256(submissions_json).hexdigest()
            or span.get("source_uri") != link.get("filing_source_uri")):
        raise ValueError("EVIDENCE_INTEGRITY_CHECK_FAILED")
    numeric_literals = find_numeric_literals_in_html_text(
        original_filing,
        prior_amount=verdict["prior_usd"],
        current_amount=verdict["current_usd"],
    )
    # Distinct from arbitrary anchored needle: this checks only two literal
    # strings within decoded HTML text nodes, NOT accounting semantics or SEC truth.
    return {
        "schema": "proofinvest.offline-local-sec-review.v1",
        "status": "reviewable_untrusted_local_evidence",
        "mode": "LOCAL_FILES_OFFLINE_UNAUTHENTICATED",
        "issuer": {
            "cik": cik, "accession": accession,
            "as_of": index["as_of_cutoff"],
            "collected_at_user_supplied_not_authenticated": index["collected_at"],
            "filing_date": link["filing_date"],
        },
        "source": {
            "submissions_uri_not_fetched": index["source_uri"],
            "filing_uri_not_fetched": link["filing_source_uri"],
            "submissions_sha256": index["source_sha256"],
            "companyfacts_sha256": hashlib.sha256(companyfacts_json).hexdigest(),
            "archived_filing_sha256": original_receipt["filing_sha256"],
            "saved_original_bytes": original_receipt["filing_bytes"],
            "span_start_byte": crosslink["start_byte"],
            "span_end_byte_exclusive": crosslink["end_byte_exclusive"],
            "literal_occurrences": 1,
            "span_proves_financial_claim": False,
            "numeric_literal_crosscheck": numeric_literals,
            "link_status": crosslink["status"],
        },
        "financial": {
            "prior_period_end": prior_end,
            "current_period_end": current_end,
            "unit": "USD",
            "prior_amount": verdict["prior_usd"],
            "current_amount": verdict["current_usd"],
            "growth_pct": verdict["growth_pct"],
            "status": verdict["status"],
            "reason_code": verdict["reason_code"],
        },
        "risk": {"status": "unavailable",
                 "reason_code": "UNAUTHENTICATED_FINANCIAL_EVIDENCE"},
        "attestations": {
            "source_authenticated": False,
            "financial_values_authenticated": False,
            "file_origin_authenticated": False,
            "source_rights_verified": False,
            "live_sec_http_called": False,
            "ai_agent_executed": False,
            "official_contest_submission": False,
        },
        "limitations": [
            "Files and collected_at are supplied by caller; origin and timestamps are unverified.",
            "Source URLs are derived from local SEC-shaped metadata, never contacted.",
            "Financial figures are compared within caller-supplied JSON, not independently proved.",
            "The exact archived byte span proves phrase location, not filing semantics or revenue.",
            "Financial numeric literals inside HTML text nodes do not establish unit, scale, period, or issuer truth.",
            "No SEC transport receipt, redistribution rights, external authentication, or investment recommendation.",
            "Report is an offline review packet, NOT an official KIC submission.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline local 10-K triplet review only; NO API/SEC calls or authenticity claims."
    )
    parser.add_argument("--submissions-json", type=Path, required=True)
    parser.add_argument("--companyfacts-json", type=Path, required=True)
    parser.add_argument("--original-file", type=Path, required=True)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--accession", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--collected-at", required=True,
                        help="Caller-asserted UTC timestamp (not authenticated).")
    parser.add_argument("--current-end", required=True)
    parser.add_argument("--prior-end", required=True)
    parser.add_argument("--needle", required=True,
                        help="One unique 4-128 character ASCII literal.")
    parser.add_argument("--claimed-growth-pct", default=None)
    args = parser.parse_args(argv)
    try:
        packet = build_local_sec_review_packet(
            submissions_json=_read_regular_local(args.submissions_json, MAX_JSON_BYTES),
            companyfacts_json=_read_regular_local(args.companyfacts_json, _MAX_FILE_BYTES),
            original_filing=_read_regular_local(args.original_file, MAX_FILING_BYTES),
            cik=args.cik, accession=args.accession,
            as_of=args.as_of, collected_at=args.collected_at,
            current_end=args.current_end, prior_end=args.prior_end,
            needle=args.needle, claimed_growth_pct=args.claimed_growth_pct,
        )
    except (ValueError, OSError, TypeError, OverflowError, RecursionError) as exc:
        # Error type only; do not leak filesystem paths, filing text or private payloads.
        parser.exit(2, f"Offline review blocked: {type(exc).__name__}\n")
    print(json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
