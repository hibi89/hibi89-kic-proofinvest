"""KUODRA: explicit live SEC 3-source capture -> guarded SQLite audit.

The same strict SEC capture adapter is reused. Disabled unless the caller
explicitly acknowledges BOTH three remote GETs and one local SQLite write.
SEC HTTPS evidence remains unverified; this is not authenticated investment
advice, a trade engine, or an autonomous LLM. No external calls in tests.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

from .guard_audit import GuardAuditStore
from .guard_review import GuardReviewStore
from .guard_workflow import run_guard_review
from .local_sec_guard_report import _check_audit_path
from .sec_three_source import run_sec_three_source_review

_HEX_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z", re.ASCII)
_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)


def _blocked(
    reason: str, *, requests: int = 0, audit_written: bool | None = False,
) -> dict[str, Any]:
    return {
        "schema": "kuodra.sec-guard-workflow.v1",
        "status": "BLOCKED",
        "reason_code": reason,
        "http_requests_attempted": requests,
        # False: no audit attempted. None: an attempted write cannot be
        # proven absent or valid; inspect SQLite before retrying this run.
        "audit_written": audit_written,
        "source_authenticated": False,
        "risk_authenticated": False,
        "ai_agent_executed": False,
        "trade_executed": False,
        "official_contest_submission": False,
    }


def _existing_audit_usable(path: Path, run_id: str) -> str | None:
    """Read-only preflight: never refetch expensive data for an existing run."""
    if not path.exists():
        return None
    try:
        uri = "file:" + quote(str(path.absolute()), safe="/") + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as conn:
            present = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if not {"guard_audit_events", "guard_run_registry"}.issubset(present):
                return "AUDIT_DB_SCHEMA_NOT_OURS"
            if not GuardAuditStore(path).verify_chain(conn=conn):
                return "AUDIT_DB_INTEGRITY_FAILURE"
            if not GuardReviewStore(path).verify_reviews(conn=conn):
                return "AUDIT_REVIEW_INTEGRITY_FAILURE"
            if conn.execute(
                "SELECT 1 FROM guard_run_registry WHERE run_id=?", (run_id,)
            ).fetchone():
                return "RUN_ID_ALREADY_USED_NO_REFETCH"
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return "AUDIT_DB_PREFLIGHT_FAILED"
    return None


def _trusted_capture_shape(receipt: Any, cik: str, accession: str) -> bool:
    """Check adapter contract, NOT independent SEC authenticity."""
    if not isinstance(receipt, Mapping):
        return False
    if (receipt.get("schema") != "proofinvest.sec-3source-explicit-transport.v1"
            or receipt.get("status") != "three_sec_https_responses_captured_unverified"
            or receipt.get("http_requests_attempted") != 3
            or receipt.get("live_sec_http_called") is not True
            or receipt.get("source_authenticated") is not False
            or receipt.get("financial_facts_authenticated") is not False
            or receipt.get("source_rights_verified") is not False
            or receipt.get("issuer_cik") != cik
            or receipt.get("accession") != accession):
        return False
    hashes = receipt.get("raw_response_sha256")
    urls = receipt.get("source_uris")
    numeric = receipt.get("numeric_review")
    if not isinstance(hashes, Mapping) or not isinstance(urls, Mapping) or not isinstance(numeric, Mapping):
        return False
    if any(not isinstance(hashes.get(x), str)
           or _HEX_SHA.fullmatch(hashes[x]) is None
           for x in ("submissions", "companyfacts", "original_filing")):
        return False
    if (urls.get("submissions") != f"https://data.sec.gov/submissions/CIK{cik}.json"
            or urls.get("companyfacts") != f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            or not isinstance(urls.get("original_filing"), str)
            or not urls["original_filing"].startswith(
                "https://www.sec.gov/Archives/edgar/data/" + str(int(cik)) + "/"
            )):
        return False
    if numeric.get("status") not in ("calculated_unverified", "conflict"):
        return False
    if numeric.get("source_attribution") != "SEC_HTTPS_TRANSPORT_NOT_INDEPENDENTLY_CERTIFIED":
        return False
    if any(not isinstance(numeric.get(k), str) for k in
           ("prior_usd", "current_usd", "growth_pct", "reason_code")):
        return False
    return True


def run_kuodra_sec_guard(
    *, cik: str, accession: str, current_end: str, prior_end: str,
    run_id: str, audit_db: str | Path,
    claimed_growth_pct: str | None = None, user_agent: str = "",
    allow_network: bool = False, acknowledge_three_requests: bool = False,
    acknowledge_local_audit_persistence: bool = False,
) -> dict[str, Any]:
    """Execute one bounded SEC→Decimal→Guard→audit workflow.

    Approval is per run, never inferred from a previous call or environment.
    One SEC GET each for submissions, CompanyFacts and original; no retries.
    No arbitrary raw source bytes or human information in the public result.
    """
    if (allow_network is not True or acknowledge_three_requests is not True
            or acknowledge_local_audit_persistence is not True):
        return _blocked("EXPLICIT_NETWORK_AND_AUDIT_CONSENT_REQUIRED")
    if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
        return _blocked("INVALID_RUN_ID")
    if (not isinstance(cik, str) or _CIK.fullmatch(cik) is None
            or cik == "0000000000" or not isinstance(accession, str)
            or _ACCESSION.fullmatch(accession) is None
            or not accession.startswith(cik + "-")):
        return _blocked("INVALID_CIK_OR_ACCESSION")
    try:
        dest = _check_audit_path(audit_db)
        issue = _existing_audit_usable(dest, run_id)
    except (OSError, ValueError, TypeError):
        return _blocked("INVALID_AUDIT_DESTINATION")
    if issue is not None:
        return _blocked(issue)

    receipt = run_sec_three_source_review(
        cik=cik, accession=accession, current_end=current_end,
        prior_end=prior_end, claimed_growth_pct=claimed_growth_pct,
        user_agent=user_agent, allow_network=True,
        acknowledge_three_requests=True,
    )
    attempts = receipt.get("http_requests_attempted", 0) if isinstance(receipt, Mapping) else 0
    attempts = attempts if type(attempts) is int and 0 <= attempts <= 3 else 0
    if not _trusted_capture_shape(receipt, cik, accession):
        return _blocked("SEC_CAPTURE_UNAVAILABLE_OR_CONTRACT_INVALID", requests=attempts)

    numeric = receipt["numeric_review"]
    hashes = dict(receipt["raw_response_sha256"])
    src = {
        "status": numeric["status"],
        "issuer_cik": cik,
        "accession": accession,
        "filing_date": receipt["filing_date"],
        "observed_utc_day": receipt["observed_utc_day"],
        "source_sha256": hashes,
        "source_uris": dict(receipt["source_uris"]),
        "prior_usd": numeric["prior_usd"],
        "current_usd": numeric["current_usd"],
        "growth_pct": numeric["growth_pct"],
        "reason_code": numeric["reason_code"],
        "source_authenticated": False,
        "financial_facts_authenticated": False,
    }
    try:
        reviewed = run_guard_review(src, run_id=run_id, database_path=dest, risk=None)
        if (reviewed["guard"]["decision"] not in ("HOLD", "REJECT")
                or reviewed["guard"]["source_authenticated"] is not False
                or reviewed["trade_executed"] is not False
                or not GuardAuditStore(dest).verify_chain()
                or not GuardReviewStore(dest).verify_reviews()):
            return _blocked(
                "AUDIT_INTEGRITY_OR_GUARD_FAILURE", requests=attempts,
                audit_written=None,
            )
    except (OSError, ValueError, TypeError, sqlite3.Error):
        # SQLite might have COMMITTED before validation or another failure.
        # Do not falsely claim that no audit row exists after starting write.
        return _blocked(
            "GUARD_AUDIT_WRITE_FAILED", requests=attempts, audit_written=None,
        )
    return {
        "schema": "kuodra.sec-guard-workflow.v1",
        "status": "REVIEW_RECORDED_SOURCE_UNVERIFIED",
        "run_id": run_id,
        "issuer_cik": cik,
        "accession": accession,
        "http_requests_attempted": attempts,
        "verification": dict(numeric),
        "source_sha256": hashes,
        "guard": reviewed["guard"],
        "audit": reviewed["audit"],
        "audit_written": True,
        "audit_chain_valid": True,
        "source_authenticated": False,
        "risk_authenticated": False,
        "ai_agent_executed": False,
        "trade_executed": False,
        "official_contest_submission": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="KUODRA opt-in bounded 3-GET SEC -> Guard -> SQLite. No automated investment."
    )
    for key in ("cik", "accession", "current-end", "prior-end", "run-id"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--claimed-growth-pct")
    p.add_argument("--audit-db", required=True, type=Path)
    p.add_argument("--allow-network", action="store_true")
    p.add_argument("--acknowledge-three-requests", action="store_true")
    p.add_argument("--acknowledge-local-audit-persistence", action="store_true")
    args = p.parse_args(argv)
    result = run_kuodra_sec_guard(
        cik=args.cik, accession=args.accession,
        current_end=args.current_end, prior_end=args.prior_end,
        run_id=args.run_id, audit_db=args.audit_db,
        claimed_growth_pct=args.claimed_growth_pct,
        user_agent=os.environ.get("PROOFINVEST_SEC_USER_AGENT", ""),
        allow_network=args.allow_network,
        acknowledge_three_requests=args.acknowledge_three_requests,
        acknowledge_local_audit_persistence=args.acknowledge_local_audit_persistence,
    )
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "REVIEW_RECORDED_SOURCE_UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
