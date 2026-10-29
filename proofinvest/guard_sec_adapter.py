"""Adapt existing offline SEC verdicts to the simulated Guard."""
from __future__ import annotations
from typing import Any, Mapping
from .guard_agent import evaluate_guard

DEMO_POLICY = {"mode": "DEMO_POLICY", "version": "sec-demo-1", "max_debt_to_equity_pct": "200"}

def evaluate_sec_guard(verdict: Mapping[str, Any], *, risk: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(verdict, Mapping):
        raise ValueError("Expected SEC verdict mapping")
    state = {"calculated_unverified": "VERIFIED", "conflict": "CONFLICT",
             "unavailable": "UNAVAILABLE"}.get(verdict.get("status"), "UNAVAILABLE")
    return {"sec_status": verdict.get("status"),
            "numeric_consistency_only": True,
            "external_source_authenticated": False,
            "guard": evaluate_guard(
                [{"status": state, "source_kind": "MANUALLY_CURATED_UNVERIFIED"}],
                policy=DEMO_POLICY, risk=risk)}
