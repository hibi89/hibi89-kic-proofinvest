"""Bounded offline planner for ProofInvest: route checked evidence to review.

This is deterministic workflow control, NOT a live LLM/AI agent.
No network, browser, external financial ingestion, writes, trade execution,
credential access, or source certification. The supplied facts are untrusted.
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any, Mapping

from .evidence_chain import evaluate_offline_chain


def _blocked(reason_code: str, action: str) -> dict[str, Any]:
    return {
        "schema": "proofinvest.rule-based-offline-controller.v1",
        "mode": "RULE_BASED_OFFLINE_NOT_LLM_AGENT",
        "status": "blocked",
        "reason_code": reason_code,
        "next_action": action,
        "tool_calls": [],
        "trace": [{"step": "PLAN", "decision": reason_code}],
        "evidence_chain": None,
        "tool_budget": 1,
        "external_tool_calls": 0,
        "ai_agent_executed": False,
        "live_api_called": False,
        "authenticated_external_source": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }


def run_offline_controller(
    request: Any, *,
    research_request: Any = None,
    financial_evidence: Any = None,
    risk_facts: Any = None,
) -> dict[str, Any]:
    """Make a bounded tool/next-step decision; execute at most 1 local tool.

    Caller provides the entire source record. Successful arithmetic or
    structure is NOT source authentication or an investment recommendation.
    No retries/fetches are made; missing source is escalated to human review.
    """
    if not isinstance(request, Mapping):
        return _blocked("INVALID_REQUEST", "OBTAIN_STRUCTURED_USER_REQUEST")
    issuer = request.get("issuer_id")
    year = request.get("report_year")
    if (
        not isinstance(issuer, str)
        or re.fullmatch(r"[0-9]{8}", issuer) is None
        or type(year) is not int or not 2015 <= year <= 2100
    ):
        return _blocked("INVALID_TARGET", "OBTAIN_VALID_ISSUER_AND_FISCAL_YEAR")

    claim = request.get("claimed_growth_pct")
    if claim is not None and not isinstance(claim, (str, int, float)):
        return _blocked("INVALID_CLAIM_FORMAT", "OBTAIN_VALID_GROWTH_CLAIM")
    if not isinstance(research_request, Mapping) or not isinstance(financial_evidence, Mapping):
        return _blocked("EVIDENCE_UNAVAILABLE", "OBTAIN_RESEARCH_AND_FINANCIAL_EVIDENCE")
    if (research_request.get("target_id") != issuer
            or financial_evidence.get("corp_code") != issuer
            or financial_evidence.get("report_year") != year):
        return _blocked("ISSUER_YEAR_MISMATCH", "REVIEW_ISSUER_YEAR_AND_SOURCE")

    result = _blocked("CHECK_IN_PROGRESS", "MANUAL_REVIEW")
    result["tool_calls"] = [{
        "tool": "evaluate_offline_chain",
        "source": "CALLER_SUPPLIED_METADATA_ONLY",
        "network": False,
    }]
    result["trace"] = [
        {"step": "PLAN", "decision": "RUN_LOCAL_EVIDENCE_CHAIN"},
        {"step": "EVALUATE", "tool": "evaluate_offline_chain", "network": False},
    ]
    # The only executable tool here. No additional fallback sources, retries,
    # DART callers or model decisions can be inserted from input records.
    chain = evaluate_offline_chain(
        research_request=research_request,
        financial_evidence=financial_evidence,
        claimed_growth_pct=claim,
        risk_facts=risk_facts,
    )
    result["evidence_chain"] = chain
    verification = chain.get("verification") or {}
    if not chain.get("trace_linked"):
        status, reason, next_action = (
            "blocked", "UNLINKED_PROVENANCE", "REVIEW_PRIMARY_SOURCE_AND_CITATION"
        )
    elif verification.get("state") == "conflict":
        status, reason, next_action = (
            "blocked", "GROWTH_CLAIM_CONFLICT", "REVIEW_CONFLICTING_GROWTH_CLAIM"
        )
    elif verification.get("state") != "verified":
        status, reason, next_action = (
            "blocked", "CLAIM_UNAVAILABLE", "OBTAIN_VALID_GROWTH_CLAIM"
        )
    elif chain.get("risk", {}).get("risk_calculated") is not True:
        status, reason, next_action = (
            "needs_evidence", "RISK_FACTS_NOT_ELIGIBLE",
            "OBTAIN_CITABLE_LIABILITIES_AND_EQUITY",
        )
    else:
        # Even fully linked structural calculations are NOT authenticated.
        status, reason, next_action = (
            "needs_authentication", "STRUCTURAL_RESULT_ONLY",
            "INDEPENDENT_SOURCE_AND_RIGHTS_REVIEW",
        )
    result["status"] = status
    result["reason_code"] = reason
    result["next_action"] = next_action
    result["trace"].append({"step": "DECIDE", "decision": reason})
    result["trace"].append({"step": "REPORT", "decision": "HUMAN_REVIEW_REQUIRED"})
    return result


def run_issuer_manual_demo(claim: str = "16.20") -> dict[str, Any]:
    """Use byte-pinned previously reviewed issuer JSON; never re-open its PDF."""
    from .manual_case_demo import make_research_request, read_reviewed_evidence
    evidence = read_reviewed_evidence()
    return run_offline_controller(
        {"issuer_id": evidence["corp_code"], "report_year": evidence["report_year"],
         "claimed_growth_pct": claim},
        research_request=make_research_request(evidence),
        financial_evidence=evidence,
        risk_facts=None,  # Do not fabricate balance-sheet evidence.
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rule-based, offline bounded flow; NOT a live AI Agent or DART verification"
    )
    parser.add_argument("--claim", default="16.20", help="Growth claim to compare with manual record")
    args = parser.parse_args()
    print(json.dumps(run_issuer_manual_demo(args.claim), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
