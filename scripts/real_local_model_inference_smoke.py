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
    # P188 stop/pivot: a tiny real model may emit an invalid focus despite
    # genuine token generation. Keep the P183 independent human worklist,
    # never release a disagreement, and record the safe FALLBACK as a tested
    # functional outcome rather than rerunning or weakening validation.
    policy_accepted = (
        accepted
        and review.get("model_protocol_http_verified") is True
        and review.get("model_structured_focus_verified") is True
        and review.get("focus_engine") == "B"
        and review.get("reason_code") == "DERIVED_STATUS_TRIAGE_ONLY"
        and review.get("model_inference_authenticated") is False
        and review.get("human_review_priority_policy_verified") is True
    )
    fallback_blocked = (
        review.get("status") == "BLOCKED"
        and review.get("reason_code") in (
            "MODEL_FOCUS_DISAGREES_WITH_LOCAL_POLICY",
            "MODEL_RESPONSE_OR_LOCAL_HTTP_INVALID",
        )
        and review.get("human_review_priority_policy_verified") is not True
        and "focus_engine" not in review
    )
    if not (policy_accepted or fallback_blocked):
        raise ValueError("P188_MODEL_GUARD_OUTCOME_NOT_SAFE")
    syntax_accepted = review.get("model_structured_focus_verified") is True

    # P191: one genuine CPU model prediction on two real PUBLIC Apple SEC
    # numeric figures. Independent Decimal source agreement is mandatory.
    from proofinvest.apple_public_model_claim import run_public_issuer_model
    issuer = run_public_issuer_model(consent=True)
    if (issuer.get("status") != "REAL_MODEL_PUBLIC_ISSUER_FACT_INDEPENDENTLY_MATCHED"
            or issuer.get("actual_model_factual_claim_verified") is not True
            or issuer.get("actual_model_token_count_verified") is not True
            or issuer.get("cash_minus_net_income_usd_millions") != "12922"
            or issuer.get("publisher_original_bytes_authenticated") is not False
            or issuer.get("full_market_ndx_peer_rights_verified") is not False
            or issuer.get("guard_policy_preview") != "HOLD"
            or issuer.get("trade_executed") is not False):
        # Record ONLY a stable reason code, never raw model text or owner data.
        raise ValueError("P191_REAL_PUBLIC_ISSUER_MODEL_INDEPENDENT_REPLAY_FAILED:"
                         + str(issuer.get("reason_code", "UNAVAILABLE"))[:90])

    # No model free text or original data published; explicit fallback
    # false claims are prohibited. This does NOT prove grounded AI reasoning.
    return {
        "status": "REAL_OLLAMA_MODEL_SAFE_POLICY_OR_FALLBACK_GUARD_HOLD",
        "model_tag": _MODEL,
        "provider": "ollama-local-in-disposable-ci",
        "actual_generated_tokens_positive": True,
        "real_model_inference_executed": True,
        "safe_human_only_triage_accepted": policy_accepted,
        "safe_fallback_blocked": fallback_blocked,
        "real_model_structured_focus_accepted": syntax_accepted,
        "real_model_missing_evidence_priority_accepted": policy_accepted,
        "real_model_policy_disagreement_observed": (
            review.get("reason_code") == "MODEL_FOCUS_DISAGREES_WITH_LOCAL_POLICY"
        ),
        "local_ollama_http_requests": 3,
        "real_public_sec_issuer_fact_model_verified": True,
        "real_public_sec_issuer_fact_independent_decimal_verified": True,
        "real_public_sec_issuer_evidence_id": issuer["evidence_id"],
        "real_public_sec_issuer_cash_minus_net_income_usdm": issuer["cash_minus_net_income_usd_millions"],
        "real_public_sec_original_bytes_authenticated": False,
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
