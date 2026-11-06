"""Zero-network local Massive JSON (3-5 equities + I:NDX) Engine A CLI."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from proofinvest.market_panel_offline import LocalMassivePanel

def _local_bytes(path: str) -> bytes:
    file = Path(path)
    if file.is_symlink() or not file.is_file() or not 0 < file.stat().st_size <= 262144:
        raise ValueError("LOCAL_FILE_NOT_BOUNDED_REGULAR")
    return file.read_bytes()

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local I:NDX and 3-5 stocks: zero API calls")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--ndx", required=True)
    parser.add_argument("--stock", nargs=4, action="append", required=True,
                        metavar=("TICKER", "CIK", "FILING_DATE", "LOCAL_JSON"))
    args = parser.parse_args(argv)
    try:
        cache = LocalMassivePanel()
        cache.ingest(_local_bytes(args.ndx), symbol="I:NDX", as_of=args.as_of)
        companies = []
        for ticker, cik, filing_date, path in args.stock:
            cache.ingest(_local_bytes(path), symbol=ticker, as_of=args.as_of)
            companies.append({"ticker": ticker, "issuer_cik": cik,
                              "filing_date": filing_date})
        report = cache.analyze(companies=companies, as_of=args.as_of)
        print(json.dumps(report, sort_keys=True, allow_nan=False))
        return 0 if report["status"] == "MULTI_ISSUER_ENGINE_A_DESCRIPTIVE_UNVERIFIED" else 2
    except (OSError, ValueError, TypeError, OverflowError):
        print(json.dumps({"schema": "kuodra.local-massive-ndx-panel.v1",
            "status": "BLOCKED", "reason_code": "LOCAL_SOURCE_INVALID_OR_UNAVAILABLE",
            "network_requests": 0, "guard_decision": "HOLD",
            "source_rights_verified": False}, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
