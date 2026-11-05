"""P252 official FRED v1 NASDAQ100 daily-index API one-shot personal research.

No I:NDX timestamp approximations, QQQ fallback, persistence or automatic GET.
Provider documentation:
  https://fred.stlouisfed.org/docs/api/fred/series_observations.html
Underlying NASDAQ100 index data are copyrighted by Nasdaq, Inc. Source
identity/redistribution/AI/commercial permissions are NOT authenticated.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import csv
import json
import re
import ssl
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener,
)

from .fred_nasdaq100_offline import parse_fred_nasdaq100_csv

_HOST = "https://api.stlouisfed.org/fred/series/observations"
_KEY = re.compile(r"[a-z0-9]{32}\Z", re.ASCII)
_MAX_BODY = 262144
_MAX_OBSERVATIONS = 200
_DAYS = 190


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("FRED_REDIRECT_BLOCKED")


def _iso(value: str) -> date:
    if type(value) is not str:
        raise ValueError("INVALID_AS_OF")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("INVALID_AS_OF") from exc
    if d.isoformat() != value or d > datetime.now(timezone.utc).date():
        raise ValueError("INVALID_AS_OF")
    return d


def _url(*, api_key: str, as_of: str) -> str:
    """Pinned FRED v1 query: immutable series, raw levels, as-of vintage."""
    day = _iso(as_of)
    if type(api_key) is not str or _KEY.fullmatch(api_key) is None:
        raise ValueError("INVALID_FRED_KEY_FORMAT")
    params = {
        "series_id": "NASDAQ100", "api_key": api_key,
        "file_type": "json", "units": "lin", "sort_order": "asc",
        "observation_start": (day - timedelta(days=_DAYS)).isoformat(),
        "observation_end": as_of, "realtime_start": as_of,
        "realtime_end": as_of, "limit": str(_MAX_OBSERVATIONS),
    }
    return _HOST + "?" + urlencode(params)


def _get(url: str) -> bytes:
    """Bounded direct HTTPS, 0 proxy/redirect/retry, opaque errors to caller."""
    opener = build_opener(ProxyHandler({}), _NoRedirect(),
                          HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(Request(url, headers={"Accept": "application/json",
                                          "User-Agent": "KUODRA/1.0 individual-research"}),
                     timeout=8) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("FRED_HTTP_RESPONSE_REJECTED")
        raw = response.read(_MAX_BODY + 1)
        if len(raw) > _MAX_BODY:
            raise ValueError("FRED_RESPONSE_SIZE_INVALID")
        return raw


def _pairs(entries: list[tuple[str, Any]]) -> dict:
    out: dict = {}
    for key, value in entries:
        if key in out:
            raise ValueError("FRED_DUPLICATE_JSON_KEY")
        out[key] = value
    return out


def _constant(_token: str):
    raise ValueError("FRED_NONFINITE_VALUE")


def parse_fred_nasdaq100_api_json(raw: bytes, *, as_of: str) -> dict[str, Any]:
    """Parse ONLY officially shaped FRED observation JSON into index receipt.

    The v1 observation response does not itself echo the series ID: it
    therefore can never certify an authenticated vendor data origin.
    """
    day = _iso(as_of)
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_BODY:
        raise ValueError("FRED_RESPONSE_SIZE_INVALID")
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                             parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("FRED_RESPONSE_JSON_INVALID") from exc
    if type(payload) is not dict:
        raise ValueError("FRED_RESPONSE_ROOT_INVALID")
    if "error_code" in payload or "error_message" in payload:
        raise ValueError("FRED_ERROR_RESPONSE")
    if (payload.get("realtime_start") != as_of
            or payload.get("realtime_end") != as_of
            or payload.get("units") != "lin"
            or payload.get("output_type") not in (1, "1")
            or payload.get("file_type") != "json"
            or payload.get("sort_order") != "asc"):
        raise ValueError("FRED_RESPONSE_CONTRACT_INVALID")
    if (payload.get("observation_start") !=
            (day - timedelta(days=_DAYS)).isoformat()
            or payload.get("observation_end") != as_of):
        raise ValueError("FRED_OBSERVATION_WINDOW_INVALID")
    rows = payload.get("observations")
    if type(rows) is not list or not 31 <= len(rows) <= _MAX_OBSERVATIONS:
        raise ValueError("FRED_OBSERVATIONS_COUNT_INVALID")
    if (type(payload.get("count")) is not int or payload["count"] < len(rows)
            or type(payload.get("offset")) is not int or payload["offset"] != 0
            or type(payload.get("limit")) is not int
            or payload["limit"] != _MAX_OBSERVATIONS):
        raise ValueError("FRED_PAGINATION_UNAVAILABLE")
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["observation_date", "NASDAQ100"])
    previous: date | None = None
    for row in rows:
        if type(row) is not dict or set(row) != {
                "realtime_start", "realtime_end", "date", "value"}:
            raise ValueError("FRED_OBSERVATION_SHAPE_INVALID")
        if row["realtime_start"] != as_of or row["realtime_end"] != as_of:
            raise ValueError("FRED_VINTAGE_MISMATCH")
        date_text = row["date"]
        if type(date_text) is not str:
            raise ValueError("FRED_OBSERVATION_DATE_INVALID")
        try:
            current = date.fromisoformat(date_text)
        except ValueError as exc:
            raise ValueError("FRED_OBSERVATION_DATE_INVALID") from exc
        if (date_text != current.isoformat() or current > day
                or current < day - timedelta(days=_DAYS)
                or (previous is not None and current <= previous)):
            raise ValueError("FRED_OBSERVATION_ORDER_OR_CUTOFF")
        previous = current
        value = row["value"]
        if type(value) is not str or len(value) > 32:
            raise ValueError("FRED_OBSERVATION_VALUE_INVALID")
        writer.writerow([date_text, value])
    # Reuse P250's strict local CSV validator (no Sunday relabel/forward-fill).
    validated = parse_fred_nasdaq100_csv(output.getvalue().encode("utf-8"),
                                         as_of=as_of)
    return {
        **validated,
        "schema": "kuodra.fred-nasdaq100-api.v1",
        "status": "FRED_API_DAILY_PARSED_ORIGIN_AND_RIGHTS_UNVERIFIED",
        "source_sha256": sha256(raw).hexdigest(),
        "source_format": "FRED_V1_JSON",
        "request_count": 1, "retries": 0,
        "network_requests": 1,
        "provider": "FRED_API_NASDAQ100_UNVERIFIED",
        "source_authenticated": False,
        "source_rights_verified": False,
        "public_display_allowed": False,
        "commercial_reuse_allowed": False,
        "ai_processing_allowed": False,
        "trade_executed": False,
    }


def run_one_fred_ndx_get(*, api_key: str, as_of: str,
                         explicit_approval: bool = False,
                         individual_research: bool = False,
                         transport: Callable[[str], bytes] | None = None,
                         paired_stock: dict | None = None,
                         paired_ticker: str | None = None,
                         paired_issuer_cik: str | None = None,
                         paired_filing_date: str | None = None) -> dict:
    """No GET unless user explicitly opts in; bounded at most 1 HTTPS GET."""
    receipt = {
        "status": "BLOCKED", "reason_code": "FRED_APPROVAL_REQUIRED",
        "network_requests": 0, "retries": 0,
        "market_data_rights_verified": False,
        "source_authenticated": False, "commercial_reuse_allowed": False,
        "public_display_allowed": False, "ai_processing_allowed": False,
    }
    if not explicit_approval or not individual_research:
        return receipt
    try:
        url = _url(api_key=api_key, as_of=as_of)
    except (TypeError, ValueError):
        return {**receipt, "reason_code": "FRED_KEY_OR_DATE_INVALID"}
    pair_fields = (paired_ticker, paired_issuer_cik, paired_filing_date)
    if paired_stock is None and any(x is not None for x in pair_fields):
        return {**receipt, "reason_code": "FRED_PAIR_ARGS_INCOMPLETE"}
    if paired_stock is not None:
        try:
            from .fred_nasdaq100_offline import _trusted_shape
            _trusted_shape(paired_stock, kind="stock", as_of=as_of)
            if (type(paired_ticker) is not str
                    or paired_stock.get("ticker") != paired_ticker
                    or type(paired_issuer_cik) is not str
                    or re.fullmatch(r"[0-9]{10}", paired_issuer_cik) is None
                    or paired_issuer_cik == "0000000000"
                    or type(paired_filing_date) is not str
                    or date.fromisoformat(paired_filing_date) >= _iso(as_of)
                    or date.fromisoformat(paired_filing_date).isoformat() != paired_filing_date):
                raise ValueError("FRED_PAIR_ARGUMENTS_INVALID")
        except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
            return {**receipt, "reason_code": "FRED_PAIR_LOCAL_INPUT_INVALID"}
    result = {**receipt, "network_requests": 1}
    try:
        raw = (transport or _get)(url)
        parsed = parse_fred_nasdaq100_api_json(raw, as_of=as_of)
        summary = {**result,
                   "status": parsed["status"], "reason_code": "SOURCE_AND_RIGHTS_UNVERIFIED",
                   "index_symbol": "I:NDX", "series_id": "NASDAQ100",
                   "point_count": parsed["point_count"],
                   "first_date": parsed["first_date"], "last_date": parsed["last_date"],
                   "source_sha256": parsed["source_sha256"]}
        if paired_stock is not None:
            from .fred_nasdaq100_offline import analyze_offline_fred_pair
            pair = analyze_offline_fred_pair(
                stock=paired_stock, index=parsed, ticker=paired_ticker,
                issuer_cik=paired_issuer_cik, filing_date=paired_filing_date,
                as_of=as_of)
            summary["paired_engine_a"] = {
                "status": ("FRED_API_ENGINE_A_DESCRIPTIVE_UNVERIFIED"
                           if pair["status"] ==
                           "OFFLINE_FRED_ENGINE_A_DESCRIPTIVE_UNVERIFIED"
                           else "BLOCKED"),
                "reason_code": pair["reason_code"],
                "matched_observation_count": pair["matched_observation_count"],
                "matched_period_start": pair.get("matched_period_start"),
                "matched_period_end": pair.get("matched_period_end"),
                "market_analysis": pair["market_analysis"],
                "source_authenticated": False, "source_rights_verified": False,
                "full_a_b_c_ready": False, "trade_executed": False,
            }
        return summary
    except HTTPError as exc:
        safe = {400: "FRED_BAD_REQUEST", 401: "FRED_UNAUTHORIZED",
                403: "FRED_FORBIDDEN", 404: "FRED_NOT_FOUND",
                429: "FRED_RATE_LIMITED"}
        return {**result, "reason_code": safe.get(exc.code, "FRED_HTTP_UNAVAILABLE"),
                "http_status": exc.code if exc.code in safe else None}
    except (URLError, OSError, TimeoutError):
        return {**result, "reason_code": "FRED_NETWORK_UNAVAILABLE"}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return {**result, "reason_code": "FRED_RESPONSE_NOT_ACCEPTED"}
