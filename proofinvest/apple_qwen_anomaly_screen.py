"""P234 bounded real Qwen public FY2026 financial anomaly screen.

Distinct from P233 cash>income comparator: two *opposite* derived financial
screen signals (inventory growth above revenue, receivables growth below
revenue) must BOTH be independently replayed from issuer public annual facts.
An actual open-weight local model proposes only bounded classification codes,
never an explanation, fraud accusation, investment recommendation or trade.

Only three derived PERCENTAGES from manually checked public Apple FY2026
financial figures are sent to user-controlled 127.0.0.1 Ollama after consent.
Historical public transcription is not authenticated SEC original bytes or
proof of index/peer/model-processing contract rights.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
from typing import Any

from .apple_fy2026_public_filing_review import (
    public_2026_values, review_apple_2026_public_financials,
)
from .ticker_local_model_triage import _call_loopback, _json_no_duplicate

_MODEL = "qwen2.5:0.5b-instruct"
_CITE = "AAPL_FY2026_ITEM8_PUBLIC_DERIVED_GROWTH"
_SCHEMA = "kuodra.p234-qwen-public-financial-signals.v1"
_HUMAN = "HUMAN_REVIEW_ONLY"
_OVER = "OUTPACES_REVENUE"
_NOT_OVER = "DOES_NOT_OUTPACE_REVENUE"
_OLLAMA_FORMAT = {
    "type": "object",
    "properties": {
        "signal": {"type": "string", "enum": [_OVER, _NOT_OVER]},
        "source_ref": {"type": "string", "enum": [_CITE]},
        "decision": {"type": "string", "enum": [_HUMAN]},
    },
    "required": ["signal", "source_ref", "decision"],
    "additionalProperties": False,
}

def _blocked(reason: str, local_calls: int = 0) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "actual_model_tokens_verified": False,
        "two_opposing_independent_signals_verified": False,
        "local_model_requests": local_calls,
        "original_sec_bytes_authenticated": False,
        "market_ndx_peer_rights_verified": False,
        "model_and_data_processing_rights_attested": False,
        "source_use_rights_verified": False,
        "full_abc_complete": False, "model_free_text_displayed": False,
        "fraud_proven": False, "investment_recommendation": False,
        "guard_decision": "HOLD", "human_approved": False,
        "trade_executed": False, "external_model_requests": 0,
        "raw_source_files_sent": False, "confidential_data_sent": False,
    }


def _checked_public_growth() -> dict[str, Any] | None:
    reviewed = review_apple_2026_public_financials(
        ticker="AAPL", accession="0000320193-26-000026",
        as_of="2026-11-05", values=public_2026_values(),
    )
    if (reviewed.get("status") !=
            "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED"
            or reviewed.get("original_bytes_authenticated") is not False
            or reviewed.get("source_rights_verified") is not False
            or reviewed.get("guard_policy_preview") != "HOLD"
            or reviewed.get("trade_executed") is not False
            or reviewed.get("fraud_proven") is not False
            or type(reviewed.get("derived_metrics")) is not dict
            or reviewed.get("signals") !=
               ["INVENTORY_GROWTH_OUTPACED_REVENUE_HUMAN_REVIEW"]):
        return None
    try:
        m = reviewed["derived_metrics"]
        checked = {
            "revenue": Decimal(m["revenue_growth_pct"]),
            "inventory": Decimal(m["inventory_growth_pct"]),
            "receivables": Decimal(m["receivables_growth_pct"]),
        }
        if (not all(x.is_finite() for x in checked.values())
                or checked["revenue"] <= 0
                or checked["inventory"] <= checked["revenue"]
                or checked["receivables"] >= checked["revenue"]
                or any(not (-100 < val < 1000) for val in checked.values())):
            return None
        # Derive the TWO expected codes independently. No model text decides.
        return {
            "growth": {k: str(v) for k, v in checked.items()},
            "expected": {
                "inventory_signal": (
                    _OVER if checked["inventory"] > checked["revenue"]
                    else _NOT_OVER
                ),
                "receivables_signal": (
                    _OVER if checked["receivables"] > checked["revenue"]
                    else _NOT_OVER
                ),
            },
        }
    except (InvalidOperation, KeyError, TypeError, ValueError, OverflowError):
        return None



def verify_local_qwen_anomaly_response(raws: Any) -> dict[str, Any]:
    """Replay TWO separate model responses against independently derived facts.

    One multi-field LLM response previously disagreed with public math, so no
    inference/safety claim is made from such a bundle. Each signal now has its
    own independently validated generation, provenance label and output policy.
    """
    checked = _checked_public_growth()
    if checked is None:
        return _blocked("PUBLIC_SOURCE_NUMERIC_REPLAY_NOT_AVAILABLE")
    if (type(raws) is not tuple or len(raws) != 2
            or any(type(raw) is not bytes or not 0 < len(raw) <= 8192
                   for raw in raws)):
        return _blocked("EXACT_TWO_MODEL_REPLIES_REQUIRED", 2)
    for i, metric in enumerate(("inventory", "receivables")):
        try:
            env = _json_no_duplicate(raws[i])
            if (type(env) is not dict or env.get("done") is not True
                    or env.get("model") != _MODEL
                    or type(env.get("eval_count")) is not int
                    or env["eval_count"] < 1
                    or type(env.get("response")) is not str
                    or not 0 < len(env["response"]) <= 512):
                return _blocked("REAL_MODEL_GENERATION_NOT_ATTESTED", 2)
            answer = _json_no_duplicate(env["response"].encode("utf-8"))
            if (type(answer) is not dict
                    or set(answer) != {"signal", "source_ref", "decision"}
                    or answer.get("source_ref") != _CITE
                    or answer.get("decision") != _HUMAN
                    or answer.get("signal") not in (_OVER, _NOT_OVER)):
                return _blocked("MODEL_SOURCE_OR_SCHEMA_OR_POLICY_INVALID", 2)
            if answer["signal"] != checked["expected"][metric + "_signal"]:
                return _blocked(
                    "MODEL_" + metric.upper() +
                    "_SIGNAL_CONFLICT_WITH_PUBLIC_MATH", 2)
        except (ValueError, TypeError, KeyError, UnicodeError,
                OverflowError, RecursionError):
            return _blocked("LOCAL_MODEL_SIGNAL_REPLAY_FAILED", 2)
    return {
        **_blocked("HUMAN_ONLY_PUBLIC_ANOMALY_SCREEN", 2),
        "status": "REAL_QWEN_TWO_PUBLIC_FINANCIAL_SIGNALS_MATCHED",
        "actual_model_tokens_verified": True,
        "two_opposing_independent_signals_verified": True,
        "verified_signals": dict(checked["expected"]),
        "growth_percentages_derived_locally": checked["growth"],
        "evidence_id": _CITE,
        "authored_interpretation": (
            "재고 증가율은 매출 증가율보다 높지만 매출채권 증가율은 "
            "매출 증가율보다 낮습니다. 2026년 공개 수치의 제한적인 "
            "산술 검토 결과이며 회계부정·투자판단을 의미하지 않습니다."
        ),
    }


def run_local_qwen_anomaly_screen(
    *, explicit_local_model_consent: bool = False,
    explicit_public_derived_consent: bool = False,
    port: int = 11435,
) -> dict[str, Any]:
    """TWO bounded loopback calls, independently authenticated by schema.

    Both human opt-ins cover exactly two public derived comparisons. No
    model output is ever shown unless both responses match independent math.
    """
    if (explicit_local_model_consent is not True
            or explicit_public_derived_consent is not True):
        return _blocked("TWO_INDEPENDENT_CONSENTS_REQUIRED")
    if type(port) is not int or port != 11435:
        return _blocked("FIXED_LOOPBACK_PORT_REQUIRED")
    checked = _checked_public_growth()
    if checked is None:
        return _blocked("PUBLIC_DERIVED_FINANCIAL_FACTS_INVALID")
    vals = checked["growth"]
    raws: list[bytes] = []
    for metric in ("inventory", "receivables"):
        # Each model only sees the TWO growth rates for this one task.
        # No answer, other signal, original numbers, raw file or issuer name.
        prompt = (
            "Compare exactly TWO public financial growth percentages. "
            "Metric=" + metric.upper() + ". Its year-on-year growth is "
            + vals[metric] + " percent. Revenue year-on-year growth is "
            + vals["revenue"] + " percent. "
            "Is the METRIC percentage strictly greater than the REVENUE "
            "percentage? If YES, signal=OUTPACES_REVENUE. "
            "If NO (less than OR equal), signal=DOES_NOT_OUTPACE_REVENUE. "
            "Return ONLY a JSON object with signal, source_ref, decision. "
            "source_ref=" + _CITE + ". decision=HUMAN_REVIEW_ONLY. "
            "No free-text, advice, forecasts or fraud accusations."
        )
        request = json.dumps({
            "model": _MODEL, "stream": False, "prompt": prompt,
            "format": _OLLAMA_FORMAT,
            "options": {"temperature": 0, "num_predict": 112},
        }, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        if not 0 < len(request) <= 2048:
            return _blocked("REQUEST_EXCEEDS_LOCAL_MODEL_BOUND", len(raws))
        try:
            raws.append(_call_loopback(request, port=port))
        except (ValueError, TypeError, OSError, UnicodeError, RecursionError):
            return _blocked("LOCAL_QWEN_PROTOCOL_OR_REPLAY_FAILED",
                            len(raws) + 1)
    return verify_local_qwen_anomaly_response(tuple(raws))
