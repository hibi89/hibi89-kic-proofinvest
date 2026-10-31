"""KUODRA Engine A: offline, source-labeled market regression.

Untrusted, operator-supplied PRICE_ONLY or adjusted proxy observations only.
OLS beta/intercept/R2 are descriptive, never bubble fractions, CAPM alpha,
causal revenue contributions, market-timing advice, or verified price feeds.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from hashlib import sha256
import json
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

MAX_UPLOAD_BYTES = 131072
_CIK = re.compile(r"[0-9]{10}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_NUM = re.compile(r"(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,8})?\Z")
_TICK = re.compile(r"[A-Za-z0-9.^_-]{1,25}\Z")
_BENCH = {"S&P_500", "NASDAQ_100", "DJIA"}
_BASIS = {"PRICE_ONLY_CLOSE", "ADJUSTED_CLOSE_TOTAL_RETURN_PROXY"}
_QUANT = Decimal("0.0001")


def _bad(code: str):
    raise ValueError(code)


def _exact(obj: Any, fields: set[str], name: str) -> dict:
    if type(obj) is not dict or set(obj) != fields:
        _bad("INVALID_" + name + "_FIELDS")
    return obj


def _str(x: Any, name: str, cap: int = 120) -> str:
    if (type(x) is not str or not 0 < len(x) <= cap
            or any(ord(c) < 32 or ord(c) == 127 for c in x)):
        _bad("INVALID_" + name)
    return x


def _date(x: Any, name: str) -> date:
    raw = _str(x, name, 10)
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
        _bad("INVALID_" + name)
    try:
        return date.fromisoformat(raw)
    except ValueError:
        _bad("INVALID_" + name)


def _decimal(x: Any, name: str) -> Decimal:
    if type(x) is not str or not _NUM.fullmatch(x):
        _bad("INVALID_" + name)
    try:
        val = Decimal(x)
    except InvalidOperation:
        _bad("INVALID_" + name)
    if not val.is_finite() or val <= 0:
        _bad("INVALID_" + name)
    return val


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            _bad("DUPLICATE_MARKET_JSON_KEY")
        out[k] = v
    return out


def parse_market_reality_json(raw: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_UPLOAD_BYTES:
        _bad("INVALID_MARKET_JSON_SIZE")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                         parse_constant=lambda _: _bad("INVALID_NONFINITE_NUMBER"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _bad("INVALID_MARKET_JSON")
    if type(obj) is not dict:
        _bad("INVALID_MARKET_JSON_ROOT")
    return obj


def _source(obj: Any, asof: date) -> dict:
    source = _exact(obj, {"provider", "url", "published_at", "sha256"}, "PRICE_SOURCE")
    provider = _str(source["provider"], "PROVIDER", 80)
    url = _str(source["url"], "PRICE_URL", 400)
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        _bad("INVALID_PRICE_URL")
    if (parsed.scheme != "https" or not parsed.hostname or "." not in parsed.hostname
            or parsed.username or parsed.password or port not in (None, 443)
            or parsed.query or parsed.fragment
            or parsed.hostname.lower() == "localhost"
            or parsed.path.startswith("//")):
        _bad("INVALID_PRICE_URL")
    pub = _date(source["published_at"], "PRICE_PUBLICATION")
    if pub > asof:
        _bad("SOURCE_PUBLISHED_AFTER_AS_OF")
    digest = source["sha256"]
    if type(digest) is not str or not _SHA.fullmatch(digest):
        _bad("INVALID_PRICE_SHA")
    return {"provider": provider, "url": url, "published_at": pub.isoformat(),
            "sha256_reported": digest, "authenticated": False}


def _series(obj: Any, asof: date, name: str) -> tuple[list[date], list[Decimal], dict]:
    data = _exact(obj, {"source", "observations"}, name)
    source = _source(data["source"], asof)
    rows = data["observations"]
    if type(rows) is not list or not 31 <= len(rows) <= 501:
        _bad("INSUFFICIENT_OR_EXCESSIVE_" + name + "_OBSERVATIONS")
    days: list[date] = []
    values: list[Decimal] = []
    for x in rows:
        record = _exact(x, {"date", "value"}, name + "_ROW")
        day = _date(record["date"], name + "_DATE")
        if day > asof or day.weekday() >= 5:
            _bad("FUTURE_OR_NON_TRADING_" + name + "_DATE")
        if days and not 1 <= (day - days[-1]).days <= 7:
            _bad("UNSORTED_DUPLICATE_OR_GAPPED_" + name + "_DATE")
        days.append(day)
        values.append(_decimal(record["value"], name + "_VALUE"))
    if _date(source["published_at"], name + "_SOURCE_PUBLICATION") < days[-1]:
        _bad("SOURCE_PUBLISHED_BEFORE_LAST_PRICE_OBSERVATION")
    return days, values, source


def _fmt(n: Decimal) -> str:
    return str(n.quantize(_QUANT, rounding=ROUND_HALF_UP))


def _sec_revenue_context(report: Any, *, cik: str, as_of: str) -> dict | None:
    """Bind displayed SEC growth to an already-produced local Guard review.

    This never attests authenticity, links a price movement causally to sales,
    or changes the Guard. Do not accept an arbitrary financial scalar.
    """
    if report is None:
        return None
    if type(report) is not dict or report.get("schema") != "proofinvest.local-sec-guard-report.v1":
        _bad("INVALID_SEC_REVIEW_CONTEXT")
    issuer, sec, source, guard = (report.get(k) for k in
                                 ("issuer", "verification", "source", "guard"))
    if not all(type(x) is dict for x in (issuer, sec, source, guard)):
        _bad("INVALID_SEC_REVIEW_CONTEXT")
    if issuer.get("cik") != cik or issuer.get("as_of") != as_of:
        _bad("SEC_REVIEW_ISSUER_OR_ASOF_MISMATCH")
    if (sec.get("status") != "calculated_unverified"
            or guard.get("decision") != "HOLD"
            or guard.get("source_authenticated") is not False):
        return None
    digest = source.get("companyfacts_sha256")
    if type(digest) is not str or not _SHA.fullmatch(digest):
        _bad("SEC_REVIEW_SOURCE_PIN_INVALID")
    growth = sec.get("growth_pct")
    if type(growth) is not str or not re.fullmatch(r"-?[0-9]{1,8}(?:\.[0-9]{1,4})?",growth):
        _bad("SEC_REVENUE_GROWTH_UNSAFE")
    end = sec.get("current_period_end")
    filing = issuer.get("filing_date")
    if _date(end, "SEC_FISCAL_END") > _date(filing, "SEC_FILED"):
        _bad("SEC_FILING_DATE_INVALID")
    if _date(filing, "SEC_FILED") > _date(as_of, "SEC_AS_OF"):
        _bad("SEC_FILING_AFTER_AS_OF")
    return {"growth_pct_calculated_unverified": growth,
            "current_period_end": end, "filing_date": filing,
            "companyfacts_sha256": digest,
            "caveat": "SEC annual revenue is a separate historic observation; it is not a regression coefficient or causal attribution.",
            "source_authenticated": False}


def analyze_market_reality(payload: Any, *, expected_issuer_cik: str | None = None,
                           analysis_as_of: str | None = None,
                           sec_review: Mapping[str, Any] | None = None,
                           uploaded_sha256: str | None = None) -> dict:
    obj = _exact(payload, {"schema", "issuer_cik", "as_of", "symbol",
                           "benchmark", "return_basis", "security", "index"}, "MARKET")
    if obj["schema"] != "kuodra.market-reality.v1":
        _bad("INVALID_MARKET_SCHEMA")
    cik = _str(obj["issuer_cik"], "ISSUER_CIK", 10)
    if not _CIK.fullmatch(cik) or cik == "0000000000":
        _bad("INVALID_ISSUER_CIK")
    if expected_issuer_cik is not None and cik != expected_issuer_cik:
        _bad("MARKET_ISSUER_MISMATCH")
    as_of = _date(obj["as_of"], "AS_OF")
    if analysis_as_of is not None and as_of != _date(analysis_as_of, "EXPECTED_ASOF"):
        _bad("MARKET_ASOF_MISMATCH")
    symbol = _str(obj["symbol"], "SYMBOL", 25)
    if not _TICK.fullmatch(symbol):
        _bad("INVALID_SYMBOL")
    benchmark = obj["benchmark"]
    if benchmark not in _BENCH:
        _bad("INVALID_BENCHMARK")
    basis = obj["return_basis"]
    if basis not in _BASIS:
        _bad("INVALID_RETURN_BASIS")
    s_days, stock, stock_src = _series(obj["security"], as_of, "STOCK")
    m_days, market, market_src = _series(obj["index"], as_of, "MARKET")
    if s_days != m_days:
        _bad("PRICE_CALENDAR_NOT_ALIGNED")
    # Historical adjusted prices sometimes get restated on dividend/split
    # actions; no data vintage claim is made from date gates alone.
    # Look-ahead gate: date-only SEC filing must predate EVERY return session.
    # Same-day publication cannot prove market-close availability.
    context = _sec_revenue_context(sec_review, cik=cik, as_of=as_of.isoformat())
    if context is not None and _date(context["filing_date"], "SEC_FILED") >= s_days[0]:
        context = None
        sec_timing = "WITHHELD_FILING_NOT_PRIOR_TO_PRICE_WINDOW"
    elif context is not None:
        sec_timing = "FILING_PREDATES_ALL_PRICE_OBSERVATIONS_UNVERIFIED"
    elif sec_review is None:
        sec_timing = "NO_SEC_REVIEW"
    else:
        sec_timing = "NO_ELIGIBLE_SEC_CONTEXT"
    if uploaded_sha256 is not None and (type(uploaded_sha256) is not str
                                         or not _SHA.fullmatch(uploaded_sha256)):
        _bad("INVALID_INPUT_SHA256")
    with localcontext() as decimal_context:
        decimal_context.prec = 40
        r_stock = [stock[i] / stock[i - 1] - 1 for i in range(1, len(stock))]
        r_market = [market[i] / market[i - 1] - 1 for i in range(1, len(market))]
        n = Decimal(len(r_stock))
        mean_s, mean_m = sum(r_stock) / n, sum(r_market) / n
        v_market = sum((x - mean_m) ** 2 for x in r_market)
        v_stock = sum((x - mean_s) ** 2 for x in r_stock)
        cov = sum((x - mean_m) * (y - mean_s)
                  for x, y in zip(r_market, r_stock))
        total_s = (stock[-1] / stock[0] - 1) * 100
        total_m = (market[-1] / market[0] - 1) * 100
        if v_market == 0:
            return {
                "schema": "kuodra.market-reality-analysis.v1",
                "status": "INSUFFICIENT_MARKET_VARIANCE", "issuer_cik": cik,
                "as_of": as_of.isoformat(), "symbol": symbol, "benchmark": benchmark,
                "return_basis": basis, "observation_count": len(stock),
                "return_count": len(r_stock), "period_start": s_days[0].isoformat(),
                "period_end": s_days[-1].isoformat(),
                "security_return_pct": _fmt(total_s),
                "benchmark_return_pct": _fmt(total_m),
                "beta": None, "regression_intercept_daily_pct": None, "r_squared": None,
                "sec_revenue_context": context,
                "sec_context_temporal_status": sec_timing,
                "historical_price_vintage_authenticated": False,
                "point_in_time_backtest_verified": False,
                "source": {"stock": stock_src, "benchmark": market_src,
                           "upload_sha256": uploaded_sha256},
                "source_authenticated": False, "audit_included": False, "market_bubble_proven": False,
                "sec_growth_caused_price_move": False, "guard_policy_modified": False,
                "trade_signal": False, "ai_generated": False,
                "limitations": ["Benchmark variance is zero; beta and OLS intercept are undefined."],
            }
        beta = cov / v_market
        alpha = (mean_s - beta * mean_m) * 100
        r2 = (cov * cov / (v_market * v_stock)) if v_stock != 0 else None
    return {
        "schema": "kuodra.market-reality-analysis.v1",
        "status": "REPORTED_UNVERIFIED", "issuer_cik": cik,
        "as_of": as_of.isoformat(), "symbol": symbol, "benchmark": benchmark,
        "return_basis": basis, "observation_count": len(stock),
        "return_count": len(r_stock), "period_start": s_days[0].isoformat(),
        "period_end": s_days[-1].isoformat(),
        "security_return_pct": _fmt(total_s), "benchmark_return_pct": _fmt(total_m),
        "beta": _fmt(beta), "regression_intercept_daily_pct": _fmt(alpha),
        "r_squared": _fmt(r2) if r2 is not None else None,
        "sec_revenue_context": context,
        "sec_context_temporal_status": sec_timing,
        "historical_price_vintage_authenticated": False,
        "point_in_time_backtest_verified": False,
        "source": {"stock": stock_src, "benchmark": market_src,
                   "upload_sha256": uploaded_sha256},
        "source_authenticated": False, "audit_included": False, "market_bubble_proven": False,
        "sec_growth_caused_price_move": False, "guard_policy_modified": False,
        "trade_signal": False, "ai_generated": False,
        "limitations": [
            "Beta measures sample covariance with a selected benchmark, not liquidity or a bubble fraction.",
            "Daily OLS intercept is not CAPM/Jensen alpha and not earnings contribution; no risk-free rate or factor controls.",
            "R-squared is in-sample fit, not forecast accuracy or causal attribution.",
            "Reported daily price history and revisions, benchmark choice, vendor rights and timestamp provenance remain unauthenticated.",
            "SEC revenue growth is withheld unless its filing day is strictly before the first market session; mixed pre/post filing periods cannot use that filing as contemporaneous context.",
            "Self-reported source URLs and digests do not authenticate historical price vintages or exclude retrospective split/dividend adjustments.",
            "Adjusted close may retrospectively account for dividends and splits, so date <= as-of alone does not prove a valid point-in-time price vintage.",
            "No valuation, intrinsic value, future return, investment recommendation or automatic trade decision is calculated.",
        ],
    }
