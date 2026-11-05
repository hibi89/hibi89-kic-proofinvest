"""P250 read-only FRED NASDAQ100 CSV validation/optional local Engine A.

Only reads explicitly selected local files. NO HTTP, keys, retries,
writeback, public display or commercial/AI reuse authorization.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import stat

from proofinvest.fred_nasdaq100_offline import (
    parse_fred_nasdaq100_csv, parse_owner_stock_csv,
    parse_owner_alpha_vantage_json, analyze_offline_fred_pair,
)

_MAX_INPUT = 2_097_152
_CODES = frozenset({
    "INVALID_CSV_BYTES", "INVALID_CSV_ENCODING", "INVALID_CSV_FORMAT",
    "UNEXPECTED_CSV_SERIES_HEADER", "CSV_TOO_MANY_ROWS",
    "INVALID_CSV_ROW_SHAPE", "INVALID_CALENDAR_DATE",
    "NONCANONICAL_CALENDAR_DATE", "FUTURE_AS_OF_DATE",
    "UNSORTED_DUPLICATE_CSV_DATE", "INVALID_DAILY_CLOSE",
    "WEEKEND_DAILY_PRICE", "POST_AS_OF_DAILY_PRICE",
    "OBSERVATION_GAP_GT_7_DAYS", "INSUFFICIENT_DAILY_OBSERVATIONS",
    "STALE_DAILY_OBSERVATIONS", "INVALID_STOCK_IDENTITY_OR_SOURCE_URL",
})


def _load_readonly(filename: str) -> bytes:
    path = Path(filename)
    if path.is_symlink():
        raise ValueError("SYMLINK_INPUT_NOT_ALLOWED")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or not 16 <= info.st_size <= _MAX_INPUT:
        raise ValueError("INVALID_FILE_SIZE_OR_TYPE")
    raw = path.read_bytes()
    if not 16 <= len(raw) <= _MAX_INPUT:
        raise ValueError("INVALID_FILE_SIZE_OR_TYPE")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FRED NASDAQ100 offline CSV check; 0 HTTP")
    parser.add_argument("--fred-csv", required=True,
                        help="User-selected local FRED NASDAQ100 CSV filename")
    parser.add_argument("--as-of", default=datetime.now(timezone.utc).date().isoformat())
    stock_group = parser.add_mutually_exclusive_group()
    stock_group.add_argument("--stock-csv", help="Optional local date,close CSV")
    stock_group.add_argument("--stock-alpha-json",
                             help="Optional owner-local Alpha Vantage daily JSON, RAM only")
    parser.add_argument("--ticker")
    parser.add_argument("--issuer-cik")
    parser.add_argument("--filing-date")
    parser.add_argument("--stock-source-url",
                        help="User supplied HTTPS descriptive source URL (unverified)")
    args = parser.parse_args(argv)
    selected = args.stock_csv or args.stock_alpha_json
    extras = (args.ticker, args.issuer_cik,
              args.filing_date, args.stock_source_url)
    incomplete = (
        (selected is None and any(extras))
        or (selected is not None and not all(extras[:3]))
        or (args.stock_csv is not None and not args.stock_source_url)
        or (args.stock_alpha_json is not None
            and args.stock_source_url is not None)
    )
    if incomplete:
        print(json.dumps({"status":"BLOCKED","reason_code":"STOCK_INPUT_INCOMPLETE",
                          "network_requests":0}))
        return 2
    try:
        fred = parse_fred_nasdaq100_csv(
            _load_readonly(args.fred_csv), as_of=args.as_of)
        output = {
            "status":"LOCAL_FRED_CSV_PARSED_ORIGIN_UNVERIFIED",
            "provider":"FRED_OWNER_CSV_UNVERIFIED",
            "index_symbol":"I:NDX", "series_id":"NASDAQ100",
            "as_of":args.as_of,
            "points":fred["point_count"], "first":fred["first_date"],
            "last":fred["last_date"],"missing":fred["missing_rows_ignored"],
            "input_sha256":fred["source_sha256"],
            "network_requests":0,"source_authenticated":False,
            "market_data_rights_verified":False,
            "public_display_allowed":False, "commercial_reuse_allowed":False,
            "ai_processing_allowed":False, "full_a_b_c_ready":False,
        }
        if selected is not None:
            # Distinct formats remain distinct: JSON SHA is NEVER relabeled
            # as an owner CSV SHA or provider-authenticated market data.
            stock = (parse_owner_stock_csv(
                _load_readonly(args.stock_csv), ticker=args.ticker,
                as_of=args.as_of, source_url=args.stock_source_url)
                if args.stock_csv is not None
                else parse_owner_alpha_vantage_json(
                    _load_readonly(args.stock_alpha_json),
                    ticker=args.ticker, as_of=args.as_of))
            result = analyze_offline_fred_pair(
                stock=stock,index=fred,ticker=args.ticker,
                issuer_cik=args.issuer_cik,filing_date=args.filing_date,
                as_of=args.as_of)
            output["pair"] = result
            if result["status"] == "BLOCKED":
                output["status"] = "PAIR_BLOCKED"
        print(json.dumps(output,sort_keys=True))
        return 0 if output["status"] != "PAIR_BLOCKED" else 2
    except (ValueError, TypeError, OSError, OverflowError, RecursionError,
            UnicodeError) as exc:
        # Fixed allowlist; raw exception strings might contain source material.
        reason = str(exc) if type(exc) is ValueError and str(exc) in _CODES else "FILE_OR_FORMAT_UNAVAILABLE"
        print(json.dumps({"status":"BLOCKED", "reason_code":reason,
                          "network_requests":0,"market_data_rights_verified":False},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
