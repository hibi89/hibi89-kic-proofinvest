"""P208: consent-gated actual Dell issuer Engine B -> offline Guard + SQLite audit.

Real FY26/FY25 working-capital numbers are from P207 independently observed
issuer first-party HTTPS receipt. This action does NOT fetch originals, prove
EDGAR byte identity, legal/commercial/AI reuse rights, or authorize trading.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any

from .dell_working_capital_review import (
    actual_working_capital_receipt, review_real_working_capital,
)
from .guard_agent import evaluate_guard
from .guard_audit import GuardAuditStore, _canonical
from .guard_review import GuardReviewStore
from .local_sec_guard_report import _check_audit_path

_POLICY = {
    "mode": "DEMO_POLICY",
    "version": "p208-real-unlicensed-human-review-hold-v1",
    "max_debt_to_equity_pct": "200",
}


def _blocked(reason: str, *, written: bool | None = False) -> dict[str, Any]:
    return {
        "schema": "kuodra.p208-real-issuer-guard-audit.v1",
        "status": "BLOCKED", "reason_code": reason,
        "audit_written": written, "audit_chain_valid": False,
        "source_authenticated": False, "sec_original_authenticated": False,
        "source_commercial_ai_rights_verified": False,
        "real_stock_ndx_peer_licensed": False, "full_abc_ready": False,
        "guard_policy_preview": "HOLD",
        "trade_executed": False, "ai_agent_executed": False,
        "network_requests": 0, "report": None,
    }


def run_real_issuer_guard_audit(
    *, run_id: str, audit_db_path: str | Path,
    acknowledge_local_persistence: bool = False,
    source_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Store only an explicit, local, non-executing human-only review audit.

    Do not create any database before both consent and pinned P207 source
    review succeeded. Existing run IDs replay only if source evidence matches.
    """
    if acknowledge_local_persistence is not True:
        return _blocked("EXPLICIT_LOCAL_AUDIT_CONSENT_REQUIRED")
    if type(run_id) is not str or not (1 <= len(run_id) <= 128) or not all(
        c.isascii() and (c.isalnum() or c in "_-") for c in run_id
    ):
        return _blocked("INVALID_AUDIT_RUN_ID")
    try:
        dest = _check_audit_path(audit_db_path)
    except (ValueError, OSError, TypeError):
        return _blocked("UNSAFE_AUDIT_DESTINATION")

    review = review_real_working_capital(
        reviewed_as_of="2026-11-05", receipt=source_receipt
    )
    if (review.get("status") != "P207_ACTUAL_ISSUER_WORKING_CAPITAL_REVIEW_LIMITED"
            or review.get("real_issuer_working_capital_source_seen") is not True
            or review.get("sec_original_identical") is not False
            or review.get("rights_verified") is not False
            or review.get("full_engine_b_complete") is not False
            or review.get("full_abc_ready") is not False
            or review.get("guard_policy_preview") != "HOLD"
            or review.get("trade_executed") is not False
            or type(review.get("evidence")) is not dict):
        return _blocked("REAL_SOURCE_REVIEW_UNVERIFIED_OR_CHANGED")

    e = review["evidence"]
    # All included facts are derived numbers and source SHA; never raw HTML,
    # credentials, secrets, user identity or legal entitlement.
    evidence = {
        "issuer": "DELL", "fy2026": "2026-01-30", "fy2025": "2025-01-31",
        "p207_issuer_source_sha256": e["source_sha256"],
        "p207_one_shot_ci": e["actual_one_shot_ci"],
        "source_is_unaudited": True,
        "revenue_growth_pct": e["revenue_growth_pct"],
        "asset_rows": e["asset_rows"],
        "source_commercial_ai_rights_verified": False,
        "sec_edgar_original_byte_identity": False,
        "issuer_accounting_misconduct_proven": False,
    }
    evidence_digest = sha256(_canonical(evidence)).hexdigest()
    # A real observed issuer financial signal is NOT an independently
    # authenticated SEC/market/NDX/peer+debt-risk verification. Force HOLD.
    decision = evaluate_guard(
        [{"status": "UNAVAILABLE", "source_kind": "MANUALLY_CURATED_UNVERIFIED"}],
        policy=_POLICY, risk=None,
    )
    if (decision.get("decision") != "HOLD"
            or decision.get("trade_executed") is not False
            or decision.get("source_authenticated") is not False
            or decision.get("human_approved") is not False
            or "RISK_UNAVAILABLE" not in decision.get("reason_codes", [])
            or "CLAIM_UNAVAILABLE" not in decision.get("reason_codes", [])):
        return _blocked("REAL_SOURCE_GUARD_POLICY_NOT_HOLD")

    request = {
        "schema": "kuodra.p208-derived-human-review-request.v1",
        "evidence": evidence, "evidence_digest": evidence_digest,
        "source_approved_for_external_use": False,
        "risk_authenticated": False,
        "trade_executed": False,
    }
    try:
        audit = GuardAuditStore(dest).record_decision(run_id, request, decision)
        if (not GuardAuditStore(dest).verify_chain()
                or not GuardReviewStore(dest).verify_reviews()):
            return _blocked("LOCAL_AUDIT_INTEGRITY_UNVERIFIED", written=None)
    except (ValueError, OSError, TypeError, sqlite3.Error, OverflowError):
        # Once SQLite is called, the file might have been created before the
        # exception. Never claim audit_written=False on this path.
        return _blocked("LOCAL_AUDIT_WRITE_OR_REPLAY_REJECTED", written=None)
    report = {
        "schema": "kuodra.p208-real-issuer-guard-audit-report.v1",
        "run_id": run_id, "source": "REAL_DELL_FIRSTPARTY_UNAUDITED_CI_RECEIPT",
        "source_sha256": e["source_sha256"],
        "p207_one_shot_ci": e["actual_one_shot_ci"],
        "financial_evidence_sha256": evidence_digest,
        "guard": decision, "audit": audit,
        "source_authenticated": False,
        "source_rights_verified": False, "full_abc_ready": False,
        "financial_misconduct_proven": False,
        "human_review_only": True, "trade_executed": False,
    }
    return {
        **_blocked("REAL_ISSUER_SCREENING_NOT_AUTHORIZED_INVESTMENT"),
        "status": "REAL_SOURCE_ENGINE_B_GUARD_HOLD_AUDIT_RECORDED",
        "audit_written": True, "audit_chain_valid": True,
        "report": report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline real Dell Engine B -> Guard HOLD -> local SQLite. No network."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--audit-db", required=True, type=Path)
    parser.add_argument("--acknowledge-local-audit-persistence", action="store_true")
    args = parser.parse_args(argv)
    out = run_real_issuer_guard_audit(
        run_id=args.run_id, audit_db_path=args.audit_db,
        acknowledge_local_persistence=args.acknowledge_local_audit_persistence,
        source_receipt=actual_working_capital_receipt(),
    )
    print(json.dumps(out, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if out["audit_chain_valid"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
