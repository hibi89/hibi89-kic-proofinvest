"""P250 offline Nasdaq-100 daily close CSV adapter (FRED official series ID).

No network, no credential, no persistent market data, no source/license
attestation. NASDAQ100 is Nasdaq copyrighted data surfaced by FRED:
https://fred.stlouisfed.org/series/NASDAQ100
https://fred.stlouisfed.org/docs/api/terms_of_use.html
Third-party permissions for public, AI, contest or commercial reuse are
NOT supplied by a CSV, this module, or FRED.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from io import StringIO
import json
import re
from typing import Any
from urllib.parse import urlsplit

_MAX_FILE = 2_097_152
_MAX_ROWS = 20_000
_MAX_OBSERVATIONS = 100
_DEC = Decimal("0.00000001")
_VALUE = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,8})?\Z", re.ASCII)
_SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z", re.ASCII)
_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_SHA = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_FRED_URL = "https://fred.stlouisfed.org/series/NASDAQ100"


def _iso(value: str) -> date:
    if type(value) is not str:
        raise ValueError("INVALID_CALENDAR_DATE")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("INVALID_CALENDAR_DATE") from exc
    if d.isoformat() != value:
        raise ValueError("NONCANONICAL_CALENDAR_DATE")
    return d


def _price(value: str) -> str:
    if type(value) is not str or _VALUE.fullmatch(value) is None:
        raise ValueError("INVALID_DAILY_CLOSE")
    try:
        p = Decimal(value)
        if not p.is_finite() or not 0 < p < Decimal("1e10"):
            raise ValueError("INVALID_DAILY_CLOSE")
        return format(p.quantize(_DEC, rounding=ROUND_HALF_UP), "f")
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError("INVALID_DAILY_CLOSE") from exc


def _parse_csv(raw: bytes, *, as_of: str, header: tuple[str, str],
               allow_missing: bool) -> dict[str, Any]:
    """Strict two-column CSV; reject a forged series, stale/unsafe bars."""
    if type(raw) is not bytes or not 16 <= len(raw) <= _MAX_FILE or b"\x00" in raw:
        raise ValueError("INVALID_CSV_BYTES")
    cutoff = _iso(as_of)
    if cutoff > datetime.now(timezone.utc).date():
        raise ValueError("FUTURE_AS_OF_DATE")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("INVALID_CSV_ENCODING") from exc
    try:
        rows = csv.reader(StringIO(text, newline=""), strict=True)
        columns = next(rows)
        allowed = (header, ("DATE", "NASDAQ100")) if allow_missing else (header,)
        if tuple(columns) not in allowed:
            raise ValueError("UNEXPECTED_CSV_SERIES_HEADER")
        points: list[dict[str, str]] = []
        previous_input = None
        missing = 0
        entries = 0
        for row in rows:
            entries += 1
            if entries > _MAX_ROWS:
                raise ValueError("CSV_TOO_MANY_ROWS")
            if len(row) != 2:
                raise ValueError("INVALID_CSV_ROW_SHAPE")
            d = _iso(row[0])
            if previous_input is not None and d <= previous_input:
                raise ValueError("UNSORTED_DUPLICATE_CSV_DATE")
            previous_input = d
            # Calendar validation applies to every input row, including
            # missing '.' FRED values. Otherwise a missing weekend/future
            # row can silently bypass the claimed as-of source contract.
            if d.weekday() >= 5:
                raise ValueError("WEEKEND_DAILY_PRICE")
            if d > cutoff:
                raise ValueError("POST_AS_OF_DAILY_PRICE")
            value = row[1]
            if allow_missing and value in ("", "."):
                missing += 1  # valid dated missing values, no forward fill
                continue
            close = _price(value)
            if points and (d - _iso(points[-1]["date"])).days > 7:
                # Gaps in actual observations must never be silently filled.
                raise ValueError("OBSERVATION_GAP_GT_7_DAYS")
            points.append({"date": d.isoformat(), "close": close})
    except (csv.Error, UnicodeError) as exc:
        raise ValueError("INVALID_CSV_FORMAT") from exc
    if not 31 <= len(points):
        raise ValueError("INSUFFICIENT_DAILY_OBSERVATIONS")
    points = points[-_MAX_OBSERVATIONS:]
    if (cutoff - _iso(points[-1]["date"])).days > 7:
        raise ValueError("STALE_DAILY_OBSERVATIONS")
    return {
        "close_observations": points,
        "point_count": len(points),
        "first_date": points[0]["date"],
        "last_date": points[-1]["date"],
        "input_rows": entries,
        "missing_rows_ignored": missing,
        "source_sha256": sha256(raw).hexdigest(),
        "as_of": as_of,
    }


def parse_fred_nasdaq100_csv(raw: bytes, *, as_of: str) -> dict[str, Any]:
    """Local owner-supplied FRED CSV: real benchmark *identity*, not origin proof."""
    base = _parse_csv(raw, as_of=as_of,
                      header=("observation_date", "NASDAQ100"), allow_missing=True)
    return {
        **base,
        "schema": "kuodra.fred-nasdaq100-offline.v1",
        "status": "DAILY_CLOSE_UNVERIFIED",
        "provider": "FRED_OWNER_CSV_UNVERIFIED",
        "series_id": "NASDAQ100",
        "index_symbol": "I:NDX",
        "kind": "index",
        "basis": "PRICE_ONLY_CLOSE",
        "source_url": _FRED_URL,
        "source_authenticated": False,
        "source_rights_verified": False,
        "commercial_reuse_allowed": False,
        "public_display_allowed": False,
        "ai_processing_allowed": False,
    }


def _valid_source_url(url: str) -> bool:
    if type(url) is not str or len(url) > 400:
        return False
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and bool(p.hostname)
                and "." in p.hostname and not p.username and not p.password
                and p.port in (None, 443) and not p.query and not p.fragment
                and p.hostname.lower() not in ("localhost", "127.0.0.1")
                and not p.path.startswith("//"))
    except ValueError:
        return False


def parse_owner_stock_csv(raw: bytes, *, ticker: str, as_of: str,
                          source_url: str) -> dict[str, Any]:
    """Do not assert where an owner-supplied stock CSV originally came from."""
    if (type(ticker) is not str or _SYMBOL.fullmatch(ticker) is None
            or ticker.startswith("I:") or not _valid_source_url(source_url)):
        raise ValueError("INVALID_STOCK_IDENTITY_OR_SOURCE_URL")
    base = _parse_csv(raw, as_of=as_of, header=("date", "close"),
                      allow_missing=False)
    return {
        **base,
        "schema": "kuodra.owner-stock-offline.v1",
        "status": "DAILY_CLOSE_UNVERIFIED",
        "provider": "OWNER_CSV_ORIGIN_UNVERIFIED",
        "ticker": ticker,
        "kind": "stock",
        "basis": "PRICE_ONLY_CLOSE",
        "source_url": source_url,
        "source_authenticated": False,
        "source_rights_verified": False,
        "commercial_reuse_allowed": False,
        "public_display_allowed": False,
        "ai_processing_allowed": False,
    }


def _trusted_shape(receipt: dict, *, kind: str, as_of: str) -> dict[str, str]:
    if type(receipt) is not dict:
        raise ValueError("OFFLINE_SOURCE_UNTRUSTED")
    api_index = (kind == "index"
                 and receipt.get("schema") == "kuodra.fred-nasdaq100-api.v1"
                 and receipt.get("status") ==
                 "FRED_API_DAILY_PARSED_ORIGIN_AND_RIGHTS_UNVERIFIED"
                 and receipt.get("provider") == "FRED_API_NASDAQ100_UNVERIFIED"
                 and receipt.get("source_format") == "FRED_V1_JSON"
                 and type(receipt.get("request_count")) is int
                 and receipt["request_count"] == 1
                 and type(receipt.get("network_requests")) is int
                 and receipt["network_requests"] == 1
                 and type(receipt.get("retries")) is int
                 and receipt["retries"] == 0
                 and receipt.get("trade_executed") is False)
    if ((not api_index and (
                receipt.get("schema") != (
                    "kuodra.fred-nasdaq100-offline.v1" if kind == "index"
                    else "kuodra.owner-stock-offline.v1")
                or receipt.get("status") != "DAILY_CLOSE_UNVERIFIED"))
            or receipt.get("kind") != kind
            or receipt.get("basis") != "PRICE_ONLY_CLOSE"
            or receipt.get("as_of") != as_of
            or receipt.get("source_authenticated") is not False
            or receipt.get("source_rights_verified") is not False
            or receipt.get("commercial_reuse_allowed") is not False
            or receipt.get("public_display_allowed") is not False
            or receipt.get("ai_processing_allowed") is not False
            or type(receipt.get("source_sha256")) is not str
            or _SHA.fullmatch(receipt["source_sha256"]) is None
            or not _valid_source_url(receipt.get("source_url"))):
        raise ValueError("OFFLINE_SOURCE_UNTRUSTED")
    if kind == "index" and (
            (not api_index and receipt.get("provider") != "FRED_OWNER_CSV_UNVERIFIED")
            or receipt.get("index_symbol") != "I:NDX"
            or receipt.get("series_id") != "NASDAQ100"
            or receipt.get("source_url") != _FRED_URL):
        raise ValueError("INDEX_SOURCE_IDENTITY_MISMATCH")
    if kind == "stock" and (
            receipt.get("provider") != "OWNER_CSV_ORIGIN_UNVERIFIED"
            or type(receipt.get("ticker")) is not str
            or _SYMBOL.fullmatch(receipt["ticker"]) is None):
        raise ValueError("STOCK_SOURCE_IDENTITY_MISMATCH")
    from .market_pair_engine_a import _points
    return _points(receipt, kind=kind, cutoff=_iso(as_of))


def analyze_offline_fred_pair(*, stock: dict, index: dict, ticker: str,
                              issuer_cik: str, filing_date: str,
                              as_of: str) -> dict[str, Any]:
    """Actual local Decimal Engine A; no claim of authenticated real sources."""
    blocked = {
        "schema": "kuodra.fred-offline-engine-a.v1",
        "status": "BLOCKED", "reason_code": "OFFLINE_SOURCE_OR_CALENDAR_INVALID",
        "market_analysis": None, "matched_observation_count": 0,
        "network_requests": 0, "source_authenticated": False,
        "source_rights_verified": False, "commercial_reuse_allowed": False,
        "public_display_allowed": False, "ai_processing_allowed": False,
        "full_a_b_c_ready": False, "guard_executed": False,
        "trade_executed": False,
    }
    try:
        if (type(ticker) is not str or _SYMBOL.fullmatch(ticker) is None
                or type(issuer_cik) is not str or _CIK.fullmatch(issuer_cik) is None
                or issuer_cik == "0000000000" or stock.get("ticker") != ticker):
            raise ValueError("INVALID_ISSUER")
        cutoff, filing = _iso(as_of), _iso(filing_date)
        if cutoff <= filing:
            raise ValueError("NO_POST_FILING_PERIOD")
        sp = _trusted_shape(stock, kind="stock", as_of=as_of)
        ip = _trusted_shape(index, kind="index", as_of=as_of)
        # Fully validated in-memory receipts; prices before filing never enter
        # the regression. Reject incompatible calendars rather than filling.
        sd = {d for d in sp if _iso(d) > filing}
        idays = {d for d in ip if _iso(d) > filing}
        common = sorted(sd & idays)
        if (len(common) < 31 or 5 * len(common) < 4 * len(sd)
                or 5 * len(common) < 4 * len(idays)
                or (cutoff - _iso(common[-1])).days > 7):
            raise ValueError("POST_FILING_PERIOD_INCOMPATIBLE")
        if any((_iso(b) - _iso(a)).days > 7 for a,b in zip(common, common[1:])):
            raise ValueError("GAPPED_PAIR")
        common = common[-100:]
        def make_series(points: dict, receipt: dict) -> dict:
            return {
                "source": {
                    "provider": receipt["provider"],
                    "url": receipt["source_url"],
                    "published_at": as_of,
                    "sha256": receipt["source_sha256"],
                },
                "observations": [{"date": d, "value": points[d]} for d in common],
            }
        payload = {
            "schema": "kuodra.market-reality.v1", "issuer_cik": issuer_cik,
            "as_of": as_of, "symbol": ticker, "benchmark": "NASDAQ_100",
            "return_basis": "PRICE_ONLY_CLOSE",
            "security": make_series(sp, stock),
            "index": make_series(ip, index),
        }
        from .market_reality import analyze_market_reality
        wire = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        result = analyze_market_reality(
            payload, expected_issuer_cik=issuer_cik, analysis_as_of=as_of,
            sec_review=None, uploaded_sha256=sha256(wire).hexdigest(),
        )
        if (result.get("status") not in
                ("REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE")
                or result.get("source_authenticated") is not False
                or result.get("trade_signal") is not False
                or result.get("market_bubble_proven") is not False
                or result.get("guard_policy_modified") is not False):
            raise ValueError("INVALID_ENGINE_TRUST_CONTRACT")
        return {
            **blocked,
            "status": "OFFLINE_FRED_ENGINE_A_DESCRIPTIVE_UNVERIFIED",
            "reason_code": "SOURCE_ORIGIN_AND_RIGHTS_NOT_VERIFIED",
            "ticker": ticker, "index_symbol": "I:NDX",
            "matched_observation_count": len(common),
            "matched_period_start": common[0],
            "matched_period_end": common[-1],
            "stock_file_sha256": stock["source_sha256"],
            "index_file_sha256": index["source_sha256"],
            "index_source_format": (
                "FRED_V1_JSON" if index.get("schema") ==
                "kuodra.fred-nasdaq100-api.v1" else "OWNER_CSV_UNVERIFIED"),
            "derived_payload_sha256": sha256(wire).hexdigest(),
            "market_analysis": {
                k: result.get(k) for k in (
                    "status", "security_return_pct", "benchmark_return_pct",
                    "beta", "regression_intercept_daily_pct", "r_squared",
                )
            }
        }
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        return blocked

def plan_local_stock_for_fred_index(*, stock: dict, ticker: str,
                                    issuer_cik: str, filing_date: str,
                                    as_of: str) -> dict[str, Any]:
    """P256: validate stock and feasible post-filing window BEFORE a FRED GET.

    Local facts are strictly owner asserted. A ready plan does not prove any
    index overlap, vendor authenticity, legal entitlement, or SEC accession.
    Returns only redacted metadata; never raw closes or complete trade dates.
    """
    blocked = {
        "schema": "kuodra.fred-local-stock-pair-plan.v1",
        "status": "BLOCKED",
        "reason_code": "LOCAL_STOCK_OR_FILING_NOT_ELIGIBLE",
        "network_requests": 0,
        "stock_source_sha256": None,
        "source_authenticated": False,
        "source_rights_verified": False,
        "commercial_reuse_allowed": False,
        "public_display_allowed": False,
        "ai_processing_allowed": False,
        "full_a_b_c_ready": False,
        "trade_executed": False,
    }
    try:
        if (type(stock) is not dict
                or type(ticker) is not str or _SYMBOL.fullmatch(ticker) is None
                or stock.get("ticker") != ticker
                or type(issuer_cik) is not str
                or _CIK.fullmatch(issuer_cik) is None
                or issuer_cik == "0000000000"):
            raise ValueError("INVALID_STOCK_IDENTITY")
        cutoff, filed = _iso(as_of), _iso(filing_date)
        if filed >= cutoff:
            raise ValueError("FILING_AFTER_CUTOFF")
        rows = _trusted_shape(stock, kind="stock", as_of=as_of)
        # FRED v1 adapter only requests this historical window. A local
        # stock dataset with fewer than 31 eligible sessions in this window
        # cannot possibly satisfy the actual Engine A index overlap gate.
        from datetime import timedelta
        first = cutoff - timedelta(days=190)
        eligible = [d for d in rows if filed < _iso(d) <= cutoff
                    and _iso(d) >= first]
        if (len(eligible) < 31
                or (cutoff - _iso(eligible[-1])).days > 7
                or any((_iso(b) - _iso(a)).days > 7
                       for a, b in zip(eligible, eligible[1:]))):
            raise ValueError("INSUFFICIENT_POSSIBLE_POST_FILING_MATCHES")
        return {
            **blocked,
            "status": "LOCAL_STOCK_READY_INDEX_REQUIRED_UNVERIFIED",
            "reason_code": "FRED_INDEX_MATCH_AND_RIGHTS_NOT_VERIFIED",
            "ticker": ticker, "issuer_cik": issuer_cik, "as_of": as_of,
            "filing_date": filing_date,
            "eligible_post_filing_sessions": len(eligible),
            "first_eligible_date": eligible[0],
            "last_eligible_date": eligible[-1],
            "stock_source_sha256": stock["source_sha256"],
        }
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return blocked

