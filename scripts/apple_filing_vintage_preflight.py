"""Human-invoked Apple public filing date-only metadata preflight; no HTTP."""
from __future__ import annotations

import argparse
import json

from proofinvest.apple_public_filing_vintage import check_apple_public_filing_vintage


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline Apple 10-K public-metadata vintage gate")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--accession", required=True)
    parser.add_argument("--period-end", required=True)
    args = parser.parse_args(argv)
    result = check_apple_public_filing_vintage(
        ticker=args.ticker, as_of=args.as_of, accession=args.accession,
        fiscal_period_end=args.period_end,
    )
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == (
        "PUBLIC_FILING_VINTAGE_METADATA_MATCHED_ORIGINAL_UNVERIFIED"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
