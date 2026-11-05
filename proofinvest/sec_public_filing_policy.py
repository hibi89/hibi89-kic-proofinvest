"""P236 first-party SEC EDGAR public filing general reuse policy checkpoint.

Manually verified two independent SEC.gov official statements on 2026-11-05:
- SEC webmaster FAQ: EDGAR PUBLIC filings are free to access and reuse.
- SEC Privacy Information / Website Dissemination: copying/distribution of
  sec.gov public information without the agency's permission, with SEC mark
  and artwork restrictions and source citation guidance.

Important: this only verifies the *general official published policy*. It
does not certify the caller's particular file as an SEC EDGAR original, any
third-party assets/contractual terms, issuer/source hash or the right to use
third-party stock, Nasdaq-100/NDX/peer data. No HTTP or API GET occurs, and
the historically blocked P105 SEC URL is never contacted/retried.
"""
from __future__ import annotations

from typing import Any

from .apple_fy2026_public_filing_review import (
    public_2026_values, review_apple_2026_public_financials,
)

_POLICY_AS_OF = "2026-11-05"
_FAQ = "https://www.sec.gov/files/about/webmaster-faq.htm"
_DISSEMINATION = "https://www.sec.gov/about/privacy-information"
_SOURCE = (
    "https://www.sec.gov/Archives/edgar/data/320193/"
    "000032019326000026/aapl-20260926.htm"
)
_ALLOWED_INTENTS = frozenset({
    "LOCAL_FINANCIAL_RESEARCH",
    "PUBLIC_EDGAR_FACTS_IN_HUMAN_REPORT",
})


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p236-sec-edgar-public-policy.v1",
        "status": "BLOCKED",
        "reason_code": reason,
        "policy_reviewed_kst": _POLICY_AS_OF,
        "official_policy_evidence_urls": [_FAQ, _DISSEMINATION],
        "evidence_owner": "US_SECURITIES_AND_EXCHANGE_COMMISSION",
        "official_general_public_edgar_filing_reuse_policy_verified": False,
        "official_general_public_edgar_copying_policy_verified": False,
        "reference_is_manually_reviewed_public_filing": False,
        "exact_sec_edgar_original_bytes_authenticated": False,
        "sec_accession_origin_authenticated": False,
        "individual_source_document_use_rights_verified": False,
        "non_edgar_exhibits_or_artwork_cleared": False,
        "sec_logo_or_trademark_permission": False,
        "financial_market_data_rights_verified": False,
        "nasdaq100_ndx_data_rights_verified": False,
        "peer_data_rights_verified": False,
        "financial_ai_processing_rights_verified": False,
        "vendor_contract_or_client_entitlement_verified": False,
        "sec_api_transport_reauthorized": False,
        "automated_sec_gets_performed": 0,
        "external_network_requests": 0,
        "raw_source_documents_stored": False,
        "data_uploaded_to_model": False,
        "public_production_authorized": False,
        "guard_policy_preview": "HOLD",
        "investment_recommendation": False,
        "trade_executed": False,
    }


def verify_official_public_edgar_reuse_policy(
    *,
    filing_reference: Any,
    issuer: Any,
    accession: Any,
    as_of: Any,
    intended_use: Any = "LOCAL_FINANCIAL_RESEARCH",
) -> dict[str, Any]:
    """Narrowly record public EDGAR reuse policy + an UNAUTHENTICATED link.

    A source reference is not a raw original. This must never be used as
    a source-specific vendor/license attestation or permission to retry SEC.
    """
    if type(intended_use) is not str or intended_use not in _ALLOWED_INTENTS:
        return _base("POLICY_USE_CASE_NOT_COVERED_BY_NARROW_CHECKPOINT")
    if (type(filing_reference) is not str
            or filing_reference != _SOURCE
            or type(issuer) is not str or issuer != "AAPL"
            or type(accession) is not str
            or accession != "0000320193-26-000026"
            or type(as_of) is not str or as_of != _POLICY_AS_OF):
        return _base("REVIEWED_PUBLIC_FILING_REFERENCE_IDENTITY_REQUIRED")
    reviewed = review_apple_2026_public_financials(
        ticker=issuer, accession=accession, as_of=as_of,
        values=public_2026_values(),
    )
    if (reviewed.get("status") !=
            "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED"
            or reviewed.get("public_filing_url") != filing_reference
            or reviewed.get("original_bytes_authenticated") is not False
            or reviewed.get("source_rights_verified") is not False
            or reviewed.get("guard_policy_preview") != "HOLD"
            or reviewed.get("trade_executed") is not False):
        return _base("MANUALLY_REVIEWED_REFERENCE_REPLAY_FAILED")
    return {
        **_base("OFFICIAL_SEC_POLICY_PUBLIC_REUSE_BUT_NO_RAW_ORIGIN_PROOF"),
        "status": "OFFICIAL_PUBLIC_EDGAR_GENERAL_REUSE_POLICY_VERIFIED",
        "official_general_public_edgar_filing_reuse_policy_verified": True,
        "official_general_public_edgar_copying_policy_verified": True,
        "reference_is_manually_reviewed_public_filing": True,
        "intended_use": intended_use,
        "issuer": issuer,
        "public_filing_reference": filing_reference,
        "accession_reference_not_authenticated": accession,
        "scope": "GENERAL_PUBLIC_EDGAR_FILING_CONTENT_NOT_RAW_AUTHENTICATION",
        "policy_exceptions": [
            "NOT_SEC_SEAL_ARTWORK_OR_REGISTERED_MARKS",
            "NOT_SEPARATELY_LICENSED_MARKET_NDX_OR_VENDOR_CONTENT",
            "NOT_A_PROVEN_SEC_SERVER_BYTE_HASH_OR_RECORD_IDENTITY",
            "NOT_AUTHORIZATION_TO_RETRY_PREVIOUS_SEC_403",
        ],
        "source_attribution_recommended": True,
    }
