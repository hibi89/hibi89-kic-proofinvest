"""Offline P231 Guard receipt verifier; prints only limited status and hashes.

python -m scripts.verify_p231_receipt --abc-review abc.json --receipt hold.json
    --audit-db path/to/kuodra-real-abc-guard-audit.sqlite3

All input files are local. Does not alter SQLite or access SEC/vendor/LLM.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from proofinvest.real_issuer_abc_receipt_replay import verify_p231_local_receipt


def _read_json(path: Path) -> object:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
        raise ValueError("INVALID_LOCAL_JSON_FILE_OR_SIZE")
    with path.open("rb") as f:
        data = f.read(1048577)
    if not data or len(data) > 1048576:
        raise ValueError("INVALID_LOCAL_JSON_FILE_OR_SIZE")
    return json.loads(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only local P231 receipt replay")
    parser.add_argument("--abc-review", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--audit-db", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        packet = _read_json(args.abc_review)
        receipt = _read_json(args.receipt)
        result = verify_p231_local_receipt(
            abc_review=packet, receipt=receipt, audit_db_path=args.audit_db)
    except (ValueError, TypeError, OSError, UnicodeError,
            RecursionError, json.JSONDecodeError):
        result = {
            "status": "BLOCKED", "reason_code": "LOCAL_JSON_INPUT_INVALID",
            "source_authenticated_by_sec": False, "market_rights_verified": False,
            "peer_rights_verified": False, "trade_executed": False,
            "sqlite_written": False, "network_requests": 0,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")))
    return 0 if result["status"] == "VERIFIED_LOCAL_RECEIPT_MATCH_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
