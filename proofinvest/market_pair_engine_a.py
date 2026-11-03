"""P141: bind a daily stock source to a *real index series* for Engine A.

The paired, exact-calendar inputs are only descriptive and unauthenticated.
No ETF proxy, forward filling, lookahead into an issuer's unpublished 10-K,
LLM call, SEC/provider HTTP, Guard override, persistent cache or trade.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import re
from typing import Any

_BENCHMARK_SYMBOL = {"NASDAQ_100": "NDX", "S&P_500": "SPX", "DJIA": "DJI"}
_TICKER = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}\Z", re.ASCII)
_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_VALUE = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,8})?\Z", re.ASCII)
_PUBLIC_DOCUMENTATION = "https://www.alphavantage.co/documentation/"


def _blocked(reason: str) -> dict[str, Any]:
    return {"schema": "kuodra.p141-market-pair-engine-a.v1",
            "status": "BLOCKED", "reason_code": reason,
            "market_analysis": None, "matched_observation_count": 0,
            "source_authenticated": False,
            "source_rights_verified": False,
            "point_in_time_verified": False,
            "guard_executed": False, "ai_agent_executed": False,
            "trade_executed": False, "network_requests": 0,
            "full_a_b_c_ready": False}


def _date(x: Any) -> date:
    if type(x) is not str:
        raise ValueError("INVALID_DATE")
    day = date.fromisoformat(x)
    if day.isoformat() != x:
        raise ValueError("NONCANONICAL_DATE")
    return day


def _points(receipt: dict, *, kind: str) -> dict[str, str]:
    rows = receipt.get("close_observations")
    if type(rows) is not list or not 31 <= len(rows) <= 100:
        raise ValueError("INVALID_PRICE_POINT_COUNT")
    points: dict[str, str] = {}
    for row in rows:
        if type(row) is not dict or set(row) != {"date", "close"}:
            raise ValueError("INVALID_PRICE_ROW_FIELDS")
        day, value = row["date"], row["close"]
        observed = _date(day)
        if observed.weekday() >= 5 or type(value) is not str or not _VALUE.fullmatch(value):
            raise ValueError("PRICE_POINT_INVALID")
        if day in points or not (0 < float(value) < 1e10):
            raise ValueError("DUPLICATE_OR_BAD_PRICE")
        points[day] = value
    if sorted(points) != list(points):
        raise ValueError("PRICE_ORDER_INVALID")
    if receipt.get("first_date") != min(points) or receipt.get("last_date") != max(points):
        raise ValueError("RECEIPT_DATE_MISMATCH")
    if receipt.get("point_count") != len(points):
        raise ValueError("RECEIPT_COUNT_MISMATCH")
    return points


def build_market_reality_payload(*, stock: dict, index: dict,
                                 ticker: str, issuer_cik: str,
                                 filing_date: str, as_of: str,
                                 benchmark: str = "NASDAQ_100") -> dict:
    """Pure conversion to pre-existing market_reality.v1 math contract.

    Caller-supplied issuer CIK and filing date are *not* independently
    authenticated; the as-of metadata is the local calculation date and is
    NOT a certified vendor publication timestamp.
    """
    if (type(stock) is not dict or type(index) is not dict
            or type(ticker) is not str or not _TICKER.fullmatch(ticker)
            or type(issuer_cik) is not str or not _CIK.fullmatch(issuer_cik)
            or issuer_cik == "0000000000"
            or type(benchmark) is not str or benchmark not in _BENCHMARK_SYMBOL):
        raise ValueError("PAIR_ISSUER_OR_BENCHMARK_INVALID")
    cutoff, filing = _date(as_of), _date(filing_date)
    if filing >= cutoff:
        raise ValueError("FILING_NOT_AVAILABLE_BEFORE_AS_OF")
    if (stock.get("schema") != "kuodra.alpha-vantage-daily-source.v1"
            or stock.get("status") != "PRICE_ONLY_UNVERIFIED"
            or stock.get("provider") != "alpha_vantage"
            or stock.get("ticker") != ticker
            or stock.get("as_of") != as_of
            or stock.get("basis") != "PRICE_ONLY_CLOSE"
            or stock.get("issuer_authenticated") is not False
            or stock.get("market_data_rights_verified") is not False
            or stock.get("trade_executed") is not False
            or stock.get("requests_attempted") not in (0, 1)
            or index.get("schema") != "kuodra.alpha-vantage-official-index.v1"
            or index.get("status") != "OFFICIAL_INDEX_SYMBOL_RESPONSE_UNVERIFIED"
            or index.get("provider") != "alpha_vantage"
            or index.get("benchmark") != benchmark
            or index.get("index_symbol") != _BENCHMARK_SYMBOL[benchmark]
            or index.get("as_of") != as_of
            or index.get("basis") != "PRICE_ONLY_CLOSE"
            or index.get("provider_response_authenticated") is not False
            or index.get("source_rights_verified") is not False
            or index.get("premium_entitlement_verified") is not False
            or index.get("trade_executed") is not False
            or index.get("requests_attempted") not in (0, 1)):
        raise ValueError("PAIR_SOURCE_CONTRACT_INVALID")
    for x in (stock, index):
        h = x.get("source_sha256")
        if type(h) is not str or not _SHA.fullmatch(h):
            raise ValueError("SOURCE_HASH_INVALID")
    stock_map = _points(stock, kind="stock")
    index_map = _points(index, kind="index")
    common = sorted(set(stock_map) & set(index_map))
    # Missing sessions must not be quietly forward-filled or interpolated.
    if (len(common) < 31 or len(common) * 5 < len(stock_map) * 4
            or len(common) * 5 < len(index_map) * 4):
        raise ValueError("PRICE_INDEX_CALENDAR_NOT_COMPATIBLE")
    common = common[-100:]
    if _date(common[0]) <= filing:
        raise ValueError("PRICE_WINDOW_NOT_AFTER_SEC_FILING")
    if (cutoff - _date(common[-1])).days > 7:
        raise ValueError("STALE_PRICE_OR_INDEX_FOR_AS_OF")
    for older, newer in zip(common, common[1:]):
        if not 1 <= (_date(newer) - _date(older)).days <= 7:
            raise ValueError("MISSING_CONSECUTIVE_TRADING_SESSIONS")
    def series(points: dict[str, str], h: str) -> dict:
        return {"source": {"provider": "ALPHA_VANTAGE_RESPONSE_UNVERIFIED",
                            "url": _PUBLIC_DOCUMENTATION,
                            "published_at": as_of, "sha256": h},
                "observations": [{"date": day, "value": points[day]}
                                 for day in common]}
    return {"schema": "kuodra.market-reality.v1",
            "issuer_cik": issuer_cik, "as_of": as_of,
            "symbol": ticker, "benchmark": benchmark,
            "return_basis": "PRICE_ONLY_CLOSE",
            "security": series(stock_map, stock["source_sha256"]),
            "index": series(index_map, index["source_sha256"])}


def analyze_price_index_pair(*, stock: dict, index: dict, ticker: str,
                             issuer_cik: str, filing_date: str, as_of: str,
                             benchmark: str = "NASDAQ_100") -> dict[str, Any]:
    """Actually invoke existing Decimal OLS Engine A, never issue an API GET."""
    try:
        payload = build_market_reality_payload(
            stock=stock, index=index, ticker=ticker, issuer_cik=issuer_cik,
            filing_date=filing_date, as_of=as_of, benchmark=benchmark)
        from .market_reality import analyze_market_reality
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        result = analyze_market_reality(
            payload, expected_issuer_cik=issuer_cik,
            analysis_as_of=as_of, sec_review=None,
            uploaded_sha256=sha256(data).hexdigest(),
        )
        if (type(result) is not dict
                or result.get("status") not in (
                    "REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE")
                or result.get("market_bubble_proven") is not False
                or result.get("trade_signal") is not False
                or result.get("guard_policy_modified") is not False
                or result.get("source_authenticated") is not False):
            return _blocked("ENGINE_A_TRUST_CONTRACT_INVALID")
        return {
            **_blocked(""), "status": "ENGINE_A_PRICE_INDEX_DESCRIPTIVE_UNVERIFIED",
            "reason_code": "NO_PUBLISHER_AUTH_OR_INDEX_REUSE_RIGHTS_PROOF",
            "ticker": ticker, "issuer_cik": issuer_cik, "as_of": as_of,
            "benchmark": benchmark, "stock_response_sha256": stock["source_sha256"],
            "index_response_sha256": index["source_sha256"],
            "matched_observation_count": len(payload["index"]["observations"]),
            "source_payload_sha256": sha256(data).hexdigest(),
            "market_analysis": {
                "status": result["status"],
                "security_return_pct": result.get("security_return_pct"),
                "benchmark_return_pct": result.get("benchmark_return_pct"),
                "beta": result.get("beta"),
                "regression_intercept_daily_pct": result.get(
                    "regression_intercept_daily_pct"),
                "r_squared": result.get("r_squared"),
            },
        }
    except (ValueError, TypeError, KeyError, AttributeError,
            OverflowError, RecursionError):
        return _blocked("SOURCE_OR_ENGINE_A_INPUT_UNAVAILABLE")


def fetch_and_analyze_market_pair(*, ticker: str, issuer_cik: str,
                                  filing_date: str, as_of: str,
                                  api_key: str | None, benchmark: str = "NASDAQ_100",
                                  explicit_click: bool = False,
                                  provider_rights_approved: bool = False,
                                  premium_entitlement_approved: bool = False,
                                  stock_transport=None, index_transport=None) -> dict:
    """Fail-closed single-click plan: at most one stock and one index GET.

    The issuer CIK/date must come from a *separately source-bound* filing review.
    No API GET if that metadata, entitlement, target or cutoff is invalid.
    Granted operation permission does not authenticate data origin or rights.
    """
    import os
    if (not (explicit_click and provider_rights_approved
             and premium_entitlement_approved)
            or any(os.environ.get(k) != "1" for k in (
                "KUODRA_ENABLE_ALPHA_VANTAGE_DAILY",
                "KUODRA_ENABLE_ALPHA_VANTAGE_INDEX",
                "KUODRA_ALPHA_VANTAGE_INDEX_PREMIUM_APPROVED",
                "KUODRA_ALPHA_VANTAGE_RIGHTS_APPROVED"))):
        return _blocked("PROVIDER_OR_PREMIUM_EXECUTION_NOT_APPROVED")
    try:
        if (type(ticker) is not str or not _TICKER.fullmatch(ticker)
                or type(issuer_cik) is not str or not _CIK.fullmatch(issuer_cik)
                or issuer_cik == "0000000000"
                or type(benchmark) is not str or benchmark not in _BENCHMARK_SYMBOL
                or type(api_key) is not str or not api_key.isascii()
                or not 8 <= len(api_key) <= 80 or not api_key.isalnum()
                or _date(filing_date) >= _date(as_of)
                or _date(as_of) > date.today()):
            return _blocked("INVALID_PRE_NETWORK_SOURCE_OR_CREDENTIALS")
    except (TypeError, ValueError, OverflowError):
        return _blocked("INVALID_PRE_NETWORK_SOURCE_OR_CREDENTIALS")
    from .market_provider_alpha_vantage import fetch_daily_close
    from .market_provider_alpha_vantage_index import fetch_index_daily
    stock = fetch_daily_close(
        ticker=ticker, as_of=as_of, api_key=api_key,
        explicit_click=True, rights_approved=True,
        transport=stock_transport)
    if stock.get("status") != "PRICE_ONLY_UNVERIFIED":
        return {**_blocked("STOCK_VENDOR_UNAVAILABLE"),
                "network_requests": stock.get("requests_attempted", 0)}
    index = fetch_index_daily(
        benchmark=benchmark, as_of=as_of, api_key=api_key,
        explicit_click=True, rights_approved=True, premium_approved=True,
        transport=index_transport)
    if index.get("status") != "OFFICIAL_INDEX_SYMBOL_RESPONSE_UNVERIFIED":
        return {**_blocked("INDEX_VENDOR_UNAVAILABLE"),
                "network_requests": (stock.get("requests_attempted", 0)
                                     + index.get("requests_attempted", 0))}
    report = analyze_price_index_pair(
        stock=stock, index=index, ticker=ticker, issuer_cik=issuer_cik,
        filing_date=filing_date, as_of=as_of, benchmark=benchmark)
    report["network_requests"] = (
        stock.get("requests_attempted", 0) + index.get("requests_attempted", 0))
    return report
