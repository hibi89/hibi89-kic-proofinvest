"""P104 single-ticker bounded optional Engine A/C evidence join.

Market/index and industry/peer providers are NOT connected yet. Optional
caller-provided bytes may pass the existing strict source-bound math engines.
This never fetches prices, promises rights, persists input, computes risk
scores, changes Guard, or authenticates historical market data.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any

from .industry_vision import (
    MAX_UPLOAD_BYTES as INDUSTRY_LIMIT, analyze_industry_vision,
    parse_industry_vision_json,
)
from .market_reality import (
    MAX_UPLOAD_BYTES as MARKET_LIMIT, analyze_market_reality,
    parse_market_reality_json,
)
from .ticker_sec_financial_bridge import inspect_collected_annual_revenue
from .ticker_sec_original_guard_preview import inspect_original_guard_preview


def _slot(reason: str) -> dict:
    return {"status": "UNAVAILABLE", "reason_code": reason,
            "input_sha256": None, "source_authenticated": False,
            "provider_rights_verified": False}


def _output() -> dict:
    return {
        "schema": "kuodra.single-ticker-a-c-source-join.v1",
        "status": "UNAVAILABLE",
        "reason_code": "P101_P102_EVIDENCE_REQUIRED",
        "ticker": None, "issuer_cik": None, "as_of": None,
        "engine_a": _slot("MARKET_PROVIDER_NOT_CONNECTED"),
        "engine_c": _slot("INDUSTRY_PROVIDER_NOT_CONNECTED"),
        "source_authenticated": False, "source_rights_verified": False,
        "market_data_vintage_authenticated": False,
        "industry_outlook_verified": False, "all_three_engines_ready": False,
        "guard_executed": False, "audit_written": False,
        "ai_interpretation_ready": False, "trade_executed": False,
    }


def evaluate_ticker_a_c(
    sec_receipt: dict, sec_sources: dict[str, bytes] | None,
    *, market_json: bytes | None = None, industry_json: bytes | None = None,
) -> dict[str, Any]:
    """Join exact same-10-K SEC evidence with independent optional A/C inputs.

    Input bytes are provided by a caller; the producer, license and data
    vintage are NOT trusted. No HTTP at any point in this function.
    """
    result = _output()
    if market_json is None and industry_json is None:
        result["reason_code"] = "A_C_PROVIDER_NOT_CONNECTED"
        return result
    revenue = inspect_collected_annual_revenue(sec_receipt, sec_sources)
    if revenue.get("status") != "REVENUE_CALCULATED_UNVERIFIED":
        result["reason_code"] = "SEC_FISCAL_EVIDENCE_UNAVAILABLE"
        return result
    preview = inspect_original_guard_preview(
        sec_receipt, sec_sources, expected_revenue=revenue)
    guard = preview.get("guard_preview")
    if (preview.get("status") != "ORIGINAL_CONTEXT_MATCH_UNVERIFIED"
            or type(guard) is not dict
            or guard.get("decision") != "HOLD"
            or preview.get("source_authenticated") is not False
            or preview.get("guard_executed") is not False
            or preview.get("audit_written") is not False):
        result["reason_code"] = "SEC_ORIGINAL_CONTEXT_OR_GUARD_NOT_ELIGIBLE"
        return result
    cik, as_of, ticker = (
        revenue["issuer_cik"], revenue["as_of"], revenue["ticker"])
    result.update(status="PARTIAL_SOURCE_ANALYSIS_UNVERIFIED",
                  reason_code="A_C_INPUTS_ARE_UNAUTHENTICATED",
                  ticker=ticker, issuer_cik=cik, as_of=as_of)

    if market_json is not None:
        try:
            market = parse_market_reality_json(market_json)
            # The engine validates CIK and as-of, but not that the security
            # symbol belongs to this exact ticker; add that binding here.
            if market.get("symbol") != ticker:
                raise ValueError("MARKET_TICKER_MISMATCH")
            a = analyze_market_reality(
                market, expected_issuer_cik=cik,
                analysis_as_of=as_of, sec_review=None,
                uploaded_sha256=sha256(market_json).hexdigest(),
            )
            if (a.get("status") not in
                    ("REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE")
                    or a.get("source_authenticated") is not False
                    or a.get("audit_included") is not False
                    or a.get("market_bubble_proven") is not False
                    or a.get("guard_policy_modified") is not False
                    or a.get("trade_signal") is not False
                    or a.get("sec_revenue_context") is not None):
                raise ValueError("MARKET_TRUST_CONTRACT_INVALID")
            # A filing published mid-window is not usable as the context
            # for earlier price returns. Entire source interval must follow
            # filing date, as exact release times are not authenticated.
            if date.fromisoformat(a["period_start"]) <= date.fromisoformat(
                    revenue["filing_date"]):
                raise ValueError("PRICE_WINDOW_NOT_AFTER_SEC_FILING")
            result["engine_a"] = {
                "status": a["status"],
                "reason_code": "PRICE_OLS_DESCRIPTIVE_ONLY",
                "input_sha256": sha256(market_json).hexdigest(),
                "benchmark": a["benchmark"], "return_basis": a["return_basis"],
                "period_start": a["period_start"], "period_end": a["period_end"],
                "observation_count": a["observation_count"],
                "security_return_pct": a["security_return_pct"],
                "benchmark_return_pct": a["benchmark_return_pct"],
                "beta": a["beta"], "regression_intercept_daily_pct":
                a["regression_intercept_daily_pct"], "r_squared": a["r_squared"],
                "source_authenticated": False,
                "provider_rights_verified": False,
            }
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
            result["engine_a"] = _slot("MARKET_SOURCE_OR_PERIOD_NOT_COMPATIBLE")

    if industry_json is not None:
        try:
            industry = analyze_industry_vision(
                parse_industry_vision_json(industry_json),
                expected_issuer_cik=cik, analysis_as_of=as_of,
            )
            periods = industry["periods"]
            target = industry["target"]
            if (industry.get("status") not in
                    ("OBSERVED_COMPARISON_UNVERIFIED", "INSUFFICIENT_EVIDENCE")
                    or periods["prior_end"] != revenue["prior_end"]
                    or periods["current_end"] != revenue["current_end"]
                    or target["cik"] != cik
                    or Decimal(target["prior_revenue_usd"]) != Decimal(revenue["prior_usd"])
                    or Decimal(target["current_revenue_usd"]) != Decimal(revenue["current_usd"])
                    or Decimal(target["growth_pct_reported_input"]) !=
                    Decimal(revenue["growth_pct"])
                    or industry.get("source_authenticated") is not False
                    or industry.get("industry_outlook_verified") is not False
                    or industry.get("guard_decision_changed") is not False
                    or industry.get("trade_signal") is not False):
                raise ValueError("INDUSTRY_SEC_FISCAL_COHORT_MISMATCH")
            source_by_id = {s["id"]: s for s in industry["sources"]}
            for ref in target["source_ids"]:
                source = source_by_id[ref]
                if (source["sha256"] != revenue["companyfacts_sha256"]
                        or source["published_at"] < revenue["filing_date"]):
                    raise ValueError("INDUSTRY_TARGET_SOURCE_NOT_SEC_PINNED")
            result["engine_c"] = {
                "status": industry["status"],
                "reason_code": "PEER_AND_SECTOR_REPORTED_INPUT_UNVERIFIED",
                "input_sha256": sha256(industry_json).hexdigest(),
                "industry": industry["industry"],
                "industry_measure": industry["industry_series"]["kind"],
                "peer_count": len(industry["peers"]),
                "peer_median_growth_pct": industry["peer_median_growth_pct"],
                "growth_gap_to_industry_pp":
                industry["growth_gap_to_industry_pp"],
                "growth_gap_to_peer_median_pp":
                industry["growth_gap_to_peer_median_pp"],
                "source_authenticated": False,
                "provider_rights_verified": False,
            }
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError,
                InvalidOperation):
            result["engine_c"] = _slot("INDUSTRY_SOURCE_OR_FISCAL_COHORT_NOT_COMPATIBLE")
    return result
