"""P112: read-only Nasdaq-100 supplier/rights preflight; never fetches data.

Published price/access statements are NOT permissions, account entitlements or
proof of vendor origin. This module intentionally cannot authorize a request.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

# Public supplier pages checked 2026-11-02 KST; not user account evidence.
# Codes avoid turning apparently free index access into commercial permission.
_CANDIDATES = {
    "massive": ("PUBLIC_BASIC_NDX_LISTED", "https://massive.com/indices"),
    "twelve_data": ("INDEX_API_OFFERED_NDX_BASIC_UNCONFIRMED", "https://twelvedata.com/indices"),
    "fred": ("NASDAQ100_SERIES_NASDAQ_COPYRIGHT", "https://fred.stlouisfed.org/series/NASDAQ100"),
    "nasdaq_gids": ("NASDAQ_SOURCE_LICENSE_SALES_REQUIRED", "https://www.nasdaq.com/products/global-indexes/data/gids"),
    "nasdaq_data_link": ("EXACT_NDX_DATASET_COVERAGE_UNCONFIRMED", "https://data.nasdaq.com/"),
}
_USES = frozenset({"internal_research", "contest_judge_demo", "public_dashboard", "commercial_product"})

# P125: official legal/product disclosures checked on 2026-11-03 KST.
# Descriptions of publicly stated restrictions, NOT advice, account proof,
# data access permission or a claim that any vendor plan was purchased.
_LEGAL_GAPS = {
    "massive": {
        "terms_url": "https://massive.com/legal/market-data-terms-of-service",
        "other_official_url": "https://massive.com/knowledge-base/article/how-can-i-redistribute-massives-market-data",
        "codes": [
            "PERSONAL_SUBSCRIPTION_EXCLUDES_BUSINESS_AND_THIRD_PARTY_APPLICATION",
            "DERIVED_ANALYTICS_EXTERNAL_USE_REQUIRES_RELEVANT_PERMISSION",
            "INDEX_NON_DISPLAY_ENTITLEMENT_UNVERIFIED",
        ],
        "next_evidence": "WRITTEN_VENDOR_DATA_USE_SCOPE_AND_ACCOUNT_ENTITLEMENT",
    },
    "twelve_data": {
        "terms_url": "https://twelvedata.com/terms",
        "other_official_url": "https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage",
        "codes": [
            "FREE_TIER_COMMERCIAL_USE_PROHIBITED",
            "INDIVIDUAL_PLANS_INTERNAL_OR_NON_PRODUCTION_ONLY",
            "EXTERNAL_DISPLAY_AND_REDISTRIBUTION_REQUIRE_APPROPRIATE_RIGHTS",
            "NDX_INSTRUMENT_AND_NON_DISPLAY_ENTITLEMENT_UNVERIFIED",
        ],
        "next_evidence": "EXACT_SYMBOL_COVERAGE_AND_BUSINESS_DISPLAY_LICENSE",
    },
    "fred": {
        "terms_url": "https://fred.stlouisfed.org/legal/terms/",
        "other_official_url": "https://fred.stlouisfed.org/docs/api/terms_of_use.html",
        "codes": [
            "FRED_API_AI_SYSTEM_USE_RESTRICTIONS_APPLY",
            "THIRD_PARTY_INDEX_COPYRIGHT_NOT_OVERRIDDEN_BY_API",
            "COPYRIGHT_OWNER_PERMISSION_FOR_NONPERSONAL_USE_UNVERIFIED",
        ],
        "next_evidence": "WRITTEN_RIGHTS_FOR_AI_USE_AND_NASDAQ100_SERIES",
    },
    "nasdaq_data_link": {
        "terms_url": "https://data.nasdaq.com/about/terms",
        "other_official_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=DN2026-5",
        "review_date": "2026-11-05",
        "codes": [
            "2026_11_01_NASDAQ_DATA_LINK_TERMS_IN_EFFECT",
            "EXACT_NDX_INSTRUMENT_COVERAGE_NOT_PROVEN",
            "LICENSE_ORDER_FORM_AND_ACCOUNT_ENTITLEMENT_REQUIRED",
            "EXTERNAL_DERIVED_ANALYTICS_AND_SAAS_RIGHTS_NOT_GRANTED_BY_DEFAULT",
            "INDEX_OWNER_POLICY_MAY_REQUIRE_SEPARATE_PERMISSION",
        ],
        "next_evidence": "EXACT_NDX_SERIES_ORDER_FORM_LICENSE_AI_ANALYTICS_DISPLAY_SCOPE",
    },
    "nasdaq_gids": {
        "terms_url": "https://www.nasdaq.com/products/global-indexes/data/gids",
        "other_official_url": "https://www.nasdaqtrader.com/TraderNews.aspx?id=DN2026-5",
        "codes": [
            "GIDS_NEW_CLIENT_DELAYED_LICENSE_NOT_OFFERED_SINCE_2026_09_01",
            "INDEX_DATA_DISTRIBUTION_ENTITLEMENT_UNVERIFIED",
            "PERFORMANCE_BENCHMARK_LICENSE_IF_APPLICABLE",
        ],
        "next_evidence": "EXACT_NDX_EOD_OR_REAL_TIME_LICENSE_AND_BENCHMARK_SCOPE",
    },
}



def evaluate_provider(*, provider: str, intended_use: str) -> dict[str, Any]:
    """Publish a zero-I/O rights decision; never accept self-asserted clearance.

    For a genuine vendor-data workflow, separate proof of instrument coverage,
    account entitlements, derived-data permissions, and owner approval remains
    mandatory outside this static preflight, including for contest judges.
    """
    if type(provider) is not str or provider not in _CANDIDATES:
        raise ValueError("UNKNOWN_PROVIDER")
    if type(intended_use) is not str or intended_use not in _USES:
        raise ValueError("UNKNOWN_INTENDED_USE")
    coverage, url = _CANDIDATES[provider]
    legal = _LEGAL_GAPS[provider]
    return {
        "schema": "kuodra.provider-rights-preflight.v1",
        "provider": provider,
        "intended_use": intended_use,
        "published_ndx_coverage": coverage,
        "published_information_url": url,
        "public_terms_reviewed_kst": legal.get("review_date", "2026-11-03"),
        "official_terms_url": legal["terms_url"],
        "official_secondary_url": legal["other_official_url"],
        "license_blocker_codes": list(legal["codes"]),
        "required_next_evidence": legal["next_evidence"],
        "intended_use_is_already_licensed": False,
        "ai_system_use_rights_verified": False,
        "exact_instrument_and_lookback_coverage_verified": False,
        "source_update_time_verified": False,
        "request_execution_authorized": False,
        "status": "BLOCKED_VENDOR_RIGHTS_AND_OWNER_APPROVAL_REQUIRED",
        "reason_code": "PUBLIC_CATALOG_AND_PRICE_ARE_NOT_A_LICENSE",
        "account_entitlement_verified": False,
        "ndx_identity_independently_verified": False,
        "data_use_permission_verified": False,
        "derived_analytics_display_permission_verified": False,
        "redistribution_permission_verified": False,
        "owner_network_approval_received": False,
        "network_requests_executed": 0,
        "paid_services_activated": False,
        "trade_executed": False,
        "guard_decision": "HOLD",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only NDX provider rights preflight (zero network)")
    parser.add_argument("--provider", choices=sorted(_CANDIDATES), required=True)
    parser.add_argument("--use", choices=sorted(_USES), required=True)
    args = parser.parse_args(argv)
    print(json.dumps(evaluate_provider(provider=args.provider, intended_use=args.use),
                     ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 2  # Blocked is intentional, never interpreted as execution clearance.


if __name__ == "__main__":
    raise SystemExit(main())
