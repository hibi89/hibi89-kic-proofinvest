"""P211: P209 original-backed NVIDIA FY2026 Engine B -> explicit local Guard audit.

Reuses the existing audited Guard/SQLite store without copying raw publisher
HTML, fetching external sources, asserting SEC identity/rights, or trading.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any

from .guard_agent import evaluate_guard
from .guard_audit import GuardAuditStore, _canonical
from .guard_review import GuardReviewStore
from .local_sec_guard_report import _check_audit_path
from .nvidia_real_issuer_review import actual_nvidia_issuer_receipt, review_nvidia_actual_release

_POLICY = {
    "mode": "DEMO_POLICY",
    "version": "p211-real-nvda-unlicensed-human-review-hold-v1",
    "max_debt_to_equity_pct": "200",
}


def _blocked(reason: str, *, written: bool | None = False) -> dict[str, Any]:
    return {
        "schema": "kuodra.p211-nvda-real-issuer-guard-audit.v1",
        "status": "BLOCKED", "reason_code": reason,
        "audit_written": written, "audit_chain_valid": False,
        "issuer_publisher_original_seen": False,
        "sec_original_authenticated": False,
        "source_commercial_ai_rights_verified": False,
        "real_stock_ndx_peer_licensed": False, "full_abc_ready": False,
        "guard_policy_preview": "HOLD",
        "trade_executed": False, "ai_agent_executed": False,
        "network_requests": 0, "report": None,
    }


def run_nvidia_guard_audit(
    *, run_id: str, audit_db_path: str | Path,
    acknowledge_local_persistence: bool = False,
    source_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record genuine publisher-derived metrics only after explicit local consent."""
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

    review = review_nvidia_actual_release(
        as_of="2026-11-05", receipt=source_receipt
    )
    if (review.get("status") != "REAL_NVDA_FY2026_2025_ISSUER_GAAP_REVIEW_LIMITED"
            or review.get("issuer_original_publisher_seen") is not True
            or review.get("sec_original_identical") is not False
            or review.get("commercial_ai_rights_verified") is not False
            or review.get("licensed_stock_ndx_peer_available") is not False
            or review.get("full_engine_b_authenticated") is not False
            or review.get("full_abc_ready") is not False
            or review.get("guard_policy_preview") != "HOLD"
            or review.get("trade_executed") is not False
            or type(review.get("evidence")) is not dict):
        return _blocked("NVDA_ORIGINAL_PUBLISHER_REVIEW_UNVERIFIED_OR_CHANGED")

    e = review["evidence"]
    m = e.get("metrics")
    if (type(m) is not dict or e.get("ticker") != "NVDA"
            or e.get("amount_unit") != "USD_millions"
            or e.get("release_unaudited") is not True
            or e.get("issuer_source_sha256") !=
            actual_nvidia_issuer_receipt()["source_sha256"]
            or e.get("fiscal_2026_end") != "2026-01-25"
            or e.get("fiscal_2025_end") != "2025-01-26"
            or any(type(m.get(k)) is not str for k in (
                "revenue_growth_pct", "ar_growth_pct",
                "inventory_growth_pct", "ar_growth_minus_revenue_pp",
                "inventory_growth_minus_revenue_pp", "cfo_to_net_income_2026",
            ))):
        return _blocked("NVDA_DERIVED_FINANCIAL_CONTEXT_INVALID")

    # Facts, original SHA and issuer CI reference only. No raw HTML, personal
    # records or claims of financial misconduct, legal rights, index coverage.
    evidence = {
        "issuer": "NVDA",
        "fy2026": e["fiscal_2026_end"], "fy2025": e["fiscal_2025_end"],
        "p209_issuer_original_sha256": e["issuer_source_sha256"],
        "p209_one_shot_ci": e["source_ci_run"],
        "source_is_unaudited": True,
        "revenue_growth_pct": m["revenue_growth_pct"],
        "ar_growth_pct": m["ar_growth_pct"],
        "inventory_growth_pct": m["inventory_growth_pct"],
        "ar_growth_minus_revenue_pp": m["ar_growth_minus_revenue_pp"],
        "inventory_growth_minus_revenue_pp": m["inventory_growth_minus_revenue_pp"],
        "cfo_to_net_income_2026": m["cfo_to_net_income_2026"],
        "source_commercial_ai_rights_verified": False,
        "sec_edgar_original_byte_identity": False,
        "issuer_accounting_misconduct_proven": False,
    }
    digest = sha256(_canonical(evidence)).hexdigest()
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
        return _blocked("NVDA_GUARD_HOLD_POLICY_CHANGED")

    request = {
        "schema": "kuodra.p211-nvda-derived-human-review-request.v1",
        "evidence": evidence, "evidence_digest": digest,
        "source_approved_for_external_use": False,
        "risk_authenticated": False, "trade_executed": False,
    }
    try:
        audit = GuardAuditStore(dest).record_decision(run_id, request, decision)
        if (not GuardAuditStore(dest).verify_chain()
                or not GuardReviewStore(dest).verify_reviews()):
            return _blocked("LOCAL_AUDIT_INTEGRITY_UNVERIFIED", written=None)
    except (ValueError, OSError, TypeError, sqlite3.Error, OverflowError):
        return _blocked("LOCAL_AUDIT_WRITE_OR_REPLAY_REJECTED", written=None)

    report = {
        "schema": "kuodra.p211-nvda-real-guard-audit-report.v1",
        "run_id": run_id, "source": "REAL_NVDA_FIRSTPARTY_UNAUDITED_CI_RECEIPT",
        "source_sha256": e["issuer_source_sha256"],
        "source_ci_run": e["source_ci_run"],
        "financial_evidence_sha256": digest,
        "guard": decision, "audit": audit,
        "issuer_publisher_original_seen": True,
        "sec_original_authenticated": False,
        "source_rights_verified": False,
        "full_abc_ready": False, "financial_misconduct_proven": False,
        "human_review_only": True, "trade_executed": False,
    }
    return {
        **_blocked("NVDA_ORIGINAL_FINANCIAL_REVIEW_ONLY_NOT_AUTHORIZED_TRADING"),
        "status": "REAL_NVDA_ENGINE_B_GUARD_HOLD_AUDIT_RECORDED",
        "audit_written": True, "audit_chain_valid": True,
        "issuer_publisher_original_seen": True, "report": report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline real NVDA metrics -> Guard HOLD -> local SQLite. No network."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--audit-db", required=True, type=Path)
    parser.add_argument("--acknowledge-local-audit-persistence", action="store_true")
    args = parser.parse_args(argv)
    result = run_nvidia_guard_audit(
        run_id=args.run_id, audit_db_path=args.audit_db,
        acknowledge_local_persistence=args.acknowledge_local_audit_persistence,
        source_receipt=actual_nvidia_issuer_receipt(),
    )
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if result["audit_chain_valid"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
