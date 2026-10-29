"""Replayable judge matrix for the OFFLINE deterministic ProofInvest router.

Usage:
  python -m scripts.kic_router_judge_matrix /tmp/kic/router-matrix.json

Every case uses only the checked-in manually curated Apple excerpt. This
does NOT validate a live LLM Planner, original SEC bytes or financial advice.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from proofinvest.intent_router import route_question

# Cases cover each route, as-of, claim conflicts and unsupported/ambiguous
# inputs. Expectations are explicit so the runner cannot "grade itself".
CASES: tuple[tuple[str, str, str, str, str | None, str | None], ...] = (
    ("01_matching_claim", "Apple FY2025 매출 성장률 6.43%", "needs_evidence",
     "MISSING_RISK_OR_SOURCE_PROOF", "GROWTH_CHECK", "HOLD"),
    ("02_conflicting_claim", "Apple FY2025 매출 성장률 20%", "blocked",
     "GROWTH_CLAIM_CONFLICT", "GROWTH_CHECK", "REJECT"),
    ("03_missing_claim", "Apple 2025 매출 성장률 검산", "needs_evidence",
     "MISSING_RISK_OR_SOURCE_PROOF", "GROWTH_CHECK", "HOLD"),
    ("04_future_filing_cutoff", "Apple 매출 성장률 6.43% 2025-10-30",
     "needs_evidence", "MISSING_RISK_OR_SOURCE_PROOF", "GROWTH_CHECK", "HOLD"),
    ("05_source_provenance", "Apple 공시 원문 근거", "needs_authentication",
     "MANUAL_EXCERPT_NOT_PRIMARY_SEC_BYTES", "SOURCE_REVIEW", None),
    ("06_risk_without_facts", "Apple 부채비율 위험 진단", "needs_evidence",
     "VERIFIED_LIABILITIES_AND_EQUITY_MISSING", "RISK_CHECK", "HOLD"),
    ("07_no_issuer", "매출 성장률 20%", "needs_clarification",
     "MISSING_ISSUER", None, None),
    ("08_multiple_intents", "Apple 매출 성장률 및 부채 위험", "needs_clarification",
     "AMBIGUOUS_OR_MISSING_INTENT", None, None),
    ("09_unsupported_issuer", "삼성 매출 성장률 20%", "blocked",
     "UNSUPPORTED_ISSUER_ONLY_APPLE_SAMPLE", None, None),
    ("10_multiple_claims", "Apple 매출 성장률 20% 25%", "needs_clarification",
     "MULTIPLE_GROWTH_CLAIMS", None, None),
    ("11_multiple_asof", "Apple 부채 2025-10-31 2025-11-01", "needs_clarification",
     "MULTIPLE_AS_OF_DATES", None, None),
    ("12_unsupported_year", "Apple FY2024 매출 성장률", "blocked",
     "UNSUPPORTED_FISCAL_YEAR_ONLY_FY2025", None, None),
    ("13_no_intent", "Apple에 대해 얘기해 줘", "needs_clarification",
     "AMBIGUOUS_OR_MISSING_INTENT", None, None),
    ("14_english_growth", "Apple revenue growth 20%", "blocked",
     "GROWTH_CLAIM_CONFLICT", "GROWTH_CHECK", "REJECT"),
    ("15_english_source", "Apple filing source", "needs_authentication",
     "MANUAL_EXCERPT_NOT_PRIMARY_SEC_BYTES", "SOURCE_REVIEW", None),
)


def run_matrix() -> dict[str, Any]:
    outcomes = []
    errors = []
    for case_id, question, status, reason, intent, guard in CASES:
        actual = route_question(question)
        observed = {
            "status": actual["status"], "reason_code": actual["reason_code"],
            "selected_intent": actual["selected_intent"],
            "guard_decision": actual["guard"]["decision"] if actual["guard"] else None,
        }
        expected = {
            "status": status, "reason_code": reason,
            "selected_intent": intent, "guard_decision": guard,
        }
        invariants = (
            actual["external_tool_calls"] == 0
            and actual["live_api_called"] is False
            and actual["ai_agent_executed"] is False
            and actual["trade_executed"] is False
            and actual["authenticated_external_source"] is False
            and actual["source_rights_verified"] is False
            and actual["official_contest_submission"] is False
            and len(actual["tool_calls"]) <= actual["tool_budget"] <= 2
            and (intent is not None or actual["tool_calls"] == [])
        )
        if case_id == "04_future_filing_cutoff":
            invariants = invariants and actual["evidence"]["status"] == "unavailable"
            invariants = invariants and actual["evidence"]["reason_code"] == "FILING_AFTER_AS_OF"
        if case_id == "02_conflicting_claim":
            invariants = invariants and actual["evidence"]["growth_pct"] == "6.43"
        if case_id == "06_risk_without_facts":
            invariants = invariants and actual["evidence"]["ratio_pct"] is None
        passed = observed == expected and invariants
        if not passed:
            errors.append(case_id)
        outcomes.append({
            "id": case_id, "question": question,
            "expected": expected, "observed": observed,
            "safety_invariants_pass": invariants, "result": "PASS" if passed else "FAIL",
        })
    digest = hashlib.sha256(json.dumps(
        outcomes, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {
        "schema": "proofinvest.router-judge-matrix.v1",
        "mode": "DETERMINISTIC_OFFLINE_NOT_LLM",
        "status": "PASS" if not errors else "FAIL",
        "cases": len(CASES), "passed": len(CASES) - len(errors),
        "failed": len(errors), "failed_case_ids": errors,
        "case_results_sha256": digest,
        "real_sec_requests": 0, "llm_requests": 0, "trades": 0,
        "source_authenticated": False,
        "source_kind": "MANUALLY_CURATED_SEC_FORMAT_NOT_RAW_API",
        "results": outcomes,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Offline deterministic KIC router test matrix")
    p.add_argument("output", type=Path, help="Destination JSON (must not already exist)")
    args = p.parse_args()
    result = run_matrix()
    path = args.output.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({
        "result": result["status"], "passed": result["passed"],
        "cases": result["cases"], "sha256": result["case_results_sha256"],
        "output": str(path),
    }, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
