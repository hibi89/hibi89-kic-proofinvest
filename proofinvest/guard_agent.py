"""Offline deterministic simulated investment-review Guard. No source authentication."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


def _decimal(value: Any) -> Decimal | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        number = Decimal(value)
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def evaluate_guard(
    verifications: list[Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
    risk: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return eligibility, never execution authorization.

    Expected verification verdicts are VERIFIED/CONFLICT/UNAVAILABLE.
    Policy is explicitly demonstrative and must be versioned.
    A risk ratio and threshold are exact decimal strings.
    """
    reasons: list[str] = []
    if not isinstance(verifications, list) or not verifications:
        reasons.append("MISSING_VERIFICATIONS")
    elif any(not isinstance(item, Mapping) for item in verifications):
        reasons.append("INVALID_VERIFICATION")
    else:
        statuses = [item.get("status") for item in verifications]
        if any(status == "CONFLICT" for status in statuses):
            reasons.append("CLAIM_CONFLICT")
        if any(status not in ("VERIFIED", "CONFLICT", "UNAVAILABLE") for status in statuses):
            reasons.append("INVALID_VERIFICATION")
        if "UNAVAILABLE" in statuses:
            reasons.append("CLAIM_UNAVAILABLE")
        if any(item.get("source_kind") not in ("SYNTHETIC_FIXTURE", "MANUALLY_CURATED_UNVERIFIED")
               for item in verifications):
            reasons.append("SOURCE_NOT_DEMO_ELIGIBLE")
    if not isinstance(policy, Mapping) or policy.get("mode") != "DEMO_POLICY" or not isinstance(policy.get("version"), str) or not policy["version"].strip():
        reasons.append("INVALID_POLICY")
    threshold = _decimal(policy.get("max_debt_to_equity_pct")) if isinstance(policy, Mapping) else None
    if threshold is None or threshold < 0:
        reasons.append("INVALID_THRESHOLD")
    if not isinstance(risk, Mapping) or risk.get("risk_calculated") is not True:
        reasons.append("RISK_UNAVAILABLE")
    else:
        ratio = _decimal(risk.get("comparison_ratio_pct"))
        if ratio is None or ratio < 0:
            reasons.append("RISK_UNAVAILABLE")
        elif threshold is not None and ratio > threshold:
            reasons.append("DEMO_LIMIT_BREACH")
    if "CLAIM_CONFLICT" in reasons or "DEMO_LIMIT_BREACH" in reasons:
        decision = "REJECT"
    elif reasons:
        decision = "HOLD"
    else:
        decision = "APPROVE"
    return {
        "schema": "proofinvest.guard-decision.v1",
        "decision": decision,
        "meaning": "ELIGIBLE_FOR_HUMAN_REVIEW_ONLY" if decision == "APPROVE" else "NO_AUTHORIZATION",
        "reason_codes": sorted(set(reasons)) or ["DEMO_RULES_PASSED"],
        "policy_version": policy.get("version") if isinstance(policy, Mapping) else None,
        "source_authenticated": False,
        "trade_executed": False,
        "human_approved": False,
    }
