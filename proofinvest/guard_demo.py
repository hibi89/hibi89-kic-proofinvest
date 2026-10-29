"""Run a reproducible local Guard audit demo without network or trading.

Usage: python -m proofinvest.guard_demo --database /tmp/proofinvest-demo.sqlite
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from .guard_audit import GuardAuditStore
from .guard_review import GuardReviewStore
from .guard_workflow import run_guard_review


def run_demo(database_path: str | Path) -> dict:
    """Exercise HOLD, REJECT and APPROVE + explicit simulated review."""
    db = Path(database_path)
    examples = [
        ("missing-risk", {"status": "calculated_unverified"}, None, None),
        ("conflict", {"status": "conflict"},
         {"risk_calculated": True, "comparison_ratio_pct": "100"}, None),
        ("simulated", {"status": "calculated_unverified"},
         {"risk_calculated": True, "comparison_ratio_pct": "100"},
         {"reviewer": "offline-demo", "action": "AUTHORIZE_SIMULATION",
          "reason": "Explicit synthetic-only demonstration approval"}),
    ]
    outcomes = []
    for run_id, verdict, risk, review in examples:
        outcome = run_guard_review(
            verdict, run_id=run_id, database_path=db, risk=risk, **(review or {})
        )
        outcomes.append({
            "run_id": run_id,
            "decision": outcome["guard"]["decision"],
            "reason_codes": outcome["guard"]["reason_codes"],
            "review_action": outcome["review"]["action"] if outcome["review"] else None,
            "trade_executed": outcome["trade_executed"],
        })
    if [x["decision"] for x in outcomes] != ["HOLD", "REJECT", "APPROVE"]:
        raise RuntimeError("Unexpected Guard demo decisions")
    audit_valid = GuardAuditStore(db).verify_chain()
    reviews_valid = GuardReviewStore(db).verify_reviews()
    if not audit_valid or not reviews_valid:
        raise RuntimeError("Guard demo audit integrity failed")
    return {
        "schema": "proofinvest.guard-demo.v1",
        "source_kind": "SYNTHETIC_SCENARIO_NOT_AUTHENTICATED",
        "live_api_called": False,
        "trade_executed": False,
        "audit_valid": audit_valid,
        "reviews_valid": reviews_valid,
        "runs": outcomes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Guard end-to-end demo")
    parser.add_argument("--database", type=Path, help="SQLite destination; default: temporary")
    args = parser.parse_args()
    if args.database is not None:
        result = run_demo(args.database)
    else:
        with tempfile.TemporaryDirectory(prefix="proofinvest-guard-") as directory:
            result = run_demo(Path(directory) / "demo.sqlite")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
