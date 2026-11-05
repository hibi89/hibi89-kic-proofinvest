"""P223: Two independently published SEC-form issuer filing peer references for NVDA.

AMD bridge is reused, INTC audited 2025 10-K and a separate public IR
earnings release are separately manually checked. No raw INTC HTML source
bytes were obtained in code, and issuer SHA cannot authenticate a market
provider or grant commercial/LLM rights. This is *limited cross-company
descriptive growth*, not a representative sector census or complete Engine C.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .amd_10k_peer_bridge import compare_nvda_amd_audited_10k_peer
from .real_issuer_ticker_review import review_supported_real_ticker

_AS_OF = "2026-11-05"
_INTEL_10K = (
    "https://www.intc.com/filings-reports/annual-reports/content/"
    "0000050863-26-000011/intc-20251227.htm"
)
_INTEL_PRESS = (
    "https://www.intc.com/news-events/press-releases/detail/1759/"
    "intel-reports-fourth-quarter-and-full-year-2025-financial"
)
_INTEL_FACTS = {
    "revenue_2025": "52853",
    "revenue_2024": "53101",
    "gross_profit_2025": "18375",
    "gross_profit_2024": "17345",
    "cost_of_sales_2025": "34478",
    "cost_of_sales_2024": "35756",
}


def actual_intc_audited_10k_text_receipt() -> dict[str, Any]:
    return {
        "schema": "kuodra.p223-intc-publisher-mirrored-audited-10k.v1",
        "ticker": "INTC", "issuer_cik": "0000050863",
        "form": "10-K", "accession": "0000050863-26-000011",
        "report_filed": "2026-01-23",
        "fiscal_latest_end": "2025-12-27",
        "fiscal_prior_end": "2024-12-28",
        "accounting": "US_GAAP_CONSOLIDATED",
        "values_unit": "USD_millions",
        "source_url": _INTEL_10K,
        "source_method": "FIRST_PARTY_AUDITED_10K_MANUAL_PAGE_REVIEW",
        "facts": dict(_INTEL_FACTS),
        "actual_raw_bytes_sha256": None,
        "sec_edgar_original_identity_verified": False,
        "commercial_ai_rights_verified": False,
        "redistribution_rights_verified": False,
    }


def actual_intc_separate_earnings_receipt() -> dict[str, Any]:
    return {
        "schema": "kuodra.p223-intc-publisher-annual-earnings.v1",
        "ticker": "INTC", "publisher": "Intel Investor Relations",
        "published": "2026-01-22",
        "fiscal_latest_end": "2025-12-27",
        "fiscal_prior_end": "2024-12-28",
        "values_unit": "USD_millions",
        "release_unaudited": True,
        "source_url": _INTEL_PRESS,
        "facts": dict(_INTEL_FACTS),
        "actual_raw_bytes_sha256": None,
        "source_rights_verified": False,
    }


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p223-nvda-amd-intc-two-peer-ledger.v1",
        "status": "BLOCKED", "reason_code": reason,
        "peer_sources_raw_byte_verified": False,
        "peer_rights_verified": False,
        "representative_peers_verified": False,
        "legal_model_input_rights_verified": False,
        "market_ndx_rights_verified": False,
        "engine_c_complete": False, "full_abc_complete": False,
        "guard_policy_preview": "HOLD",
        "investment_recommendation": False, "trade_executed": False,
        "network_requests": 0, "model_requests": 0,
    }


def review_two_official_10k_peers(
    *, ticker: str = "NVDA", reviewed_as_of: str = _AS_OF,
    intel_10k: dict[str, Any] | None = None,
    intel_release: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Independent AMD + Intel audit references, immutable, fail-closed."""
    if type(ticker) is not str or ticker != "NVDA" or reviewed_as_of != _AS_OF:
        return _blocked("UNSUPPORTED_ISSUER_OR_SOURCE_VINTAGE")
    tenk = actual_intc_audited_10k_text_receipt()
    press = actual_intc_separate_earnings_receipt()
    if intel_10k is None:
        intel_10k = tenk
    if intel_release is None:
        intel_release = press
    if (type(intel_10k) is not dict or intel_10k != tenk
            or type(intel_release) is not dict or intel_release != press):
        return _blocked("INTC_OFFICIAL_DOCUMENT_FACTS_OR_METADATA_CHANGED")
    amd = compare_nvda_amd_audited_10k_peer(ticker="NVDA",
                                          reviewed_as_of=reviewed_as_of)
    nvda = review_supported_real_ticker("NVDA", as_of=reviewed_as_of)
    if (amd.get("status") != "ONE_REAL_AUDITED_10K_PEER_CROSSCHECK_ONLY"
            or amd.get("amd_two_independent_official_documents_reconciled") is not True
            or amd.get("engine_c_complete") is not False
            or amd.get("peer_rights_verified") is not False
            or amd.get("current_fiscal_end_gap_days") != 29
            or nvda.get("status") != "REAL_ISSUER_HUMAN_REVIEW_ONLY"
            or nvda.get("publisher_original_observed") is not True
            or nvda.get("source_authenticated_by_sec") is not False
            or nvda.get("source_rights_verified") is not False
            or nvda.get("source_sha256") != amd.get("nvda_original_source_sha256")
            or nvda.get("guard_policy_preview") != "HOLD"):
        return _blocked("PREEXISTING_REAL_AMD_OR_NVDA_SOURCE_CHAIN_FAILED")
    try:
        source_date = date.fromisoformat(intel_10k["report_filed"])
        release_date = date.fromisoformat(intel_release["published"])
        analysis_date = date.fromisoformat(reviewed_as_of)
        latest_end = date.fromisoformat(intel_10k["fiscal_latest_end"])
        prior_end = date.fromisoformat(intel_10k["fiscal_prior_end"])
        nvda_latest = date.fromisoformat(nvda["fiscal_latest_end"])
        nvda_prior = date.fromisoformat(nvda["fiscal_prior_end"])
        if (not (prior_end < latest_end < release_date < source_date < analysis_date)
                or (latest_end-prior_end).days not in range(350, 381)
                or abs((nvda_latest-latest_end).days) != 29
                or abs((nvda_prior-prior_end).days) != 29
                or intel_10k["source_url"] == intel_release["source_url"]):
            return _blocked("PEER_SOURCE_PUBLICATION_OR_FISCAL_PERIOD_INVALID")
        facts = intel_10k["facts"]
        if any(facts.get(k) != v for k, v in intel_release["facts"].items()):
            return _blocked("INTEL_TWO_OFFICIAL_DOCUMENTS_NUMERIC_CONFLICT")
        money = {k: Decimal(v) for k, v in facts.items()}
        revenue_new = money["revenue_2025"]
        revenue_old = money["revenue_2024"]
        gross_new = money["gross_profit_2025"]
        gross_old = money["gross_profit_2024"]
        if (not 0 < gross_new < revenue_new
                or not 0 < gross_old < revenue_old
                or revenue_new - money["cost_of_sales_2025"] != gross_new
                or revenue_old - money["cost_of_sales_2024"] != gross_old):
            return _blocked("INTEL_GAAP_STATEMENT_ARITHMETIC_CONFLICT")
        two = Decimal("0.01")
        fmt = lambda v: str(v.quantize(two, rounding=ROUND_HALF_UP))
        growth = fmt((revenue_new / revenue_old - 1) * 100)
        margin_new = fmt(gross_new / revenue_new * 100)
        margin_old = fmt(gross_old / revenue_old * 100)
        nvda_growth = nvda["issuer_revenue_growth_pct"]
        if (growth != "-0.47" or margin_new != "34.77"
                or margin_old != "32.66"
                or nvda_growth != "65.47"
                or amd["amd_revenue_growth_pct"] != "34.34"):
            return _blocked("PREVAILING_FINANCIAL_PRECISION_OR_SOURCE_CHANGED")
        # Always subtract the original full-precision fiscal growth ratios
        # before rounding once for presentation. Subtracting displayed
        # 65.47 - 34.34 would misstate the AMD gap as 31.13 instead of 31.14.
        unrounded_nvda = (Decimal("215938") / Decimal("130497") - 1) * 100
        unrounded_intc = (revenue_new / revenue_old - 1) * 100
        unrounded_amd = (Decimal("34639") / Decimal("25785") - 1) * 100
        nvda_gap = fmt(unrounded_nvda - unrounded_intc)
        amd_gap = fmt(unrounded_nvda - unrounded_amd)
        if nvda_gap != "65.94" or amd_gap != "31.14":
            return _blocked("PEER_GROWTH_GAP_MATH_MISMATCH")
        return {
            **_blocked("HUMAN_ONLY_TWO_PEER_DOCUMENT_CROSSCHECK_UNLICENSED"),
            "status": "TWO_DISTINCT_AUDITED_PEER_REFERENCES_LIMITED",
            "target_ticker": "NVDA",
            "as_of": reviewed_as_of,
            "real_nvda_issuer_original_source_sha256": nvda["source_sha256"],
            "same_broad_industry_only": True,
            "two_distinct_official_10k_peers_confirmed": True,
            "independent_official_release_reconciliation": True,
            "peer_count": 2,
            "source_consolidation_comparability_blocked": True,
            "intel_altera_2025_deconsolidation_not_adjusted": True,
            "different_business_models": True,
            "fiscal_end_offsets_days": {"AMD": 29, "INTC": 29},
            "revenue_growth_observations_not_sector_rank": [
                {"ticker": "NVDA", "fy_latest": nvda["fiscal_latest_end"],
                 "revenue_growth_pct": nvda_growth,
                 "source_url": nvda["source_url"],
                 "actual_source_sha256": nvda["source_sha256"]},
                {"ticker": "AMD", "fy_latest": "2025-12-27",
                 "revenue_growth_pct": amd["amd_revenue_growth_pct"],
                 "source_url": amd["amd_audited_10k_filing"],
                 "actual_source_sha256": None},
                {"ticker": "INTC", "fy_latest": "2025-12-27",
                 "revenue_growth_pct": growth,
                 "source_url": _INTEL_10K,
                 "actual_source_sha256": None}
            ],
            "intel_filing_accession": intel_10k["accession"],
            "intel_audited_10k_url": _INTEL_10K,
            "intel_separate_release_url": _INTEL_PRESS,
            "intel_2025_revenue_usdm": str(revenue_new),
            "intel_2024_revenue_usdm": str(revenue_old),
            "intel_2025_gross_profit_usdm": str(gross_new),
            "intel_2024_gross_profit_usdm": str(gross_old),
            "intel_2025_gross_margin_pct": margin_new,
            "intel_2024_gross_margin_pct": margin_old,
            "observed_nvda_minus_amd_growth_pp": amd_gap,
            "observed_nvda_minus_intc_growth_pp": nvda_gap,
        }
    except (ArithmeticError, ValueError, TypeError, KeyError, OverflowError):
        return _blocked("INTEL_OR_GROUP_FINANCIAL_REPLAY_INVALID")
