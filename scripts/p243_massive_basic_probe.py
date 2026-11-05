"""Manually approved one-shot free Massive Basic Stocks + true NDX probe.

No SEC GET, storage, public output or original market bars. Exactly one
stock GET, then one I:NDX GET; no retry/redirect/proxy. Launch requires
--live, a real TTY and a separate typed confirmation. Personal research only.

Examples:
  python -m scripts.p243_massive_basic_probe --ticker AAPL
  python -m scripts.p243_massive_basic_probe --ticker AAPL --live
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
import re
import sys
from urllib.error import HTTPError, URLError

from proofinvest.market_provider_massive import (
    _KEY, _SYMBOL, _https_get, _url, parse_massive_daily,
    free_basic_safe_as_of,
)

_APPROVAL = "REQUEST MASSIVE BASIC PERSONAL"
_SAFE_PARSE = frozenset({"INVALID_MASSIVE_JSON","PROVIDER_STATUS_SYMBOL_OR_PAGINATION_INVALID",
    "INVALID_DAILY_OBSERVATION_COUNT","RESULTS_COUNT_MISMATCH","QUERY_COUNT_INVALID",
    "UNADJUSTED_STOCK_ONLY","INDEX_ADJUSTED_FIELD_INVALID",
    "INVALID_BAR_FIELDS","INVALID_BAR_TIME_OR_CLOSE",
    "NON_DAILY_BAR_TIMESTAMP","INVALID_BAR_VALUE",
    "NONTRADING_FUTURE_OR_BAD_CLOSE","UNSORTED_DUPLICATE_OR_GAPPED_BAR",
    "ROUNDED_ZERO_CLOSE","RESPONSE_SYMBOL_OR_SIZE_INVALID"})
def _diagnose(exc):
    # Never emit exception text, URL, provider body, headers or API key.
    if isinstance(exc, HTTPError):
        code = exc.code
        return ({401:"HTTP_AUTH_REJECTED",403:"HTTP_FORBIDDEN",
                 404:"HTTP_NOT_FOUND",429:"HTTP_RATE_LIMITED"}.get(
                     code,"HTTP_OTHER_ERROR"), code if code in (401,403,404,429) else None)
    if isinstance(exc, (URLError, TimeoutError, OSError)):
        return ("NETWORK_OR_TLS_UNAVAILABLE",None)
    if isinstance(exc, ValueError):
        msg = str(exc)
        return ("PARSER_"+msg if msg in _SAFE_PARSE else
                "PARSER_OR_RESPONSE_UNAVAILABLE",None)
    return ("LOCAL_PROCESSING_UNAVAILABLE",None)



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Massive one-shot personal EOD source probe")
    parser.add_argument("--live", action="store_true",
                        help="Allow up to two actual Massive HTTPS GETs after TTY confirmation")
    parser.add_argument("--ticker", default="AAPL", help="One uppercase stock ticker")
    safe_as_of = free_basic_safe_as_of()
    parser.add_argument("--as-of", default=safe_as_of,
                        help="historical EOD YYYY-MM-DD (default: conservative free Basic date)")
    args = parser.parse_args(argv)
    try:
        validated_asof = datetime.strptime(args.as_of, "%Y-%m-%d").date()
        valid = (args.as_of == validated_asof.isoformat()
                 and _SYMBOL.fullmatch(args.ticker) is not None)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        print(json.dumps({"status":"BLOCKED","reason_code":"INVALID_TICKER_OR_DATE",
                          "network_requests":0},sort_keys=True))
        return 2
    if args.as_of > safe_as_of:
        print(json.dumps({"status":"BLOCKED",
                          "reason_code":"FREE_BASIC_EOD_NOT_AVAILABLE_YET",
                          "safe_as_of":safe_as_of,
                          "network_requests":0},sort_keys=True))
        return 2
    if not args.live:
        print(json.dumps({"status":"DRY_RUN_NO_REQUEST",
                          "ticker":args.ticker,"index":"I:NDX",
                          "as_of":args.as_of,"network_requests":0,
                          "commercial_reuse_allowed":False},sort_keys=True))
        return 0
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(json.dumps({"status":"BLOCKED","reason_code":"TTY_REQUIRED",
                          "network_requests":0},sort_keys=True))
        return 2
    print("Only personal research with your $0 Individual Basic account.")
    print("2 requests maximum (stock once, actual I:NDX once).")
    print("Never paste your key into chat, GitHub, or screenshots.")
    try:
        consent = input("Type REQUEST MASSIVE BASIC PERSONAL for 2 live GETs: ").strip()
    except (EOFError, KeyboardInterrupt):
        consent = ""
    if consent != _APPROVAL:
        print(json.dumps({"status":"BLOCKED","reason_code":"OWNER_DECLINED",
                          "network_requests":0},sort_keys=True))
        return 2
    try:
        key = getpass.getpass("Massive API Key (hidden): ")
    except (EOFError, KeyboardInterrupt):
        key = ""
    if _KEY.fullmatch(key) is None:
        print(json.dumps({"status":"BLOCKED","reason_code":"INVALID_KEY_SHAPE",
                          "network_requests":0},sort_keys=True))
        return 2
    attempts = 0
    stage = "stock"
    try:
        stock_url = _url(symbol=args.ticker, as_of=args.as_of,
                         api_key=key, index=False)
        attempts += 1
        stock = parse_massive_daily(
            _https_get(stock_url), symbol=args.ticker,
            as_of=args.as_of, index=False)
        stage = "index"
        index_url = _url(symbol="I:NDX", as_of=args.as_of,
                         api_key=key, index=True)
        attempts += 1
        ndx = parse_massive_daily(_https_get(index_url), symbol="I:NDX",
                                  as_of=args.as_of, index=True)
        receipt = {
            "status":"TWO_SOURCE_DAILY_PARSED_ORIGIN_AND_RIGHTS_UNVERIFIED",
            "stock_ticker":args.ticker,"index_symbol":"I:NDX",
            "as_of":args.as_of,
            "stock_points":stock["point_count"],
            "index_points":ndx["point_count"],
            "stock_first":stock["first_date"],"stock_last":stock["last_date"],
            "index_first":ndx["first_date"],"index_last":ndx["last_date"],
            "stock_body_sha256":stock["source_sha256"],
            "index_body_sha256":ndx["source_sha256"],
            "provider":"massive", "network_requests":attempts,"retries":0,
            "provider_origin_independently_authenticated":False,
            "market_data_rights_verified":False,
            "commercial_reuse_allowed":False,"external_display_allowed":False,
            "full_a_b_c_ready":False,
        }
        print(json.dumps(receipt,sort_keys=True))
        return 0
    except (ValueError, TypeError, OSError, OverflowError, TimeoutError,
            KeyError, RecursionError, AttributeError) as exc:
        reason, http_code = _diagnose(exc)
        output = {"status":"BLOCKED", "reason_code":reason,
                  "failed_stage":stage, "network_requests":attempts,
                  "retries":0, "market_data_rights_verified":False}
        if http_code is not None:
            output["http_status"] = http_code
        print(json.dumps(output,sort_keys=True))
        return 2
    finally:
        key = None


if __name__ == "__main__":
    raise SystemExit(main())
