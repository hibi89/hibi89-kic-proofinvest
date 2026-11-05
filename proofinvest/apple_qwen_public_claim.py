"""P233 local Qwen numerical source-check on public Apple 2026 filing facts.

A real model is required in the dedicated [qwen-real-e2e] CI job. Only two
manually reviewed PUBLIC financial numbers, not SEC original text/files, are
passed to a local loopback endpoint. The independent Decimal arithmetic, not
the model, decides correctness. No investments, trading, source ownership,
copyright license, market index entitlement, or EDGAR original proof claimed.
"""
from __future__ import annotations

from decimal import Decimal
import json
from typing import Any

from .apple_fy2026_public_filing_review import (
    public_2026_values, review_apple_2026_public_financials,
)
from .ticker_local_model_triage import _call_loopback, _json_no_duplicate

_MODEL = "qwen2.5:0.5b-instruct"
_CITE = "AAPL_FY2026_ITEM8_PUBLIC_NUMERIC_TRANSCRIPTION"
_SCHEMA = {
    "type": "object",
    "properties": {
        "comparison": {
            "type": "string",
            "enum": ["CASH_GREATER", "CASH_NOT_GREATER"],
        },
        "source_ref": {"type": "string", "enum": [_CITE]},
        "decision": {"type": "string", "enum": ["HUMAN_REVIEW_ONLY"]},
    },
    "required": ["comparison", "source_ref", "decision"],
    "additionalProperties": False,
}
_OUT = "kuodra.p233-qwen-public-numeric-fact-v1"


def _blocked(reason: str, requests: int = 0) -> dict[str, Any]:
    return {
        "schema": _OUT, "status": "BLOCKED", "reason_code": reason,
        "local_model_requests": requests,
        "actual_model_tokens_verified": False,
        "independent_public_fact_validated": False,
        "issuer_raw_sec_bytes_authenticated": False,
        "copyright_or_model_data_rights_attested": False,
        "true_ndx_stock_or_peer_rights_verified": False,
        "model_answer_used_without_independent_check": False,
        "external_model_requests": 0, "secrets_or_originals_sent": False,
        "human_approval": False, "guard_policy_preview": "HOLD",
        "investment_advice": False, "trade_executed": False,
    }


def _public() -> dict[str, Any]:
    return review_apple_2026_public_financials(
        ticker="AAPL", accession="0000320193-26-000026",
        as_of="2026-11-05", values=public_2026_values(),
    )


def verify_local_qwen_public_facts(raw: Any) -> dict[str, Any]:
    """Return only authored deterministic text after independent fact replay."""
    source = _public()
    if (source.get("status") !=
            "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED"
            or source.get("source_rights_verified") is not False
            or source.get("original_bytes_authenticated") is not False
            or source.get("trade_executed") is not False):
        return _blocked("PUBLISHED_PUBLIC_NUMERIC_REVIEW_UNAVAILABLE")
    if type(raw) is not bytes or not 0 < len(raw) <= 8192:
        return _blocked("INVALID_LOCAL_MODEL_RESPONSE", 1)
    try:
        envelope = _json_no_duplicate(raw)
        if (type(envelope) is not dict
                or envelope.get("done") is not True
                or envelope.get("model") != _MODEL
                or type(envelope.get("eval_count")) is not int
                or envelope["eval_count"] < 1
                or type(envelope.get("response")) is not str
                or not 0 < len(envelope["response"]) <= 512):
            return _blocked("ACTUAL_MODEL_GENERATION_NOT_PROVEN", 1)
        claim = _json_no_duplicate(envelope["response"].encode("utf-8"))
        if (type(claim) is not dict
                or set(claim) != {"comparison", "source_ref", "decision"}
                or claim.get("source_ref") != _CITE
                or claim.get("decision") != "HUMAN_REVIEW_ONLY"
                or claim.get("comparison") not in
                   ("CASH_GREATER", "CASH_NOT_GREATER")):
            return _blocked("STRUCTURED_MODEL_POLICY_OR_CITATION_INVALID", 1)
        facts = source["transcribed_financial_statement_values"]
        cfo = Decimal(facts["operating_cash_flow"]["2026_usd_millions"])
        income = Decimal(facts["net_income"]["2026_usd_millions"])
        expected = "CASH_GREATER" if cfo > income else "CASH_NOT_GREATER"
        if claim["comparison"] != expected:
            return _blocked("REAL_MODEL_PUBLIC_NUMERIC_CLAIM_DISAGREES", 1)
        return {
            **_blocked("PUBLIC_NUMBERS_ONLY_NO_LICENSE_ATTESTATION", 1),
            "status": "ACTUAL_LOCAL_MODEL_PUBLIC_NUMERIC_COMPARISON_MATCHED",
            "reason_code": "INDEPENDENT_DECIMAL_MATCH_HUMAN_ONLY",
            "actual_model_tokens_verified": True,
            "independent_public_fact_validated": True,
            "evidence_id": _CITE,
            "verified_public_comparison": expected,
            "cash_minus_net_income_usd_millions": str(cfo - income),
            "model_free_text_displayed": False,
            "issuer_source_filing_url": source["public_filing_url"],
        }
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError,
            RecursionError):
        return _blocked("LOCAL_MODEL_FACT_REPLAY_EXCEPTION", 1)


def run_actual_local_qwen_public_facts(
    *, explicit_public_local_consent: bool = False,
    port: int = 11435,
) -> dict[str, Any]:
    """One request only after explicit consent; no owner originals transmitted."""
    if explicit_public_local_consent is not True:
        return _blocked("EXPLICIT_LOCAL_PUBLIC_FACT_MODEL_CONSENT_REQUIRED")
    if type(port) is not int or port != 11435:
        return _blocked("MODEL_FIXED_LOOPBACK_PORT_REQUIRED")
    source = _public()
    if (source.get("status") !=
            "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED"
            or source.get("source_rights_verified") is not False):
        return _blocked("PUBLIC_SOURCE_REVIEW_INVALID")
    facts = source["transcribed_financial_statement_values"]
    # Never include the answer, difference, filing file, original text or keys.
    prompt = (
        "Read these TWO positive integers, reported in USD millions from "
        "PUBLIC manually transcribed Apple FY2026 Form 10-K financial facts. "
        "Cash from operations = "
        + facts["operating_cash_flow"]["2026_usd_millions"]
        + ". Net income = " + facts["net_income"]["2026_usd_millions"]
        + ". Is cash from operations numerically GREATER than net income? "
        "Use comparison CASH_GREATER for yes, CASH_NOT_GREATER for no. "
        "Output a JSON object ONLY with comparison, source_ref, decision. "
        "source_ref must be " + _CITE
        + " and decision must be HUMAN_REVIEW_ONLY. "
        "Do not add advice, explanation, forecasts, or any extra fields."
    )
    request = json.dumps({
        "model": _MODEL, "stream": False, "prompt": prompt,
        "format": _SCHEMA,
        "options": {"temperature": 0, "num_predict": 128},
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if len(request) > 2048:
        return _blocked("PUBLIC_FACT_LOCAL_MODEL_REQUEST_OVER_LIMIT")
    try:
        response = _call_loopback(request, port=port)
    except (ValueError, TypeError, OSError, UnicodeError):
        return _blocked("LOCAL_MODEL_HTTP_UNAVAILABLE", 1)
    return verify_local_qwen_public_facts(response)
