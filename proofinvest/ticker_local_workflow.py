"""P122: bounded execution trace for the existing four-file ticker workflow.

This genuinely invokes the existing local computations in order. It is NOT
a model planner, a source-authentication service or a trading/audit agent.
No network retry, DB write, original-file persistence or publisher rights.
"""
from __future__ import annotations

from typing import Any


def _empty(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.local-ticker-workflow.v1",
        "mode": "DETERMINISTIC_LOCAL_TOOLS_NOT_LLM_AGENT",
        "status": "BLOCKED",
        "reason_code": reason,
        "next_action": "REVIEW_LOCAL_INPUTS",
        "tool_budget": 7,
        "tool_calls_executed": 0,
        "tool_trace": [],
        "receipt": None,
        "revenue": None,
        "original": None,
        "supplementary": None,
        "engine_b": None,
        "report": None,
        "network_requests": 0,
        "guard_executed": False,
        "audit_written": False,
        "human_approved": False,
        "trade_executed": False,
        "ai_agent_executed": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }


def run_local_ticker_workflow(
    *, ticker: str, as_of: str, sources: dict[str, bytes],
    market_json: bytes | None = None,
    industry_json: bytes | None = None,
) -> dict[str, Any]:
    """Execute bounded stage calls, stop at first ineligible evidence result.

    Source bytes stay with caller. The returned record has metadata, derived
    results and redacted report only. Verification replays exact original
    local bytes; a successful replay is NOT an SEC publisher attestation.
    """
    out = _empty("LOCAL_INPUTS_REQUIRED")
    if type(sources) is not dict or set(sources) != {
            "ticker_map", "submissions", "companyfacts", "original_10k"}:
        return out
    if (any(type(raw) is not bytes for raw in sources.values())
            or (market_json is not None and type(market_json) is not bytes)
            or (industry_json is not None and type(industry_json) is not bytes)):
        return out

    def step(name: str, status: str, *, accepted: bool) -> None:
        out["tool_trace"].append({
            "step": len(out["tool_trace"]) + 1, "tool": name,
            "status": status, "accepted": accepted,
            "network_requests": 0,
        })
        out["tool_calls_executed"] += 1

    try:
        from .ticker_local_sources import prepare_local_ticker_sources
        from .ticker_sec_financial_bridge import inspect_collected_annual_revenue
        from .ticker_sec_original_guard_preview import inspect_original_guard_preview
        from .ticker_market_industry_bridge import evaluate_ticker_a_c
        from .ticker_engine_b_bridge import inspect_ticker_engine_b
        from .ticker_local_report import make_local_report, verify_local_report

        receipt = prepare_local_ticker_sources(
            ticker=ticker, as_of=as_of, sources=sources)
        ok = receipt.get("status") == "local_four_sources_unverified"
        step("prepare_local_ticker_sources", receipt.get("status", "UNAVAILABLE"),
             accepted=ok)
        if not ok:
            out.update(reason_code="SOURCE_IDENTITY_OR_FILING_UNAVAILABLE",
                       next_action="REVIEW_FOUR_SOURCE_IDENTITY_AND_PERIOD")
            return out
        out["receipt"] = receipt

        revenue = inspect_collected_annual_revenue(receipt, sources)
        ok = revenue.get("status") == "REVENUE_CALCULATED_UNVERIFIED"
        step("inspect_collected_annual_revenue", revenue.get("status", "UNAVAILABLE"),
             accepted=ok)
        if not ok:
            out.update(reason_code="FISCAL_REVENUE_UNAVAILABLE",
                       next_action="REVIEW_FINANCIAL_SOURCE_AND_UNITS")
            return out
        out["revenue"] = revenue

        original = inspect_original_guard_preview(
            receipt, sources, expected_revenue=revenue)
        guard = original.get("guard_preview")
        # A Guard REJECT for unreadable/missing original is a safe policy
        # decision, but not sufficient evidence to generate a source report.
        # Explicit original identity conflict remains reviewable with REJECT.
        ok = (original.get("status") in (
            "ORIGINAL_CONTEXT_MATCH_UNVERIFIED",
            "ORIGINAL_SELF_CLAIM_CONFLICT",
        ) and type(guard) is dict
            and guard.get("decision") in ("HOLD", "REJECT")
            and guard.get("trade_executed") is False
            and guard.get("human_approved") is False
            and original.get("guard_executed") is False
            and original.get("audit_written") is False)
        step("inspect_original_guard_preview",
             original.get("status", "UNAVAILABLE"), accepted=ok)
        if not ok:
            out.update(reason_code="ORIGINAL_GUARD_REVIEW_UNAVAILABLE",
                       next_action="REVIEW_ORIGINAL_AND_GUARD_CONTEXT")
            return out
        out["original"] = original

        engine_b = inspect_ticker_engine_b(
            receipt, sources, expected_revenue=revenue,
            expected_original=original,
        )
        b_ok = (
            engine_b.get("status") in ("REVIEWED_UNVERIFIED", "UNAVAILABLE")
            and engine_b.get("source_authenticated") is False
            and engine_b.get("source_rights_verified") is False
            and engine_b.get("accounting_fraud_proven") is False
            and engine_b.get("guard_executed") is False
            and engine_b.get("trade_executed") is False
            and engine_b.get("companyfacts_sha256") ==
                receipt["source_sha256"]["companyfacts"]
        )
        step("inspect_ticker_engine_b", engine_b.get("status", "UNAVAILABLE"),
             accepted=b_ok)
        if not b_ok:
            out.update(reason_code="ENGINE_B_TRUST_CONTRACT_INVALID",
                       next_action="REVIEW_CASHFLOW_SOURCE_AND_PERIOD")
            return out
        out["engine_b"] = engine_b

        supplementary = evaluate_ticker_a_c(
            receipt, sources, market_json=market_json,
            industry_json=industry_json)
        ok = (supplementary.get("source_authenticated") is False
              and supplementary.get("source_rights_verified") is False
              and supplementary.get("trade_executed") is False
              and supplementary.get("guard_executed") is False
              and type(supplementary.get("engine_a")) is dict
              and type(supplementary.get("engine_c")) is dict)
        step("evaluate_ticker_a_c",
             supplementary.get("status", "UNAVAILABLE"), accepted=ok)
        if not ok:
            out.update(reason_code="OPTIONAL_ENGINE_CONTRACT_INVALID",
                       next_action="REVIEW_MARKET_AND_PEER_INPUTS")
            return out
        out["supplementary"] = supplementary

        report = make_local_report(
            receipt, revenue, original, supplementary, engine_b=engine_b)
        step("make_local_report", report["status"], accepted=True)

        verification = verify_local_report(
            report, sources=sources, market_json=market_json,
            industry_json=industry_json)
        replay_ok = verification.get("status") == "PASS"
        step("verify_local_report", verification.get("reason_code", "UNAVAILABLE"),
             accepted=replay_ok)
        if not replay_ok:
            out.update(reason_code="INDEPENDENT_REPLAY_FAILED",
                       next_action="REVIEW_LOCAL_SOURCE_INTEGRITY")
            return out
        out.update(
            report=report, status="READY_FOR_HUMAN_REVIEW_UNVERIFIED",
            reason_code="LOCAL_REPLAY_PASS_EXTERNAL_RIGHTS_NOT_VERIFIED",
            next_action="INDEPENDENT_SOURCE_AND_LICENSE_REVIEW",
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError,
            RecursionError, UnicodeError):
        out.update(status="BLOCKED", reason_code="LOCAL_WORKFLOW_INVALID",
                   next_action="REVIEW_LOCAL_INPUTS", report=None)
    return out
