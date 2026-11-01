"""P109 strict offline adapter for operator-supplied Twelve Data 1day responses.

Not a Twelve Data API client. Free Basic data is test/internal-only:
no provider HTTP, credentials, distribution, production or license claim.
The provider's 'Index' type and true Nasdaq-100 index symbol must be
established; an ETF (QQQ) is never silently substituted for Nasdaq-100.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any

from .issuer_ir_engine_bridge import analyze_historical_ir_engines
from .local_sec_packet import _read_regular_local
from .market_price_csv import market_price_csv_to_json

MAX_RESPONSE_BYTES = 131_072
_ENDPOINT_NO_KEY = "https://api.twelvedata.com/time_series"
_NUMBER = re.compile(r"(?:0|[1-9][0-9]{0,10})(?:\.[0-9]{1,8})?\Z")
_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_REF = "https://twelvedata.com/docs"


def _reject(code: str) -> None:
    raise ValueError(code)


def _pairs(entries: list[tuple[str, Any]]) -> dict:
    obj = {}
    for k, v in entries:
        if k in obj:
            _reject("DUPLICATE_PROVIDER_JSON_KEY")
        obj[k] = v
    return obj


def _date(value: str, field: str) -> date:
    if type(value) is not str or _DAY.fullmatch(value) is None:
        _reject("INVALID_" + field)
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            _reject("INVALID_" + field)
        return parsed
    except ValueError:
        _reject("INVALID_" + field)


def _price(value: Any) -> str:
    if type(value) is not str or _NUMBER.fullmatch(value) is None:
        _reject("INVALID_PROVIDER_CLOSE")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        _reject("INVALID_PROVIDER_CLOSE")
    if not amount.is_finite() or amount <= 0:
        _reject("INVALID_PROVIDER_CLOSE")
    return value


def _read_series(raw: bytes, *, symbol: str, market_kind: str,
                 as_of: date, retrieved_at: date) -> dict[str, str]:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_RESPONSE_BYTES:
        _reject("PROVIDER_RESPONSE_BYTES_INVALID")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                         parse_constant=lambda _: _reject("NONFINITE_PROVIDER_JSON"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _reject("PROVIDER_RESPONSE_NOT_JSON")
    if type(obj) is not dict or obj.get("status") != "ok":
        _reject("PROVIDER_REPORTED_ERROR_OR_STATUS_UNKNOWN")
    meta, values = obj.get("meta"), obj.get("values")
    if type(meta) is not dict or type(values) is not list:
        _reject("PROVIDER_META_OR_VALUES_MISSING")
    if (meta.get("symbol") != symbol or meta.get("interval") != "1day"
            or meta.get("exchange_timezone") != "America/New_York"
            or meta.get("type") != market_kind
            or (meta.get("currency") != "USD" if market_kind == "Common Stock"
                else meta.get("currency") not in (None, "USD"))):
        _reject("PROVIDER_SYMBOL_TYPE_CURRENCY_INTERVAL_MISMATCH")
    if not 31 <= len(values) <= 501:
        _reject("PROVIDER_OBSERVATION_LIMIT")
    out: dict[str, str] = {}
    last = None
    for row in values:
        if type(row) is not dict:
            _reject("PROVIDER_ROW_NOT_OBJECT")
        day = _date(row.get("datetime"), "OBSERVATION_DATE")
        if day.weekday() >= 5 or day > as_of or day > retrieved_at:
            _reject("PROVIDER_NONTRADING_FUTURE_OR_UNAVAILABLE_DATE")
        # Twelve Data's historical time_series is reverse chronological;
        # reject mixed order and duplicates, do not silently reorder.
        if last is not None and day >= last:
            _reject("PROVIDER_DATES_DUPLICATE_OR_NOT_DESCENDING")
        if day <= date(2025, 2, 26):
            _reject("PRICE_PRECEDES_ISSUER_IR_PUBLICATION")
        out[day.isoformat()] = _price(row.get("close"))
        last = day
    return out


def prepare_private_twelvedata_pair(
    stock_response: bytes, index_response: bytes, *,
    as_of: str = "2025-10-16", retrieved_at: str = "2025-10-16",
    index_symbol: str = "NDX", acknowledged_internal_test: bool = False,
) -> dict[str, Any]:
    """Create a P108-ready CSV from TWO validated internal-test responses.

    Requires exact Nasdaq-100 *index* type from provider; NDX availability,
    account entitlements, and license are NOT independently established.
    No API key passed, accepted or saved.
    """
    if acknowledged_internal_test is not True:
        _reject("TEST_ONLY_USAGE_ACK_REQUIRED")
    if index_symbol != "NDX":
        _reject("UNREVIEWED_INDEX_SYMBOL_OR_ETF_PROXY")
    asof, received = _date(as_of, "AS_OF"), _date(retrieved_at, "RETRIEVED_AT")
    if not (date(2025, 2, 26) <= received <= asof <= date.today()):
        _reject("PROVIDER_RESPONSE_VINTAGE_AFTER_AS_OF_OR_FUTURE")
    stock = _read_series(stock_response, symbol="NVDA", market_kind="Common Stock",
                         as_of=asof, retrieved_at=received)
    index = _read_series(index_response, symbol=index_symbol, market_kind="Index",
                         as_of=asof, retrieved_at=received)
    if set(stock) != set(index):
        _reject("PROVIDER_MARKET_CALENDAR_NOT_ALIGNED")
    if not 31 <= len(stock) <= 501:
        _reject("PROVIDER_MATCHED_ROWS_INSUFFICIENT")
    csv_buffer = StringIO(newline="")
    writer = csv.writer(csv_buffer, lineterminator="\n")
    writer.writerow(("date", "security_close", "benchmark_close"))
    for day in sorted(stock):
        writer.writerow((day, stock[day], index[day]))
    paired = csv_buffer.getvalue().encode("utf-8")
    market_price_csv_to_json(
        paired, issuer_cik="0001045810", as_of=as_of,
        symbol="NVDA", benchmark="NASDAQ_100",
        return_basis="PRICE_ONLY_CLOSE",
        source_url=_ENDPOINT_NO_KEY, published_at=retrieved_at,
    )
    return {
        "schema": "kuodra.twelvedata-offline-paired-intake.v1",
        "status": "LOCAL_TEST_RESPONSE_VALIDATED_ORIGIN_UNVERIFIED",
        "market_csv": paired,
        "source_url_no_credentials": _ENDPOINT_NO_KEY,
        "retrieved_at_operator_reported": retrieved_at,
        "stock_response_sha256": sha256(stock_response).hexdigest(),
        "index_response_sha256": sha256(index_response).hexdigest(),
        "paired_csv_sha256": sha256(paired).hexdigest(),
        "observation_count": len(stock),
        "first_date": min(stock), "last_date": max(stock),
        "stock_symbol": "NVDA", "index_symbol": index_symbol,
        "index_is_not_etf": True,
        "origin_authenticated": False, "provider_rights_verified": False,
        "commercial_display_permitted": False, "redistribution_permitted": False,
        "point_in_time_vintage_authenticated": False,
        "network_requests": 0,
    }


def run_private_twelvedata_p108(
    stock_response: bytes, index_response: bytes, *,
    as_of: str = "2025-10-16", retrieved_at: str = "2025-10-16",
    index_symbol: str = "NDX", acknowledged_internal_test: bool = False,
) -> dict:
    """Use P108 true arithmetic, never upgrade to real licensed E2E."""
    intake = prepare_private_twelvedata_pair(
        stock_response, index_response, as_of=as_of, retrieved_at=retrieved_at,
        index_symbol=index_symbol,
        acknowledged_internal_test=acknowledged_internal_test,
    )
    result = analyze_historical_ir_engines(
        as_of=as_of, price_csv=intake["market_csv"],
        price_source_url=intake["source_url_no_credentials"],
        price_published_at=retrieved_at,
    )
    if (result.get("engine_a", {}).get("status") != "REPORTED_UNVERIFIED"
            or result.get("engine_b", {}).get("status") !=
            "PARTIAL_HISTORICAL_MANUAL_NUMERIC_ONLY"
            or result.get("guard", {}).get("decision") != "HOLD"
            or result.get("network_requests") != 0
            or result.get("sec_accessed") is not False
            or result.get("full_abc_authenticated") is not False):
        _reject("P108_PROVIDER_EVIDENCE_JOIN_NOT_ELIGIBLE")
    public_receipt = {key: val for key, val in intake.items() if key != "market_csv"}
    return {
        "schema": "kuodra.twelvedata-p108-private-test.v1",
        "status": "OFFLINE_MARKET_MATH_ONLY_UNAUTHENTICATED",
        "intake": public_receipt, "analysis": result,
        "full_real_data_pipeline_verified": False,
        "provider_account_connected": False,
        "external_requests_executed": 0,
        "guard_decision": "HOLD", "trade_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Twelve Data historical response files to offline A/B/C; NO HTTP")
    p.add_argument("--stock-response", type=Path, required=True)
    p.add_argument("--index-response", type=Path, required=True)
    p.add_argument("--as-of", default="2025-10-16")
    p.add_argument("--retrieved-at", required=True)
    p.add_argument("--confirm-internal-test-only", action="store_true")
    args = p.parse_args(argv)
    try:
        if not args.confirm_internal_test_only:
            _reject("TEST_ONLY_USAGE_ACK_REQUIRED")
        if args.stock_response.resolve() == args.index_response.resolve():
            _reject("SAME_PROVIDER_FILE_NOT_TWO_SOURCES")
        stock = _read_regular_local(args.stock_response, MAX_RESPONSE_BYTES)
        index = _read_regular_local(args.index_response, MAX_RESPONSE_BYTES)
        out = run_private_twelvedata_p108(
            stock, index, as_of=args.as_of, retrieved_at=args.retrieved_at,
            acknowledged_internal_test=True,
        )
        print(json.dumps(out, sort_keys=True, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            InvalidOperation, RecursionError):
        print(json.dumps({
            "status": "UNAVAILABLE", "reason_code": "PROVIDER_INPUT_OR_LICENSE_GATE_BLOCKED",
            "external_requests_executed": 0, "trade_executed": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
