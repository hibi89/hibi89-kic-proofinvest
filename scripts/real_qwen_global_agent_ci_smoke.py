"""P265 one real Qwen1.5B local tool choice on authored question, no originals."""
from __future__ import annotations
import json

from proofinvest.global_question_agent import (
    answer_global_question, preflight_global_question,
    verify_global_question_answer,
)

def main() -> None:
    # Fixed public operator test question only. No publisher/SEC bytes or user
    # private prompt, no market API, no external model network.
    q = "For NVIDIA check inventory and cash flow, but answer the cash flow first."
    pre = preflight_global_question(q)
    if (pre.get("status") != "READY"
            or pre.get("intent") != "WORKING_CAPITAL"
            or pre.get("candidate_intents") != ["WORKING_CAPITAL","CASHFLOW"]):
        raise AssertionError("P265_TOOL_SELECTION_PREFLIGHT_INVALID")
    packet = answer_global_question(
        q, use_local_model=True,
        consent_local_model=True, consent_question_text=True)
    if (packet.get("status") != "QUESTION_SOURCE_BOUND_LOCAL_REVIEW_HOLD"
            or packet.get("intent") != "CASHFLOW"
            or packet.get("local_model_calls") != 1
            or packet.get("local_model_protocol_verified") is not True
            or packet.get("real_model_provider_authenticated") is not False
            or packet.get("guard_policy_preview") != "HOLD"
            or packet.get("external_sharing_allowed") is not False
            or packet.get("ai_agent_executed") is not False
            or packet.get("trade_executed") is not False
            or packet.get("source_rights_verified") is not False
            or packet.get("full_abc_complete") is not False
            or not verify_global_question_answer(packet,q)):
        raise AssertionError("P265_REAL_QWEN_MODEL_TOOL_SELECTION_FAILED:"+
                             str(packet.get("reason_code","UNKNOWN")))
    print(json.dumps({
        "status":"PASS",
        "real_model_generated_tokens":True,
        "model_selected_tool":"CASHFLOW",
        "deterministic_first_tool":"WORKING_CAPITAL",
        "publisher_origins_sent_to_model":False,
        "source_bound_replay":True,
        "guard":"HOLD","trades":0,
        "actual_model_provider_authenticated":False,
        "full_authorized_financial_ai":False,
        "public_production":False,
    },sort_keys=True))


if __name__ == "__main__":
    main()
