"""Offline-only Disclosure Lightning CLI; never performs HTTP."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from .mvp import export_filings, parse_submissions, persist, read_json_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DL local SEC-shaped JSON -> SQLite -> manifest")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--collected-at", required=True, help="Explicit offset-aware ISO timestamp")
    parser.add_argument("--as-of", required=True, help="YYYY-MM-DD UTC end-of-day cutoff")
    args = parser.parse_args(argv)
    try:
        parsed = parse_submissions(
            read_json_file(args.input), cik=args.cik,
            collected_at=args.collected_at, as_of=args.as_of,
        )
        stats = persist(args.database, parsed)
        report = {
            "schema": "disclosure-lightning.offline-mvp-result.v1",
            "status": parsed["status"], "provider": "SEC_EDGAR",
            "source_kind": parsed["source_kind"],
            "live_api_called": False, "source_rights_verified": False,
            "source_payload_sha256": parsed["source_payload_sha256"],
            "accepted_records": len(parsed["records"]),
            "excluded_future": parsed["excluded_future"],
            **stats,
            "envelopes": export_filings(args.database, cik=args.cik),
        }
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({
            "status": "unavailable",
            "reason_code": str(exc) if isinstance(exc, ValueError) else "LOCAL_IO_OR_CONTRACT_ERROR",
            "live_api_called": False,
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
