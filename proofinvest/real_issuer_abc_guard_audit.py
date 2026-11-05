"""P231: explicitly consented source-bound *partial* NVDA A/B/C Guard HOLD audit.

Actual historical NVDA publisher source B, operator-unverified market A, and
manually corroborated AMD/INTC peer C are independently replayed before any
local SQLite side effect. The Guard always HOLDs. Only hashes and limited
availability statuses persist, never uploaded price rows or original files.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sqlite3
from typing import Any

from .guard_agent import evaluate_guard
from .guard_audit import GuardAuditStore, _canonical
from .guard_review import GuardReviewStore
from .local_sec_guard_report import _check_audit_path
from .real_issuer_abc_local_review import replay_partial_source_bound_abc
from .real_issuer_abc_fact_review import (
    build_source_factual_abc_brief, replay_source_factual_abc_brief,
)

_POLICY = {
    "mode": "DEMO_POLICY",
    "version": "p231-source-bound-partial-abc-guard-hold-v1",
    "max_debt_to_equity_pct": "200",
}
_STATUS = "PARTIAL_SOURCE_BOUND_ABC_GUARD_HOLD_AUDIT_RECORDED"
_SCHEMA = "kuodra.p231-partial-abc-local-guard-audit.v1"


def _blocked(reason: str, *, written: bool | None = False) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "audit_written": written, "audit_chain_valid": False,
        "source_authenticated_by_sec": False,
        "market_provider_authenticated": False,
        "market_rights_verified": False, "peer_rights_verified": False,
        "ai_model_source_use_approved": False,
        "guard_policy_preview": "HOLD", "full_abc_complete": False,
        "trade_executed": False, "network_requests": 0,
        "report": None,
    }


def run_source_bound_abc_hold_audit(
    *, abc_review: Any, audit_db_path: str | Path,
    acknowledge_local_persistence: bool = False,
) -> dict[str, Any]:
    """One audited operator action. No consent, no source, or failed replay → no write.

    The deterministic run id makes the SAME source-backed review idempotent;
    changed local market inputs yield a distinct event, never overwrite prior
    evidence. A hash-chain does not authenticate the source or secure a DB
    against a privileged editor rewriting it in full.
    """
    if acknowledge_local_persistence is not True:
        return _blocked("EXPLICIT_LOCAL_SQLITE_PERSISTENCE_CONSENT_REQUIRED")
    if type(abc_review) is not dict or not replay_partial_source_bound_abc(abc_review):
        return _blocked("ACTUAL_ISSUER_MARKET_PEER_SOURCE_REPLAY_FAILED")
    brief = build_source_factual_abc_brief(abc_review)
    if (brief.get("status") != "LOCAL_A_B_C_CLAIM_REVIEW_FOR_HUMAN_ONLY"
            or not replay_source_factual_abc_brief(brief, abc_review)
            or abc_review.get("ticker") != "NVDA"
            or abc_review.get("as_of") != "2026-11-05"
            or abc_review.get("market_rights_verified") is not False
            or abc_review.get("peer_rights_verified") is not False
            or abc_review.get("sec_edgar_original_bytes_verified") is not False
            or abc_review.get("full_abc_complete") is not False
            or abc_review.get("ai_agent_executed") is not False
            or abc_review.get("trade_executed") is not False
            or brief.get("market_source_authenticated") is not False
            or brief.get("legal_model_use_approved") is not False
            or brief.get("external_sharing_allowed") is not False):
        return _blocked("PARTIAL_ABC_FACT_REVIEW_OR_RIGHTS_INVALID")
    try:
        dest = _check_audit_path(audit_db_path)
    except (TypeError, ValueError, OSError):
        return _blocked("UNSAFE_LOCAL_AUDIT_DB_PATH")
    # Bounded provenance only. No source URL/text, prices, API keys, original
    # issuer facts, user identity, unlicensed peer text or investment score.
    evidence = {
        "ticker": "NVDA",
        "reviewed_as_of": "2026-11-05",
        "issuer_publisher_sha256": abc_review["source_linked_issuer_sha256"],
        "operator_stock_file_sha256": abc_review["stock_uploaded_sha256"],
        "operator_ndx_file_sha256": abc_review["ndx_uploaded_sha256"],
        "unkeyed_partial_abc_sha256": abc_review["derived_sha256"],
        "historical_source_brief_sha256": brief["brief_sha256"],
        "engine_availability": {
            "A": "UNAVAILABLE_PROVIDER_ORIGIN_AND_RIGHTS",
            "B": "VERIFIED_HISTORICAL_NUMERIC_MATCH_ONLY",
            "C": "PUBLIC_TEXT_NUMERIC_MATCH_RAW_UNVERIFIED",
        },
        "engine_c_manual_reference_peers": ["AMD", "INTC"],
        "publisher_original_seen_not_sec_attested": True,
        "source_rights_verified": False,
        "market_rights_verified": False,
        "peer_rights_verified": False,
        "full_abc_complete": False,
        "trade_executed": False,
    }
    digest=sha256(_canonical(evidence)).hexdigest()
    decision=evaluate_guard(
        [{"status":"UNAVAILABLE","source_kind":"MANUALLY_CURATED_UNVERIFIED"}],
        policy=_POLICY, risk=None,
    )
    if (decision.get("schema") != "proofinvest.guard-decision.v1"
            or decision.get("decision") != "HOLD"
            or decision.get("reason_codes") !=
               ["CLAIM_UNAVAILABLE", "RISK_UNAVAILABLE"]
            or decision.get("source_authenticated") is not False
            or decision.get("human_approved") is not False
            or decision.get("trade_executed") is not False):
        return _blocked("GUARD_HOLD_INVARIANT_BROKEN")
    request = {
        "schema": "kuodra.p231-partial-source-abc-local-hold-request.v1",
        "evidence": evidence,
        "evidence_digest": digest,
        "source_approved_for_external_use": False,
        "market_provider_authenticated": False,
        "risk_authenticated": False,
        "trade_executed": False,
    }
    run_id="p231_" + abc_review["derived_sha256"]
    try:
        store=GuardAuditStore(dest)
        audit=store.record_decision(run_id,request,decision)
        if (not store.verify_chain()
                or not GuardReviewStore(dest).verify_reviews()):
            return _blocked("GUARD_SQLITE_CHAIN_INTEGRITY_FAILED",written=None)
    except (ValueError, OSError, TypeError, sqlite3.Error,
            OverflowError, RecursionError):
        return _blocked("SQLITE_AUDIT_WRITE_OR_REPLAY_FAILED",written=None)
    return {
        **_blocked("PARTIAL_ABC_UNLICENSED_HUMAN_ONLY"),
        "status": _STATUS, "audit_written": True, "audit_chain_valid": True,
        "report": {
            "schema": "kuodra.p231-partial-abc-hold-receipt.v1",
            "run_id": run_id,
            "source_bound_abc_digest": abc_review["derived_sha256"],
            "redacted_evidence_digest": digest,
            "issuer_source_sha256": abc_review["source_linked_issuer_sha256"],
            "guard": decision,
            "audit": audit,
            "source_origin_and_rights_verified": False,
            "market_rights_verified": False, "peer_rights_verified": False,
            "full_abc_complete": False, "external_sharing_allowed": False,
            "human_review_only": True, "trade_executed": False,
        },
    }
