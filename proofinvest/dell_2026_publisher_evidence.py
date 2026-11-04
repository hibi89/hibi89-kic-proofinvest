"""P196 genuine one-shot issuer-hosted Dell 2026 report -> offline B evidence.

The source SHA/size/HTTPS/financial-cell receipt is from ACTUAL GitHub Actions
run #41881814888 (2026-11-05 KST), not fixture/network request. These bytes
are ephemeral (NOT saved); binding the receipt does not prove SEC EDGAR
byte-equivalence, completeness of filing audit, AI license or business use.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .dell_issuer_2026_10k_once import _URL
from .apple_public_peer_reality import public_primary_revenue_values

_RUN = "https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41881814888"
_FUNCTION_SHA = "63ad62162522463644f92feb5ebcd05bb8698abc"
_ORIGINAL_SHA256 = "c48524018e82710057f6ef7cb27b665c4c7f4a39b65b02973417de0d68a5a4ac"
_ORIGINAL_LENGTH = 3610307
_CFO_2026 = Decimal("11185")
_NET_INCOME_2026 = Decimal("5936")
_VERIFIED_TICKER = "DELL"
_VERIFIED_ACCESSION = "0001571996-26-000008"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p196-real-dell-issuer-b-evidence.v1",
        "status": "BLOCKED",
        "reason_code": reason,
        "publisher_https_original_seen": False,
        "sec_edgar_original_byte_equivalence_verified": False,
        "source_rights_verified": False,
        "full_engine_b_authenticated": False,
        "full_engine_abc_ready": False,
        "peer_licensed_and_period_aligned": False,
        "price_ndx_licensed": False,
        "model_input_authorized": False,
        "ai_agent_executed": False,
        "guard_policy_preview": "HOLD",
        "investor_approved": False,
        "trade_executed": False,
        "raw_original_retained": False,
        "network_requests": 0,
        "evidence": None,
    }


def actual_p195_source_receipt() -> dict[str, Any]:
    """Return fixed metadata copied from observed exact-SHA actual CI log."""
    return {
        "status": "ISSUER_HTTPS_REAL_DELL_2026_10K_BYTES_CROSSCHECKED",
        "schema": "kuodra.p195-first-party-dell-2026-10k-one-shot.v1",
        "public_issuer_report_url": _URL,
        "ticker": _VERIFIED_TICKER,
        "accession_in_official_issuer_url": _VERIFIED_ACCESSION,
        "fy2026_end": "2026-01-30",
        "fy2025_end": "2025-01-31",
        "issuer_https_get_attempted": 1,
        "issuer_https_get_budget": 1,
        "issuer_https_host_verified": True,
        "issuer_html_10k_numbers_crosschecked": True,
        "source_original_sha256": _ORIGINAL_SHA256,
        "source_original_bytes": _ORIGINAL_LENGTH,
        "annual_net_revenue_2026_usd_millions": "113538",
        "annual_net_revenue_2025_usd_millions": "95567",
        "sec_edgar_identical_original_verified": False,
        "source_rights_verified": False,
        "model_processing_rights_verified": False,
        "original_bytes_uploaded": False,
        "original_bytes_written_to_disk": False,
        "trade_executed": False,
        "sec_http_requests": 0,
        "redirects_followed": 0,
    }


def review_verified_dell_first_party_raw_evidence(
    *, as_of: str, receipt: dict[str, Any],
) -> dict[str, Any]:
    if type(as_of) is not str or as_of != "2026-11-05":
        return _blocked("PUBLISHED_SOURCE_REVIEW_VINTAGE_INVALID")
    if type(receipt) is not dict or receipt != actual_p195_source_receipt():
        return _blocked("SOURCE_MUST_MATCH_REAL_PINNED_CI_RECEIPT")
    expected = public_primary_revenue_values()["DELL"]
    if (expected != {"2026": "113538", "2025": "95567"}
            or receipt.get("public_issuer_report_url") != _URL):
        return _blocked("INDEPENDENT_FIRST_PARTY_REVENUE_CROSSCHECK_FAILED")
    sales_cur = Decimal(expected["2026"])
    sales_prior = Decimal(expected["2025"])
    growth = ((sales_cur - sales_prior) / sales_prior * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    cash_to_income = (_CFO_2026 / _NET_INCOME_2026).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP)
    if growth != Decimal("18.80") or cash_to_income != Decimal("1.8843"):
        return _blocked("INDEPENDENT_PUBLIC_FILING_NUMERIC_REPLAY_INVALID")
    return {
        **_blocked("ISSUER_SITE_ORIGINAL_IS_NOT_SEC_ORIGIN_ATTESTATION"),
        "status": "DELL_REAL_FIRST_PARTY_ORIGINAL_NUMERIC_REVIEW_READY_LIMITED",
        "publisher_https_original_seen": True,
        "evidence": {
            "issuer": "Dell Technologies Inc.",
            "ticker": "DELL",
            "source_url": _URL,
            "fiscal_year_end": "2026-01-30",
            "prior_year_end": "2025-01-31",
            "publication_reviewed_as_of": as_of,
            "actual_source_ci_run": _RUN,
            "actual_source_functional_sha": _FUNCTION_SHA,
            "raw_original_bytes_sha256": _ORIGINAL_SHA256,
            "raw_original_byte_count": _ORIGINAL_LENGTH,
            "actual_issuer_https_gets": 1,
            "revenue_2026_usd_millions": str(sales_cur),
            "revenue_2025_usd_millions": str(sales_prior),
            "revenue_yoy_pct": str(growth),
            "operating_cash_flow_2026_usd_millions": str(_CFO_2026),
            "net_income_2026_usd_millions": str(_NET_INCOME_2026),
            "cash_flow_to_net_income_ratio": str(cash_to_income),
            "cash_flow_exceeds_net_income_usd_millions": str(
                _CFO_2026 - _NET_INCOME_2026),
            "human_review_finding": "CFO_EXCEEDS_NET_INCOME_NO_FRAUD_CONCLUSION",
        },
    }
