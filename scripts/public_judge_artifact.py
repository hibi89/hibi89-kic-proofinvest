"""Build a tiny, allowlisted PUBLIC receipt from the offline judge replay.

Never archive raw filings, private contest PDFs, local paths, user-supplied
text, tracebacks, environment values or credentials. Not a final DAKER receipt.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from proofinvest.judge_replay import replay
from proofinvest.manual_case_demo import REVIEWED_GIT_BLOB_SHA1

SCHEMA = "proofinvest.public-offline-judge-replay.v1"
CASES = (("match", "16.20", "verified"), ("conflict", "30", "conflict"),
         ("no_claim", None, "unavailable"))
MAX_ARTIFACT_BYTES = 2048
FIXED_SCOPE = "2024/2023 issuer-manual revenue arithmetic, offline only"


def make_receipt() -> dict[str, Any]:
    """Translate the full internal replay into a strict safe public projection."""
    original = replay()
    if (original.get("schema") != "proofinvest.offline-judge-replay.v1"
            or original.get("reviewed_record_git_blob_sha1") != REVIEWED_GIT_BLOB_SHA1
            or any(original.get(k) is not False for k in (
                "live_api_called", "independent_dart_authentication",
                "ai_agent_executed", "investment_recommendation",
                "actual_official_hackathon_submission"))):
        raise ValueError("Replay authentication contract changed")
    values = original.get("scenarios")
    if not isinstance(values, list) or len(values) != len(CASES):
        raise ValueError("Expected exactly three offline replay scenarios")
    cases = []
    for record, (scenario, claim, outcome) in zip(values, CASES):
        if (not isinstance(record, Mapping)
                or record.get("scenario") != scenario
                or record.get("claim_pct") != claim
                or record.get("verification_state") != outcome
                or record.get("risk_state") != "unavailable"
                or record.get("risk_calculated") is not False
                or record.get("manual_computed_pct") != "16.20"):
            raise ValueError("Unsafe or unexpected replay case")
        cases.append({"case": scenario, "claim_pct": claim,
                      "manual_arithmetic": outcome, "risk": "withheld"})
    return {
        "schema": SCHEMA,
        "reviewed_public_json_git_blob_sha1": REVIEWED_GIT_BLOB_SHA1,
        "scope": FIXED_SCOPE,
        "source_reauthenticated": False,
        "dart_accessed": False,
        "ai_agent_executed": False,
        "risk_calculated": False,
        "official_contest_submission": False,
        "private_proposal_included": False,
        "scenarios": cases,
    }


def encode(receipt: dict[str, Any]) -> bytes:
    payload = (json.dumps(receipt, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise ValueError("Replay receipt exceeds public artifact byte limit")
    return payload


def verify_file(path: Path) -> None:
    # Exact byte comparison prevents extra unknown fields, comments, stale
    # receipts, data from accidental environment/file leaks and substitutions.
    actual = path.read_bytes()
    if actual != encode(make_receipt()):
        raise ValueError("Public replay receipt mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description="Allowlisted public judge replay CI receipt")
    parser.add_argument("--verify", action="store_true", help="Fail if output differs from replay")
    parser.add_argument("output", type=Path, help="Existing file in --verify mode; new file otherwise")
    args = parser.parse_args()
    if args.verify:
        verify_file(args.output)
        print("PUBLIC_JUDGE_RECEIPT_VERIFIED")
    else:
        with args.output.open("xb") as out:
            out.write(encode(make_receipt()))
        verify_file(args.output)
        print("PUBLIC_JUDGE_RECEIPT_GENERATED_AND_VERIFIED")


if __name__ == "__main__":
    main()
