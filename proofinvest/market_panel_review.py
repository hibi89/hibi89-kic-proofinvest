"""Human-triggered local-only P270 Massive-shaped market-data review.

Every invocation recreates the bounded in-memory six-slot Engine A cache.
This does not retrieve vendor data, authenticate prices, grant licensed use,
or allow display outside the owner-only loopback application.
"""
from __future__ import annotations

from typing import Any
from .market_panel_offline import LocalMassivePanel

_ALLOWED = ("NVDA", "AAPL", "MSFT", "AMZN", "GOOGL")
_CIK = {
    "NVDA": "0001045810",
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "AMZN": "0001018724",
    "GOOGL": "0001652044",
}
_MAX_UPLOAD = 262144


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.local-massive-ndx-panel.v1",
        "status": "BLOCKED", "reason_code": reason,
        "issuers": [], "network_requests": 0, "guard_decision": "HOLD",
        "source_authenticated": False, "source_rights_verified": False,
        "public_display_allowed": False, "full_a_b_c_ready": False,
        "trade_executed": False,
    }


def review_local_market_panel(
    sources: dict[str, bytes],
    symbols: list[str],
    filing_dates: dict[str, str],
    *,
    as_of: str,
) -> dict[str, Any]:
    """One-shot validate -> calculate -> discard; never cache uploaded bytes.

    CIK mapping is fixed for the five permitted candidate issuers, but a
    mapping is not proof that uploaded price bars originated from a vendor.
    """
    if (type(symbols) is not list or not 3 <= len(symbols) <= 5
            or len(set(symbols)) != len(symbols)
            or any(type(s) is not str or s not in _ALLOWED for s in symbols)
            or type(filing_dates) is not dict
            or set(filing_dates) != set(symbols)
            or any(type(d) is not str for d in filing_dates.values())
            or type(sources) is not dict
            or set(sources) != (set(symbols) | {"I:NDX"})
            or any(type(raw) is not bytes or not 0 < len(raw) <= _MAX_UPLOAD
                   for raw in sources.values())):
        return _blocked("MISSING_OR_INVALID_BOUNDED_OWNER_INPUT")
    try:
        panel = LocalMassivePanel()
        panel.ingest(sources["I:NDX"], symbol="I:NDX", as_of=as_of)
        for ticker in symbols:
            panel.ingest(sources[ticker], symbol=ticker, as_of=as_of)
        companies = [{"ticker": ticker, "issuer_cik": _CIK[ticker],
                      "filing_date": filing_dates[ticker]} for ticker in symbols]
        report = panel.analyze(companies=companies, as_of=as_of)
        # This provenance label is essential: raw source JSON can be forged.
        report["human_uploaded_local_only"] = True
        report["vendor_response_authenticity_verified"] = False
        report["issuer_filing_dates_operator_declared"] = True
        report["executable_network_calls"] = 0
        return report
    except (ValueError, TypeError, OverflowError, KeyError):
        return _blocked("LOCAL_MARKET_SOURCE_CALENDAR_OR_IDENTITY_REJECTED")


def verify_local_market_panel(
    report: dict[str, Any],
    sources: dict[str, bytes],
    symbols: list[str],
    filing_dates: dict[str, str],
    *,
    as_of: str,
) -> bool:
    """Replay from all original bytes before enabling a local JSON export."""
    if type(report) is not dict or report.get("status") != (
            "MULTI_ISSUER_ENGINE_A_DESCRIPTIVE_UNVERIFIED"):
        return False
    return report == review_local_market_panel(
        sources, symbols, filing_dates, as_of=as_of)
