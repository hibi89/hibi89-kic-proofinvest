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

from proofinvest.market_provider_massive import (
    _KEY, _SYMBOL, _https_get, _url, parse_massive_daily,
)

_APPROVAL = "REQUEST MASSIVE BASIC PERSONAL"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Massive one-shot personal EOD source probe")
    parser.add_argument("--live", action="store_true",
                        help="Allow up to two actual Massive HTTPS GETs after TTY confirmation")
    parser.add_argument("--ticker", default="AAPL", help="One uppercase stock ticker")
    parser.add_argument("--as-of", default=datetime.now(timezone.utc).date().isoformat(),
                        help="UTC date YYYY-MM-DD")
    args = parser.parse_args(argv)
    if (_SYMBOL.fullmatch(args.ticker) is None
            or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", args.as_of)
            or args.as_of > datetime.now(timezone.utc).date().isoformat()):
        print(json.dumps({"status":"BLOCKED","reason_code":"INVALID_TICKER_OR_DATE",
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
    try:
        stock_url = _url(symbol=args.ticker, as_of=args.as_of,
                         api_key=key, index=False)
        attempts += 1
        stock = parse_massive_daily(
            _https_get(stock_url), symbol=args.ticker,
            as_of=args.as_of, index=False)
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
            KeyError, RecursionError, AttributeError):
        print(json.dumps({"status":"BLOCKED",
                          "reason_code":"MASSIVE_PLAN_OR_RESPONSE_UNAVAILABLE",
                          "network_requests":attempts,"retries":0,
                          "market_data_rights_verified":False},sort_keys=True))
        return 2
    finally:
        key = None


if __name__ == "__main__":
    raise SystemExit(main())
