"""Single offline SEC -> Guard -> SQLite audit flow; no trading or network."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .guard_audit import GuardAuditStore
from .guard_review import GuardReviewStore
from .guard_sec_adapter import evaluate_sec_guard


def run_guard_review(
    sec_verdict: Mapping[str, Any],
    *,
    run_id: str,
    database_path: str | Path,
    risk: Mapping[str, Any] | None = None,
    reviewer: str | None = None,
    action: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Persist Guard decision before any explicit human review.

    A numeric SEC comparison is not independent SEC source authentication.
    A missing Risk result means HOLD. All approvals are simulation-only.
    """
    # Reject incomplete review submissions before any audit write.
    # An invalid review must not create a new Guard decision as a side effect.
    wants_review = any(value is not None for value in (reviewer, action, reason))
    if wants_review and not all(
        isinstance(value, str) and value.strip()
        for value in (reviewer, action, reason)
    ):
        raise ValueError("Explicit reviewer, action and reason are all required")
    mapped = evaluate_sec_guard(sec_verdict, risk=risk)
    request = {
        "sec_status": mapped["sec_status"],
        "source_authenticated": False,
        "risk": dict(risk) if risk is not None else None,
        "policy_version": mapped["guard"]["policy_version"],
    }
    receipt = GuardAuditStore(database_path).record_decision(
        run_id, request, mapped["guard"]
    )
    result = {
        "schema": "proofinvest.guard-offline-run.v1",
        "run_id": run_id,
        "guard": mapped["guard"],
        "audit": receipt,
        "review": None,
        "live_api_called": False,
        "trade_executed": False,
    }
    if wants_review:
        result["review"] = GuardReviewStore(database_path).record_review(
            run_id, reviewer, action, reason
        )
    return result
