"""P222: AMD's separate official FY2025 10-K audited facts corroborate P210 IR.

The 10-K has been manually read at AMD's official filing mirror, not
downloaded as raw bytes through this program. This is *not* a vendor license,
SEC EDGAR byte identity, fully representative peer set or complete Engine C.
Only derived, reviewable annual metrics are returned, with a Guard HOLD.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .amd_nvidia_public_reference import (
    actual_amd_public_newsroom_receipt,
    compare_nvda_amd_public_annual_reference,
)
from .nvidia_real_issuer_review import actual_nvidia_issuer_receipt
from .real_issuer_ticker_review import review_supported_real_ticker

_FORM_10K_URL = (
    "https://ir.amd.com/financial-information/sec-filings/content/"
    "0000002488-26-000018/amd-20251227.htm"
)
_VINTAGE = "2026-11-05"
_10K_FACTS = {
    "revenue_2025": "34639",
    "revenue_2024": "25785",
    "gaap_net_income_2025": "4335",
    "gaap_net_income_2024": "1641",
    "gaap_operating_income_2025": "3694",
    "gaap_operating_income_2024": "1900",
    "data_center_revenue_2025": "16635",
    "data_center_revenue_2024": "12579",
}


def actual_amd_official_10k_text_receipt() -> dict[str, Any]:
    """Human-reviewed 10-K mirrored by issuer, no raw byte SHA."""
    return {
        "schema": "kuodra.p222-amd-official-2025-10k-audited-text.v1",
        "ticker": "AMD",
        "publisher": "AMD Investor Relations",
        "filing_form": "10-K",
        "filing_accession": "0000002488-26-000018",
        "published": "2026-02-04",
        "fiscal_latest_end": "2025-12-27",
        "fiscal_prior_end": "2024-12-28",
        "currency_unit": "USD_millions",
        "accounting": "GAAP_CONSOLIDATED",
        "official_issuer_10k_url": _FORM_10K_URL,
        "facts": dict(_10K_FACTS),
        "source_method": "PUBLIC_FIRST_PARTY_10K_HTML_MANUAL_FACT_CHECK_NO_RAW",
        "source_original_bytes_verified": False,
        "sec_edgar_original_identical": False,
        "source_rights_verified": False,
        "peer_licensed_for_distribution": False,
        "network_requests": 0,
    }


def _blocked(code: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p222-audited-amd-nvda-local-peer.v1",
        "status": "BLOCKED",
        "reason_code": code,
        "source_raw_bytes_authenticated": False,
        "sec_edgar_original_identical": False,
        "peer_rights_verified": False,
        "market_ndx_rights_verified": False,
        "representative_sector_set": False,
        "financial_policies_fully_comparable": False,
        "engine_c_complete": False,
        "full_abc_complete": False,
        "guard_policy_preview": "HOLD",
        "trade_executed": False,
        "network_requests": 0,
    }


def compare_nvda_amd_audited_10k_peer(
    *, ticker: str = "NVDA", reviewed_as_of: str = _VINTAGE,
    amd_10k_receipt: dict[str, Any] | None = None,
    amd_press_receipt: dict[str, Any] | None = None,
    nvda_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cross-document annual GAAP fact checks, fiscal offsets, derived metrics."""
    if type(ticker) is not str or ticker != "NVDA" or reviewed_as_of != _VINTAGE:
        return _blocked("TICKER_OR_REVIEW_VINTAGE_NOT_ATTESTED")
    expected_10k = actual_amd_official_10k_text_receipt()
    if amd_10k_receipt is None:
        amd_10k_receipt = expected_10k
    if type(amd_10k_receipt) is not dict or amd_10k_receipt != expected_10k:
        return _blocked("AMD_OFFICIAL_10K_FACTS_OR_METADATA_CHANGED")
    expected_press = actual_amd_public_newsroom_receipt()
    if amd_press_receipt is None:
        amd_press_receipt = expected_press
    if type(amd_press_receipt) is not dict or amd_press_receipt != expected_press:
        return _blocked("AMD_PRESS_RELEASE_FACTS_OR_METADATA_CHANGED")
    if nvda_receipt is None:
        nvda_receipt = actual_nvidia_issuer_receipt()
    issuer = review_supported_real_ticker("NVDA", as_of=reviewed_as_of)
    if (issuer.get("status") != "REAL_ISSUER_HUMAN_REVIEW_ONLY"
            or issuer.get("publisher_original_observed") is not True
            or issuer.get("ticker") != "NVDA"
            or issuer.get("guard_policy_preview") != "HOLD"
            or issuer.get("source_rights_verified") is not False
            or issuer.get("source_authenticated_by_sec") is not False):
        return _blocked("NVIDIA_REAL_ISSUER_REVIEW_INVALID")
    # P210 provides independently recomputed NVIDIA real publisher receipt.
    prior = compare_nvda_amd_public_annual_reference(
        reviewed_as_of=reviewed_as_of,
        amd_receipt=amd_press_receipt,
        nvidia_receipt=nvda_receipt,
    )
    if (prior.get("status") !=
            "HUMAN_REFERENCE_NVDA_AMD_GAAP_GROWTH_DIFFERENT_PERIODS"
            or prior.get("actual_nvda_issuer_raw_verified") is not True
            or prior.get("amd_web_text_reference_validated") is not True
            or prior.get("licensed_representative_same_sector_peer") is not False
            or type(prior.get("evidence")) is not dict):
        return _blocked("NVDA_P210_REAL_ISSUER_OR_AMD_REFERENCE_FAILED")
    e = prior["evidence"]
    rows = e.get("issuer_rows")
    if (type(rows) is not list or len(rows) != 2
            or rows[0].get("ticker") != "NVDA"
            or rows[1].get("ticker") != "AMD"
            or rows[0].get("original_sha256") != issuer.get("source_sha256")
            or rows[1].get("original_sha256") is not None
            or e.get("current_fiscal_end_gap_days") != 29
            or e.get("prior_fiscal_end_gap_days") != 29
            or e.get("peer_conclusion") !=
               "WITHHELD_DIFFERENT_PERIOD_ENDS_AND_SEGMENT_MIX"):
        return _blocked("ISSUER_FINANCIAL_AND_10K_FISCAL_LINK_FAILED")
    for key, value in amd_10k_receipt["facts"].items():
        if amd_press_receipt["facts"].get(key) != value:
            return _blocked("AMD_10K_VS_PRESS_GAAP_CONFLICT")
    try:
        if (date.fromisoformat(amd_10k_receipt["published"]) >
                date.fromisoformat(reviewed_as_of)):
            return _blocked("PEER_REPORT_FUTURE_LEAKAGE")
        latest, earlier = (
            Decimal(amd_10k_receipt["facts"]["gaap_net_income_2025"]),
            Decimal(amd_10k_receipt["facts"]["gaap_net_income_2024"]),
        )
        rev_now = Decimal(amd_10k_receipt["facts"]["revenue_2025"])
        rev_before = Decimal(amd_10k_receipt["facts"]["revenue_2024"])
        if min(latest, earlier, rev_now, rev_before) <= 0:
            return _blocked("INVALID_GAAP_ANNUAL_NUMBERS")
        two = Decimal("0.01")
        margin = str((latest / rev_now * 100).quantize(two, rounding=ROUND_HALF_UP))
        old_margin = str((earlier / rev_before * 100).quantize(two, rounding=ROUND_HALF_UP))
        if (rows[1].get("annual_gaap_revenue_latest_usdm") != str(rev_now)
                or rows[1].get("annual_gaap_revenue_prior_usdm") != str(rev_before)
                or rows[0].get("annual_gaap_revenue_growth_pct") !=
                   issuer.get("issuer_revenue_growth_pct")
                or rows[1].get("annual_gaap_revenue_growth_pct") != "34.34"
                or margin != "12.51" or old_margin != "6.36"
                or e.get("revenue_growth_difference_pp_observed_not_sector_rank") != "31.14"):
            return _blocked("AUDITED_REAL_PEER_GAAP_RECOMPUTATION_CONFLICT")
        return {
            **_blocked("FIRST_PARTY_DERIVED_FISCAL_REFERENCE_NOT_LICENSED_PEER_SET"),
            "status": "ONE_REAL_AUDITED_10K_PEER_CROSSCHECK_ONLY",
            "issuer": "NVDA", "peer": "AMD",
            "review_as_of": reviewed_as_of,
            "amd_audited_10k_filing": _FORM_10K_URL,
            "amd_press_release": amd_press_receipt["official_public_page"],
            "amd_filing_accession": amd_10k_receipt["filing_accession"],
            "amd_10k_filed": amd_10k_receipt["published"],
            "amd_two_independent_official_documents_reconciled": True,
            "amd_revenue_2025_usdm": str(rev_now),
            "amd_revenue_2024_usdm": str(rev_before),
            "amd_gaap_net_income_2025_usdm": str(latest),
            "amd_gaap_net_income_2024_usdm": str(earlier),
            "amd_gaap_net_margin_2025_pct": margin,
            "amd_gaap_net_margin_2024_pct": old_margin,
            "nvda_source_url": issuer["source_url"],
            "nvda_original_source_sha256": issuer["source_sha256"],
            "nvda_revenue_growth_pct": rows[0]["annual_gaap_revenue_growth_pct"],
            "amd_revenue_growth_pct": rows[1]["annual_gaap_revenue_growth_pct"],
            "observed_growth_gap_pp_not_sector_rank":
                e["revenue_growth_difference_pp_observed_not_sector_rank"],
            "current_fiscal_end_gap_days": e["current_fiscal_end_gap_days"],
            "prior_fiscal_end_gap_days": e["prior_fiscal_end_gap_days"],
            "difference_in_company_product_mix": True,
            "single_peer_not_representative": True,
            "publication_consent_required": True,
        }
    except (KeyError, TypeError, ArithmeticError, ValueError, OverflowError):
        return _blocked("AUDITED_PEER_FINANCIAL_INPUT_INVALID")
