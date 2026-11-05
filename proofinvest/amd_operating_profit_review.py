"""P228: AMD audited GAAP operating-profit trajectory, independent peer C dimension.

Only previously human-reconciled first-party 2025 10-K and separate annual
release values are used; no network fetch, investment advice, normalization,
business comparability assertion, copyright/license entitlement or trades.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .amd_10k_peer_bridge import (
    actual_amd_official_10k_text_receipt,
    compare_nvda_amd_audited_10k_peer,
)
from .amd_nvidia_public_reference import actual_amd_public_newsroom_receipt
from .intel_amd_peer_cohort import review_two_official_10k_peers

_SCHEMA = "kuodra.p228-amd-audited-operating-profit.v1"
_STATUS = "AMD_AUDITED_OPERATING_MARGIN_HUMAN_ONLY"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "peer_raw_bytes_verified": False, "peer_rights_verified": False,
        "market_rights_verified": False, "sec_original_identical": False,
        "full_sector_comparability_verified": False,
        "engine_c_complete": False, "full_abc_complete": False,
        "llm_invoked": False, "guard_policy_preview": "HOLD",
        "investment_recommendation": False, "trade_executed": False,
        "network_requests": 0,
    }


def review_amd_operating_profit(
    *, ticker: str = "NVDA", reviewed_as_of: str = "2026-11-05",
    amd_10k: Any = None, amd_release: Any = None,
) -> dict[str, Any]:
    """Reconcile audited GAAP operating income to revenue and prior year.

    The AMD FY2025 release includes MI308 export-control inventory charges:
    observed margins must not be normalized without independently proven data.
    """
    if ticker != "NVDA" or reviewed_as_of != "2026-11-05":
        return _blocked("UNSUPPORTED_REAL_ISSUER_OR_VINTAGE")
    expected_tenk = actual_amd_official_10k_text_receipt()
    expected_release = actual_amd_public_newsroom_receipt()
    tenk = expected_tenk if amd_10k is None else amd_10k
    press = expected_release if amd_release is None else amd_release
    if (type(tenk) is not dict or tenk != expected_tenk
            or type(press) is not dict or press != expected_release):
        return _blocked("SOURCE_RECEIPT_CHANGED_OR_RIGHTS_PROMOTED")
    prior = compare_nvda_amd_audited_10k_peer(
        ticker=ticker, reviewed_as_of=reviewed_as_of,
        amd_10k_receipt=tenk, amd_press_receipt=press,
    )
    cohort = review_two_official_10k_peers(
        ticker=ticker, reviewed_as_of=reviewed_as_of,
    )
    if (prior.get("status") != "ONE_REAL_AUDITED_10K_PEER_CROSSCHECK_ONLY"
            or prior.get("amd_two_independent_official_documents_reconciled") is not True
            or prior.get("peer_rights_verified") is not False
            or prior.get("current_fiscal_end_gap_days") != 29
            or cohort.get("status") != "TWO_DISTINCT_AUDITED_PEER_REFERENCES_LIMITED"
            or cohort.get("peer_rights_verified") is not False
            or cohort.get("engine_c_complete") is not False
            or cohort.get("real_nvda_issuer_original_source_sha256") !=
               prior.get("nvda_original_source_sha256")):
        return _blocked("INDEPENDENT_PEER_SOURCE_CHAIN_INVALID")
    try:
        facts = tenk["facts"]
        if (tenk["published"] != "2026-02-04"
                or press["published"] != "2026-02-03"
                or tenk["fiscal_latest_end"] != "2025-12-27"
                or tenk["fiscal_prior_end"] != "2024-12-28"
                or tenk["currency_unit"] != "USD_millions"
                or tenk["source_original_bytes_verified"] is not False
                or tenk["source_rights_verified"] is not False
                or press["facts"] != facts
                or facts["gaap_operating_income_2025"] != "3694"
                or facts["gaap_operating_income_2024"] != "1900"
                or facts["revenue_2025"] != "34639"
                or facts["revenue_2024"] != "25785"):
            return _blocked("GAAP_OR_SOURCE_VINTAGE_MISMATCH")
        op25 = Decimal(facts["gaap_operating_income_2025"])
        op24 = Decimal(facts["gaap_operating_income_2024"])
        rev25 = Decimal(facts["revenue_2025"])
        rev24 = Decimal(facts["revenue_2024"])
        if not (0 < op25 < rev25 and 0 < op24 < rev24):
            return _blocked("INCONSISTENT_GAAP_OPERATING_INCOME")
        fmt = lambda x: str(x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        p25 = op25 / rev25 * 100
        p24 = op24 / rev24 * 100
        op_yoy = (op25 / op24 - 1) * 100
        sales_yoy = (rev25 / rev24 - 1) * 100
        values = (fmt(p25), fmt(p24), fmt(p25 - p24),
                  fmt(op_yoy), fmt(sales_yoy))
        if values != ("10.66", "7.37", "3.30", "94.42", "34.34"):
            return _blocked("AUDITED_MARGIN_MATH_MISMATCH")
        return {
            **_blocked("GAAP_HISTORY_ONLY_NOT_LICENSED_PEER_COMPLETION"),
            "status": _STATUS, "ticker": ticker, "as_of": reviewed_as_of,
            "accounting": "AUDITED_AMD_GAAP_CONSOLIDATED",
            "fiscal_latest_end": tenk["fiscal_latest_end"],
            "fiscal_prior_end": tenk["fiscal_prior_end"],
            "unit": "USD_millions",
            "gaap_operating_income_2025_usdm": str(op25),
            "gaap_operating_income_2024_usdm": str(op24),
            "revenue_2025_usdm": str(rev25),
            "revenue_2024_usdm": str(rev24),
            "operating_margin_2025_pct": values[0],
            "operating_margin_2024_pct": values[1],
            "operating_margin_change_pp": values[2],
            "operating_income_growth_pct": values[3],
            "revenue_growth_pct": values[4],
            "amd_10k_url": tenk["official_issuer_10k_url"],
            "amd_release_url": press["official_public_page"],
            "nvda_publisher_source_sha256": prior["nvda_original_source_sha256"],
            "amd_actual_source_sha256": None,
            "amd_two_independent_official_documents_reconciled": True,
            "mi308_export_charge_2025_unadjusted": True,
            "nvidia_amd_fiscal_gap_days": 29,
            "differing_company_business_mix": True,
            "raw_provider_rights_verified": False,
            "financial_conclusion": "WITHHELD_HUMAN_ONLY",
        }
    except (KeyError, TypeError, ValueError, ArithmeticError, OverflowError):
        return _blocked("SOURCE_FACT_REPLAY_INVALID")
