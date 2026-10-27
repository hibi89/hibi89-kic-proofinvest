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
        "ixbrl_context_match": False,
        "numeric_text_match": False,
        "reason_codes": ["REPLAY_UNAVAILABLE"],
        "review_actions": ["RECHECK_LOCAL_ARCHIVE"],
        "source_authenticated": False,
        "investment_recommendation": False,
        "trade_authorized": False,
        "external_http_called": False,
    }
    if not isinstance(replay, dict):
        return summary
    if replay.get("status") != "offline_capture_replayed_unverified":
        # Preserve only stable, explicitly known failure codes; never echo
        # untrusted exception text or local paths into compact output.
        known_failures = {
            "ARCHIVED_BYTES_OR_MANIFEST_INVALID",
            "UNTRUSTED_OR_INCONSISTENT_ARCHIVED_CLOCK",
            "ARCHIVED_DISCLOSURE_CANNOT_BE_REANALYZED",
            "REPLAY_DIGEST_CONFLICT",
            "REPLAY_TRUST_BOUNDARY_FAILED",
        }
        code = replay.get("reason_code")
        if isinstance(code, str) and code in known_failures:
            summary["reason_codes"] = [code]
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
    if (triage.get("financial_values_authenticated") is not False
            or triage.get("investment_recommendation") is not False
            or triage.get("external_http_called") is not False
            or replay.get("financial_values_authenticated") is not False
            or replay.get("source_rights_verified") is not False
            or replay.get("official_contest_submission") is not False):
        summary["reason_codes"] = ["TRUST_BOUNDARY_VIOLATION"]
        return summary
    financial_status = financial.get("status")
    risk_status = risk.get("status")
    if not isinstance(financial_status, str) or not isinstance(risk_status, str):
        summary["reason_codes"] = ["INVALID_REVIEW_STATUS"]
        return summary
    if (triage.get("priority") == "normal" and
            (triage.get("status") != "offline_evidence_ready_for_human_review"
             or financial_status != "calculated_unverified"
             or risk_status != "reviewed_unverified")):
        summary["reason_codes"] = ["INCONSISTENT_REVIEW_PRIORITY"]
        return summary
    summary["status"] = "human_review_required"
    summary["review_priority"] = "high" if triage.get("priority") != "normal" else "normal"
    allowed_financial = {"calculated_unverified", "conflict"}
    allowed_risk = {"reviewed_unverified", "unavailable"}
    if financial.get("status") in allowed_financial:
        summary["financial_status"] = financial["status"]
    if risk.get("status") in allowed_risk:
        summary["risk_status"] = risk["status"]
    corroboration = risk.get("corroboration")
    if isinstance(corroboration, dict) and corroboration.get("issuer_authenticated") is False:
        summary["ixbrl_context_match"] = corroboration.get("ixbrl_context_match") is True
        summary["numeric_text_match"] = corroboration.get("numeric_text_match") is True
    # Allowlist known internal codes; never surface arbitrary caller-provided text.
    allowed_codes = {
        "EXTERNAL_SOURCE_AUTHENTICITY_UNVERIFIED", "FINANCIAL_CLAIM_CONFLICT",
        "FINANCIAL_CALCULATION_UNAVAILABLE", "RISK_ASSESSMENT_UNAVAILABLE",
        "RISK_REVIEW_MISSING", "SOURCE_SPAN_MISSING", "FINANCIAL_REVIEW_MISSING",
    }
    codes = triage.get("reason_codes")
    summary["reason_codes"] = sorted(set(code for code in codes
        if isinstance(code, str) and code in allowed_codes)) if isinstance(codes, list) else []
    actions = ["VERIFY_PROVIDER_ORIGIN_AND_RIGHTS"]
    if summary["financial_status"] == "conflict":
        actions.append("RECONCILE_FINANCIAL_CLAIM")
    elif summary["financial_status"] != "calculated_unverified":
        actions.append("RECALCULATE_FINANCIAL_EVIDENCE")
    if summary["risk_status"] != "reviewed_unverified":
        actions.append("REVIEW_LOCAL_RISK_FLAGS")
    if not summary["ixbrl_context_match"]:
        actions.append("INSPECT_IXBRL_CONTEXT_AND_UNITS")
    if not summary["numeric_text_match"]:
        actions.append("LOCATE_ORIGINAL_NUMERIC_TEXT")
    summary["review_actions"] = actions
    return summary
