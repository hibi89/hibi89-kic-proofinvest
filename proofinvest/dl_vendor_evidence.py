"""Offline-only DL saved-filing evidence candidates into ProofInvest Guard review.

This is not SEC source authentication, financial normalization, advice, or trading.
No network, no database writes, and no silent approval.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import re
from typing import Any

from integrations.dl_vendor import extract
from .guard_sec_adapter import evaluate_sec_guard


def review_saved_dl_evidence(
    *, db_path: str | Path, cik: str, accession: str, sha256: str,
    as_of: str, term: str, max_results: int = 5,
) -> dict[str, Any]:
    """Read one pinned offline DL receipt and expose human-review-only candidates.

    The vendor reader checks stored source bytes, accession and point-in-time
    eligibility; this adapter refuses to promote text into verified numeric facts.
    """
    if (not isinstance(cik, str)
            or re.fullmatch(r"[0-9]{10}", cik, re.ASCII) is None
            or not cik.strip("0")
            or not isinstance(accession, str)
            or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession, re.ASCII) is None
            or not accession.startswith(cik + "-")
            or not isinstance(sha256, str)
            or re.fullmatch(r"[a-f0-9]{64}", sha256, re.ASCII) is None):
        raise ValueError("INVALID_PINNED_DL_IDENTITY")
    if not isinstance(as_of, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", as_of) is None:
        raise ValueError("INVALID_AS_OF")
    try:
        date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValueError("INVALID_AS_OF") from exc
    if (not isinstance(term, str) or not 2 <= len(term) <= 80
            or not term.strip()
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in term)
            or type(max_results) is not int or not 1 <= max_results <= 20):
        raise ValueError("INVALID_EVIDENCE_SEARCH")
    if not isinstance(db_path, (str, Path)):
        raise ValueError("EXISTING_DL_DB_REQUIRED")
    path = Path(db_path).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError("EXISTING_DL_DB_REQUIRED")

    receipt = extract.from_saved_original(
        db_path=path, cik=cik, accession=accession, sha256=sha256, as_of=as_of,
    )
    if (receipt.get("schema") != "disclosure-lightning.extracted-text.v1"
            or receipt.get("issuer_cik") != cik
            or receipt.get("accession") != accession
            or receipt.get("filing_sha256") != sha256
            or receipt.get("as_of") != as_of
            or receipt.get("source_authenticity_verified") is not False
            or receipt.get("suitable_for_automatic_financial_facts") is not False):
        raise ValueError("UNTRUSTED_DL_EXTRACTION_RECEIPT")

    matches = extract.find_evidence_candidates(
        receipt, term=term, max_results=max_results,
    )
    if (matches.get("source_authenticity_verified") is not False
            or matches.get("financial_claim_verified") is not False
            or matches.get("filing_sha256") != sha256
            or matches.get("issuer_cik") != cik
            or matches.get("accession") != accession):
        raise ValueError("UNTRUSTED_DL_CANDIDATES")

    # No verified numeric source or risk measurement is available from text
    # extraction alone. The deterministic Guard must therefore HOLD.
    guard = evaluate_sec_guard({"status": "unavailable"})["guard"]
    if guard.get("decision") != "HOLD" or guard.get("trade_executed") is not False:
        raise ValueError("DL_GUARD_FAILED_CLOSED")
    return {
        "schema": "proofinvest.dl-evidence-guard-review.v1",
        "status": ("candidates_for_human_review" if matches["returned"]
                   else "no_matching_evidence"),
        "issuer_cik": cik,
        "accession": accession,
        "as_of": as_of,
        "filing_sha256": sha256,
        "source_uri": receipt["source_uri"],
        "search_term": term,
        "candidate_count": matches["returned"],
        "candidates": matches["candidates"],
        "search_scope_truncated": matches["search_scope_truncated"],
        "guard": guard,
        "external_source_authenticated": False,
        "financial_claim_verified": False,
        "human_approved": False,
        "trade_executed": False,
        "live_api_called": False,
        "official_contest_submission": False,
    }
