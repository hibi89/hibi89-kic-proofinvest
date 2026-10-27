"""Offline batch screening of independently retained SEC-shaped ZIP captures.

Each capture is isolated. This command never sends HTTP or exports source bytes.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

from proofinvest.offline_review_summary import build_offline_review_summary
from proofinvest.sec_bundle_replay import replay_local_capture


def review_capture_batch(
    bundles: list[Path], *, current_end: str, prior_end: str, needle: str,
    claimed_growth_pct: str | None = None,
) -> dict:
    if not isinstance(bundles, list) or not 1 <= len(bundles) <= 20:
        raise ValueError("Expected 1-20 local captures")
    items = []
    for index, bundle in enumerate(bundles):
        try:
            result = replay_local_capture(
                bundle, current_end=current_end, prior_end=prior_end,
                needle=needle, claimed_growth_pct=claimed_growth_pct,
            )
            # Always recompute from the replay receipt. Never trust a caller-supplied
            # embedded summary, which could contain arbitrary raw filing content.
            summary = build_offline_review_summary(result)
        except (ValueError, TypeError, OSError, KeyError, RecursionError):
            summary = build_offline_review_summary(None)
        items.append({"index": index, "summary": summary})
    # Human work queue: blocked first, then high-priority review, then normal.
    # Preserve original input index as a stable tie-breaker; never expose paths.
    queue = sorted(
        items,
        key=lambda item: (
            0 if item["summary"]["status"] == "blocked" else
            1 if item["summary"]["review_priority"] == "high" else 2,
            item["index"],
        ),
    )
    return {
        "schema": "proofinvest.offline-review-batch.v1",
        "review_queue": [
            {"index": item["index"],
             "status": item["summary"]["status"],
             "priority": item["summary"]["review_priority"],
             "next_action": item["summary"]["review_actions"][0]}
            for item in queue
        ],
        "count": len(items),
        "blocked_count": sum(i["summary"]["status"] == "blocked" for i in items),
        "high_priority_count": sum(i["summary"]["review_priority"] == "high" for i in items),
        "ready_for_human_review_count": sum(
            i["summary"]["status"] == "human_review_required" for i in items
        ),
        "items": items,
        "action_counts": {
            action: sum(action in item["summary"]["review_actions"] for item in items)
            for action in (
                "RECHECK_LOCAL_ARCHIVE", "VERIFY_PROVIDER_ORIGIN_AND_RIGHTS",
                "RECONCILE_FINANCIAL_CLAIM", "RECALCULATE_FINANCIAL_EVIDENCE",
                "REVIEW_LOCAL_RISK_FLAGS", "INSPECT_IXBRL_CONTEXT_AND_UNITS",
                "LOCATE_ORIGINAL_NUMERIC_TEXT",
            )
        },
        "source_authenticated": False,
        "investment_recommendation": False,
        "trade_authorized": False,
        "external_http_called": False,
    }


def format_review_queue_csv(batch: dict) -> str:
    """Produce a spreadsheet-friendly queue from allowlisted, computed fields."""
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("index", "status", "priority", "next_action"))
    for item in batch["review_queue"]:
        writer.writerow((item["index"], item["status"], item["priority"], item["next_action"]))
    return stream.getvalue()


def discover_capture_files(directory: Path) -> list[Path]:
    """List regular ZIP captures, bounded and without following file symlinks."""
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Expected a regular local directory")
    captures = sorted(
        (entry for entry in directory.iterdir()
         if entry.suffix.lower() == ".zip" and entry.is_file()
         and not entry.is_symlink()),
        key=lambda entry: entry.name,
    )
    if not 1 <= len(captures) <= 20:
        raise ValueError("Expected 1-20 ZIP captures in directory")
    return captures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline local ZIP batch review; NO NETWORK")
    parser.add_argument("bundles", nargs="*", type=Path)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--current-end", required=True)
    parser.add_argument("--prior-end", required=True)
    parser.add_argument("--needle", required=True)
    parser.add_argument("--claimed-growth-pct")
    parser.add_argument("--format", choices=("json", "csv"), default="json",
                        help="CSV emits only the safe prioritized review queue")
    args = parser.parse_args(argv)
    if bool(args.directory) == bool(args.bundles):
        parser.error("Provide either ZIP paths or --directory")
    try:
        captures = discover_capture_files(args.directory) if args.directory else args.bundles
        output = review_capture_batch(
            captures, current_end=args.current_end, prior_end=args.prior_end,
            needle=args.needle, claimed_growth_pct=args.claimed_growth_pct,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.format == "csv":
        print(format_review_queue_csv(output), end="")
    else:
        print(json.dumps(output, sort_keys=True, indent=2))
    return 2 if output["blocked_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
