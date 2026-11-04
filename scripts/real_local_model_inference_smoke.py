"""P181 genuine small local Ollama model inference on only synthetic statuses.

This runs inside a disposable public GitHub Actions runner, using a pinned
Ollama image and a published Apache-2.0 135M model pulled into tmpfs. It
validates an *actual* response with positive token evaluation count, then
runs the existing strict P179 KUODRA human-only gate. It must never see
user originals, DAKER files, secrets, real SEC responses, or private data.

The result is an execution receipt only; source-grounded investment LLM
quality, publisher provenance, legal data rights and Production stay HOLD.
"""
from __future__ import annotations

import json
import os
import urllib.request

from proofinvest.ticker_local_model_triage import (
    _call_loopback, _json_no_duplicate, triage_review,
)
from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from tests.test_ticker_offline_review_builder import payload

_PORT = 11435
_MODEL = "smollm2:135m-instruct-q4_K_M"


def run() -> dict[str, object]:
    if os.environ.get("KUODRA_P181_PUBLIC_SYNTHETIC_ONLY") != "1":
        raise ValueError("P181_CI_SYNTHETIC_ONLY_GATE_REQUIRED")
    fixture = build_offline_initial_review(**payload())
    if fixture.get("status") != "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED":
        raise ValueError("P181_SYNTHETIC_ORIGINAL_REPLAY_BLOCKED")
    # Only synthetic A/B/C status codes. No ticker or any source identity.
    direct = json.dumps({
        "model": _MODEL, "stream": False, "format": "json",
        "prompt": (
            'Return exactly a JSON object with the key "probe" and value '
            '"LOCAL_MODEL_EXECUTED". Do not mention any financial company.'
        ), "options": {"temperature": 0, "num_predict": 48},
    }, sort_keys=True, separators=(",", ":")).encode()
    answer = _json_no_duplicate(_call_loopback(direct, port=_PORT))
    if (type(answer) is not dict or answer.get("done") is not True
            or answer.get("model") != _MODEL
            or type(answer.get("eval_count")) is not int
            or answer["eval_count"] < 1
            or type(answer.get("response")) is not str
            or not 0 < len(answer["response"]) <= 2048):
        raise ValueError("P181_REAL_MODEL_TOKEN_EVALUATION_NOT_PROVEN")

    review = triage_review(
        fixture["review_packet"], fixture["source_clearance_report"],
        model=_MODEL, port=_PORT, allow_local_model=True,
        confirm_local_derivative_processing=True,
    )
    if (review.get("guard_policy_preview") != "HOLD"
            or review.get("source_authenticated") is not False
            or review.get("source_rights_verified") is not False
            or review.get("ai_agent_executed") is not False
            or review.get("trade_executed") is not False
            or review.get("external_sharing_allowed") is not False
            or review.get("external_network_requests") != 0
            or review.get("loopback_http_attempts") != 1):
        raise ValueError("P181_LOCAL_MODEL_DID_NOT_PRESERVE_GUARD")
    accepted = review["status"] == (
        "LOCAL_MODEL_TRIAGE_PROTOCOL_UNVERIFIED_MODEL_ORIGIN"
    )
    if accepted:
        if (review.get("model_protocol_http_verified") is not True
                or review.get("focus_engine") not in ("A", "B", "C")):
            raise ValueError("P181_ACCEPTED_MODEL_OUTPUT_INVALID")
    elif review["status"] != "BLOCKED":
        raise ValueError("P181_UNKNOWN_MODEL_RESPONSE_STATUS")

    # Never publish the direct model response or the private/synthetic inputs.
    return {
        "status": "REAL_OLLAMA_MODEL_INFERENCE_EXECUTED_GUARD_HOLD",
        "model_tag": _MODEL,
        "provider": "ollama-local-in-disposable-ci",
        "actual_generated_tokens_positive": True,
        "real_model_inference_executed": True,
        "safe_human_only_triage_accepted": accepted,
        "safe_fallback_blocked": not accepted,
        "local_ollama_http_requests": 2,
        "source_authenticated": False,
        "source_rights_verified": False,
        "data_rights_verified": False,
        "source_grounded_ai_quality_verified": False,
        "model_origin_cryptographically_authenticated": False,
        "ai_agent_executed": False,
        "guard_policy_preview": "HOLD",
        "trade_executed": False,
        "public_production_deployed": False,
        "daker_submitted": False,
        "originals_sent": False,
    }


def main() -> int:
    print(json.dumps(run(), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
