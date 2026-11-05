"""P252 FRED NASDAQ100 official index API: explicit one GET / 0 retry.

DRY RUN is the default. Never share FRED key, URL, response body or prices.
FRED API terms: https://fred.stlouisfed.org/docs/api/terms_of_use.html
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import getpass
import json
import sys

from proofinvest.market_provider_fred_api import run_one_fred_ndx_get

_APPROVAL = "REQUEST FRED NASDAQ100 PERSONAL"
_TERMS = "https://fred.stlouisfed.org/docs/api/terms_of_use.html"


def _safe_date() -> str:
    # Avoid partial US session or a delayed FRED publisher update.
    day = datetime.now(timezone.utc).date()
    for _ in range(2):
        day -= timedelta(days=1)
        while day.weekday() > 4:
            day -= timedelta(days=1)
    return day.isoformat()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="One-shot official FRED NASDAQ100 personal request")
    ap.add_argument("--as-of", default=None, help="Historical point-in-time date YYYY-MM-DD")
    ap.add_argument("--live", action="store_true", help="Explicit personal FRED API GET")
    args = ap.parse_args(argv)
    asof = args.as_of or _safe_date()
    try:
        d = datetime.strptime(asof, "%Y-%m-%d").date()
        valid = asof == d.isoformat() and asof <= _safe_date()
    except (ValueError, TypeError):
        valid = False
    if not valid:
        print(json.dumps({"status": "BLOCKED", "reason_code": "FRED_AS_OF_DATE_NOT_SAFE",
                          "network_requests": 0, "retries": 0}, sort_keys=True))
        return 2
    if not args.live:
        print(json.dumps({"status":"DRY_RUN_NO_REQUEST",
                          "series_id":"NASDAQ100", "index_symbol":"I:NDX",
                          "provider":"FRED", "as_of":asof,
                          "network_requests":0, "retries":0,
                          "commercial_reuse_allowed":False},sort_keys=True))
        return 0
    print("Personal research only. 1 FRED NASDAQ100 GET maximum; no retry.")
    print("FRED API terms:", _TERMS)
    print("NASDAQ100 is copyrighted Nasdaq data; commercial/AI/judge rights NOT verified.")
    print("Never paste the key into chat, screenshots or GitHub.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(json.dumps({"status":"BLOCKED","reason_code":"REAL_TTY_REQUIRED",
                          "network_requests":0,"retries":0}))
        return 2
    try:
        consent = input("Type " + _APPROVAL + " for 1 live GET: ").strip()
    except (KeyboardInterrupt, EOFError):
        consent = ""
    if consent != _APPROVAL:
        print(json.dumps({"status":"BLOCKED","reason_code":"OWNER_DECLINED",
                          "network_requests":0,"retries":0}))
        return 2
    try:
        key = getpass.getpass("FRED API Key (hidden): ").strip()
    except (KeyboardInterrupt, EOFError):
        print(json.dumps({"status":"BLOCKED","reason_code":"KEY_INPUT_CANCELLED",
                          "network_requests":0,"retries":0}))
        return 2
    try:
        result = run_one_fred_ndx_get(
            api_key=key, as_of=asof, explicit_approval=True,
            individual_research=True)
    finally:
        key = None
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "FRED_API_DAILY_PARSED_ORIGIN_AND_RIGHTS_UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
