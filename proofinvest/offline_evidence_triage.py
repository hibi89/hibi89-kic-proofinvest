"""Fail-closed, offline KIC evidence decision gate.

This is a review-priority signal, never an investment recommendation or SEC
authentication. No network, persistence, model calls, or order execution.
"""
from __future__ import annotations

from typing import Any


def triage_offline_replay(replay: Any) -> dict[str, Any]:
    """Classify a replay receipt without upgrading unverified evidence."""
    result: dict[str, Any] = {
        "schema": "proofinvest.offline-evidence-triage.v1",
        "status": "manual_review_required",
        "priority": "high",
        "reason_codes": [],
        "source_authenticated": False,
        "financial_values_authenticated": False,
        "investment_recommendation": False,
        "trade_authorized": False,
        "external_http_called": False,
    }
    reasons: list[str] = result["reason_codes"]
    if not isinstance(replay, dict):
        reasons.append("INVALID_REPLAY")
        return result
    if replay.get("status") != "offline_capture_replayed_unverified":
        reasons.append("REPLAY_NOT_VERIFIED_LOCALLY")
        return result
    # Any positive external attestation is an invalid trust-boundary escalation.
    for key in ("source_authenticated", "financial_values_authenticated",
                "source_rights_verified", "external_http_called",
                "official_contest_submission"):
        if replay.get(key) is not False:
            reasons.append("TRUST_BOUNDARY_VIOLATION")
            return result
    integrity = replay.get("local_integrity")
    if not isinstance(integrity, dict) or integrity.get("status") != "bundle_integrity_pass_origin_unverified":
        reasons.append("BUNDLE_INTEGRITY_NOT_CONFIRMED")
        return result
    if not isinstance(replay.get("offline_financial_review"), dict):
        reasons.append("FINANCIAL_REVIEW_MISSING")
        return result
    financial = replay["offline_financial_review"]
    if financial.get("status") == "conflict":
        reasons.append("FINANCIAL_CLAIM_CONFLICT")
        return result
    if financial.get("status") not in ("calculated_unverified",):
        reasons.append("FINANCIAL_CALCULATION_UNAVAILABLE")
        return result
    if not isinstance(replay.get("risk"), dict):
        reasons.append("RISK_REVIEW_MISSING")
        return result
    if not isinstance(replay.get("source_span"), dict):
        reasons.append("SOURCE_SPAN_MISSING")
        return result
    reasons.append("EXTERNAL_SOURCE_AUTHENTICITY_UNVERIFIED")
    result["priority"] = "normal"
    result["status"] = "offline_evidence_ready_for_human_review"
    return result
