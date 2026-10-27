"""Fail-closed, deterministic review of a PREVIOUS SEC HTTP verification verdict.

This module performs zero network calls, model inference, authentication,
investment advice, writes, or external actions. The upstream SEC adapter may
have attempted one separately authorized HTTP request; this local review
does not upgrade structural arithmetic to authenticated issuer evidence.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

_MODE = "RULE_BASED_SEC_VERDICT_REVIEW_NOT_LLM_AGENT"
_OK_SOURCE = "SEC_HTTPS_CONCEPT_RESPONSE_NOT_INDEPENDENTLY_CERTIFIED"
_FAIL_SOURCE = "SEC_API_NETWORK_ATTEMPT_NOT_FACT_CERTIFICATION"


def review_sec_verdict(verdict: Any) -> dict[str, Any]:
    """Return a bounded PLAN/EVALUATE/DECIDE/REPORT trace or fail closed."""
    state = "blocked"
    reason = "UNTRUSTED_VERDICT_CONTRACT"
    action = "REVIEW_SEC_VERIFICATION_INPUT"
    upstream_http = False

    if isinstance(verdict, Mapping):
        attempted = verdict.get("http_request_attempted")
        upstream_http = attempted is True
        flags_ok = (
            type(attempted) is bool
            and verdict.get("live_api_called") is attempted
            and verdict.get("authenticated_external_source") is False
            and verdict.get("source_rights_verified") is False
            and verdict.get("ai_agent_executed") is False
            and verdict.get("official_contest_submission") is False
        )
        status = verdict.get("status")
        if (
            flags_ok and status == "unavailable"
            and verdict.get("schema") == "proofinvest.sec-concept-http-gate.v1"
            and verdict.get("source_kind") == _FAIL_SOURCE
            and isinstance(verdict.get("reason_code"), str)
            and re.fullmatch(r"[A-Z_]{3,80}", verdict["reason_code"])
            and verdict.get("growth_pct") is None
        ):
            reason, action = "SEC_EVIDENCE_UNAVAILABLE", "CHECK_SOURCE_OR_REQUEST_HUMAN_REVIEW"
        elif (
            flags_ok and attempted is True
            and verdict.get("schema") == "proofinvest.sec-companyfacts-offline.v1"
            and verdict.get("source_kind") == _OK_SOURCE
            and status in ("calculated_unverified", "conflict")
            and verdict.get("risk_calculated") is False
            and isinstance(verdict.get("growth_pct"), str)
            and re.fullmatch(r"[+-]?\\d{1,6}\\.\\d{2}", verdict["growth_pct"])
            and all(isinstance(verdict.get(k), str)
                    and re.fullmatch(r"\\d{1,18}", verdict[k])
                    for k in ("current_usd", "prior_usd"))
        ):
            if status == "conflict":
                reason, action = "SEC_GROWTH_CLAIM_CONFLICT", "REVIEW_DISPUTED_GROWTH_CLAIM"
            else:
                state = "needs_authentication"
                reason, action = (
                    "SEC_STRUCTURAL_RESULT_ONLY", "INDEPENDENT_SEC_SOURCE_AND_RIGHTS_REVIEW"
                )

    trace = [
        {"step": "PLAN", "decision": "REVIEW_PREVIOUS_SEC_VERDICT"},
        {"step": "EVALUATE", "decision": "CHECK_PROVENANCE_AND_SAFETY_FLAGS",
         "network": False},
        {"step": "DECIDE", "decision": reason},
        {"step": "REPORT", "decision": "HUMAN_REVIEW_REQUIRED"},
    ]
    return {
        "schema": "proofinvest.sec-verdict-local-review.v1",
        "mode": _MODE,
        "status": state,
        "reason_code": reason,
        "next_action": action,
        "trace": trace,
        "tool_budget": 0,
        "external_tool_calls": 0,
        "upstream_http_request_attempted": upstream_http,
        "ai_agent_executed": False,
        "authenticated_external_source": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }
