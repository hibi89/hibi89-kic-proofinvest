"""Opt-in local model triage for already redacted KUODRA review report pair.

Example:
python -m scripts.local_model_triage_cli --review x.json --rights y.json
    --model llama3.2 --allow-local-model --confirm-local-derivative-processing

No model is installed here; do not run without a trusted, user-managed
Ollama-compatible server listening on the *local* loopback address.
"""
from __future__ import annotations

import argparse
import json

from .local_originals_review_cli import _read_original
from proofinvest.ticker_local_model_triage import triage_review


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Strict local-only model triage")
    parser.add_argument("--review", required=True)
    parser.add_argument("--rights", required=True)
    parser.add_argument("--model", default="llama3.2")
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--allow-local-model", action="store_true")
    parser.add_argument("--confirm-local-derivative-processing", action="store_true")
    args = parser.parse_args(argv)
    # Explicit consent must precede even reading file bytes.
    if not args.allow_local_model or not args.confirm_local_derivative_processing:
        out = triage_review(
            b"", b"", model=args.model, port=args.port,
        )
    else:
        try:
            review = _read_original(args.review, 28672)
            rights = _read_original(args.rights, 9216)
            out = triage_review(
                review, rights, model=args.model, port=args.port,
                allow_local_model=True,
                confirm_local_derivative_processing=True,
            )
        except (ValueError, OSError, TypeError, KeyError):
            out = {
                "status": "BLOCKED", "reason_code": "LOCAL_REVIEW_FILES_INVALID",
                "external_network_requests": 0,
                "source_rights_verified": False,
                "model_inference_authenticated": False,
                "ai_agent_executed": False, "trade_executed": False,
                "guard_policy_preview": "HOLD",
            }
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    return 0 if out["status"] == "LOCAL_MODEL_TRIAGE_PROTOCOL_UNVERIFIED_MODEL_ORIGIN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
