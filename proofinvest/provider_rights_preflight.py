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
}
_USES = frozenset({"internal_research", "contest_judge_demo", "public_dashboard", "commercial_product"})


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
    return {
        "schema": "kuodra.provider-rights-preflight.v1",
        "provider": provider,
        "intended_use": intended_use,
        "published_ndx_coverage": coverage,
        "published_information_url": url,
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
