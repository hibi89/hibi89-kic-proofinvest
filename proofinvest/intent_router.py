"""Deterministic offline question-to-tool routing for KIC ProofInvest MVP.

NOT an LLM planner, an autonomous research agent, source authentication, or
investment advice. Only pinned, offline sources are admitted. No network,
external API, credentials, persistent DB writes, trading, or retries.
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any

from .guard_sec_adapter import evaluate_sec_guard
from .sec_companyfacts import run_curated_apple_demo

_EXPLICIT_SOURCE = ("원문", "근거", "출처", "evidence", "filing", "source")
_GROWTH = ("성장률", "매출", "revenue", "growth", "sales")
_RISK = ("위험", "리스크", "부채", "debt", "risk", "liabilities")
_SOURCE = ("공시", "10-k", "10k", "sec")
_DATE = re.compile(r"(?<!\d)(20\d\d-\d\d-\d\d)(?!\d)")
_CLAIM = re.compile(r"(?<![\d.])([+]?\d{1,5}(?:\.\d{1,4})?)\s*%")
_OTHER_ISSUERS = ("삼성", "samsung", "tesla", "테슬라", "마이크로소프트", "microsoft")
_MODE = "DETERMINISTIC_OFFLINE_ROUTER_NOT_LLM_AGENT"


def _result(status: str, reason: str, question: str | None = None) -> dict[str, Any]:
    return {
        "schema": "proofinvest.intent-router.v1",
        "mode": _MODE,
        "status": status,
        "reason_code": reason,
        "question_to_user": question,
        "selected_intent": None,
        "selected_tool": None,
        "tool_calls": [],
        "trace": [{"step": "PLAN", "decision": reason}],
        "evidence": None,
        "guard": None,
        "tool_budget": 2,
        "external_tool_calls": 0,
        "ai_agent_executed": False,
        "authenticated_external_source": False,
        "source_rights_verified": False,
        "live_api_called": False,
        "trade_executed": False,
        "official_contest_submission": False,
    }


def route_question(question: Any) -> dict[str, Any]:
    """Classify one Korean/English question and execute bounded local tools."""
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 240:
        return _result("blocked", "INVALID_QUESTION")
    if any(ord(c) < 32 or ord(c) == 127 for c in question):
        return _result("blocked", "INVALID_CONTROL_CHAR")
    q = question.casefold()
    growth = any(term in q for term in _GROWTH)
    risk = any(term in q for term in _RISK)
    source = any(term in q for term in _EXPLICIT_SOURCE)
    if not (growth or risk or source):
        source = any(term in q for term in _SOURCE)
    intents = [name for name, enabled in (
        ("GROWTH_CHECK", growth), ("RISK_CHECK", risk), ("SOURCE_REVIEW", source)
    ) if enabled]
    if len(intents) != 1:
        return _result(
            "needs_clarification", "AMBIGUOUS_OR_MISSING_INTENT",
            "매출 성장률, 공시 출처, 위험 지표 중 무엇을 확인할까요?",
        )
    if any(name in q for name in _OTHER_ISSUERS):
        return _result("blocked", "UNSUPPORTED_ISSUER_ONLY_APPLE_SAMPLE")
    if not any(name in q for name in ("apple", "애플")):
        return _result(
            "needs_clarification", "MISSING_ISSUER",
            "오프라인 예제의 Apple FY2025 자료를 검토할까요?",
        )
    if re.search(r"(?<!\d)20(?:1\d|2[0-4]|2[6-9])(?=\D|$)", q):
        return _result("blocked", "UNSUPPORTED_FISCAL_YEAR_ONLY_FY2025")
    matches = _DATE.findall(q)
    if len(matches) > 1:
        return _result(
            "needs_clarification", "MULTIPLE_AS_OF_DATES",
            "기준일을 YYYY-MM-DD 하나로 지정해 주세요.",
        )
    as_of = matches[0] if matches else "2025-11-01"
    intent = intents[0]
    claim: str | None = None
    if intent == "GROWTH_CHECK":
        claims = _CLAIM.findall(q)
        if len(claims) > 1:
            return _result(
                "needs_clarification", "MULTIPLE_GROWTH_CLAIMS",
                "검산할 성장률 주장 하나를 %로 입력해 주세요.",
            )
        claim = claims[0] if claims else None

    result = _result("completed", "STRUCTURAL_NUMERIC_ONLY")
    result["selected_intent"] = intent
    result["trace"] = [
        {"step": "PLAN", "decision": "SINGLE_INTENT_SELECTED"},
        {"step": "SELECT", "decision": intent},
    ]

    if intent == "SOURCE_REVIEW":
        # An index URL in a manually curated excerpt does NOT prove that
        # the original SEC response was fetched or authenticated.
        verdict = run_curated_apple_demo(as_of=as_of)
        result["selected_tool"] = "run_curated_apple_demo"
        result["tool_calls"] = ["run_curated_apple_demo"]
        result["status"] = "needs_authentication"
        result["reason_code"] = "MANUAL_EXCERPT_NOT_PRIMARY_SEC_BYTES"
        result["evidence"] = {
            "source_kind": verdict["demonstration_source"],
            "accession": verdict.get("accession"),
            "filing_index_url_not_authenticated": verdict.get("sec_filing_index"),
            "as_of": as_of,
        }
    elif intent == "GROWTH_CHECK":
        verdict = run_curated_apple_demo(
            as_of=as_of, claimed_growth_pct=claim
        )
        mapped = evaluate_sec_guard(verdict)
        result["selected_tool"] = "run_curated_apple_demo + evaluate_sec_guard"
        result["tool_calls"] = [
            "run_curated_apple_demo", "evaluate_sec_guard"
        ]
        result["evidence"] = {
            "source_kind": verdict["demonstration_source"],
            "status": verdict["status"],
            "growth_pct": verdict["growth_pct"],
            "reason_code": verdict["reason_code"],
            "as_of": as_of,
            "claim_pct": claim,
        }
        result["guard"] = mapped["guard"]
        result["status"] = (
            "blocked" if mapped["guard"]["decision"] == "REJECT"
            else "needs_evidence"
        )
        result["reason_code"] = (
            "GROWTH_CLAIM_CONFLICT"
            if verdict["status"] == "conflict"
            else "MISSING_RISK_OR_SOURCE_PROOF"
        )
    else:
        # Never fabricate audited liabilities/equity from a revenue figure.
        mapped = evaluate_sec_guard({"status": "unavailable"})
        result["selected_tool"] = "evaluate_sec_guard"
        result["tool_calls"] = ["evaluate_sec_guard"]
        result["guard"] = mapped["guard"]
        result["status"] = "needs_evidence"
        result["reason_code"] = "VERIFIED_LIABILITIES_AND_EQUITY_MISSING"
        result["evidence"] = {"risk_calculated": False, "ratio_pct": None}

    result["trace"] += [
        {"step": "EXECUTE", "decision": result["selected_tool"]},
        {"step": "GUARD", "decision": (
            result["guard"]["decision"] if result["guard"] else "NOT_ELIGIBLE"
        )},
        {"step": "REPORT", "decision": result["reason_code"]},
    ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pinned offline deterministic tool router, NOT a live AI agent"
    )
    parser.add_argument("--question", required=True)
    args = parser.parse_args()
    print(json.dumps(route_question(args.question), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
