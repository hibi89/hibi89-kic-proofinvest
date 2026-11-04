"""Human-operated offline numeric model-claim verifier; never calls an API."""
from __future__ import annotations

import argparse
import json

from .local_originals_review_cli import _read_original
from proofinvest.ticker_local_model_numeric_claim import verify_local_model_numeric_claim


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Strict offline source-linked numeric model draft gate")
    parser.add_argument("--review", required=True)
    parser.add_argument("--rights", required=True)
    parser.add_argument("--draft", required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_local_model_numeric_claim(
            _read_original(args.review, 28672),
            _read_original(args.rights, 9216),
            _read_original(args.draft, 1024),
        )
    except (ValueError, TypeError, KeyError, OSError):
        result = {"schema": "kuodra.local-model-numeric-claim-check.v1",
                  "status": "BLOCKED", "reason_code": "OFFLINE_FILES_INVALID",
                  "publisher_source_authenticated": False,
                  "source_rights_verified": False, "ai_agent_executed": False,
                  "guard_policy_preview": "HOLD", "trade_executed": False,
                  "external_network_requests": 0}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == (
        "LOCAL_MODEL_NUMERIC_MATCH_TO_UNSIGNED_REVIEW_ONLY"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
