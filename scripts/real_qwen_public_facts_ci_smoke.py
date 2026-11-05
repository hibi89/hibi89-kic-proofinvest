"""P233 actual Qwen 0.5B evaluation in an isolated local CI Ollama runtime."""
from __future__ import annotations
import json
from proofinvest.apple_qwen_public_claim import run_actual_local_qwen_public_facts


def main() -> int:
    result = run_actual_local_qwen_public_facts(explicit_public_local_consent=True)
    if (result.get("status") != "ACTUAL_LOCAL_MODEL_PUBLIC_NUMERIC_COMPARISON_MATCHED"
            or result.get("actual_model_tokens_verified") is not True
            or result.get("independent_public_fact_validated") is not True
            or result.get("cash_minus_net_income_usd_millions") != "12922"
            or result.get("guard_policy_preview") != "HOLD"
            or result.get("trade_executed") is not False
            or result.get("issuer_raw_sec_bytes_authenticated") is not False
            or result.get("copyright_or_model_data_rights_attested") is not False
            or result.get("true_ndx_stock_or_peer_rights_verified") is not False
            or result.get("external_model_requests") != 0
            or result.get("secrets_or_originals_sent") is not False):
        raise ValueError("P233_REAL_QWEN_PUBLIC_NUMERIC_FACT_NOT_ACCEPTED:" +
                         str(result.get("reason_code", "UNKNOWN")))
    # Keep CI evidence bounded, do not emit raw original inputs or model text.
    print(json.dumps({
        "status": "PASS", "actual_model_qwen_inference_verified": True,
        "model": "qwen2.5:0.5b-instruct",
        "independent_public_numeric_fact_match": True,
        "reference": result["evidence_id"],
        "human_only": True, "guard": "HOLD",
        "original_sec_bytes_attested": False,
        "index_licensed": False, "commercial_ai_data_rights_attested": False,
        "public_production": False, "trades": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
