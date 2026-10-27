"""Compact, non-advisory KIC review dashboard from offline replay results.

Never copies untrusted filing text, issuer identity, or private local paths.
"""
from __future__ import annotations
from typing import Any


def build_offline_review_summary(replay: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "schema": "proofinvest.offline-review-summary.v1",
        "status": "blocked",
        "review_priority": "high",
        "financial_status": "unavailable",
        "risk_status": "unavailable",
        "reason_codes": ["REPLAY_UNAVAILABLE"],
        "source_authenticated": False,
        "investment_recommendation": False,
        "trade_authorized": False,
        "external_http_called": False,
    }
    if not isinstance(replay, dict) or replay.get("status") != "offline_capture_replayed_unverified":
        return summary
    triage = replay.get("human_review_triage")
    financial = replay.get("offline_financial_review")
    risk = replay.get("risk")
    if not isinstance(triage, dict) or not isinstance(financial, dict) or not isinstance(risk, dict):
        return summary
    if (triage.get("source_authenticated") is not False
            or triage.get("trade_authorized") is not False
            or replay.get("source_authenticated") is not False
            or replay.get("external_http_called") is not False):
        summary["reason_codes"] = ["TRUST_BOUNDARY_VIOLATION"]
        return summary
    if triage.get("status") not in ("manual_review_required",
                                     "offline_evidence_ready_for_human_review"):
        return summary
    summary["status"] = "human_review_required"
    summary["review_priority"] = "high" if triage.get("priority") != "normal" else "normal"
    allowed_financial = {"calculated_unverified", "conflict"}
    allowed_risk = {"reviewed_unverified", "unavailable"}
    if financial.get("status") in allowed_financial:
        summary["financial_status"] = financial["status"]
    if risk.get("status") in allowed_risk:
        summary["risk_status"] = risk["status"]
    # Allowlist known internal codes; never surface arbitrary caller-provided text.
    allowed_codes = {
        "EXTERNAL_SOURCE_AUTHENTICITY_UNVERIFIED", "FINANCIAL_CLAIM_CONFLICT",
        "FINANCIAL_CALCULATION_UNAVAILABLE", "RISK_ASSESSMENT_UNAVAILABLE",
        "RISK_REVIEW_MISSING", "SOURCE_SPAN_MISSING", "FINANCIAL_REVIEW_MISSING",
    }
    codes = triage.get("reason_codes")
    summary["reason_codes"] = sorted(set(code for code in codes
        if isinstance(code, str) and code in allowed_codes)) if isinstance(codes, list) else []
    return summary
