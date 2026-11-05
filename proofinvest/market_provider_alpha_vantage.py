"""Explicitly gated, bounded on-demand daily CLOSE provider adapter.

No SEC calls, no background jobs, no license inference, no persistent cache.
One HTTPS GET at most when operator has separately authorized access and
confirmed their market-data entitlement. Price-only evidence is not Engine A.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
import re
import ssl
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

_HOST = "https://www.alphavantage.co/query"
_MAX_BODY = 262144
_MAX_POINTS = 100
_SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}\Z", re.ASCII)
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,8})?\Z", re.ASCII)


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.alpha-vantage-daily-source.v1",
        "status": "BLOCKED", "reason_code": reason,
        "provider": "alpha_vantage", "ticker": None,
        "close_observations": [], "source_sha256": None,
        "requests_attempted": 0, "retries": 0,
        "issuer_authenticated": False, "market_data_rights_verified": False,
        "full_a_b_c_ready": False, "trade_executed": False,
    }


def _no_duplicate(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def _nonfinite(token):
    raise ValueError("NON_FINITE_JSON")


def parse_daily_close_bytes(raw: bytes, *, ticker: str, as_of: str) -> dict:
    """Strict parser for one Alpha Vantage TIME_SERIES_DAILY JSON response.

    Caller-observed timestamps and response digests do not authenticate vendor
    provenance or grant display/redistribution rights.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_BODY:
        raise ValueError("RESPONSE_SIZE_INVALID")
    if type(ticker) is not str or not _SYMBOL.fullmatch(ticker):
        raise ValueError("TICKER_INVALID")
    try:
        cutoff = date.fromisoformat(as_of)
        if as_of != cutoff.isoformat():
            raise ValueError("DATE_FORMAT_INVALID")
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate,
                             parse_constant=_nonfinite)
    except (TypeError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("RESPONSE_JSON_INVALID") from exc
    if type(payload) is not dict:
        raise ValueError("RESPONSE_ROOT_INVALID")
    if any(k in payload for k in ("Note", "Information", "Error Message")):
        raise ValueError("PROVIDER_NOTICE_OR_LIMIT")
    meta = payload.get("Meta Data")
    series = payload.get("Time Series (Daily)")
    if (type(meta) is not dict or type(series) is not dict
            or meta.get("2. Symbol") != ticker
            or not 31 <= len(series) <= _MAX_POINTS):
        raise ValueError("TICKER_METADATA_OR_PERIOD_COUNT_INVALID")
    points = []
    for day, row in series.items():
        if type(day) is not str or type(row) is not dict:
            raise ValueError("DAILY_POINT_INVALID")
        try:
            observed = date.fromisoformat(day)
        except ValueError as exc:
            raise ValueError("DAILY_DATE_INVALID") from exc
        if observed.isoformat() != day or observed.weekday() >= 5:
            raise ValueError("DAILY_TRADING_DATE_INVALID")
        amount = row.get("4. close")
        if type(amount) is not str or not _DECIMAL.fullmatch(amount):
            raise ValueError("DAILY_CLOSE_INVALID")
        try:
            value = Decimal(amount)
        except InvalidOperation as exc:
            raise ValueError("DAILY_CLOSE_INVALID") from exc
        if not value.is_finite() or value <= 0:
            raise ValueError("DAILY_CLOSE_INVALID")
        if observed <= cutoff:
            points.append((day, amount))
    points.sort(key=lambda pair: pair[0])
    if not 31 <= len(points) <= _MAX_POINTS:
        raise ValueError("INSUFFICIENT_AS_OF_PRICE_POINTS")
    for (earlier, _), (later, _) in zip(points, points[1:]):
        if not 1 <= (date.fromisoformat(later) - date.fromisoformat(earlier)).days <= 7:
            raise ValueError("PRICE_WINDOW_GAP_INVALID")
    return {
        **_hold(""), "status": "PRICE_ONLY_UNVERIFIED",
        "reason_code": "PROVIDER_RESPONSE_NOT_INDEPENDENTLY_AUTHENTICATED",
        "ticker": ticker, "as_of": as_of, "basis": "PRICE_ONLY_CLOSE",
        "first_date": points[0][0], "last_date": points[-1][0],
        "point_count": len(points),
        "close_observations": [{"date": day, "close": value} for day, value in points],
        "source_sha256": sha256(raw).hexdigest(),
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("PROVIDER_REDIRECT_BLOCKED")


def _https_get(url: str) -> bytes:
    """Fixed-host TLS GET, 8s timeout, no redirect and max 256KiB body."""
    # Never inherit HTTP(S)_PROXY for requests whose URL contains an API key.
    opener = build_opener(ProxyHandler({}), _NoRedirect(),
                          HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(Request(url, headers={"Accept": "application/json",
                                           "User-Agent": "KUODRA/1.0 licensed-data-client"}), timeout=8) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("PROVIDER_HTTP_STATUS_INVALID")
        data = response.read(_MAX_BODY + 1)
        if len(data) > _MAX_BODY:
            raise ValueError("RESPONSE_SIZE_INVALID")
        return data


def fetch_daily_close(*, ticker: str, as_of: str, api_key: str | None,
                      explicit_click: bool = False, rights_approved: bool = False,
                      transport: Callable[[str], bytes] | None = None) -> dict:
    """At most one request, never fetches without config + per-click gates.

    No response or error exposes API key, URL, personal data or raw source.
    This cannot authenticate the vendor's legal rights or license grant.
    """
    blocked = _hold("OPERATOR_APPROVAL_OR_PROVIDER_KEY_REQUIRED")
    if (not explicit_click or not rights_approved
            or os.environ.get("KUODRA_ENABLE_ALPHA_VANTAGE_DAILY") != "1"
            or os.environ.get("KUODRA_ALPHA_VANTAGE_RIGHTS_APPROVED") != "1"):
        return blocked
    if (type(ticker) is not str or not _SYMBOL.fullmatch(ticker)
            or type(api_key) is not str or not 8 <= len(api_key) <= 80
            or not api_key.isascii() or not api_key.isalnum()):
        return _hold("TICKER_OR_PROVIDER_KEY_INVALID")
    try:
        cutoff = date.fromisoformat(as_of)
        if as_of != cutoff.isoformat() or cutoff > datetime.now(timezone.utc).date():
            return _hold("AS_OF_DATE_INVALID")
    except (ValueError, TypeError):
        return _hold("AS_OF_DATE_INVALID")
    url = _HOST + "?" + urlencode({
        "function": "TIME_SERIES_DAILY", "symbol": ticker,
        "outputsize": "compact", "datatype": "json", "apikey": api_key,
    })
    try:
        data = (transport or _https_get)(url)
        result = parse_daily_close_bytes(data, ticker=ticker, as_of=as_of)
    except (ValueError, OSError, TypeError, KeyError, OverflowError,
            TimeoutError, RecursionError):
        result = _hold("PROVIDER_REQUEST_OR_DATA_UNAVAILABLE")
    result["requests_attempted"] = 1
    return result


def render_daily_price_panel(st: Any, *, ticker: str, as_of: str,
                             ticker_valid: bool) -> None:
    """Dependency-free Streamlit-like UI; never queries without a real click.

    API key is read only from an operator-supplied environment variable and
    is never rendered, returned or persisted by this function.
    """
    st.subheader("일별 주가 자동 조회 · 공급자 권한 승인 후 사용")
    st.caption("Alpha Vantage 일별 종가, 종목당 버튼 클릭 시 최대 1회 GET. "
               "무료 한도·재사용/표시 권리는 별도 확인 대상입니다. "
               "SEC 403 재시도·매매·백그라운드 자동 수집은 없습니다.")
    active = (
        os.environ.get("KUODRA_ENABLE_ALPHA_VANTAGE_DAILY") == "1"
        and os.environ.get("KUODRA_ALPHA_VANTAGE_RIGHTS_APPROVED") == "1"
        and bool(os.environ.get("KUODRA_ALPHA_VANTAGE_API_KEY"))
    )
    if not active:
        st.warning("주가 API 비활성: 공급자 계정·이용권한·비밀키 설정 승인 대기.")
    acknowledged = st.checkbox(
        "이번 종목에 한하여 허용된 Alpha Vantage 일별 조회 1회를 실행합니다",
        value=False, key="kuodra_p140_av_ack",
    )
    if not st.button(
        "승인된 일별 종가 1회 조회",
        key="kuodra_p140_av_once",
        disabled=not (active and acknowledged and ticker_valid),
    ):
        return
    response = fetch_daily_close(
        ticker=ticker, as_of=as_of,
        api_key=os.environ.get("KUODRA_ALPHA_VANTAGE_API_KEY"),
        explicit_click=True, rights_approved=True,
    )
    if response["status"] != "PRICE_ONLY_UNVERIFIED":
        st.warning("주가 조회 불가 또는 제공자 응답 검증 실패; 재시도하지 않습니다.")
        st.code(response["reason_code"], language="text")
        return
    st.metric("최근 일별 종가 · 제공자 응답, 미인증",
              response["close_observations"][-1]["close"])
    st.json({
        "ticker": response["ticker"], "as_of": response["as_of"],
        "first_date": response["first_date"], "last_date": response["last_date"],
        "point_count": response["point_count"], "basis": response["basis"],
        "provider": response["provider"], "source_sha256": response["source_sha256"],
        "requests_attempted": response["requests_attempted"],
        "issuer_authenticated": False,
        "market_data_rights_verified": False,
        "full_a_b_c_ready": False, "trade_executed": False,
    })
    st.warning("일별 종가만 수집했습니다. 실제 지수·기업공시와의 기간 결합, "
               "공급자 이용권한 및 Engine A/B/C 전체 검증은 아직 완료되지 않았습니다.")
