"""P194: issuer-first-party FY2026 observed revenue reference set, no API.

Small PUBLIC first-party reported financial values, independently transcribed
as of 2026-11-05 KST. These enterprises have different fiscal cutoffs and
business mixes; this is NOT a licensed, comparable same-sector peer basket.
No raw document bytes, market prices, NDX, originals, model or trades.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

_REVIEWED = date(2026, 11, 5)
# Public facts, USD millions, reported GAAP consolidated annual revenue.
# Issuer-published reports, independently opened/reviewed as of _REVIEWED.
_REFERENCES = {
    "AAPL": {
        "issuer": "Apple Inc.",
        "source": "https://www.sec.gov/Archives/edgar/data/320193/"
                  "000032019326000026/aapl-20260926.htm",
        "source_kind": "SEC_EDGAR_10K_PUBLIC_HTML_REFERENCE",
        "accession": "0000320193-26-000026",
        "fy2026_end": "2026-09-26",
        "fy2025_end": "2025-09-27",
        "revenue2026": "478834",
        "revenue2025": "416161",
        "business_mix": "CONSUMER_DEVICES_AND_SERVICES",
    },
    "MSFT": {
        "issuer": "Microsoft Corporation",
        "source": "https://www.microsoft.com/investor/reports/ar26/index.html",
        "source_kind": "PUBLISHER_ANNUAL_REPORT_PUBLIC_HTML_REFERENCE",
        "accession": None,
        "fy2026_end": "2026-06-30",
        "fy2025_end": "2025-06-30",
        "revenue2026": "331839",
        "revenue2025": "281724",
        "business_mix": "SOFTWARE_CLOUD_AND_COMPUTING",
    },
    "DELL": {
        "issuer": "Dell Technologies Inc.",
        "source": "https://investors.delltechnologies.com/sec-filings/"
                  "all-sec-filings/content/0001571996-26-000008/"
                  "dell-20260130.htm",
        "source_kind": "PUBLISHER_IR_10K_PUBLIC_HTML_REFERENCE",
        "accession": "0001571996-26-000008",
        "fy2026_end": "2026-01-30",
        "fy2025_end": "2025-01-31",
        "revenue2026": "113538",
        "revenue2025": "95567",
        "business_mix": "PCS_ENTERPRISE_HARDWARE_SERVICES",
    },
}
_EXPECTED = ("AAPL", "MSFT", "DELL")


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.public-fy2026-cross-issuer-reference.v1",
        "status": "BLOCKED",
        "reason_code": reason,
        "issuer_rows": [],
        "source_bytes_authenticated": False,
        "provider_peer_license_verified": False,
        "same_sector_comparability_verified": False,
        "aligned_fiscal_periods_verified": False,
        "full_engine_c_peer_inference_ready": False,
        "market_ndx_stock_ready": False,
        "ai_agent_executed": False,
        "guard_policy_preview": "HOLD",
        "human_review_required": True,
        "investment_advice": False,
        "trade_executed": False,
        "external_network_requests": 0,
        "raw_source_documents_persisted": False,
        "external_sharing_rights_verified": False,
        "model_processing_rights_verified": False,
    }


def public_primary_revenue_values() -> dict[str, dict[str, str]]:
    """Fresh copy; caller mutation never changes reviewed reference facts."""
    return {
        ticker: {"2026": _REFERENCES[ticker]["revenue2026"],
                 "2025": _REFERENCES[ticker]["revenue2025"]}
        for ticker in _EXPECTED
    }


def _positive_integer(value: object) -> Decimal:
    if (type(value) is not str or not value.isascii()
            or not value.isdigit() or not 0 < len(value) <= 12):
        raise ValueError("UNTRUSTED_REVENUE_TYPE")
    n = Decimal(value)
    if n <= 0:
        raise ValueError("NONPOSITIVE_REVENUE")
    return n


def review_public_fiscal_peers(
    *, as_of: str, revenue_values: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Show real publicly reported *reference growth*, never a sector score.

    All rows must match independently reviewed SEC/issuer public financial
    statement figures exactly. This strict static offline contract purposely
    does not assert publisher raw-byte authenticity or market-data rights.
    """
    if type(as_of) is not str or len(as_of) != 10:
        return _base("AS_OF_REQUIRED")
    try:
        d = date.fromisoformat(as_of)
        if d.isoformat() != as_of:
            return _base("AS_OF_NONCANONICAL")
    except ValueError:
        return _base("AS_OF_INVALID")
    if d != _REVIEWED:
        return _base("PUBLIC_CATALOG_ONLY_VALID_AT_REVIEWED_AS_OF")
    if type(revenue_values) is not dict or set(revenue_values) != set(_EXPECTED):
        return _base("EXACT_THREE_PUBLIC_ISSUER_REFERENCES_REQUIRED")
    rows = []
    try:
        for symbol in _EXPECTED:
            observed = revenue_values[symbol]
            if type(observed) is not dict or set(observed) != {"2025", "2026"}:
                return _base("EXACT_FISCAL_YEAR_KEYS_REQUIRED")
            current = _positive_integer(observed["2026"])
            prior = _positive_integer(observed["2025"])
            expected = _REFERENCES[symbol]
            if (current != Decimal(expected["revenue2026"])
                    or prior != Decimal(expected["revenue2025"])):
                return _base("PUBLISHED_REFERENCE_REVENUE_MISMATCH")
            if (date.fromisoformat(expected["fy2026_end"]) > d
                    or date.fromisoformat(expected["fy2025_end"]) > d):
                return _base("FUTURE_FISCAL_PERIOD_NOT_ALLOWED")
            growth = (current / prior - 1) * 100
            rows.append({
                "ticker": symbol,
                "issuer": expected["issuer"],
                "fy2026_end": expected["fy2026_end"],
                "fy2025_end": expected["fy2025_end"],
                "fy2026_revenue_usd_millions": str(current),
                "fy2025_revenue_usd_millions": str(prior),
                "yoy_revenue_growth_pct": str(
                    growth.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "business_mix": expected["business_mix"],
                "primary_public_report": expected["source"],
                "reference_kind": expected["source_kind"],
                "accession_if_known": expected["accession"],
            })
    except (ValueError, TypeError, InvalidOperation, OverflowError):
        return _base("PUBLIC_REVENUE_DECIMAL_RECALCULATION_INVALID")
    ends = {x["fy2026_end"] for x in rows}
    mixes = {x["business_mix"] for x in rows}
    if len(ends) == 1 or len(mixes) == 1:
        # A future catalog update must have its intended limitation reconsidered.
        return _base("P194_FISCAL_OR_MIX_ASSUMPTIONS_CHANGED")
    return {
        **_base("PUBLIC_ISSUER_REVENUE_ONLY_NOT_COMPARABLE_SECTOR"),
        "status": "INDICATIVE_REAL_PRIMARY_PUBLIC_YOY_FISCAL_REVENUE_ONLY",
        "catalog_reviewed_as_of": d.isoformat(),
        "currency": "USD",
        "unit": "MILLIONS",
        "issuer_rows": rows,
        "reference_count": len(rows),
        "fiscal_cutoffs_differ": True,
        "business_models_differ": True,
        "consolidated_revenue_growth_only": True,
        "sector_rank_or_growth_conclusion": "UNAVAILABLE_UNALIGNED_PERIODS_AND_MIX",
        "reconcile_same_period_peers_before_engine_c": True,
    }
