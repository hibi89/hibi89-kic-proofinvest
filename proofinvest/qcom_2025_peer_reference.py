"""P230: newly independent FY2025 public audited-text Qualcomm (QCOM) peer.

Historical human review only. The issuer's FY2025 SEC 10-K GAAP operations
statement was manually crosschecked with the separately issued 2025
Qualcomm newsroom FY result (44.3 billion rounded and GAAP $5.01 EPS).
No raw SEC bytes were fetched or authenticated, issuer/page copyrights and
commercial/AI/data-use rights remain unverified, and neither Qualcomm
licensing revenues nor its September fiscal year are NVIDIA equivalents.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .intel_amd_peer_cohort import review_two_official_10k_peers
from .real_issuer_ticker_review import review_supported_real_ticker

_SCHEMA = "kuodra.p230-qcom-third-historical-peer.v1"
_STATUS = "THIRD_QCOM_PUBLIC_AUDITED_10K_HUMAN_REFERENCE_ONLY"
_TENK = "https://www.sec.gov/Archives/edgar/data/804328/000080432825000085/qcom-20250928.htm"
_PRESS = "https://www.qualcomm.com/news/releases/2025/11/qualcomm-announces-fourth-quarter-and-fiscal-2025-results"
_AS_OF = "2026-11-05"
_FACTS = {
    "equipment_and_services_2025":"37869",
    "equipment_and_services_2024":"32791",
    "licensing_2025":"6415", "licensing_2024":"6171",
    "revenue_2025":"44284", "revenue_2024":"38962",
    "cost_of_revenue_2025":"19738", "cost_of_revenue_2024":"17060",
    "r_and_d_2025":"9042", "r_and_d_2024":"8893",
    "sga_2025":"3110", "sga_2024":"2759",
    "other_2025":"39", "other_2024":"179",
    "operating_income_2025":"12355", "operating_income_2024":"10071",
}


def official_qcom_fy2025_10k_public_text_receipt() -> dict[str,Any]:
    return {
        "schema":"kuodra.p230-qcom-publisher-2025-10k-public-text.v1",
        "ticker":"QCOM", "cik":"0000804328", "form":"10-K",
        "accession":"0000804328-25-000085", "filed":"2025-11-05",
        "fiscal_latest_end":"2025-09-28", "fiscal_prior_end":"2024-09-29",
        "accounting":"US_GAAP_CONSOLIDATED",
        "amount_unit":"USD_millions", "source_url":_TENK,
        "facts":dict(_FACTS), "original_raw_bytes_sha256":None,
        "source_rights_verified":False,
        "sec_original_byte_identical":False,
        "model_processing_rights_verified":False,
    }


def official_qcom_fy2025_public_release_receipt() -> dict[str,Any]:
    return {
        "schema":"kuodra.p230-qcom-publisher-2025-release-public-text.v1",
        "ticker":"QCOM", "published":"2025-11-05",
        "fiscal_latest_end":"2025-09-28",
        "publisher":"Qualcomm Newsroom",
        "official_url":_PRESS,
        "gaap_annual_revenue_rounded_billions":"44.3",
        "gaap_diluted_eps":"5.01",
        "annual_2025_revenue_exact_from_release":None,
        "source_rights_verified":False,
        "raw_release_sha256":None,
        "commercial_reuse_approved":False,
    }


def _blocked(reason: str) -> dict[str,Any]:
    return {
        "schema":_SCHEMA, "status":"BLOCKED", "reason_code":reason,
        "peer_original_raw_verified":False,
        "sec_original_byte_identical":False,
        "peer_rights_verified":False,
        "representative_peers_verified":False,
        "market_rights_verified":False,
        "legal_model_use_rights_verified":False,
        "engine_c_complete":False, "full_abc_complete":False,
        "guard_policy_preview":"HOLD",
        "investment_recommendation":False, "trade_executed":False,
        "network_requests":0, "model_requests":0,
    }


def review_public_qualcomm_third_peer(
    *, ticker: Any = "NVDA", reviewed_as_of: Any = _AS_OF,
    qcom_10k: Any = None, qcom_release: Any = None,
) -> dict[str,Any]:
    """Distinct public GAAP source observation, never a licensed sector rank."""
    if (type(ticker) is not str or ticker!="NVDA"
            or type(reviewed_as_of) is not str or reviewed_as_of!=_AS_OF):
        return _blocked("ISSUER_OR_REVIEW_VINTAGE_UNSUPPORTED")
    expected_tenk=official_qcom_fy2025_10k_public_text_receipt()
    expected_press=official_qcom_fy2025_public_release_receipt()
    tenk=expected_tenk if qcom_10k is None else qcom_10k
    press=expected_press if qcom_release is None else qcom_release
    if (type(tenk) is not dict or tenk!=expected_tenk
            or type(press) is not dict or press!=expected_press):
        return _blocked("OFFICIAL_QCOM_PUBLIC_REFERENCE_CHANGED")
    peers=review_two_official_10k_peers(ticker=ticker,reviewed_as_of=reviewed_as_of)
    issuer=review_supported_real_ticker(ticker,as_of=reviewed_as_of)
    if (peers.get("status")!="TWO_DISTINCT_AUDITED_PEER_REFERENCES_LIMITED"
            or peers.get("peer_count")!=2
            or peers.get("peer_rights_verified") is not False
            or peers.get("representative_peers_verified") is not False
            or peers.get("engine_c_complete") is not False
            or peers.get("guard_policy_preview")!="HOLD"
            or issuer.get("status")!="REAL_ISSUER_HUMAN_REVIEW_ONLY"
            or issuer.get("ticker")!="NVDA"
            or issuer.get("source_rights_verified") is not False
            or issuer.get("publisher_original_observed") is not True
            or issuer.get("source_sha256") !=
               peers.get("real_nvda_issuer_original_source_sha256")):
        return _blocked("PREVIOUS_TWO_PEER_OR_NVDA_SOURCE_CHAIN_INVALID")
    try:
        latest=date.fromisoformat(tenk["fiscal_latest_end"])
        prior=date.fromisoformat(tenk["fiscal_prior_end"])
        nv_latest=date.fromisoformat(issuer["fiscal_latest_end"])
        nv_prior=date.fromisoformat(issuer["fiscal_prior_end"])
        release_date=date.fromisoformat(press["published"])
        filed=date.fromisoformat(tenk["filed"])
        if (not prior<latest<release_date<=filed<=date.fromisoformat(reviewed_as_of)
                or (latest-prior).days not in range(350,380)
                or (nv_latest-latest).days!=119
                or (nv_prior-prior).days!=119
                or press["fiscal_latest_end"] != tenk["fiscal_latest_end"]
                or tenk["source_rights_verified"] is not False):
            return _blocked("QCOM_FISCAL_VINTAGE_OR_SOURCE_INVALID")
        f={k:Decimal(v) for k,v in tenk["facts"].items()}
        for yy in ("2025","2024"):
            if (f["equipment_and_services_"+yy]+f["licensing_"+yy]
                    != f["revenue_"+yy]):
                return _blocked("QCOM_SEGMENT_REVENUE_DOES_NOT_SUM")
            if (f["revenue_"+yy]-f["cost_of_revenue_"+yy]
                    -f["r_and_d_"+yy]-f["sga_"+yy]-f["other_"+yy]
                    != f["operating_income_"+yy]):
                return _blocked("QCOM_GAAP_OPERATING_PROFIT_DOES_NOT_RECONCILE")
        rev25=f["revenue_2025"];rev24=f["revenue_2024"]
        op25=f["operating_income_2025"];op24=f["operating_income_2024"]
        if not (0<op24<rev24 and 0<op25<rev25):
            return _blocked("QCOM_GAAP_INPUT_UNSAFE")
        fmt=lambda x: str(x.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))
        growth=fmt((rev25/rev24-1)*100)
        margin25=fmt(op25/rev25*100);margin24=fmt(op24/rev24*100)
        marginchange=fmt((op25/rev25-op24/rev24)*100)
        release_round=fmt(rev25/Decimal("1000"))
        if ((growth,margin25,margin24,marginchange)!=
                ("13.66","27.90","25.85","2.05")
                or release_round!="44.28"
                or press["gaap_annual_revenue_rounded_billions"]!="44.3"
                or press["gaap_diluted_eps"]!="5.01"
                or tenk["original_raw_bytes_sha256"] is not None
                or tenk["source_rights_verified"] is not False):
            return _blocked("QCOM_10K_AND_PRESS_ROUNDED_GAAP_MISMATCH")
        return {
            **_blocked("PUBLIC_TEXT_REVIEW_NOT_LICENSED_THIRD_PEER"),
            "status":_STATUS,
            "ticker":"NVDA", "reference_peer":"QCOM",
            "as_of":reviewed_as_of, "peer_count_prior":2,
            "distinct_public_10k_peer_count_descriptive":3,
            "official_10k_form":tenk["form"], "filing_accession":tenk["accession"],
            "issuer_cik":tenk["cik"],
            "qcom_audited_text_10k_url":tenk["source_url"],
            "qcom_issuer_newsroom_url":press["official_url"],
            "qcom_annual_latest_end":tenk["fiscal_latest_end"],
            "qcom_annual_prior_end":tenk["fiscal_prior_end"],
            "qcom_revenue_2025_usdm":str(rev25),
            "qcom_revenue_2024_usdm":str(rev24),
            "qcom_gaap_operating_income_2025_usdm":str(op25),
            "qcom_gaap_operating_income_2024_usdm":str(op24),
            "qcom_revenue_growth_pct":growth,
            "qcom_gaap_operating_margin_2025_pct":margin25,
            "qcom_gaap_operating_margin_2024_pct":margin24,
            "qcom_gaap_operating_margin_delta_pp":marginchange,
            "press_revenue_is_rounded_only":True,
            "source_reconciliation_scope":"ROUNDED_ANNUAL_REVENUE_AND_PERIOD_ONLY",
            "nvda_publisher_source_sha256":issuer["source_sha256"],
            "qcom_10k_raw_sha256":None, "qcom_release_raw_sha256":None,
            "nvda_qcom_fiscal_offset_days":119,
            "amd_intc_qcom_fiscal_offset_days":90,
            "qcom_licensing_component_not_equivalent_to_nvda":True,
            "qcom_2025_deferred_tax_valuation_charge_not_normalized":True,
            "different_business_and_fiscal_windows":True,
            "full_peer_ranking_or_forecast_withheld":True,
            "human_review_only":True,
        }
    except (ValueError,TypeError,KeyError,ArithmeticError,OverflowError):
        return _blocked("QCOM_OFFICIAL_GAAP_SOURCE_REPLAY_FAILED")
