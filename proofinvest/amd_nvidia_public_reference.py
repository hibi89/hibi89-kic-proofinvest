"""P210 pivot: NVIDIA verified real issuer and AMD first-party public *reference*.

Only NVIDIA had actual issuer raw HTML/SHA confirmed in P209 CI. AMD is a
separate publicly reviewed official AMD Newsroom FY2025 annual GAAP facts
transcription, not a verified raw-file capture or licensed market provider.
Period end dates differ 29 days in both annual cohorts. This is a bounded
human-only same-industry reference, NOT comparable representative full Engine C
or a financial ranking. Zero network, imports of failed P210 raw probes,
persistence, model calls or securities execution.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .nvidia_real_issuer_review import (
    actual_nvidia_issuer_receipt, review_nvidia_actual_release,
)

_AMD_URL = "https://newsroom.amd.com/news/amd-reports-fourth-quarter-and-full-year-2025-fina/"
_OBSERVED = "2026-11-05"
_AMD_FACTS = {
    "revenue_2025": "34639", "revenue_2024": "25785",
    "gaap_net_income_2025": "4335", "gaap_net_income_2024": "1641",
    "gaap_operating_income_2025": "3694",
    "gaap_operating_income_2024": "1900",
    "data_center_revenue_2025": "16635",
    "data_center_revenue_2024": "12579",
}


def actual_amd_public_newsroom_receipt() -> dict[str, Any]:
    """Manually checked visible public issuer report; no raw SHA attestation."""
    return {
        "schema": "kuodra.p210-amd-issuer-public-gaap-web-text-reference.v1",
        "ticker": "AMD", "issuer": "Advanced Micro Devices, Inc.",
        "publisher": "AMD Newsroom", "official_public_page": _AMD_URL,
        "published": "2026-02-03", "observed_as_of": _OBSERVED,
        "fiscal_latest_end": "2025-12-27",
        "fiscal_prior_end": "2024-12-28",
        "values_unit": "USD_millions",
        "accounting": "GAAP_ANNUAL_CONSOLIDATED_2025_2024",
        "data_center_mix": "CPU_GPU_APU_AI_ACCELERATORS_NETWORK_FPGAS_MIX",
        "facts": dict(_AMD_FACTS),
        "method": "OFFICIAL_WEBPAGE_VISIBLE_TEXT_HUMAN_REVIEW_NO_RAW_BYTE_SHA",
        "publisher_original_bytes_verified": False,
        "sec_edgar_original_byte_identity": False,
        "commercial_ai_rights_verified": False,
        "redistribution_rights_verified": False,
        "trade_executed": False,
    }


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p210-near-fiscal-semiconductor-reference.v1",
        "status": "BLOCKED", "reason_code": reason,
        "evidence": None, "actual_nvda_issuer_raw_verified": False,
        "amd_web_text_reference_validated": False,
        "amd_original_raw_bytes_verified": False,
        "originals_sec_byte_identical": False,
        "source_commercial_ai_rights_verified": False,
        "licensed_representative_same_sector_peer": False,
        "cross_issuer_accounting_policy_compatible": False,
        "fiscal_windows_identical": False, "price_ndx_available": False,
        "engine_c_completed": False, "full_abc_ready": False,
        "ai_agent_executed": False, "guard_policy_preview": "HOLD",
        "trade_executed": False, "network_requests": 0,
    }


def _pct(a: Decimal, b: Decimal) -> Decimal:
    if b <= 0 or a <= 0:
        raise ValueError("NONPOSITIVE_REVENUE")
    return (a/b-1)*100


def _two(x: Decimal) -> str:
    return str(x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compare_nvda_amd_public_annual_reference(
    *, reviewed_as_of: str, amd_receipt: dict[str, Any],
    nvidia_receipt: dict[str, Any],
) -> dict[str, Any]:
    """Compare reported annual GAAP growth with fiscal-offset safety checks.

    No raw AMD publisher-HTML assertion, provider market/index rights,
    verified segment definition equivalence or production inference.
    """
    if reviewed_as_of != _OBSERVED:
        return _blocked("PUBLIC_FACTS_AS_OF_NOT_CURRENTLY_REVIEWED")
    if type(amd_receipt) is not dict or amd_receipt != actual_amd_public_newsroom_receipt():
        return _blocked("AMD_PUBLIC_ISSUER_GAAP_RECEIPT_CHANGED")
    nvidia = review_nvidia_actual_release(
        as_of=_OBSERVED, receipt=nvidia_receipt
    )
    if (nvidia.get("status") != "REAL_NVDA_FY2026_2025_ISSUER_GAAP_REVIEW_LIMITED"
            or nvidia.get("issuer_original_publisher_seen") is not True
            or nvidia.get("sec_original_identical") is not False
            or nvidia.get("commercial_ai_rights_verified") is not False
            or nvidia.get("licensed_stock_ndx_peer_available") is not False
            or nvidia.get("full_abc_ready") is not False
            or nvidia.get("trade_executed") is not False
            or type(nvidia.get("evidence")) is not dict):
        return _blocked("ACTUAL_NVIDIA_P209_RAW_PUBLISHER_RECEIPT_INVALID")
    nv = nvidia["evidence"]
    nm = nv.get("metrics")
    if (nv.get("ticker") != "NVDA"
            or type(nm) is not dict
            or nv.get("fiscal_2026_end") != "2026-01-25"
            or nv.get("fiscal_2025_end") != "2025-01-26"
            or nm.get("revenue_2026_usdm") != "215938"
            or nm.get("revenue_2025_usdm") != "130497"):
        return _blocked("NVIDIA_ISSUER_REVENUE_OR_FISCAL_CONTEXT_CHANGED")
    try:
        af = amd_receipt["facts"]
        amd_latest = Decimal(af["revenue_2025"])
        amd_prior = Decimal(af["revenue_2024"])
        amd_dc_latest = Decimal(af["data_center_revenue_2025"])
        amd_dc_prior = Decimal(af["data_center_revenue_2024"])
        amd_growth = _pct(amd_latest, amd_prior)
        nvda_growth = _pct(Decimal(nm["revenue_2026_usdm"]),
                           Decimal(nm["revenue_2025_usdm"]))
        amd_dc_growth = _pct(amd_dc_latest, amd_dc_prior)
        latest_gap = abs((
            date.fromisoformat(nv["fiscal_2026_end"]) -
            date.fromisoformat(amd_receipt["fiscal_latest_end"])).days)
        prior_gap = abs((
            date.fromisoformat(nv["fiscal_2025_end"]) -
            date.fromisoformat(amd_receipt["fiscal_prior_end"])).days)
        nvda_year_len = (date.fromisoformat(nv["fiscal_2026_end"]) -
                         date.fromisoformat(nv["fiscal_2025_end"])).days
        amd_year_len = (date.fromisoformat(amd_receipt["fiscal_latest_end"]) -
                        date.fromisoformat(amd_receipt["fiscal_prior_end"])).days
        if (latest_gap != 29 or prior_gap != 29
                or not (350 <= nvda_year_len <= 380)
                or not (350 <= amd_year_len <= 380)
                or _two(amd_growth) != "34.34"
                or _two(nvda_growth) != "65.47"
                or _two(amd_dc_growth) != "32.24"
                or _two(nvda_growth-amd_growth) != "31.14"):
            return _blocked("DIFFERENT_FISCAL_COHORT_OR_GAAP_REFERENCE_UNVERIFIED")
        return {
            **_blocked("PUBLIC_REFERENCES_ONLY_LICENSED_SECTOR_INFERENCE_BLOCKED"),
            "status": "HUMAN_REFERENCE_NVDA_AMD_GAAP_GROWTH_DIFFERENT_PERIODS",
            "actual_nvda_issuer_raw_verified": True,
            "amd_web_text_reference_validated": True,
            "evidence": {
                "sector": "SEMICONDUCTOR_COMPANIES_BROAD_INDUSTRY_ONLY",
                "method": "NVDA_ACTUAL_RAW_SHA_VS_AMD_OFFICIAL_WEB_TEXT_TRANSCRIPTION",
                "current_fiscal_end_gap_days": latest_gap,
                "prior_fiscal_end_gap_days": prior_gap,
                "fiscal_periods_differ": True,
                "different_product_and_segment_mix": True,
                "same_sector_not_equivalent_competitive_MARKET_SCOPE": True,
                "issuer_rows": [
                    {
                        "ticker": "NVDA", "fiscal_latest_end": "2026-01-25",
                        "fiscal_prior_end": "2025-01-26",
                        "annual_gaap_revenue_latest_usdm": nm["revenue_2026_usdm"],
                        "annual_gaap_revenue_prior_usdm": nm["revenue_2025_usdm"],
                        "annual_gaap_revenue_growth_pct": _two(nvda_growth),
                        "first_party_report": nv["issuer_source_url"],
                        "original_sha256": nv["issuer_source_sha256"],
                        "provenance": "ACTUAL_FIRST_PARTY_HTML_SHA_INDEPENDENT_CI",
                    },
                    {
                        "ticker": "AMD", "fiscal_latest_end": "2025-12-27",
                        "fiscal_prior_end": "2024-12-28",
                        "annual_gaap_revenue_latest_usdm": af["revenue_2025"],
                        "annual_gaap_revenue_prior_usdm": af["revenue_2024"],
                        "annual_gaap_revenue_growth_pct": _two(amd_growth),
                        "first_party_report": _AMD_URL,
                        "original_sha256": None,
                        "provenance": "OFFICIAL_PUBLIC_WEB_TEXT_MANUALLY_TRANSCRIBED",
                    },
                ],
                "amd_data_center_revenue_latest_usdm": af["data_center_revenue_2025"],
                "amd_data_center_growth_pct": _two(amd_dc_growth),
                "revenue_growth_difference_pp_observed_not_sector_rank": _two(
                    nvda_growth - amd_growth),
                "peer_conclusion": "WITHHELD_DIFFERENT_PERIOD_ENDS_AND_SEGMENT_MIX",
                "market_share_inferred": False,
                "industry_rank_inferred": False,
                "accounting_fraud_proven": False,
                "trade_executed": False,
            },
        }
    except (KeyError, TypeError, ValueError, ArithmeticError, OverflowError):
        return _blocked("PUBLIC_ISSUER_REVENUE_REVIEW_INVALID")


def main() -> int:
    import json
    out=compare_nvda_amd_public_annual_reference(
        reviewed_as_of=_OBSERVED,
        amd_receipt=actual_amd_public_newsroom_receipt(),
        nvidia_receipt=actual_nvidia_issuer_receipt(),
    )
    print(json.dumps(out,sort_keys=True,ensure_ascii=False,allow_nan=False))
    return 0 if out["status"] == "HUMAN_REFERENCE_NVDA_AMD_GAAP_GROWTH_DIFFERENT_PERIODS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
