"""P227: AMD data-center segment as a separate actual-source peer C dimension.

Uses only manually cross-checked FY2025/FY2024 first-party AMD 10-K and
independent release facts already retained in the repository. No source GET,
price provider, redistribution right, sector ranking, prediction or trade.
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

_SCHEMA = "kuodra.p227-amd-datacenter-segment-peer.v1"
_STATUS = "AMD_DATACENTER_ACTUAL_10K_SEGMENT_HUMAN_REVIEW_ONLY"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "source_raw_bytes_verified": False,
        "peer_rights_verified": False, "market_rights_verified": False,
        "financial_comparability_verified": False, "representative_peers_verified": False,
        "engine_c_complete": False, "full_abc_complete": False,
        "ai_agent_executed": False, "guard_policy_preview": "HOLD",
        "investment_recommendation": False, "trade_executed": False,
        "network_requests": 0,
    }


def review_amd_datacenter_segment(
    *, ticker: str = "NVDA", reviewed_as_of: str = "2026-11-05",
    amd_10k: Any = None, amd_release: Any = None,
) -> dict[str, Any]:
    """Independent derived segment growth and total-revenue share, fail closed.

    A segment is NOT a peer company: NVIDIA total revenue versus AMD Data
    Center segment is an illustration of different scope, not a fair ranking.
    """
    if ticker != "NVDA" or reviewed_as_of != "2026-11-05":
        return _blocked("UNSUPPORTED_TICKER_OR_VINTAGE")
    expected_10k = actual_amd_official_10k_text_receipt()
    expected_press = actual_amd_public_newsroom_receipt()
    tenk = expected_10k if amd_10k is None else amd_10k
    press = expected_press if amd_release is None else amd_release
    if (type(tenk) is not dict or tenk != expected_10k
            or type(press) is not dict or press != expected_press):
        return _blocked("AMENDED_OR_UNTRUSTED_SEGMENT_SOURCE")
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
            or cohort.get("peer_count") != 2
            or cohort.get("real_nvda_issuer_original_source_sha256") != prior.get("nvda_original_source_sha256")
            or cohort.get("peer_rights_verified") is not False
            or cohort.get("engine_c_complete") is not False):
        return _blocked("PRIOR_REAL_SOURCE_CHAIN_INVALID")
    try:
        facts = tenk["facts"]
        if (tenk["fiscal_latest_end"] != "2025-12-27"
                or tenk["fiscal_prior_end"] != "2024-12-28"
                or tenk["currency_unit"] != "USD_millions"
                or tenk["source_original_bytes_verified"] is not False
                or tenk["source_rights_verified"] is not False
                or press["facts"] != facts
                or facts["data_center_revenue_2025"] != "16635"
                or facts["data_center_revenue_2024"] != "12579"
                or facts["revenue_2025"] != "34639"
                or facts["revenue_2024"] != "25785"):
            return _blocked("SEGMENT_SOURCE_CONTRACT_MISMATCH")
        dc25, dc24 = (Decimal(facts["data_center_revenue_2025"]),
                      Decimal(facts["data_center_revenue_2024"]))
        total25, total24 = (Decimal(facts["revenue_2025"]),
                            Decimal(facts["revenue_2024"]))
        if not (0 < dc25 <= total25 and 0 < dc24 <= total24):
            return _blocked("SEGMENT_EXCEEDS_GAAP_TOTAL")
        fmt = lambda value: str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        dc_growth = fmt((dc25 / dc24 - 1) * 100)
        share25 = fmt(dc25 / total25 * 100)
        share24 = fmt(dc24 / total24 * 100)
        share_change = fmt((dc25 / total25 - dc24 / total24) * 100)
        if (dc_growth, share25, share24, share_change) != (
                "32.24", "48.02", "48.78", "-0.76"):
            return _blocked("INDEPENDENT_SEGMENT_MATH_MISMATCH")
        return {
            **_blocked("SOURCE_TEXT_ONLY_NOT_REUSABLE_FINANCIAL_ADVICE"),
            "status": _STATUS, "ticker": ticker,
            "reviewed_as_of": reviewed_as_of,
            "segment": "AMD_DATA_CENTER", "accounting": "US_GAAP_AUDITED_10K",
            "fiscal_latest_end": tenk["fiscal_latest_end"],
            "fiscal_prior_end": tenk["fiscal_prior_end"],
            "currency_unit": "USD_millions",
            "data_center_revenue_2025_usdm": str(dc25),
            "data_center_revenue_2024_usdm": str(dc24),
            "amd_total_revenue_2025_usdm": str(total25),
            "amd_total_revenue_2024_usdm": str(total24),
            "segment_growth_pct": dc_growth,
            "segment_share_of_amd_revenue_2025_pct": share25,
            "segment_share_of_amd_revenue_2024_pct": share24,
            "segment_share_change_pp": share_change,
            "amd_10k_url": tenk["official_issuer_10k_url"],
            "amd_independent_release_url": press["official_public_page"],
            "nvda_publisher_source_sha256": prior["nvda_original_source_sha256"],
            "peer_source_raw_sha256": None,
            "two_first_party_amd_documents_manually_reconciled": True,
            "nvda_vs_amd_segment_comparable": False,
            "different_business_mix": True,
            "nvda_fiscal_end_gap_days": 29,
            "intel_altera_deconsolidation_unadjusted": True,
            "human_only_review": True,
        }
    except (ValueError, ArithmeticError, TypeError, KeyError, OverflowError):
        return _blocked("SEGMENT_REPLAY_INVALID")
