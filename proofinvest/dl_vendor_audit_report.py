"""Pinned local DL filing -> Guard HOLD -> SQLite audit -> review report.

No network, no trading, no inferred financial verification, and no official
contest submission. Explicit human review only; source SHA proves local bytes,
not provenance. The report carries checksums rather than untrusted filing text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .dl_vendor_evidence import review_saved_dl_evidence
from .guard_audit import GuardAuditStore
from .guard_review import GuardReviewStore
from .guard_workflow import run_guard_review


def _fingerprint(value: dict[str, Any]) -> str:
    serialized = json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def run_saved_dl_audit_report(
    *,
    dl_db_path: str | Path,
    audit_db_path: str | Path,
    cik: str,
    accession: str,
    sha256: str,
    as_of: str,
    term: str,
    run_id: str,
    max_results: int = 5,
    reviewer: str | None = None,
    action: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Record a reviewed, non-executing DL evidence result.

    The immutable Guard run identity binds the complete extracted result
    digest (including source SHA, UTC as-of and candidate text hashes).
    Retrying a run with changed evidence fails; the audit is not SEC-signed.
    """
    # Reject unsafe human actions before opening or creating an audit database.
    wants_review = any(value is not None for value in (reviewer, action, reason))
    if wants_review:
        if (not all(isinstance(v, str) and v.strip()
                    for v in (reviewer, action, reason))
                or action not in ("ACKNOWLEDGE", "REQUEST_EXCEPTION")
                or not 1 <= len(reviewer.strip()) <= 80
                or not 5 <= len(reason.strip()) <= 1000):
            raise ValueError("DL permits explicit acknowledgement or exception request only")
    if not isinstance(dl_db_path, (str, Path)) or not isinstance(
            audit_db_path, (str, Path)):
        raise ValueError("Local SQLite paths required")
    src = Path(dl_db_path).expanduser()
    dst = Path(audit_db_path).expanduser()
    if (dst.is_symlink() or (dst.exists() and not dst.is_file())
            or src.resolve() == dst.resolve()):
        raise ValueError("Separate regular Guard audit database required")

    evidence = review_saved_dl_evidence(
        db_path=src, cik=cik, accession=accession, sha256=sha256,
        as_of=as_of, term=term, max_results=max_results,
    )
    # A bounded text candidate is not verified numeric evidence or Risk data.
    if (evidence.get("guard", {}).get("decision") != "HOLD"
            or evidence.get("external_source_authenticated") is not False
            or evidence.get("financial_claim_verified") is not False
            or evidence.get("trade_executed") is not False):
        raise ValueError("DL evidence trust boundary violated")

    evidence_digest = _fingerprint(evidence)
    guard_run = run_guard_review(
        {"status": "unavailable"},
        run_id=run_id,
        database_path=dst,
        source_evidence_digest=evidence_digest,
        reviewer=reviewer,
        action=action,
        reason=reason,
    )
    if guard_run["guard"] != evidence["guard"]:
        raise ValueError("Guard result diverged from reviewed DL evidence")
    audit_valid = GuardAuditStore(dst).verify_chain()
    review_valid = GuardReviewStore(dst).verify_reviews()
    if not audit_valid or not review_valid:
        raise ValueError("DL Guard audit or review integrity invalid")

    references = [
        {
            "text_sha256": candidate["text_sha256"],
            "source_locator": candidate["source_locator"],
            "citation_status": candidate["citation_status"],
            "financial_claim_verified": False,
        }
        for candidate in evidence["candidates"]
    ]
    return {
        "schema": "proofinvest.dl-saved-audit-report.v1",
        "status": "unverified_evidence_audited_for_human_review",
        "source": {
            "issuer_cik": cik,
            "accession": accession,
            "as_of": as_of,
            "filing_sha256": sha256,
            "source_uri": evidence["source_uri"],
            "source_authenticated": False,
        },
        "evidence": {
            "status": evidence["status"],
            "search_term": term,
            "candidate_count": evidence["candidate_count"],
            "search_scope_truncated": evidence["search_scope_truncated"],
            "references": references,
            "source_evidence_digest": evidence_digest,
            "financial_claim_verified": False,
        },
        "guard": guard_run["guard"],
        "audit": {
            "run_id": run_id,
            "event_id": guard_run["audit"]["event_id"],
            "event_hash": guard_run["audit"]["event_hash"],
            "replayed": guard_run["audit"]["replayed"],
            "chain_valid": audit_valid,
            "human_review_integrity_valid": review_valid,
            "independently_anchored": False,
        },
        "human_review": guard_run["review"],
        "limitations": [
            "Source bytes are local and not independently SEC-authenticated.",
            "Financial values and risk are unverified; Guard decision is HOLD.",
            "Local audit hashes are tamper-evident, not externally immutable.",
            "No trade execution or official KIC contest submission.",
        ],
        "live_api_called": False,
        "trade_executed": False,
        "investment_recommendation": False,
        "official_contest_submission": False,
    }


def render_dl_audit_markdown(result: dict[str, Any]) -> str:
    """Printable report metadata; never render untrusted filing text as Markdown."""
    if (not isinstance(result, dict)
            or result.get("schema") != "proofinvest.dl-saved-audit-report.v1"
            or result.get("status") != "unverified_evidence_audited_for_human_review"
            or result.get("trade_executed") is not False
            or result.get("live_api_called") is not False
            or not isinstance(result.get("source"), dict)
            or not isinstance(result.get("evidence"), dict)
            or not isinstance(result.get("guard"), dict)
            or not isinstance(result.get("audit"), dict)
            or result["guard"].get("decision") != "HOLD"
            or result["audit"].get("chain_valid") is not True
            or result["audit"].get("human_review_integrity_valid") is not True):
        raise ValueError("Invalid DL audit report or unverified integrity")
    src, evid, audit = (result[key] for key in ("source", "evidence", "audit"))
    return "\n".join([
        "# ProofInvest — DL offline evidence review (UNVERIFIED)",
        "",
        "**Not investment advice, SEC authentication or a KIC submission.**",
        "",
        "## Filing reference",
        f"- CIK: `{src['issuer_cik']}`",
        f"- Accession: `{src['accession']}`",
        f"- UTC as-of: `{src['as_of']}`",
        f"- Locally stored original SHA-256: `{src['filing_sha256']}`",
        "",
        "## Evidence and independent checks",
        f"- Candidate fragments: {evid['candidate_count']} (human review only)",
        f"- Evidence fingerprint: `{evid['source_evidence_digest']}`",
        "- Financial claim verified: **NO**",
        "- SEC source authenticated: **NO**",
        "- Risk calculated: **NO**",
        "",
        "## Guard and audit",
        "- Guard decision: **HOLD** (no execution authorization)",
        f"- Audit run: `{audit['run_id']}`",
        f"- Audit event hash: `{audit['event_hash']}`",
        "- Local audit and human review integrity checks: PASS",
        "- External audit anchoring: NO",
        "",
        "Untrusted filing excerpts are intentionally omitted from this Markdown.",
        "This report is not the official organizer PDF.",
        "",
    ])

def main(argv: list[str] | None = None) -> int:
    """Run the explicit local-only report pipeline; stdout contains no raw HTML."""
    parser = argparse.ArgumentParser(
        description="Offline pinned DL filing -> Guard HOLD -> SQLite audit -> report",
    )
    parser.add_argument("--dl-db", type=Path, required=True, help="Existing saved DL ledger")
    parser.add_argument("--audit-db", type=Path, required=True, help="Separate Guard audit ledger")
    parser.add_argument("--cik", required=True)
    parser.add_argument("--accession", required=True)
    parser.add_argument("--sha256", required=True, help="Saved original SHA-256")
    parser.add_argument("--as-of", required=True, help="Evidence cutoff UTC YYYY-MM-DD")
    parser.add_argument("--term", required=True, help="Literal evidence search term")
    parser.add_argument("--run-id", required=True, help="Stable idempotency key")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--reviewer")
    parser.add_argument("--action", choices=("ACKNOWLEDGE", "REQUEST_EXCEPTION"))
    parser.add_argument("--reason")
    args = parser.parse_args(argv)
    try:
        result = run_saved_dl_audit_report(
            dl_db_path=args.dl_db, audit_db_path=args.audit_db,
            cik=args.cik, accession=args.accession, sha256=args.sha256,
            as_of=args.as_of, term=args.term, run_id=args.run_id,
            max_results=args.max_results,
            reviewer=args.reviewer, action=args.action, reason=args.reason,
        )
    except (OSError, ValueError, TypeError, KeyError):
        # Never echo local user paths, filing bytes or database error payloads.
        print(json.dumps({"status": "DL_AUDIT_FAILED",
                          "reason_code": "INVALID_LOCAL_INPUT_OR_EVIDENCE"}),
              file=sys.stderr)
        return 2
    if args.format == "markdown":
        print(render_dl_audit_markdown(result), end="")
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
