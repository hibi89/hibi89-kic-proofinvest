"""One genuine Qwen2.5 1.5B public three-evidence-card summary with strict replay."""
from __future__ import annotations
import json
from proofinvest.apple_qwen_public_brief import run_local_public_evidence_summary


def main() -> int:
    x=run_local_public_evidence_summary(
        local_model_confirmed=True,public_fact_summary_consent=True)
    if (x.get("status") != "REAL_LOCAL_MODEL_MULTI_PUBLIC_FACT_BRIEF_VERIFIED"
            or x.get("actual_model_tokens_verified") is not True
            or x.get("source_bound_multi_fact_model_verified") is not True
            or x.get("scenario") !=
               "LIMITED_HISTORICAL_FINANCIAL_FACTS_MARKET_UNVERIFIED"
            or x.get("source_refs") != [
                "PUBLIC_CFO_GT_NET_INCOME",
                "PUBLIC_INVENTORY_GROWTH_GT_REVENUE",
                "PUBLIC_RECEIVABLES_GROWTH_NOT_GT_REVENUE"]
            or x.get("model_free_text_displayed") is not False
            or x.get("guard_policy_preview") != "HOLD"
            or x.get("trades_executed") != 0
            or x.get("publisher_original_byte_authenticated") is not False
            or x.get("market_price_ndx_rights_verified") is not False
            or x.get("source_redistribution_rights_verified") is not False
            or x.get("external_model_calls") != 0
            or x.get("confidential_originals_transmitted") is not False):
        raise ValueError("P235_REAL_SOURCE_GROUNDED_BRIEF_NOT_VERIFIED:"
                         +str(x.get("reason_code","UNKNOWN"))[:90])
    print(json.dumps({
        "status":"PASS","real_model_generated_tokens":True,
        "independently_replayed_actual_public_facts":3,
        "approved_human_only_source_card_report":True,
        "model_free_text_visible":False,
        "guard":"HOLD","trades":0,
        "raw_SEC_source_verified":False,
        "true_NDX_rights_verified":False,
        "public_production":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
