"""Read-only local SEC CompanyFacts verifier: no download, LLM, or network."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat

from .sec_companyfacts import verify_sec_annual_revenue

MAX_INPUT_BYTES = 25_000_000


def read_local_companyfacts(path: Path):
    """Accept only ordinary bounded local JSON; reject symlinks and missing data."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("SYMLINK_INPUT_FORBIDDEN")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode):
            raise ValueError("NOT_REGULAR_JSON_FILE")
        if meta.st_size > MAX_INPUT_BYTES:
            raise ValueError("INPUT_SIZE_LIMIT")
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("INPUT_SIZE_LIMIT")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_JSON") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline, local JSON-to-SEC-evidence verifier; NEVER downloads SEC data."
    )
    parser.add_argument("source_json", type=Path, help="Local SEC CompanyFacts JSON file")
    for key in ("cik", "accession", "current-end", "prior-end", "as-of"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--claimed-growth-pct", default=None)
    args = parser.parse_args(argv)
    try:
        data = read_local_companyfacts(args.source_json)
    except (ValueError, OSError):
        print(json.dumps({
            "status": "unavailable", "reason_code": "LOCAL_INPUT_REJECTED",
            "live_api_called": False, "official_contest_submission": False,
        }))
        return 2
    verdict = verify_sec_annual_revenue(
        data, cik=args.cik, accession=args.accession,
        current_end=args.current_end, prior_end=args.prior_end,
        as_of=args.as_of, claimed_growth_pct=args.claimed_growth_pct,
    )
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["status"] == "calculated_unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
