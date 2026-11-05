"""One user-entered US ticker -> genuine pinned issuer-origin financial review.

Only NVDA and DELL have independently observed first-party source bytes.
This is neither an arbitrary-ticker SEC API nor licensed stock/NDX/peer data.
Caller receives only bounded, derived figures and immutable source digests.
No new HTTP, source writes, model calls, investments or provider permission.
"""
from __future__ import annotations

from typing import Any

_SCHEMA = "kuodra.p218-real-issuer-ticker-review.v1"
_VINTAGE = "2026-11-05"
_SUPPORTED = ("NVDA", "DELL")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "source_authenticated_by_sec": False,
        "source_rights_verified": False, "market_ndx_peer_licensed": False,
        "engine_a_complete": False, "engine_c_complete": False,
        "full_abc_complete": False,
        "llm_invoked": False, "network_requests": 0,
        "guard_policy_preview": "HOLD", "guard_executed": False,
        "investment_recommendation": False, "trade_executed": False,
    }


def _review_nvda() -> dict[str, Any]:
    from .nvidia_real_issuer_review import (
        actual_nvidia_issuer_receipt, review_nvidia_actual_release,
    )
    receipt = actual_nvidia_issuer_receipt()
    r = review_nvidia_actual_release(as_of=_VINTAGE, receipt=receipt)
    e = r.get("evidence")
    if (r.get("status") != "REAL_NVDA_FY2026_2025_ISSUER_GAAP_REVIEW_LIMITED"
            or r.get("issuer_original_publisher_seen") is not True
            or r.get("sec_original_identical") is not False
            or r.get("commercial_ai_rights_verified") is not False
            or r.get("full_abc_ready") is not False
            or r.get("guard_policy_preview") != "HOLD"
            or r.get("trade_executed") is not False
            or type(e) is not dict
            or e.get("ticker") != "NVDA"
            or e.get("cik") != "0001045810"
            or e.get("issuer_source_sha256") != receipt.get("source_sha256")
            or e.get("fiscal_2026_end") != "2026-01-25"
            or e.get("fiscal_2025_end") != "2025-01-26"
            or e.get("release_unaudited") is not True
            or e.get("amount_unit") != "USD_millions"):
        return _blocked("NVDA_ORIGINAL_REVIEW_CONTRACT_INVALID")
    m = e.get("metrics")
    if type(m) is not dict or any(m.get(key) != expected for key, expected in {
            "revenue_growth_pct": "65.47",
            "cfo_to_net_income_2026": "0.8555",
            "ar_growth_minus_revenue_pp": "1.30",
            "inventory_growth_minus_revenue_pp": "46.86",
    }.items()):
        return _blocked("NVDA_REAL_GAAP_METRIC_REPLAY_FAILED")
    return {
        **_blocked("PINNED_FIRST_PARTY_ORIGIN_ONLY_RIGHTS_UNKNOWN"),
        "status": "REAL_ISSUER_HUMAN_REVIEW_ONLY",
        "ticker": "NVDA", "cik": "0001045810",
        "review_as_of": _VINTAGE, "fiscal_latest_end": e["fiscal_2026_end"],
        "fiscal_prior_end": e["fiscal_2025_end"],
        "source_kind": "FIRST_PARTY_UNAUDITED_RELEASE",
        "source_sha256": e["issuer_source_sha256"],
        "source_url": e["issuer_source_url"],
        "source_ci_run": e["source_ci_run"],
        "publisher_original_observed": True,
        "issuer_revenue_growth_pct": m["revenue_growth_pct"],
        "cashflow_to_net_income_ratio": m["cfo_to_net_income_2026"],
        "receivables_minus_revenue_growth_pp": m["ar_growth_minus_revenue_pp"],
        "inventory_minus_revenue_growth_pp": m["inventory_growth_minus_revenue_pp"],
        "financial_review": "ISSUER_ENGINE_B_NUMERICAL_SCREEN_UNVERIFIED",
        "market_price_status": "UNAVAILABLE",
        "ndx_benchmark_status": "UNAVAILABLE",
        "peer_evidence_status": "UNAVAILABLE",
    }


def _review_dell() -> dict[str, Any]:
    from .dell_2026_publisher_evidence import (
        actual_p195_source_receipt, review_verified_dell_first_party_raw_evidence,
    )
    from .dell_working_capital_review import (
        actual_working_capital_receipt, review_real_working_capital,
    )
    from .dell_regulator_index_match import reviewed_real_dell_regulator_issuer_evidence
    regulator = reviewed_real_dell_regulator_issuer_evidence()
    sec = regulator.get("evidence")
    if (regulator.get("status") !=
                "INDEPENDENT_SEC_FILING_INDEX_MATCHED_WITH_LIVE_ISSUER_XBRL"
            or regulator.get("independent_regulator_index_metadata_reconciled") is not True
            or regulator.get("sec_original_bytes_obtained") is not False
            or regulator.get("raw_sec_edgar_original_authenticated") is not False
            or regulator.get("commercial_and_model_processing_rights_proven") is not False
            or type(sec) is not dict
            or sec.get("ticker") != "DELL"
            or sec.get("cik") != "0001571996"
            or sec.get("accession") != "0001571996-26-000008"
            or sec.get("report_end") != "2026-01-30"):
        return _blocked("DELL_SEC_INDEX_ISSUER_IDENTITY_UNAVAILABLE")
    report = review_verified_dell_first_party_raw_evidence(
        as_of=_VINTAGE, receipt=actual_p195_source_receipt())
    capital = review_real_working_capital(
        reviewed_as_of=_VINTAGE, receipt=actual_working_capital_receipt())
    e, w = report.get("evidence"), capital.get("evidence")
    if (report.get("status") !=
                "DELL_REAL_FIRST_PARTY_ORIGINAL_NUMERIC_REVIEW_READY_LIMITED"
            or report.get("publisher_https_original_seen") is not True
            or report.get("sec_edgar_original_byte_equivalence_verified") is not False
            or report.get("source_rights_verified") is not False
            or report.get("guard_policy_preview") != "HOLD"
            or report.get("trade_executed") is not False
            or capital.get("status") != "P207_ACTUAL_ISSUER_WORKING_CAPITAL_REVIEW_LIMITED"
            or capital.get("real_issuer_working_capital_source_seen") is not True
            or capital.get("rights_verified") is not False
            or capital.get("sec_original_identical") is not False
            or capital.get("full_abc_ready") is not False
            or capital.get("guard_policy_preview") != "HOLD"
            or capital.get("trade_executed") is not False
            or type(e) is not dict or type(w) is not dict
            or e.get("ticker") != "DELL"
            or e.get("fiscal_year_end") != "2026-01-30"
            or e.get("prior_year_end") != "2025-01-31"
            or e.get("raw_original_bytes_sha256") != sec.get("publisher_sha256")
            or sec.get("publisher_official_url") != e.get("source_url")
            or e.get("raw_original_bytes_sha256") !=
                actual_p195_source_receipt().get("source_original_sha256")
            or w.get("source_sha256") != actual_working_capital_receipt().get("source_sha256")
            or w.get("source_is_unaudited") is not True):
        return _blocked("DELL_CROSS_DOCUMENT_REVIEW_CONTRACT_INVALID")
    rows = w.get("asset_rows")
    if (type(rows) is not dict
            or any(type(rows.get(k)) is not dict for k in
                   ("trade_receivables", "inventories"))
            or e.get("revenue_yoy_pct") != w.get("revenue_growth_pct")
            or e.get("revenue_yoy_pct") != "18.80"
            or e.get("cash_flow_to_net_income_ratio") != "1.8843"
            or rows["trade_receivables"].get("growth_minus_revenue_pp") != "51.96"
            or rows["inventories"].get("growth_minus_revenue_pp") != "36.60"):
        return _blocked("DELL_REAL_GAAP_FINANCIAL_REPLAY_FAILED")
    return {
        **_blocked("PINNED_FIRST_PARTY_ORIGIN_ONLY_RIGHTS_UNKNOWN"),
        "status": "REAL_ISSUER_HUMAN_REVIEW_ONLY",
        "ticker": "DELL", "cik": sec["cik"],
        "filing_accession": sec["accession"],
        "sec_index_metadata_reconciled": True,
        "sec_index_url": sec["regulator_index_url"],
        "review_as_of": _VINTAGE, "fiscal_latest_end": e["fiscal_year_end"],
        "fiscal_prior_end": e["prior_year_end"],
        "source_kind": "FIRST_PARTY_10K_AND_UNAUDITED_RELEASE",
        "source_sha256": e["raw_original_bytes_sha256"],
        "source_url": e["source_url"],
        "source_ci_run": e["actual_source_ci_run"],
        "supplementary_source_sha256": w["source_sha256"],
        "supplementary_source_url": w["source_url"],
        "supplementary_source_ci_run": w["actual_one_shot_ci"],
        "publisher_original_observed": True,
        "issuer_revenue_growth_pct": e["revenue_yoy_pct"],
        "cashflow_to_net_income_ratio": e["cash_flow_to_net_income_ratio"],
        "receivables_minus_revenue_growth_pp":
            rows["trade_receivables"]["growth_minus_revenue_pp"],
        "inventory_minus_revenue_growth_pp":
            rows["inventories"]["growth_minus_revenue_pp"],
        "financial_review": "ISSUER_ENGINE_B_NUMERICAL_SCREEN_UNVERIFIED",
        "market_price_status": "UNAVAILABLE",
        "ndx_benchmark_status": "UNAVAILABLE",
        "peer_evidence_status": "UNAVAILABLE",
    }


def review_supported_real_ticker(ticker: Any, *, as_of: str = _VINTAGE) -> dict[str, Any]:
    """Offline real-issuer query, never claim arbitrary ticker/data coverage."""
    if type(ticker) is not str or type(as_of) is not str:
        return _blocked("TICKER_OR_REVIEW_VINTAGE_INVALID")
    ticker = ticker.strip().upper()
    if not ticker or len(ticker) > 12 or any(
            not c.isascii() or not c.isalnum() for c in ticker):
        return _blocked("TICKER_SYNTAX_INVALID")
    if ticker not in _SUPPORTED:
        return _blocked("ISSUER_ORIGINAL_NOT_YET_REVIEWED")
    if as_of != _VINTAGE:
        return _blocked("SOURCE_RECEIPT_REVIEW_VINTAGE_NOT_ATTESTED")
    try:
        result = _review_nvda() if ticker == "NVDA" else _review_dell()
        if result.get("status") != "REAL_ISSUER_HUMAN_REVIEW_ONLY":
            return result
        # Never promote an issuer-origin receipt to an SEC or licensed feed.
        if (result.get("publisher_original_observed") is not True
                or any(result.get(k) is not False for k in (
                    "source_authenticated_by_sec", "source_rights_verified",
                    "market_ndx_peer_licensed", "full_abc_complete",
                    "engine_a_complete", "engine_c_complete", "trade_executed",
                    "llm_invoked", "investment_recommendation"))
                or result.get("guard_policy_preview") != "HOLD"
                or result.get("network_requests") != 0):
            return _blocked("SOURCE_RIGHTS_GUARD_CONTRACT_INVALID")
        return result
    except (ValueError, TypeError, KeyError, OSError, OverflowError, ArithmeticError):
        return _blocked("FIRST_PARTY_RECEIPT_REPLAY_UNAVAILABLE")
