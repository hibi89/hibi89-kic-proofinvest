"""Offline judge replay: reviewed SEC web numbers -> numeric claim -> demo Guard.

Manual SEC rendered-web observations, not original SEC API/HTML bytes.
This is a read-only, deterministic *illustration* of Guard precedence:
CONFLICT -> REJECT; matched numbers with missing Risk -> HOLD.
Never stores an audit, authenticates a source, accesses HTTP or executes a trade.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
import re
from typing import Any

from .guard_agent import evaluate_guard
from .guard_sec_adapter import DEMO_POLICY
from .sec_primary_web_brief import build_web_only_brief

_CLAIM = re.compile(r"-?(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,2})?\Z", re.ASCII)
_UNVERIFIED = (
    "source_authenticated", "original_sec_bytes_verified",
    "rights_verified", "point_in_time_verified",
    "real_sec_three_engine_e2e_verified", "guard_executed",
    "ai_agent_executed", "audit_written", "trade_executed",
    "financial_misconduct_proven", "external_http_called",
)


def review_manual_web_growth_claim(claimed_growth_pct: str | None = None) -> dict[str, Any]:
    """Show three fail-closed demo outcomes without live SEC or persistent audit.

    None = absent claim; explicit percent must be a finite bounded decimal
    with at most two fractional digits (same precision as reviewed figure).
    Guard is actually invoked, but *only* under demo policy with no Risk.
    """
    if claimed_growth_pct is not None:
        if type(claimed_growth_pct) is not str or not _CLAIM.fullmatch(claimed_growth_pct):
            raise ValueError("INVALID_DEMO_GROWTH_CLAIM")
        claimed = Decimal(claimed_growth_pct)
        if not Decimal("-100") <= claimed <= Decimal("999.99"):
            raise ValueError("DEMO_GROWTH_CLAIM_OUT_OF_RANGE")
    else:
        claimed = None

    brief = build_web_only_brief()
    if (type(brief) is not dict
            or brief.get("schema") != "kuodra.sec-web-manual-brief.v1"
            or brief.get("source_basis") != "SEC_RENDERED_WEB_TEXT_MANUALLY_CHECKED_NOT_ORIGINAL"
            or brief.get("manual_cells_checked") != 28
            or brief.get("issuer") != "Apple Inc."
            or brief.get("unit") != "USD_MILLIONS"
            or type(brief.get("unverified")) is not dict
            or set(brief["unverified"]) != set(_UNVERIFIED)
            or any(brief["unverified"][key] is not False for key in _UNVERIFIED)
            or type(brief.get("metrics")) is not list
            or len(brief["metrics"]) != 14):
        raise ValueError("MANUAL_WEB_SOURCE_TRUST_GATE_FAILED")

    # Recalculate from evidence rather than trusting a reported growth field.
    sales = [item for item in brief["metrics"] if item.get("key") == "sales"]
    if len(sales) != 1:
        raise ValueError("MANUAL_WEB_SALES_MISSING_OR_AMBIGUOUS")
    try:
        prior, current = Decimal(sales[0]["fy2024"]), Decimal(sales[0]["fy2025"])
        if prior <= 0 or current < 0:
            raise ValueError("MANUAL_WEB_SALES_INVALID")
        actual = ((current / prior - 1) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )
        if brief["analysis"]["revenue_growth_pct"] != str(actual):
            raise ValueError("MANUAL_WEB_GROWTH_VS_SALES_CONFLICT")
    except (KeyError, TypeError, ArithmeticError):
        raise ValueError("MANUAL_WEB_NUMERIC_CONTRACT_INVALID") from None

    verdict = ("UNAVAILABLE" if claimed is None
               else "VERIFIED" if claimed == actual else "CONFLICT")
    guard = evaluate_guard(
        [{"status": verdict, "source_kind": "MANUALLY_CURATED_UNVERIFIED"}],
        policy=DEMO_POLICY, risk=None,
    )
    decision_expected = "REJECT" if verdict == "CONFLICT" else "HOLD"
    reasons = guard.get("reason_codes")
    if (guard.get("decision") != decision_expected
            or type(reasons) is not list
            or "RISK_UNAVAILABLE" not in reasons
            or (("CLAIM_CONFLICT" in reasons) != (verdict == "CONFLICT"))
            or (("CLAIM_UNAVAILABLE" in reasons) != (verdict == "UNAVAILABLE"))
            or guard.get("source_authenticated") is not False
            or guard.get("trade_executed") is not False
            or guard.get("human_approved") is not False):
        raise ValueError("DEMO_GUARD_POLICY_CONTRACT_CHANGED")

    return {
        "schema": "kuodra.sec-web-claim-guard-demo.v1",
        "mode": "OFFLINE_MANUAL_SEC_WEB_NUMERIC_DEMO_NOT_REAL_SEC_SOURCE",
        "issuer": "Apple Inc.",
        "official_web_view_url": brief["source_url"],
        "financial_basis": brief["source_basis"],
        "manual_cells_checked": 28,
        "claim_growth_pct": str(claimed) if claimed is not None else None,
        "manual_web_growth_pct": str(actual),
        "claim_minus_manual_web_pp": (
            str((claimed - actual).quantize(Decimal("0.01")))
            if claimed is not None else None
        ),
        "numeric_verdict": verdict,
        "numeric_verdict_not_issuer_authentication": True,
        "guard": guard,
        "guard_performed_only_as_demo": True,
        "risk_evidence_present": False,
        "source_authenticated": False,
        "original_sec_bytes_verified": False,
        "market_and_industry_inputs_verified": False,
        "real_sec_a_b_c_end_to_end_verified": False,
        "rights_verified": False,
        "point_in_time_verified": False,
        "real_llm_called": False,
        "external_http_called": False,
        "persistent_audit_written": False,
        "trade_executed": False,
        "financial_misconduct_proven": False,
        "contest_submitted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="No-network SEC-web-manual numeric demo + actual simulated Guard"
    )
    parser.add_argument("--claimed-growth-pct", default=None,
                        help="Illustrative numeric growth assertion, e.g. 30 or 6.43; omit for missing")
    args = parser.parse_args(argv)
    try:
        result = review_manual_web_growth_claim(args.claimed_growth_pct)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        print(json.dumps({
            "schema": "kuodra.sec-web-claim-guard-demo.v1",
            "status": "BLOCKED",
            "reason_code": "MANUAL_WEB_DEMO_INPUT_OR_TRUST_INVALID",
            "source_authenticated": False,
            "trade_executed": False,
            "external_http_called": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
