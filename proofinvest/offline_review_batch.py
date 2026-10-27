"""Offline batch screening of independently retained SEC-shaped ZIP captures.

Each capture is isolated. This command never sends HTTP or exports source bytes.
"""
from __future__ import annotations

import argparse
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
            summary = result.get("review_summary")
            if not isinstance(summary, dict):
                summary = build_offline_review_summary(result)
        except (ValueError, TypeError, OSError, KeyError, RecursionError):
            summary = build_offline_review_summary(None)
        items.append({"index": index, "summary": summary})
    return {
        "schema": "proofinvest.offline-review-batch.v1",
        "count": len(items),
        "blocked_count": sum(i["summary"]["status"] == "blocked" for i in items),
        "high_priority_count": sum(i["summary"]["review_priority"] == "high" for i in items),
        "items": items,
        "source_authenticated": False,
        "investment_recommendation": False,
        "trade_authorized": False,
        "external_http_called": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline local ZIP batch review; NO NETWORK")
    parser.add_argument("bundles", nargs="+", type=Path)
    parser.add_argument("--current-end", required=True)
    parser.add_argument("--prior-end", required=True)
    parser.add_argument("--needle", required=True)
    parser.add_argument("--claimed-growth-pct")
    args = parser.parse_args(argv)
    try:
        output = review_capture_batch(
            args.bundles, current_end=args.current_end, prior_end=args.prior_end,
            needle=args.needle, claimed_growth_pct=args.claimed_growth_pct,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(output, sort_keys=True, indent=2))
    return 2 if output["blocked_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
