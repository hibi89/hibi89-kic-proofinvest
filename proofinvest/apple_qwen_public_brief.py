"""P235 source-bound PUBLIC issuer evidence summary by actual local model.

Stop/Pivot from failed P234 LLM *arithmetic*. All financial comparisons are
performed using independently replayed Decimal public Apple Item 8 facts.
The local model only selects an evidence-grounded reporting classification
and exact source card identifiers; no model free text is shown or trusted.
No SEC original, raw financial input, ticker, URLs, model prompt injection,
NDX, commercial vendor data or user bytes reach the model.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
import json

from .apple_fy2026_public_filing_review import (
    public_2026_values, review_apple_2026_public_financials,
)
from .ticker_local_model_triage import _call_loopback, _json_no_duplicate

_MODEL = "qwen2.5:1.5b-instruct"
_SCHEMA = "kuodra.p235-real-public-evidence-summary.v1"
_REFS = (
    "PUBLIC_CFO_GT_NET_INCOME",
    "PUBLIC_INVENTORY_GROWTH_GT_REVENUE",
    "PUBLIC_RECEIVABLES_GROWTH_NOT_GT_REVENUE",
)
_SCENARIO = "LIMITED_HISTORICAL_FINANCIAL_FACTS_MARKET_UNVERIFIED"
_POLICY = "HUMAN_REVIEW_ONLY"
_FORMAT = {
    "type":"object",
    "properties":{
        "scenario":{"type":"string","enum":[
            _SCENARIO,
            "ALL_SOURCES_VERIFIED",
        ]},
        "source_refs":{"type":"array","items":{
            "type":"string","enum":list(_REFS)},"minItems":3,
            "maxItems":3},
        "decision":{"type":"string","enum":[_POLICY]},
    },
    "required":["scenario","source_refs","decision"],
    "additionalProperties":False,
}


def _blocked(reason: str, calls: int = 0) -> dict[str, Any]:
    return {
        "schema":_SCHEMA,"status":"BLOCKED","reason_code":reason,
        "actual_model_tokens_verified":False,
        "source_bound_multi_fact_model_verified":False,
        "local_model_calls":calls,"external_model_calls":0,
        "publisher_original_byte_authenticated":False,
        "source_redistribution_rights_verified":False,
        "market_price_ndx_rights_verified":False,
        "representative_peer_rights_verified":False,
        "financial_ai_full_authorized":False,
        "full_abc_complete":False,
        "model_free_text_displayed":False,
        "market_prediction":False,"fraud_proven":False,
        "investment_recommendation":False,
        "guard_policy_preview":"HOLD","trades_executed":0,
        "confidential_originals_transmitted":False,
    }


def _evidence() -> dict[str, Any] | None:
    result = review_apple_2026_public_financials(
        ticker="AAPL",as_of="2026-11-05",
        accession="0000320193-26-000026",
        values=public_2026_values(),
    )
    if (result.get("status") !=
            "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED"
            or result.get("original_bytes_authenticated") is not False
            or result.get("source_rights_verified") is not False
            or result.get("guard_policy_preview") != "HOLD"
            or result.get("trade_executed") is not False
            or result.get("fraud_proven") is not False):
        return None
    try:
        rows = result["transcribed_financial_statement_values"]
        m = result["derived_metrics"]
        cash = Decimal(rows["operating_cash_flow"]["2026_usd_millions"])
        net = Decimal(rows["net_income"]["2026_usd_millions"])
        rev = Decimal(m["revenue_growth_pct"])
        inv = Decimal(m["inventory_growth_pct"])
        ar = Decimal(m["receivables_growth_pct"])
        if (not all(v.is_finite() for v in (cash,net,rev,inv,ar))
                or not (cash > net > 0 and inv > rev > ar)
                or result["signals"] !=
                    ["INVENTORY_GROWTH_OUTPACED_REVENUE_HUMAN_REVIEW"]
                or cash-net != Decimal("12922")):
            return None
        return {
            "facts":{
                _REFS[0]:"SUPPORTED_PUBLIC_NUMERIC_MATCH",
                _REFS[1]:"SUPPORTED_PUBLIC_GROWTH_MATCH",
                _REFS[2]:"SUPPORTED_PUBLIC_GROWTH_NONMATCH",
            },
            "market":"MISSING_PROVIDER_ORIGIN_AND_RIGHTS",
            "filing_url":result["public_filing_url"],
            "period":result["fiscal_period_ends"]["2026"],
            "authored_text":(
                "Apple FY2026 공개 공시 수치에 따르면 영업현금흐름은 순이익보다 "
                "높고, 재고 증가율은 매출 증가율을 초과하지만 매출채권 "
                "증가율은 초과하지 않습니다. 이는 제한적인 과거 사실 검토이며 "
                "시장 시세·Nasdaq-100 원본 및 사용권이 검증되지 않았으므로 "
                "투자 또는 회계부정 판단을 보류합니다."
            ),
        }
    except (KeyError,TypeError,ValueError,InvalidOperation,OverflowError):
        return None


def verify_public_evidence_model_response(raw: Any) -> dict[str, Any]:
    evidence = _evidence()
    if evidence is None:
        return _blocked("INDEPENDENT_PUBLIC_FACT_REPLAY_FAILED")
    if type(raw) is not bytes or not 0 < len(raw) <= 8192:
        return _blocked("MODEL_RESPONSE_LENGTH_OR_TYPE_INVALID",1)
    try:
        packet=_json_no_duplicate(raw)
        if (type(packet) is not dict
                or packet.get("done") is not True
                or packet.get("model") != _MODEL
                or type(packet.get("eval_count")) is not int
                or packet["eval_count"] < 1
                or type(packet.get("response")) is not str
                or not 0 < len(packet["response"]) <= 1024):
            return _blocked("GENUINE_LOCAL_MODEL_TOKEN_NOT_ATTESTED",1)
        out = _json_no_duplicate(packet["response"].encode("utf-8"))
        if (type(out) is not dict
                or set(out) != {"scenario","source_refs","decision"}
                or out.get("scenario") != _SCENARIO
                or out.get("decision") != _POLICY
                or type(out.get("source_refs")) is not list
                or out["source_refs"] != list(_REFS)):
            return _blocked("MODEL_SOURCE_CARD_OR_POLICY_MISMATCH",1)
        return {
            **_blocked("PUBLIC_FACTS_ONLY_HUMAN_REVIEW",1),
            "status":"REAL_LOCAL_MODEL_MULTI_PUBLIC_FACT_BRIEF_VERIFIED",
            "reason_code":"INDEPENDENT_PUBLIC_CARDS_AND_MODEL_MATCH",
            "actual_model_tokens_verified":True,
            "source_bound_multi_fact_model_verified":True,
            "scenario":_SCENARIO,
            "source_refs":list(_REFS),
            "public_filing_reference":evidence["filing_url"],
            "fiscal_period_end":evidence["period"],
            "approved_human_only_text":evidence["authored_text"],
            "model_free_text_displayed":False,
        }
    except (ValueError,TypeError,KeyError,UnicodeError,OverflowError,
            RecursionError):
        return _blocked("LOCAL_MODEL_SCHEMA_OR_SOURCE_PARSE_FAILED",1)


def run_local_public_evidence_summary(
    *,local_model_confirmed: bool = False,
    public_fact_summary_consent: bool = False,
    port: int = 11435,
) -> dict[str, Any]:
    if local_model_confirmed is not True or public_fact_summary_consent is not True:
        return _blocked("TWO_EXPLICIT_PUBLIC_LOCAL_CONSENTS_REQUIRED")
    if type(port) is not int or port != 11435:
        return _blocked("FIXED_LOOPBACK_PORT_REQUIRED")
    evidence = _evidence()
    if evidence is None:
        return _blocked("PUBLIC_FINANCIAL_SOURCE_NOT_READY")
    # Provide derivative evidence statuses only; not ticker, raw values, SEC
    # file, provider data, historical document, private packets, or URLs.
    labels = json.dumps(evidence["facts"],sort_keys=True,separators=(",",":"))
    prompt = (
        "You are summarizing the AVAILABILITY of three already-validated "
        "PUBLIC historical financial evidence cards. Do NOT compute any "
        "numbers: a deterministic calculator already did so. "
        "The source card labels and their matching statuses are: "+labels+". "
        "MARKET_SOURCE="+evidence["market"]+". "
        "If market source is MISSING_PROVIDER_ORIGIN_AND_RIGHTS, the scenario "
        "must be LIMITED_HISTORICAL_FINANCIAL_FACTS_MARKET_UNVERIFIED, "
        "not ALL_SOURCES_VERIFIED. "
        "Return JSON only with scenario, source_refs, decision. "
        "source_refs must be an array listing the THREE source card keys "
        "given above in this order: "+
        ",".join(_REFS)+". "
        "decision must be HUMAN_REVIEW_ONLY. No explanations or advice."
    )
    payload = json.dumps({
        "model":_MODEL,"prompt":prompt,"stream":False,
        "format":_FORMAT,"options":{"temperature":0,"num_predict":155},
    },ensure_ascii=False,separators=(",",":"),sort_keys=True).encode()
    if not 0 < len(payload) <= 2048:
        return _blocked("BOUNDED_MODEL_REQUEST_EXCEEDED")
    try:
        raw = _call_loopback(payload,port=port)
    except (ValueError,OSError,TypeError,UnicodeError):
        return _blocked("LOCAL_MODEL_HTTP_UNAVAILABLE",1)
    return verify_public_evidence_model_response(raw)
