"""Massive $0 individual-plan daily stock and genuine Nasdaq-100 index adapter.

Provider documentation: https://massive.com/docs/rest/indices/aggregates/custom-bars
No API request occurs on import, in parsing, or without an explicit click,
local owner gate, and separately authorized provider use. Account screenshots
do NOT prove redistribution, judge-display, commercial or AI-use rights.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
import os
import re
import ssl
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener,
)

_HOST = "https://api.massive.com"
_DOC = "https://massive.com/docs/rest/indices/aggregates/custom-bars"
_SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}\Z", re.ASCII)
_KEY = re.compile(r"[A-Za-z0-9_\-]{8,128}\Z", re.ASCII)
_SHA = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_MAX_RESPONSE = 262144
_MAX_ROWS = 160
_PLANS = ("KUODRA_ENABLE_MASSIVE_PAIR", "KUODRA_MASSIVE_PERSONAL_RESEARCH_APPROVED")
_QUANT = Decimal("0.00000001")


def _blocked(code: str, requests: int = 0) -> dict:
    return {
        "schema": "kuodra.massive-engine-a.v1", "status": "BLOCKED",
        "reason_code": code, "provider": "massive",
        "market_analysis": None, "matched_observation_count": 0,
        "network_requests": requests, "retries": 0,
        "source_authenticated": False, "source_rights_verified": False,
        "public_display_allowed": False, "commercial_reuse_allowed": False,
        "full_a_b_c_ready": False, "guard_executed": False,
        "ai_agent_executed": False, "trade_executed": False,
    }


def _pairs(items):
    output = {}
    for key, val in items:
        if key in output:
            raise ValueError("DUPLICATE_JSON_KEY")
        output[key] = val
    return output


def _bad_constant(_):
    raise ValueError("INVALID_NONFINITE_JSON_VALUE")


def free_basic_safe_as_of(utc_today: date | None = None) -> str:
    """Conservatively select two completed weekdays before UTC today.

    Massive free EOD aggregates exclude the CURRENT Eastern trading day until
    after 00:00 ET, which may lag UTC/KST. Backing off two weekdays avoids an
    in-progress U.S. session without relying on Windows zoneinfo/tzdata or
    inventing holiday calendars. Deliberately favors safety over freshness.
    """
    cursor = utc_today if utc_today is not None else datetime.now(timezone.utc).date()
    if type(cursor) is not date:
        raise ValueError("UTC_DATE_INVALID")
    for _ in range(2):
        cursor -= timedelta(days=1)
        while cursor.weekday() >= 5:
            cursor -= timedelta(days=1)
    return cursor.isoformat()


def _day(value: str) -> date:
    if type(value) is not str:
        raise ValueError("INVALID_DATE")
    day = date.fromisoformat(value)
    if day.isoformat() != value:
        raise ValueError("NONCANONICAL_DATE")
    return day


def parse_massive_daily(raw: bytes, *, symbol: str, as_of: str,
                        index: bool = False) -> dict[str, Any]:
    """Parse official daily Custom Bars JSON, no claims of real origin/rights.

    Stock: AAPL/NVDA; actual Nasdaq-100 only: I:NDX, never QQQ proxy.
    Daily bar timestamps are Unix milliseconds; UTC date is the exchange's
    business day for the documented eastern-time daily aggregates.
    """
    if (type(raw) is not bytes or not 0 < len(raw) <= _MAX_RESPONSE
            or type(index) is not bool
            or type(symbol) is not str
            or (symbol != "I:NDX" if index else _SYMBOL.fullmatch(symbol) is None)):
        raise ValueError("RESPONSE_SYMBOL_OR_SIZE_INVALID")
    cutoff = _day(as_of)
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_float=Decimal, parse_constant=_bad_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError("INVALID_MASSIVE_JSON") from exc
    if (type(data) is not dict or data.get("status") != "OK"
            or data.get("ticker") != symbol
            or "next_url" in data
            or any(k in data for k in ("error", "message", "Error", "Information"))):
        raise ValueError("PROVIDER_STATUS_SYMBOL_OR_PAGINATION_INVALID")
    rows = data.get("results")
    if type(rows) is not list or not 31 <= len(rows) <= _MAX_ROWS:
        raise ValueError("INVALID_DAILY_OBSERVATION_COUNT")
    if ("resultsCount" in data and (
            type(data["resultsCount"]) is not int
            or data["resultsCount"] != len(rows))):
        raise ValueError("RESULTS_COUNT_MISMATCH")
    if ("queryCount" in data and (
            type(data["queryCount"]) is not int or data["queryCount"] < len(rows))):
        raise ValueError("QUERY_COUNT_INVALID")
    if not index and data.get("adjusted") is not False:
        # Split-adjusted historical series can create point-in-time leakage.
        raise ValueError("UNADJUSTED_STOCK_ONLY")
    if index and "adjusted" in data:
        raise ValueError("INDEX_ADJUSTED_FIELD_INVALID")
    observations = []
    previous = None
    for row in rows:
        if type(row) is not dict or "t" not in row or "c" not in row:
            raise ValueError("INVALID_BAR_FIELDS")
        timestamp, raw_close = row["t"], row["c"]
        if (type(timestamp) is not int or not 946684800000 <= timestamp < 4102444800000
                or type(raw_close) not in (int, Decimal, float)):
            raise ValueError("INVALID_BAR_TIME_OR_CLOSE")
        try:
            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
            # ET midnight daily bars lie in the early UTC hours; reject
            # intraday or arbitrary future timestamps posing as a daily bar.
            if not 4 <= dt.hour <= 10 or dt.minute != 0 or dt.second != 0:
                raise ValueError("NON_DAILY_BAR_TIMESTAMP")
            observed = dt.date()
            amount = Decimal(str(raw_close))
        except (ValueError, OverflowError, InvalidOperation) as exc:
            raise ValueError("INVALID_BAR_VALUE") from exc
        if (observed.weekday() >= 5 or observed > cutoff
                or not amount.is_finite() or not Decimal(0) < amount < Decimal("1e10")):
            raise ValueError("NONTRADING_FUTURE_OR_BAD_CLOSE")
        if previous is not None and not 1 <= (observed - previous).days <= 7:
            raise ValueError("UNSORTED_DUPLICATE_OR_GAPPED_BAR")
        previous = observed
        amount = amount.quantize(_QUANT, rounding=ROUND_HALF_UP)
        if amount <= 0:
            raise ValueError("ROUNDED_ZERO_CLOSE")
        observations.append({"date": observed.isoformat(), "close": format(amount, "f")})
    observations = observations[-100:]
    return {
        "schema": "kuodra.massive-daily-source.v1",
        "status": "DAILY_CLOSE_UNVERIFIED",
        "provider": "massive", "symbol": symbol, "as_of": as_of,
        "kind": "index" if index else "stock",
        "basis": "PRICE_ONLY_CLOSE",
        "close_observations": observations,
        "point_count": len(observations),
        "first_date": observations[0]["date"], "last_date": observations[-1]["date"],
        "source_sha256": sha256(raw).hexdigest(),
        "network_requests": 0,
        "source_authenticated": False, "source_rights_verified": False,
        "commercial_reuse_allowed": False, "external_display_allowed": False,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("PROVIDER_REDIRECT_BLOCKED")


def _https_get(url: str) -> bytes:
    """Direct TLS, no ambient proxies, no redirects/retries, 8s, 256KiB."""
    opener = build_opener(ProxyHandler({}), _NoRedirect(),
                          HTTPSHandler(context=ssl.create_default_context()))
    request = Request(url, headers={
        "Accept": "application/json", "User-Agent": "KUODRA/1.0 individual-research",
    })
    with opener.open(request, timeout=8) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("PROVIDER_HTTP_INVALID")
        body = response.read(_MAX_RESPONSE + 1)
        if len(body) > _MAX_RESPONSE:
            raise ValueError("PROVIDER_BODY_TOO_LARGE")
        return body


def _url(*, symbol: str, as_of: str, api_key: str, index: bool) -> str:
    start = (_day(as_of) - timedelta(days=180)).isoformat()
    path = f"/v2/aggs/ticker/{symbol}/range/1/day/{start}/{as_of}"
    params = {"sort": "asc", "limit": "160", "apiKey": api_key}
    if not index:
        params["adjusted"] = "false"
    return _HOST + path + "?" + urlencode(params)


def _validate_receipt(receipt: dict, *, symbol: str, as_of: str, index: bool) -> dict:
    if (type(receipt) is not dict
            or receipt.get("schema") != "kuodra.massive-daily-source.v1"
            or receipt.get("status") != "DAILY_CLOSE_UNVERIFIED"
            or receipt.get("provider") != "massive"
            or receipt.get("symbol") != symbol
            or receipt.get("kind") != ("index" if index else "stock")
            or receipt.get("as_of") != as_of
            or receipt.get("basis") != "PRICE_ONLY_CLOSE"
            or receipt.get("source_authenticated") is not False
            or receipt.get("source_rights_verified") is not False
            or receipt.get("commercial_reuse_allowed") is not False
            or receipt.get("external_display_allowed") is not False
            or type(receipt.get("source_sha256")) is not str
            or _SHA.fullmatch(receipt["source_sha256"]) is None):
        raise ValueError("MASSIVE_RECEIPT_UNTRUSTED")
    from .market_pair_engine_a import _points
    points = _points(receipt, kind="index" if index else "stock",
                     cutoff=_day(as_of))
    return points


def analyze_massive_pair(*, stock: dict, ndx: dict, ticker: str,
                         issuer_cik: str, filing_date: str, as_of: str) -> dict:
    """Run real local Decimal Engine A on already parsed in-memory receipts."""
    try:
        from .market_pair_engine_a import _CIK, _TICKER
        if (type(ticker) is not str or _TICKER.fullmatch(ticker) is None
                or type(issuer_cik) is not str or _CIK.fullmatch(issuer_cik) is None
                or issuer_cik == "0000000000"):
            raise ValueError("ISSUER_INVALID")
        filing, cutoff = _day(filing_date), _day(as_of)
        if filing >= cutoff:
            raise ValueError("NO_POST_FILING_AS_OF")
        s = _validate_receipt(stock, symbol=ticker, as_of=as_of, index=False)
        m = _validate_receipt(ndx, symbol="I:NDX", as_of=as_of, index=True)
        stock_days = {k for k in s if _day(k) > filing}
        index_days = {k for k in m if _day(k) > filing}
        common = sorted(stock_days & index_days)
        if (len(common) < 31 or len(common) * 5 < 4 * len(stock_days)
                or len(common) * 5 < 4 * len(index_days)
                or (cutoff - _day(common[-1])).days > 7):
            raise ValueError("POST_FILING_MARKET_CALENDAR_INCOMPATIBLE")
        for older, newer in zip(common, common[1:]):
            if not 1 <= (_day(newer) - _day(older)).days <= 7:
                raise ValueError("MARKET_SESSION_GAP")
        common = common[-100:]
        def series(points, digest):
            return {"source": {
                        "provider": "MASSIVE_RESPONSE_UNVERIFIED",
                        "url": _DOC, "published_at": as_of, "sha256": digest,
                    },
                    "observations": [{"date": k, "value": points[k]} for k in common]}
        payload = {
            "schema": "kuodra.market-reality.v1",
            "issuer_cik": issuer_cik, "as_of": as_of, "symbol": ticker,
            "benchmark": "NASDAQ_100", "return_basis": "PRICE_ONLY_CLOSE",
            "security": series(s, stock["source_sha256"]),
            "index": series(m, ndx["source_sha256"]),
        }
        from .market_reality import analyze_market_reality
        wire = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        analyzed = analyze_market_reality(payload, expected_issuer_cik=issuer_cik,
                                          analysis_as_of=as_of, sec_review=None,
                                          uploaded_sha256=sha256(wire).hexdigest())
        if (analyzed.get("status") not in ("REPORTED_UNVERIFIED",
                                           "INSUFFICIENT_MARKET_VARIANCE")
                or analyzed.get("source_authenticated") is not False
                or analyzed.get("trade_signal") is not False
                or analyzed.get("market_bubble_proven") is not False
                or analyzed.get("guard_policy_modified") is not False):
            raise ValueError("ENGINE_A_TRUST_CONTRACT_INVALID")
        return {**_blocked("PROVIDER_RIGHTS_AND_ORIGIN_UNVERIFIED"),
                "status": "ENGINE_A_MASSIVE_DESCRIPTIVE_UNVERIFIED",
                "ticker": ticker, "issuer_cik": issuer_cik, "as_of": as_of,
                "index_symbol": "I:NDX",
                "matched_observation_count": len(common),
                "matched_period_start": common[0], "matched_period_end": common[-1],
                "stock_response_sha256": stock["source_sha256"],
                "index_response_sha256": ndx["source_sha256"],
                "source_payload_sha256": sha256(wire).hexdigest(),
                "market_analysis": {
                    k: analyzed.get(k) for k in (
                        "status", "security_return_pct", "benchmark_return_pct",
                        "beta", "regression_intercept_daily_pct", "r_squared",
                    )}}
    except (TypeError, ValueError, KeyError, OverflowError,
            RecursionError, AttributeError):
        return _blocked("MASSIVE_RECEIPTS_OR_ENGINE_A_UNAVAILABLE")


def fetch_massive_pair(*, ticker: str, issuer_cik: str, filing_date: str,
                       as_of: str, api_key: str | None,
                       explicit_click: bool = False,
                       individual_research_approved: bool = False,
                       stock_transport: Callable[[str], bytes] | None = None,
                       index_transport: Callable[[str], bytes] | None = None) -> dict:
    """Explicit 2-request max personal research path, default OFF.

    Two requests (one stock, one NDX) count against separate free-class limits.
    No source bytes/key/URL written to disk or returned, no retries.
    """
    if (not explicit_click or not individual_research_approved
            or any(os.environ.get(k) != "1" for k in _PLANS)):
        return _blocked("OWNER_PERSONAL_RESEARCH_APPROVAL_REQUIRED")
    try:
        if (type(ticker) is not str or _SYMBOL.fullmatch(ticker) is None
                or type(issuer_cik) is not str
                or re.fullmatch(r"[0-9]{10}", issuer_cik) is None
                or issuer_cik == "0000000000" or _day(filing_date) >= _day(as_of)
                or _day(as_of) > _day(free_basic_safe_as_of())
                or type(api_key) is not str or _KEY.fullmatch(api_key) is None):
            return _blocked("PRE_NETWORK_IDENTITY_DATE_OR_KEY_INVALID")
    except (ValueError, OverflowError, TypeError):
        return _blocked("PRE_NETWORK_IDENTITY_DATE_OR_KEY_INVALID")
    attempts = 0
    try:
        stock_url = _url(symbol=ticker, as_of=as_of, api_key=api_key, index=False)
        attempts += 1
        stock = parse_massive_daily((stock_transport or _https_get)(stock_url),
                                    symbol=ticker, as_of=as_of, index=False)
        ndx_url = _url(symbol="I:NDX", as_of=as_of, api_key=api_key, index=True)
        attempts += 1
        ndx = parse_massive_daily((index_transport or _https_get)(ndx_url),
                                  symbol="I:NDX", as_of=as_of, index=True)
        result = analyze_massive_pair(stock=stock, ndx=ndx, ticker=ticker,
                                      issuer_cik=issuer_cik, filing_date=filing_date,
                                      as_of=as_of)
    except (ValueError, TypeError, OSError, KeyError, OverflowError,
            TimeoutError, RecursionError, AttributeError):
        result = _blocked("PROVIDER_REQUEST_OR_RESPONSE_UNAVAILABLE")
    result["network_requests"] = attempts
    return result
