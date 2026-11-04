"""P191 true local-model fact classification on public Apple FY2026 10-K data.

No original SEC files, private customer data, true NDX, model free-form claims,
financial advice, paid service, issuer identity proofs or commercial licenses.
"""
from __future__ import annotations

from decimal import Decimal
import json
from typing import Any

from .apple_fy2026_public_filing_review import (
    public_2026_values, review_apple_2026_public_financials,
)
from .ticker_local_model_triage import _call_loopback, _json_no_duplicate

_MODEL = "smollm2:135m-instruct-q4_K_M"
_CITE = "AAPL_2026_10K_ITEM8_CONSOLIDATED_STATEMENTS"
_GREATER = "CFO_EXCEEDS_NET_INCOME"
_NOT_GREATER = "CFO_DOES_NOT_EXCEED_NET_INCOME"
_SCHEMA = {
    "type": "object",
    "properties": {
        "claim": {"type": "string", "enum": [_GREATER, _NOT_GREATER]},
        "source_ref": {"type": "string", "enum": [_CITE]},
        "decision": {"type": "string", "enum": ["HUMAN_REVIEW_ONLY"]},
    },
    "required": ["claim", "source_ref", "decision"],
    "additionalProperties": False,
}


def _blocked(reason: str, calls: int = 0) -> dict[str, Any]:
    return {
        "schema": "kuodra.p191-public-sec-issuer-model.v1",
        "status": "BLOCKED", "reason_code": reason,
        "loopback_http_attempts": calls,
        "actual_model_token_count_verified": False,
        "actual_model_factual_claim_verified": False,
        "publisher_original_bytes_authenticated": False,
        "full_market_ndx_peer_rights_verified": False,
        "full_agent_factual_quality_verified": False,
        "source_use_rights_verified": False,
        "model_free_text_displayed": False,
        "private_input_sent": False,
        "guard_policy_preview": "HOLD",
        "investment_recommendation": False, "trade_executed": False,
        "external_network_requests": 0, "official_contest_submitted": False,
    }


def _public_review() -> dict[str, Any]:
    return review_apple_2026_public_financials(
        ticker="AAPL", accession="0000320193-26-000026",
        as_of="2026-11-05", values=public_2026_values(),
    )


def verify_public_issuer_model_reply(raw: bytes) -> dict[str, Any]:
    reviewed = _public_review()
    if (reviewed.get("status") !=
            "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED"
            or reviewed.get("original_bytes_authenticated") is not False
            or reviewed.get("source_rights_verified") is not False
            or reviewed.get("guard_policy_preview") != "HOLD"
            or reviewed.get("trade_executed") is not False):
        return _blocked("PUBLIC_REVIEW_SOURCE_CONTRACT_FAILED")
    if type(raw) is not bytes or not 0 < len(raw) <= 8192:
        return _blocked("REPLY_SIZE_OR_TYPE_BLOCKED", 1)
    try:
        envelope = _json_no_duplicate(raw)
        if (type(envelope) is not dict or envelope.get("done") is not True
                or envelope.get("model") != _MODEL
                or type(envelope.get("eval_count")) is not int
                or envelope["eval_count"] < 1
                or type(envelope.get("response")) is not str
                or not 0 < len(envelope["response"]) <= 512):
            return _blocked("REAL_MODEL_TOKEN_GENERATION_NOT_PROVEN", 1)
        proposal = _json_no_duplicate(envelope["response"].encode())
        if (type(proposal) is not dict
                or set(proposal) != {"claim", "source_ref", "decision"}
                or proposal.get("claim") not in (_GREATER, _NOT_GREATER)
                or proposal.get("source_ref") != _CITE
                or proposal.get("decision") != "HUMAN_REVIEW_ONLY"):
            return _blocked("MODEL_SCHEMA_OR_CITATION_REJECTED", 1)
        statement = reviewed["transcribed_financial_statement_values"]
        cash = Decimal(statement["operating_cash_flow"]["2026_usd_millions"])
        income = Decimal(statement["net_income"]["2026_usd_millions"])
        actual = _GREATER if cash > income else _NOT_GREATER
        if proposal["claim"] != actual:
            return _blocked("MODEL_FACT_DISAGREED_WITH_PUBLIC_NUMBERS", 1)
        return {
            **_blocked(""),
            "status": "REAL_MODEL_PUBLIC_ISSUER_FACT_INDEPENDENTLY_MATCHED",
            "reason_code": "LOCAL_MODEL_PUBLIC_SEC_NUMERIC_COMPARISON_ONLY",
            "loopback_http_attempts": 1,
            "actual_model_token_count_verified": True,
            "actual_model_factual_claim_verified": True,
            "model_claim": actual,
            "evidence_id": _CITE,
            "official_public_filing_url": reviewed["public_filing_url"],
            "filing_date": reviewed["filing_date"],
            "cash_minus_net_income_usd_millions": str(cash - income),
            "approved_human_review_text": (
                "FY2026 operating cash flow exceeds net income on manually "
                "checked public SEC figures. Not a fraud or investment conclusion."
                if cash > income else
                "FY2026 operating cash flow does not exceed net income on "
                "manually checked public SEC figures; human review only."
            ),
        }
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError,
            RecursionError):
        return _blocked("REAL_MODEL_REPLY_PARSE_OR_EVIDENCE_FAILED", 1)


def run_public_issuer_model(*, consent: bool = False, port: int = 11435) -> dict:
    if consent is not True:
        return _blocked("OPERATOR_EXPLICIT_PUBLIC_MODEL_CONSENT_REQUIRED")
    if type(port) is not int or port != 11435:
        return _blocked("LOOPBACK_PORT_NOT_ALLOWED")
    reviewed = _public_review()
    if reviewed.get("status") != (
            "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED"):
        return _blocked("PUBLIC_SOURCE_NOT_READY")
    statement = reviewed["transcribed_financial_statement_values"]
    # Model must infer the comparison: the independent expected answer is NOT sent.
    # Two actual public figures, but a simpler numeric relation for a tiny
    # 135M model. Neither the answer nor the computed difference is in prompt.
    prompt = (
        "Compare two positive integers from Apple's PUBLIC FY2026 Form 10-K "
        "Item 8 consolidated financial statements (USD millions). "
        "A = cash generated by operating activities = "
        + statement["operating_cash_flow"]["2026_usd_millions"]
        + ". B = net income = "
        + statement["net_income"]["2026_usd_millions"]
        + ". First determine whether A is strictly GREATER than B. "
        "If A>B choose claim CFO_EXCEEDS_NET_INCOME; else choose "
        "CFO_DOES_NOT_EXCEED_NET_INCOME. Output only a JSON object with "
        "claim, source_ref, decision. source_ref must be " + _CITE
        + " and decision must be HUMAN_REVIEW_ONLY. "
        "No recommendations, price forecast, or fraud claims."
    )
    request = json.dumps({
        "model": _MODEL, "stream": False, "prompt": prompt, "format": _SCHEMA,
        "options": {"temperature": 0, "num_predict": 144},
    }, sort_keys=True, separators=(",", ":")).encode()
    if len(request) > 2048:
        return _blocked("PUBLIC_MODEL_REQUEST_OVERSIZE")
    try:
        raw = _call_loopback(request, port=port)
    except (ValueError, OSError, TypeError, UnicodeError):
        return _blocked("LOCAL_ONLY_MODEL_HTTP_UNAVAILABLE", 1)
    return verify_public_issuer_model_reply(raw)
