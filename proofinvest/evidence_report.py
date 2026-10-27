"""Deterministic, offline-only ProofInvest synthetic evidence report.

Never consumes arbitrary user-provided reports. Numbers and byte-span provenance
are assembled from the existing local synthetic DL -> KIC verification chain.
The exported report is NOT the official KIC organizer PDF or SEC attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from proofinvest.kic_dl_demo import (
    AS_OF, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    replay as replay_index,
    synthetic_companyfacts,
    synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import (
    PHRASE, SYNTHETIC_HTML, replay_original,
)
from proofinvest.sec_companyfacts import verify_sec_annual_revenue

_FILE_URL = (
    "https://www.sec.gov/Archives/edgar/data/1/"
    "000000000125000001/synthetic10k.htm"
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_NUM = re.compile(r"(?:0|[1-9][0-9]{0,17})\Z")
_LIMITATIONS = (
    "SYNTHETIC_FIXTURE: nonexistent issuer, artificial filing bytes and numbers.",
    "Local SHA-256 proves saved bytes' integrity, not SEC provenance or content truth.",
    "Citation marker is separate from financial figures; it does not support the revenue claim.",
    "No independent SEC source authentication, rights review, AI agent, risk score or live HTTP.",
    "Not investment advice, KIC official submission, or a production verification report.",
)


def _reject(message: str) -> None:
    raise ValueError("SYNTHETIC_REPORT_BLOCKED:" + message)


def build_synthetic_evidence_report() -> dict[str, Any]:
    """Execute two existing DL/KIC offline paths, strictly cross-check and summarize."""
    original = replay_original()
    index = replay_index()
    numeric = verify_sec_annual_revenue(
        synthetic_companyfacts(),
        cik=SYNTHETIC_CIK,
        accession=SYNTHETIC_ACCESSION,
        current_end="2025-09-30",
        prior_end="2024-09-30",
        as_of=AS_OF,
        claimed_growth_pct="100.00",
    )
    if not all(isinstance(item, Mapping) for item in (original, index, numeric)):
        _reject("BAD_PIPELINE_RESULT")

    expected_original = {
        "schema": "proofinvest.kic-dl-original-e2e.v1",
        "status": "offline_original_source_path_pass",
        "synthetic_only": True,
        "submissions_index_stored": 2,
        "original_file_receipt_status": "SAVED",
        "original_replay_receipt_status": "REUSED",
        "original_bytes_match": True,
        "source_span_status": "untrusted_original_span_for_review",
        "issuer_cik": SYNTHETIC_CIK,
        "accession": SYNTHETIC_ACCESSION,
        "source_uri": _FILE_URL,
        "kic_metadata_link": "linked_metadata_only",
        "kic_original_crosslink": "linked_untrusted_original_span_for_review",
        "original_span_metadata_linked": True,
        "authenticated_external_source": False,
        "real_sec_network_called": False,
        "real_filing_retrieved": False,
        "official_submission_made": False,
        "numeric_facts_authenticated": False,
    }
    expected_index = {
        "schema": "proofinvest.dl-kic-synthetic-e2e-receipt.v1",
        "status": "offline_mvp_pass",
        "synthetic_data_only": True,
        "real_issuer_verified": False,
        "live_sec_requested": False,
        "full_filing_content_retrieved": False,
        "agent_executed": False,
        "official_hackathon_submitted": False,
        "issuer_cik": SYNTHETIC_CIK,
        "as_of": AS_OF,
        "dl_indexed": 2,
        "sqlite_inserted_first": 2,
        "sqlite_inserted_repeat": 0,
        "sqlite_listed_filings": 2,
        "original_filing_sha256": None,
        "synthetic_numeric_status": "calculated_unverified",
        "synthetic_growth_pct": "100.00",
        "kic_link_status": "linked_metadata_only",
        "kic_external_authentication": False,
    }
    expected_numeric = {
        "schema": "proofinvest.sec-companyfacts-offline.v1",
        "status": "calculated_unverified",
        "reason_code": "STRUCTURAL_NUMERIC_COMPARISON_ONLY",
        "cik": SYNTHETIC_CIK,
        "accession": SYNTHETIC_ACCESSION,
        "as_of": AS_OF,
        "filing_date": "2025-10-15",
        "annual_period_ends": ["2024-09-30", "2025-09-30"],
        "current_usd": "200",
        "prior_usd": "100",
        "growth_pct": "100.00",
        "source_kind": "CALLER_SUPPLIED_SEC_FORMAT_NOT_AUTHENTICATED",
        "authenticated_external_source": False,
        "source_rights_verified": False,
        "live_api_called": False,
        "ai_agent_executed": False,
        "risk_calculated": False,
        "official_contest_submission": False,
    }
    for data, expected in (
        (original, expected_original), (index, expected_index), (numeric, expected_numeric)
    ):
        if any(key not in data or data[key] != val or type(data[key]) is not type(val)
               for key, val in expected.items()):
            _reject("PIPELINE_CONTRACT_CHANGED")

    raw_sha = original.get("original_filing_sha256")
    index_sha = original.get("submissions_sha256")
    if (not isinstance(raw_sha, str) or _SHA.fullmatch(raw_sha) is None
            or not isinstance(index_sha, str) or _SHA.fullmatch(index_sha) is None
            or raw_sha != hashlib.sha256(SYNTHETIC_HTML).hexdigest()
            or index_sha != hashlib.sha256(synthetic_submissions()).hexdigest()
            or index_sha != index.get("submissions_json_sha256")
            or raw_sha == index_sha):
        _reject("SOURCE_DIGEST_SCOPE_MISMATCH")

    start, end = original.get("source_byte_start"), original.get("source_byte_end")
    if (type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(SYNTHETIC_HTML)
            or SYNTHETIC_HTML[start:end] != PHRASE.encode("ascii")):
        _reject("SOURCE_BYTE_SPAN_MISMATCH")
    if (not isinstance(original.get("escaped_context"), str)
            or len(original["escaped_context"]) > 2048
            or "<" in original["escaped_context"]
            or ">" in original["escaped_context"]
            or PHRASE not in original["escaped_context"]):
        _reject("UNSAFE_ARCHIVE_CONTEXT")
    if (not all(isinstance(numeric[k], str) and _NUM.fullmatch(numeric[k])
                for k in ("prior_usd", "current_usd"))):
        _reject("INVALID_FINANCIAL_AMOUNT")

    # Deliberately do not copy untrusted HTML (even escaped) or caller text into
    # an exported report. The matched marker is fixed and not a revenue citation.
    return {
        "schema": "proofinvest.synthetic-evidence-report.v1",
        "mode": "SYNTHETIC_FIXTURE_OFFLINE_ONLY",
        "status": "local_structural_review_only",
        "issuer": {"cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
                   "as_of": AS_OF, "filed_at": numeric["filing_date"]},
        "source": {
            "uri": _FILE_URL,
            "uri_status": "SYNTHETIC_SHAPED_URL_NOT_FETCHED",
            "submissions_json_sha256": index_sha,
            "archived_original_sha256": raw_sha,
            "archive_replay_status": "SAVED_THEN_REUSED",
            "metadata_link": original["kic_metadata_link"],
            "span_link": original["kic_original_crosslink"],
            "source_span": {
                "start_byte": start,
                "end_byte_exclusive": end,
                "literal": PHRASE,
                "supports_financial_values": False,
            },
        },
        "financial": {
            "unit": "USD", "prior_period_end": "2024-09-30",
            "current_period_end": "2025-09-30",
            "prior_revenue": numeric["prior_usd"],
            "current_revenue": numeric["current_usd"],
            "growth_pct": numeric["growth_pct"],
            "status": "calculated_unverified",
            "reason_code": "STRUCTURAL_NUMERIC_COMPARISON_ONLY",
        },
        "risk": {"status": "unavailable", "reason_code": "NO_AUTHENTICATED_RISK_INPUTS"},
        "authenticity": {
            "external_source_authenticated": False,
            "numeric_facts_authenticated": False,
            "source_rights_verified": False,
            "real_sec_network_called": False,
            "real_filing_retrieved": False,
            "ai_agent_executed": False,
            "official_contest_submission": False,
        },
        "limitations": list(_LIMITATIONS),
    }


def render_report(report: Mapping[str, Any], fmt: str = "json") -> str:
    """Only format the strict synthetic report; never convert arbitrary input."""
    if not isinstance(report, Mapping):
        _reject("BAD_REPORT")
    # Reject extra trust flag, forged fields and partially supplied reports.
    # Recompute expected report from known in-memory synthetic pipeline.
    expected = build_synthetic_evidence_report()
    if type(report) is not dict or report != expected:
        _reject("UNTRUSTED_REPORT_CONTENT")
    if fmt == "json":
        return json.dumps(expected, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if fmt != "markdown":
        raise ValueError("UNSUPPORTED_REPORT_FORMAT")
    issuer, src, fin = (expected[key] for key in ("issuer", "source", "financial"))
    span = src["source_span"]
    lines = [
        "# ProofInvest — SYNTHETIC / UNVERIFIED offline evidence report",
        "",
        "**Not a real SEC report, investment advice, or KIC submission.**",
        "",
        "## Issuer and as-of (fictional)",
        f"- CIK: {issuer['cik']}",
        f"- Accession: {issuer['accession']}",
        f"- As-of: {issuer['as_of']} | Filing date: {issuer['filed_at']}",
        "",
        "## Numerical comparison (artificial USD values)",
        f"- Prior period ({fin['prior_period_end']}): USD {fin['prior_revenue']}",
        f"- Current period ({fin['current_period_end']}): USD {fin['current_revenue']}",
        f"- Annual revenue change: {fin['growth_pct']}% — **calculated_unverified**",
        f"- Risk verdict: unavailable ({expected['risk']['reason_code']})",
        "",
        "## Local archived bytes and source-span reference",
        "- Synthetic SEC-shaped URL (NOT visited): " + src["uri"],
        f"- Submissions JSON SHA-256: {src['submissions_json_sha256']}",
        f"- Archived HTML SHA-256: {src['archived_original_sha256']}",
        f"- Byte span: [{span['start_byte']}, {span['end_byte_exclusive']})",
        f"- Literal marker: {span['literal']}",
        "- Source span **does not authenticate or prove** either revenue amount.",
        "",
        "## Source authenticity / limitations",
        "- External source authenticated: NO | Numerics authenticated: NO",
        "- Real SEC HTTP: NO | Official KIC submission: NO",
    ]
    lines.extend("- " + item for item in _LIMITATIONS)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate an offline SYNTHETIC-ONLY JSON or Markdown evidence report."
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path,
                        help="Optional new file path; existing files are never overwritten.")
    args = parser.parse_args(argv)
    try:
        payload = render_report(build_synthetic_evidence_report(), args.format)
        if args.output is None:
            print(payload, end="")
        else:
            # Explicit exclusive-create only. No implicit network or overwrite.
            with args.output.open("x", encoding="utf-8", newline="\n") as output:
                output.write(payload)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Report export unavailable: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
