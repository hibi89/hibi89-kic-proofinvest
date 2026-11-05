"""P265 one real Qwen1.5B local tool choice on authored question, no originals."""
from __future__ import annotations
import json

from proofinvest.global_question_agent import (
    answer_global_question, preflight_global_question,
    verify_global_question_answer,
)

def main() -> None:
    # Fixed, open-ended public question: either listed read-only tool is
    # acceptable. Model semantic *quality* is a separate human-review gate.
    # No publisher/SEC bytes, private prompt, market API or remote model.
    q = "For NVIDIA, consider inventory and cash flow; which should we analyze first?"
    pre = preflight_global_question(q)
    if (pre.get("status") != "READY"
            or pre.get("intent") != "WORKING_CAPITAL"
            or pre.get("candidate_intents") != ["WORKING_CAPITAL","CASHFLOW"]):
        raise AssertionError("P265_TOOL_SELECTION_PREFLIGHT_INVALID")
    packet = answer_global_question(
        q, use_local_model=True,
        consent_local_model=True, consent_question_text=True)
    if (packet.get("status") != "QUESTION_SOURCE_BOUND_LOCAL_REVIEW_HOLD"
            or packet.get("intent") not in pre["candidate_intents"]
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
        "model_selected_tool":packet["intent"],
        "model_selected_permitted_tool":packet["intent"] in pre["candidate_intents"],
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
