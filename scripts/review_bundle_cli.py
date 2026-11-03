"""Verify a downloaded KUODRA reviewer ZIP locally without extraction.

Usage: python -m scripts.review_bundle_cli kuodra-review-evidence-UNVERIFIED.zip
Exit 0 = internal A/B/C+rights+HTML/CSV integrity only; exit 2 = invalid.
Neither outcome authenticates a supplier or grants redistribution rights.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

from proofinvest.ticker_review_bundle import inspect_review_bundle_bytes


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Usage: python -m scripts.review_bundle_cli evidence.zip", file=sys.stderr)
        return 2
    try:
        target = Path(args[0])
        if not target.is_file() or not 0 < target.stat().st_size <= 150_000:
            raise ValueError("REVIEW_ZIP_INPUT_INVALID")
        raw = target.read_bytes()
        validated = inspect_review_bundle_bytes(raw)
    except (ValueError, OSError, TypeError, KeyError, UnicodeError,
            RecursionError, OverflowError):
        print(json.dumps({
            "status": "INVALID_REVIEW_BUNDLE",
            "source_rights_verified": False,
            "contest_submission_approved": False,
            "guard_policy_preview": "HOLD",
            "network_requests": 0,
        }, sort_keys=True))
        return 2
    print(json.dumps(validated, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
