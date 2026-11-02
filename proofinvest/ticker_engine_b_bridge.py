"""P124 source-bound Engine B from the exact local single-ticker 10-K.

Reuse KUODRA's existing accounting-integrity calculation. All calculations
are local, descriptive and UNAUTHENTICATED; never infer fraud, buy/sell or
override Guard. Missing earnings/cash facts are UNAVAILABLE, not healthy.
"""
from __future__ import annotations

from hashlib import sha256
from .ticker_sec_financial_bridge import inspect_collected_annual_revenue
from .ticker_sec_original_guard_preview import inspect_original_guard_preview
from .accounting_integrity import review_accounting_integrity


def _blocked(reason: str, digest: str | None = None) -> dict:
    return {
        "schema": "kuodra.ticker-engine-b-source-join.v1",
        "status": "UNAVAILABLE", "reason_code": reason,
        "companyfacts_sha256": digest,
        "net_income_usd": None, "operating_cashflow_usd": None,
        "cash_to_net_income_pct": None,
        "earnings_cash_signal": "NOT_CHECKED",
        "receivables_minus_revenue_growth_pp": None,
        "inventory_minus_revenue_growth_pp": None,
        "working_capital_review_status": "NOT_CHECKED",
        "working_capital_signals": [],
        "source_authenticated": False, "source_rights_verified": False,
        "accounting_fraud_proven": False, "guard_executed": False,
        "audit_written": False, "trade_executed": False,
        "external_http_requests": 0,
    }


def inspect_ticker_engine_b(
    receipt: dict, sources: dict[str, bytes],
    *, expected_revenue: dict | None = None,
    expected_original: dict | None = None,
) -> dict:
    """Recompute source-bound facts: no assumption of SEC-origin authenticity."""
    if type(receipt) is not dict or type(sources) is not dict:
        return _blocked("FOUR_PINNED_FILES_REQUIRED")
    digest = (receipt.get("source_sha256") or {}).get("companyfacts")
    base = _blocked("INVALID_SOURCE_BINDING", digest)
    try:
        if (receipt.get("schema") != "kuodra.local-sec-source-receipt.v1"
                or receipt.get("status") != "local_four_sources_unverified"
                or receipt.get("network_requests") != 0
                or receipt.get("source_authenticated") is not False
                or receipt.get("source_rights_verified") is not False):
            return base
        revenue = inspect_collected_annual_revenue(receipt, sources)
        if (revenue.get("status") != "REVENUE_CALCULATED_UNVERIFIED"
                or expected_revenue is not None and expected_revenue != revenue):
            return _blocked("REVENUE_NOT_REPLAYED", digest)
        original = inspect_original_guard_preview(
            receipt, sources, expected_revenue=revenue)
        if (expected_original is not None and original != expected_original
                or original.get("status") != "ORIGINAL_CONTEXT_MATCH_UNVERIFIED"
                or original.get("guard_preview", {}).get("decision") != "HOLD"):
            return _blocked("ORIGINAL_CONTEXT_NOT_ELIGIBLE", digest)
        raw = sources["companyfacts"]
        if type(raw) is not bytes or sha256(raw).hexdigest() != digest:
            return _blocked("COMPANYFACTS_BYTES_CHANGED", digest)
        reviewed = review_accounting_integrity(
            raw, cik=revenue["issuer_cik"], accession=revenue["accession"],
            current_end=revenue["current_end"], prior_end=revenue["prior_end"],
            as_of=revenue["as_of"],
        )
        if reviewed.get("status") != "reviewed_unverified":
            return _blocked("ACCOUNTING_FACTS_MISSING_OR_INVALID", digest)
        if (reviewed.get("companyfacts_sha256") != digest
                or reviewed.get("period_end") != revenue["current_end"]
                or reviewed.get("filing_date") != revenue["filing_date"]
                or reviewed.get("source_authenticated") is not False
                or reviewed.get("accounting_fraud_proven") is not False
                or reviewed.get("guard_policy_modified") is not False
                or reviewed.get("trade_executed") is not False
                or reviewed.get("live_api_called") is not False):
            return _blocked("ACCOUNTING_SOURCE_PERIOD_TRUST_INVALID", digest)
        return {
            **_blocked("", digest), "status": "REVIEWED_UNVERIFIED",
            "reason_code": "DESCRIPTIVE_CASH_EARNINGS_AND_WC_ONLY",
            "net_income_usd": reviewed["net_income_usd"],
            "operating_cashflow_usd": reviewed["operating_cashflow_usd"],
            "cash_to_net_income_pct": reviewed["cash_to_net_income_pct"],
            "earnings_cash_signal": reviewed["earnings_cash_signal"],
            "receivables_minus_revenue_growth_pp":
                reviewed["receivables_minus_revenue_growth_pp"],
            "inventory_minus_revenue_growth_pp":
                reviewed["inventory_minus_revenue_growth_pp"],
            "working_capital_review_status":
                reviewed["working_capital_review_status"],
            "working_capital_signals": list(reviewed["working_capital_signals"]),
        }
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError,
            OverflowError):
        return _blocked("ACCOUNTING_SOURCE_UNAVAILABLE", digest)
