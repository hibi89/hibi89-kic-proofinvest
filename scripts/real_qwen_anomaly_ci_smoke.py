"""P234 actual Qwen 1.5B two independent opposite public financial signals.

Execute inside the already-provisioned, pinned Docker Ollama Qwen job, after
P233. No additional model download, no private data, no unsolicited HTTP.
"""
from __future__ import annotations

import json
from proofinvest.apple_qwen_anomaly_screen import run_local_qwen_anomaly_screen


def main() -> int:
    result = run_local_qwen_anomaly_screen(
        explicit_local_model_consent=True,
        explicit_public_derived_consent=True,
    )
    if (result.get("status") != "REAL_QWEN_TWO_PUBLIC_FINANCIAL_SIGNALS_MATCHED"
            or result.get("actual_model_tokens_verified") is not True
            or result.get("two_opposing_independent_signals_verified") is not True
            or result.get("verified_signals") != {
                "inventory_signal": "OUTPACES_REVENUE",
                "receivables_signal": "DOES_NOT_OUTPACE_REVENUE",
            }
            or result.get("guard_decision") != "HOLD"
            or result.get("trade_executed") is not False
            or result.get("fraud_proven") is not False
            or result.get("model_free_text_displayed") is not False
            or result.get("original_sec_bytes_authenticated") is not False
            or result.get("model_and_data_processing_rights_attested") is not False
            or result.get("market_ndx_peer_rights_verified") is not False
            or result.get("raw_source_files_sent") is not False
            or result.get("external_model_requests") != 0):
        raise ValueError("P234_REAL_FINANCIAL_TWO_SIGNALS_NOT_INDEPENDENTLY_MATCHED:"+
                         str(result.get("reason_code", "UNAVAILABLE"))[:95])
    print(json.dumps({
        "status": "PASS", "model": "qwen2.5:1.5b-instruct",
        "genuine_generated_tokens": True,
        "independent_derived_public_checks": 2,
        "positive_inventory_divergence_verified": True,
        "negative_receivables_divergence_verified": True,
        "human_only": True, "guard": "HOLD", "trade": False,
        "source_original_authenticated": False,
        "market_and_peer_rights_verified": False,
        "public_production": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
