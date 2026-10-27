"""One-command KIC judge replay of three *offline* manual-evidence outcomes.

This runs NO external model, DART viewer, API request, browser, or live
financial ingestion. It checks a historical issuer example, its unchanged
reviewed Git blob, and intentionally withholds unsupported Risk conclusions.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from .manual_case_demo import REVIEWED_GIT_BLOB_SHA1, run_manual_case

_CASES = (
    ("match", "16.20", "verified"),
    ("conflict", "30", "conflict"),
    ("no_claim", "", "unavailable"),
)


def replay() -> dict[str, Any]:
    cases = []
    for key, claim, expected in _CASES:
        result = run_manual_case(claim)
        verification = result["verification"]
        risk = result["risk"]
        if (verification["state"] != expected
                or risk["risk_calculated"]
                or result["authenticated_external_source"]
                or result["ai_agent_executed"]
                or result["live_api_called"]
                or result["reviewed_record_git_blob_sha1"] != REVIEWED_GIT_BLOB_SHA1):
            raise ValueError("Replay safety contract failed: " + key)
        cases.append({
            "scenario": key,
            "claim_pct": claim or None,
            "verification_state": verification["state"],
            "manual_computed_pct": verification["computed_pct"],
            "trace_linked": result["trace_linked"],
            "risk_state": risk["status"],
            "risk_calculated": False,
            "reason": verification["reason"],
        })
    return {
        "schema": "proofinvest.offline-judge-replay.v1",
        "reviewed_record_git_blob_sha1": REVIEWED_GIT_BLOB_SHA1,
        "issuer_ir_page": result["issuer_ir_listing"],
        "issuer_ir_publication_date": result["issuer_ir_listed_at"],
        "data_scope": "2024/2023 CONSOLIDATED REVENUE_MANUALLY_TRANSCRIBED",
        "live_api_called": False,
        "independent_dart_authentication": False,
        "ai_agent_executed": False,
        "investment_recommendation": False,
        "actual_official_hackathon_submission": False,
        "note": ("The matching scenario is only arithmetic agreement with a "
                 "previously manually transcribed issuer record; provenance "
                 "and redistribution rights are not independently authenticated. "
                 "No liabilities/equity: Risk is intentionally withheld."),
        "scenarios": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline, non-AI KIC 3-scenario audit replay")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON (no files written)")
    args = parser.parse_args()
    out = replay()
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print("ProofInvest - 과거 수동검산 자료 3사례 재현 (오프라인, AI Agent 아님)")
    for case in out["scenarios"]:
        print(
            f"{case['scenario']}: claim={case['claim_pct'] or 'none'}, "
            f"arithmetic={case['verification_state']}, "
            f"computed={case['manual_computed_pct']}, "
            "Risk=보류"
        )
    print("원문 독립 인증/실 DART/AI 실행/투자 권고/공식 제출: 모두 아님")
    print("수동 검토 파일의 Git blob 지문 일치 확인 (발행기관 문서 진위 인증 아님)")


if __name__ == "__main__":
    main()
