"""Offline verifier for the two KUODRA reviewer downloads.

Usage:
  python -m scripts.source_clearance_cli review-packet.json rights-gaps.json

A zero exit code means the documents are *internally linked* and parsable,
NOT that the original SEC/index sources, licenses or rights were verified.
No network, no storage, no raw-source echo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


def _file_bytes(path: str, ceiling: int) -> bytes:
    target = Path(path)
    if not target.is_file() or not 0 < target.stat().st_size <= ceiling:
        raise ValueError("SOURCE_CLEARANCE_FILE_SIZE_INVALID")
    raw = target.read_bytes()
    if not 0 < len(raw) <= ceiling:
        raise ValueError("SOURCE_CLEARANCE_FILE_SIZE_CHANGED")
    return raw


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify downloaded A/B/C packet + rights GAP report locally",
    )
    parser.add_argument("review_packet", help="original review packet JSON")
    parser.add_argument("rights_gap_report", help="source clearance gap JSON")
    opts = parser.parse_args(argv)
    try:
        from proofinvest.ticker_source_clearance_packet import (
            inspect_source_clearance_packet,
        )
        original = _file_bytes(opts.review_packet, 28672)
        gaps = _file_bytes(opts.rights_gap_report, 9216)
        verdict = inspect_source_clearance_packet(
            gaps, review_packet=original,
        )
    except (ValueError, OSError, TypeError, AttributeError,
            RecursionError, UnicodeError):
        print(json.dumps({
            "status": "FAIL", "reason_code": "LOCAL_PACKET_OR_GAPS_INVALID",
            "release_gate": "HOLD", "rights_verified": False,
            "network_requests": 0, "trade_executed": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": verdict["status"],
        "review_packet_sha256": verdict["packet_sha256"],
        "rights_receipt_sha256": verdict["receipt_sha256"],
        "release_gate": "HOLD",
        "rights_verified": False,
        "publisher_origin_authenticated": False,
        "public_submission_allowed": False,
        "network_requests": 0, "trade_executed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
