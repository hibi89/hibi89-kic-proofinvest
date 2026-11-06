"""Offline 3-5 company Engine A panel sharing one actual I:NDX response.

Accepts only local operator-held Massive-format JSON. No HTTP, credentials,
vendor response persistence, external model, trading or rights promotion.
The cache is bounded to five stocks plus I:NDX and lives in process memory.
"""
from __future__ import annotations
from datetime import date
from typing import Any
from .market_provider_massive import parse_massive_daily, analyze_massive_pair

_ALLOWED = frozenset({"NVDA", "AAPL", "MSFT", "AMZN", "GOOGL"})
_NDX = "I:NDX"

def _day(value: str) -> date:
    if type(value) is not str:
        raise ValueError("DATE_INVALID")
    result = date.fromisoformat(value)
    if value != result.isoformat():
        raise ValueError("DATE_NONCANONICAL")
    return result

class LocalMassivePanel:
    """In-process six-slot provider snapshot cache; no raw source on disk."""
    def __init__(self) -> None:
        self._receipts: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        self._receipts.clear()

    @staticmethod
    def _summary(receipt: dict[str, Any], status: str) -> dict[str, Any]:
        return {"status": status, "symbol": receipt["symbol"],
                "as_of": receipt["as_of"], "last_date": receipt["last_date"],
                "point_count": receipt["point_count"],
                "source_sha256": receipt["source_sha256"],
                "provider_data_authenticated": False,
                "market_use_rights_verified": False, "network_requests": 0}

    def ingest(self, raw: bytes, *, symbol: str, as_of: str) -> dict[str, Any]:
        """Validate, deduplicate and replace an overlapping rolling snapshot.

        A changed historical bar is blocked for manual split/vendor review,
        never silently overwritten. This is a FULL overlapping snapshot update,
        not a single-row HTTP incremental endpoint.
        """
        if type(symbol) is not str or symbol not in (_ALLOWED | {_NDX}):
            raise ValueError("PANEL_SYMBOL_NOT_ALLOWED")
        _day(as_of)
        incoming = parse_massive_daily(raw, symbol=symbol, as_of=as_of,
                                       index=(symbol == _NDX))
        previous = self._receipts.get(symbol)
        if previous is not None:
            before, after = _day(previous["as_of"]), _day(as_of)
            if after < before:
                raise ValueError("STALE_SNAPSHOT_NOT_ACCEPTED")
            if after == before:
                if incoming["source_sha256"] != previous["source_sha256"]:
                    raise ValueError("SAME_ASOF_DIFFERENT_SOURCE_REVIEW_REQUIRED")
                return self._summary(previous, "CACHE_HIT")
            old = {x["date"]: x["close"] for x in previous["close_observations"]}
            new = {x["date"]: x["close"] for x in incoming["close_observations"]}
            overlap = old.keys() & new.keys()
            if len(overlap) < 20:
                raise ValueError("INSUFFICIENT_INCREMENTAL_OVERLAP")
            if any(old[day] != new[day] for day in overlap):
                raise ValueError("HISTORICAL_REVISION_MANUAL_REVIEW_REQUIRED")
            if incoming["last_date"] <= previous["last_date"]:
                raise ValueError("NO_NEW_TRADING_OBSERVATION")
        self._receipts[symbol] = incoming
        return self._summary(incoming, "INGESTED_UNVERIFIED")

    def refresh_plan(self, *, symbols: list[str], as_of: str) -> dict[str, Any]:
        """Zero-network manual import plan with 5/min Basic rate batches."""
        target = _day(as_of)
        if (type(symbols) is not list or not 3 <= len(symbols) <= 5
                or len(set(symbols)) != len(symbols)
                or any(type(s) is not str or s not in _ALLOWED for s in symbols)):
            raise ValueError("PANEL_UNIVERSE_INVALID")
        required = [_NDX, *symbols]
        missing = [s for s in required
                   if s not in self._receipts
                   or _day(self._receipts[s]["as_of"]) < target]
        return {"schema": "kuodra.local-massive-refresh-plan.v1",
                "as_of": as_of, "instruments": required,
                "manual_import_needed": missing,
                "estimated_provider_requests_if_separately_approved": len(missing),
                "batches_max_five_per_minute": [
                    missing[i:i + 5] for i in range(0, len(missing), 5)],
                "auto_refresh_enabled": False, "network_requests": 0,
                "provider_access_authorized": False}

    @staticmethod
    def _blocked(reason: str, *, as_of: str, missing: list[str]) -> dict:
        return {"schema": "kuodra.local-massive-ndx-panel.v1",
                "status": "BLOCKED", "reason_code": reason, "as_of": as_of,
                "missing_or_stale_instruments": missing, "issuers": [],
                "network_requests": 0, "guard_decision": "HOLD",
                "source_authenticated": False, "source_rights_verified": False,
                "public_display_allowed": False, "full_a_b_c_ready": False,
                "trade_executed": False}

    def analyze(self, *, companies: list[dict[str, str]],
                as_of: str) -> dict[str, Any]:
        """Run independent existing Decimal regressions with one shared NDX."""
        _day(as_of)
        if (type(companies) is not list or not 3 <= len(companies) <= 5
                or any(type(c) is not dict
                       or set(c) != {"ticker", "issuer_cik", "filing_date"}
                       or type(c["ticker"]) is not str
                       or c["ticker"] not in _ALLOWED
                       or type(c["issuer_cik"]) is not str
                       or type(c["filing_date"]) is not str for c in companies)):
            raise ValueError("PANEL_COMPANIES_INVALID")
        symbols = [x["ticker"] for x in companies]
        ciks = [x["issuer_cik"] for x in companies]
        if len(set(symbols)) != len(symbols) or len(set(ciks)) != len(ciks):
            raise ValueError("DUPLICATE_COMPANY_IDENTITY")
        plan = self.refresh_plan(symbols=symbols, as_of=as_of)
        if plan["manual_import_needed"]:
            return self._blocked("MISSING_OR_STALE_DAILY_SOURCE",
                                 as_of=as_of, missing=plan["manual_import_needed"])
        ndx = self._receipts[_NDX]
        details = []
        for company in companies:
            result = analyze_massive_pair(
                stock=self._receipts[company["ticker"]], ndx=ndx,
                ticker=company["ticker"], issuer_cik=company["issuer_cik"],
                filing_date=company["filing_date"], as_of=as_of)
            if result.get("status") != "ENGINE_A_MASSIVE_DESCRIPTIVE_UNVERIFIED":
                return self._blocked("ISSUER_CALENDAR_OR_ENGINE_A_UNAVAILABLE",
                                     as_of=as_of, missing=[])
            details.append({
                "ticker": company["ticker"], "issuer_cik": company["issuer_cik"],
                "filing_date": company["filing_date"],
                "matched_observation_count": result["matched_observation_count"],
                "matched_period_start": result["matched_period_start"],
                "matched_period_end": result["matched_period_end"],
                "stock_response_sha256": result["stock_response_sha256"],
                "index_response_sha256": result["index_response_sha256"],
                "market_analysis": result["market_analysis"],
                "guard_decision": "HOLD"})
        return {"schema": "kuodra.local-massive-ndx-panel.v1",
                "status": "MULTI_ISSUER_ENGINE_A_DESCRIPTIVE_UNVERIFIED",
                "as_of": as_of, "benchmark": "NASDAQ_100",
                "index_symbol": _NDX, "issuer_count": len(details),
                "ndx_snapshot_sha256": ndx["source_sha256"], "issuers": details,
                "network_requests": 0, "retries": 0, "guard_decision": "HOLD",
                "source_authenticated": False, "source_rights_verified": False,
                "ai_data_use_rights_verified": False, "public_display_allowed": False,
                "commercial_reuse_allowed": False, "full_a_b_c_ready": False,
                "trade_executed": False, "fundamental_price_divergence_completed": False}
