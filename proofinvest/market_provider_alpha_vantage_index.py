"""Premium Alpha Vantage *actual benchmark index* daily OHLC source, opt-in only.

Index symbols NDX/SPX/DJI use INDEX_DATA, NOT tradable ETF surrogates.
The endpoint is marked Premium in official docs (checked 2026-11-03).
No real fetch without separately approved premium entitlement, data-rights
and one explicit UI action; even then provider origin and reuse rights remain
unverified. No SEC calls, background jobs, persistence or trades.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
import re
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, HTTPSHandler, ProxyHandler, build_opener
import ssl

from .market_provider_alpha_vantage import _NoRedirect

_HOST = "https://www.alphavantage.co/query"
_BENCHMARKS = {"NASDAQ_100": "NDX", "S&P_500": "SPX", "DJIA": "DJI"}
_MAX_RESPONSE = 8_388_608
_MAX_ROWS = 16000
_PRICE = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,8})?\Z", re.ASCII)
_API_KEY = re.compile(r"[A-Za-z0-9]{8,80}\Z", re.ASCII)


def _blocked(code: str, attempts: int = 0) -> dict[str, Any]:
    return {
        "schema": "kuodra.alpha-vantage-official-index.v1",
        "status": "BLOCKED", "reason_code": code,
        "provider": "alpha_vantage", "benchmark": None, "index_symbol": None,
        "as_of": None, "close_observations": [], "source_sha256": None,
        "requests_attempted": attempts, "retries": 0,
        "provider_response_authenticated": False,
        "source_rights_verified": False,
        "premium_entitlement_verified": False,
        "full_a_b_c_ready": False, "trade_executed": False,
    }


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("DUPLICATE_INDEX_RESPONSE_KEY")
        obj[key] = value
    return obj


def _bad_constant(_value: str) -> None:
    raise ValueError("NON_FINITE_INDEX_VALUE")


def parse_index_daily_bytes(raw: bytes, *, benchmark: str, as_of: str) -> dict:
    """Parse only an unambiguous daily INDEX_DATA schema, fail-closed otherwise.

    The exact live paid JSON shape has NOT been personally tested. If an actual
    response differs, return BLOCKED rather than invent a valid index series.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_RESPONSE:
        raise ValueError("INDEX_RESPONSE_SIZE_INVALID")
    if type(benchmark) is not str or benchmark not in _BENCHMARKS:
        raise ValueError("UNSUPPORTED_INDEX_BENCHMARK")
    try:
        cutoff = date.fromisoformat(as_of)
        if type(as_of) is not str or as_of != cutoff.isoformat():
            raise ValueError("INDEX_AS_OF_INVALID")
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                             parse_constant=_bad_constant)
    except (ValueError, UnicodeError, TypeError, RecursionError) as exc:
        raise ValueError("INDEX_JSON_INVALID") from exc
    if type(payload) is not dict or any(key in payload for key in (
            "Information", "Note", "Error Message")):
        raise ValueError("PROVIDER_NOTICE_OR_INDEX_RESPONSE_INVALID")
    meta = payload.get("Meta Data")
    series = payload.get("Time Series (Daily)")
    symbol = _BENCHMARKS[benchmark]
    if (type(meta) is not dict or meta.get("2. Symbol") != symbol
            or type(series) is not dict or not 31 <= len(series) <= _MAX_ROWS):
        raise ValueError("INDEX_SYMBOL_OR_DAILY_SERIES_INVALID")
    points: list[tuple[str, str]] = []
    for day, row in series.items():
        if type(day) is not str or type(row) is not dict:
            raise ValueError("INDEX_ROW_INVALID")
        try:
            observed = date.fromisoformat(day)
        except ValueError as exc:
            raise ValueError("INDEX_DATE_INVALID") from exc
        if observed.isoformat() != day or observed.weekday() >= 5:
            raise ValueError("INDEX_NON_TRADING_OR_NONCANONICAL_DATE")
        value = row.get("4. close")
        if type(value) is not str or not _PRICE.fullmatch(value):
            raise ValueError("INDEX_CLOSE_INVALID")
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("INDEX_CLOSE_INVALID") from exc
        if not amount.is_finite() or amount <= 0:
            raise ValueError("INDEX_CLOSE_INVALID")
        if observed <= cutoff:
            points.append((day, value))
    if len(points) < 31:
        raise ValueError("INDEX_INSUFFICIENT_HISTORY_AS_OF")
    points.sort(key=lambda record: record[0])
    # For a bounded on-demand OLS, 100 trading sessions suffice; no original
    # decades-long index price body is written to disk or into a report.
    points = points[-100:]
    for (earlier, _), (later, _) in zip(points, points[1:]):
        if not 1 <= (date.fromisoformat(later) - date.fromisoformat(earlier)).days <= 7:
            raise ValueError("INDEX_DAY_GAP_INVALID")
    return {
        **_blocked(""), "status": "OFFICIAL_INDEX_SYMBOL_RESPONSE_UNVERIFIED",
        "reason_code": "PREMIUM_PROVIDER_RESPONSE_NOT_LICENSE_OR_ORIGIN_PROOF",
        "benchmark": benchmark, "index_symbol": symbol, "as_of": as_of,
        "first_date": points[0][0], "last_date": points[-1][0],
        "point_count": len(points),
        "close_observations": [{"date": day, "close": value}
                               for day, value in points],
        "source_sha256": sha256(raw).hexdigest(),
        "basis": "PRICE_ONLY_CLOSE",
    }


def _https_get_index(url: str) -> bytes:
    """Single official-domain TLS GET; no redirects, no retries, 8 MiB cap."""
    # Explicit direct TLS: do not route key-bearing URLs via ambient proxies.
    opener = build_opener(ProxyHandler({}), _NoRedirect(),
                          HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(Request(url, headers={"Accept": "application/json",
                                           "User-Agent": "KUODRA/1.0-entitlement-gated"}),
                     timeout=8) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("INDEX_HTTP_STATUS_INVALID")
        data = response.read(_MAX_RESPONSE + 1)
        if len(data) > _MAX_RESPONSE:
            raise ValueError("INDEX_RESPONSE_TOO_LARGE")
        return data


def fetch_index_daily(*, benchmark: str, as_of: str, api_key: str | None,
                      explicit_click: bool = False,
                      rights_approved: bool = False,
                      premium_approved: bool = False,
                      transport: Callable[[str], bytes] | None = None) -> dict:
    """No vendor I/O without premium, rights, operator and click gates.

    A request attempts precisely one HTTPS GET; no second try when missing,
    invalid, quota-limited or malformed. Never echoes the secret query URL.
    """
    if not (explicit_click and rights_approved and premium_approved
            and os.environ.get("KUODRA_ENABLE_ALPHA_VANTAGE_INDEX") == "1"
            and os.environ.get("KUODRA_ALPHA_VANTAGE_INDEX_PREMIUM_APPROVED") == "1"
            and os.environ.get("KUODRA_ALPHA_VANTAGE_RIGHTS_APPROVED") == "1"):
        return _blocked("INDEX_PREMIUM_OR_RIGHTS_APPROVAL_REQUIRED")
    if (type(benchmark) is not str or benchmark not in _BENCHMARKS
            or type(api_key) is not str or _API_KEY.fullmatch(api_key) is None):
        return _blocked("INDEX_BENCHMARK_OR_KEY_INVALID")
    try:
        cutoff = date.fromisoformat(as_of)
        if type(as_of) is not str or as_of != cutoff.isoformat() or cutoff > datetime.now(timezone.utc).date():
            return _blocked("INDEX_AS_OF_INVALID")
    except (TypeError, ValueError):
        return _blocked("INDEX_AS_OF_INVALID")
    url = _HOST + "?" + urlencode({
        "function": "INDEX_DATA", "symbol": _BENCHMARKS[benchmark],
        "interval": "daily", "datatype": "json", "apikey": api_key,
    })
    try:
        raw = (transport or _https_get_index)(url)
        result = parse_index_daily_bytes(raw, benchmark=benchmark, as_of=as_of)
    except (ValueError, OSError, TypeError, KeyError, OverflowError,
            TimeoutError, RecursionError):
        result = _blocked("INDEX_VENDOR_REQUEST_OR_RESPONSE_UNAVAILABLE")
    result["requests_attempted"] = 1
    return result
