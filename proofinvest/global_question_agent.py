"""Bounded global-US question -> issuer tool -> guarded cited answer.

The default route is deterministic, not a live AI Agent. An optional one-shot
locally owned Qwen planner can check the allowed intent AFTER two consents;
only the question text reaches loopback (never publisher/market originals).
No remote APIs, credentials, trades, live filing fetch or data entitlement.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

from .global_fundamentals_review import (
    build_marketless_global_review, verify_marketless_global_review,
)
from .ticker_local_model_triage import _call_loopback, _json_no_duplicate

_STATUS = "QUESTION_SOURCE_BOUND_LOCAL_REVIEW_HOLD"
_MODEL = "qwen2.5:1.5b-instruct"
_INTENTS = (
    "GUARD", "MARKET", "PEERS", "WORKING_CAPITAL", "CASHFLOW",
    "REVENUE", "SOURCE",
)
_MODEL_FORMAT = {
    "type": "object",
    "properties": {
        "issuer": {"type": "string", "enum": ["NVDA", "DELL"]},
        "intent": {"type": "string", "enum": list(_INTENTS)},
        "decision": {"type": "string", "enum": ["HUMAN_REVIEW_ONLY"]},
    },
    "required": ["issuer", "intent", "decision"],
    "additionalProperties": False,
}
_ALIASES = {
    "NVDA": (r"(?<![a-z0-9])(?:nvda|nvidia)(?![a-z0-9])", "엔비디아"),
    "DELL": (r"(?<![a-z0-9])dell(?![a-z0-9])", "델"),
}
_OTHER_TICKERS = re.compile(
    r"(?<![a-z0-9])(?:aapl|tsla|msft|goog|googl|meta|amzn|intc|"
    r"amd|qcom|qqq)(?![a-z0-9])", re.ASCII,
)
_TERMS = (
    ("GUARD", ("매수", "매도", "사도", "사야", "팔아", "추천", "투자해",
               "진입", "위험", "리스크", "부정", "buy", "sell", "fraud", "guard")),
    ("MARKET", ("주가", "나스닥", "거품", "베타", "지수", "시세",
                "market", "price", "index", "beta", "valuation")),
    ("PEERS", ("경쟁사", "경쟁", "동종", "피어", "산업비교",
               "compare", "competitor", "peer", "sector")),
    ("WORKING_CAPITAL", ("재고", "매출채권", "운전자본", "회계착시",
                         "inventory", "receivable", "working capital")),
    ("CASHFLOW", ("현금흐름", "순이익", "현금전환", "현금창출",
                  "cashflow", "cash flow", "cfo", "net income")),
    ("REVENUE", ("매출", "성장률", "revenue", "sales", "growth")),
    ("SOURCE", ("원문", "출처", "근거", "공시", "라이선스", "이용권",
                "evidence", "source", "filing", "rights", "license")),
)


def _blocked(reason: str, *, local_calls: int = 0) -> dict[str, Any]:
    return {
        "schema": "kuodra.global-question.v1",
        "status": "BLOCKED", "reason_code": reason,
        "tool_calls": 0, "local_model_calls": local_calls,
        "external_network_requests": 0,
        "local_model_protocol_verified": False,
        "real_model_provider_authenticated": False,
        "ai_agent_executed": False, "guard_policy_preview": "HOLD",
        "source_rights_verified": False, "external_sharing_allowed": False,
        "full_abc_complete": False, "trade_executed": False,
    }


def preflight_global_question(question: Any) -> dict[str, Any]:
    """Validate before any evidence tool or model request; one issuer/intent."""
    if type(question) is not str or not 4 <= len(question.strip()) <= 180:
        return _blocked("QUESTION_LENGTH_OR_TYPE")
    if any(ord(c) < 32 or ord(c) == 127 for c in question):
        return _blocked("QUESTION_CONTROL_CHAR")
    if any(x in question.lower() for x in (
            "://", "www.", "@", "<script", ".env", "api_key", "apikey")):
        return _blocked("QUESTION_SECRET_OR_EXTERNAL_CONTENT")
    if re.search(r"(?<!\d)20(?:1\d|2\d)(?!\d)", question):
        # Historical source receipts are only verified for the pinned vintage;
        # do not hallucinate a caller-requested new fiscal year.
        if "2026" not in question or len(re.findall(
                r"(?<!\d)20(?:1\d|2\d)(?!\d)", question)) != 1:
            return _blocked("UNSUPPORTED_REQUESTED_FISCAL_YEAR")
    q = question.casefold()
    tickers = [
        ticker for ticker, aliases in _ALIASES.items()
        if any(re.search(pattern, q) if pattern.startswith("(?") else
               pattern in q for pattern in aliases)
    ]
    if len(tickers) != 1:
        return _blocked("ISSUER_AMBIGUOUS_OR_NOT_SUPPORTED")
    if _OTHER_TICKERS.search(q):
        # A peer source may be requested only in a true peer question;
        # it is not an alternative supported primary issuer.
        if not (tickers[0] == "NVDA" and
                any(k in q for k in ("경쟁", "비교", "peer", "competitor")) and
                all(tok in {"amd", "intc", "qcom"} for tok in
                    _OTHER_TICKERS.findall(q))):
            return _blocked("UNSUPPORTED_SECOND_PRIMARY_OR_MARKET_TICKER")
    chosen = next((intent for intent, terms in _TERMS
                   if any(term in q for term in terms)), None)
    if chosen is None:
        return _blocked("QUESTION_INTENT_NOT_SUPPORTED")
    # If no usable peer comparison exists, the answer is UNAVAILABLE, never
    # silently substituted with unrelated company's financials.
    return {
        "status": "READY",
        "ticker": tickers[0], "intent": chosen,
        "tool": "build_marketless_global_review",
        "local_model_required": False, "market_requests": 0,
    }


def _optional_model_plan(question: str, ticker: str, intent: str) -> dict:
    """One strict, non-streaming owner-controlled loopback request."""
    prompt = (
        "Classify this operator-authored investment research question into "
        "one *permitted* local read-only issuer review tool intent. "
        "The deterministic security preflight already checked the allowed "
        "issuer and intent. Output must exactly match these verified values: "
        "issuer=" + ticker + "; intent=" + intent +
        "; decision=HUMAN_REVIEW_ONLY. No free text or advice. "
        "The operator question is: " + json.dumps(
            question, ensure_ascii=False) + ". "
        "Return a JSON object with issuer,intent,decision only."
    )
    payload = json.dumps({
        "model": _MODEL, "prompt": prompt, "stream": False,
        "format": _MODEL_FORMAT,
        "options": {"temperature": 0, "num_predict": 96},
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if not 0 < len(payload) <= 2048:
        raise ValueError("BOUNDED_LOCAL_QUESTION_PROMPT_REQUIRED")
    raw = _call_loopback(payload, port=11435, timeout_seconds=24)
    parsed = _json_no_duplicate(raw)
    if (type(parsed) is not dict
            or parsed.get("done") is not True
            or parsed.get("model") != _MODEL
            or type(parsed.get("eval_count")) is not int
            or parsed["eval_count"] <= 0
            or type(parsed.get("response")) is not str
            or not 0 < len(parsed["response"]) <= 512):
        raise ValueError("LOCAL_MODEL_RESPONSE_ENVELOPE_INVALID")
    out = _json_no_duplicate(parsed["response"].encode("utf-8"))
    if out != {"issuer": ticker, "intent": intent,
               "decision": "HUMAN_REVIEW_ONLY"}:
        raise ValueError("LOCAL_MODEL_INTENT_OR_POLICY_INVALID")
    return {"local_model_calls": 1, "model_protocol_verified": True}


def _answer(intent: str, report: dict[str, Any]) -> tuple[str, list[dict]]:
    issuer = report["ticker"]
    b, c, src = report["engine_b"], report["engine_c"], report["source"]
    citations = [{
        "kind": "FIRST_PARTY_ISSUER",
        "url": src["publisher_url"],
        "sha256": src["publisher_raw_sha256"],
        "source_authenticated_by_sec": False,
        "rights_verified": False,
    }]
    if intent == "WORKING_CAPITAL":
        text = (issuer + " 과거 발행사 수치상 매출 대비 매출채권 증가율 격차는 "
                + b["receivables_minus_revenue_growth_pp"] +
                "pp, 재고 증가율 격차는 " +
                b["inventory_minus_revenue_growth_pp"] + "pp입니다. "
                "단일 기간 10pp 이상 격차는 추가 검토 후보이며 "
                "회계부정이나 투자 결론이 아닙니다.")
    elif intent == "CASHFLOW":
        text = (issuer + " 과거 발행사 수치에서 영업현금흐름/순이익은 " +
                b["cashflow_to_net_income_ratio"] + "배입니다. "
                "기간·업종·회계정책 추가 검토 없이 이 비율로 안전성이나 "
                "회계부정을 확정할 수 없습니다.")
    elif intent == "REVENUE":
        text = (issuer + " 과거 발행사 기준 매출 성장률은 " +
                b["revenue_growth_pct"] + "%입니다. "
                "실시간 추정이나 미래 성과 예측이 아닌 과거 수치 검산입니다.")
    elif intent == "PEERS":
        if not c["peers"]:
            text = (issuer + "에 대해 원문 근거가 연결된 비교기업 묶음이 "
                    "아직 없어 경쟁사 분석을 제공할 수 없습니다.")
        else:
            peers = ", ".join(
                x["ticker"] + " " + x["revenue_growth_pct"] + "%"
                for x in c["peers"])
            text = (issuer + "와 비교할 참고기업의 과거 매출 성장률: " +
                    peers + ". 서로 다른 결산일·사업구성·원문 바이트 및 "
                    "사용권 미확인으로 업종 순위나 동질 비교로 해석할 수 없습니다.")
            citations.extend({
                "kind": "PEER_MANUALLY_REVIEWED",
                "url": x["publisher_url"],
                "sha256": None,
                "source_authenticated_by_sec": False,
                "rights_verified": False,
            } for x in c["peers"])
    elif intent == "MARKET":
        text = (issuer + "의 주가·Nasdaq-100 제공자 원본과 이용권이 "
                "검증되지 않아 시장 대비 수익률·베타·거품 판단은 "
                "UNAVAILABLE입니다. 임의 주가나 ETF 대체값을 사용하지 않습니다.")
    elif intent == "SOURCE":
        text = (issuer + " 발행사 원문을 과거에 관측한 SHA 기록은 있지만 "
                "SEC EDGAR 원본 동일성·재사용·AI 처리·공개 시연 권한을 "
                "인증하지 않았습니다. 출처 확인이 추가로 필요합니다.")
    else:
        text = (issuer + "에 대한 Guard는 HOLD입니다. "
                "확인되지 않은 외부 출처·시장 데이터·위험 자료가 있으므로 "
                "매수/매도 판단이나 거래 승인을 할 수 없습니다.")
    text += " 출처 확인 전 투자권고 불가 · Guard HOLD."
    return text, citations


def answer_global_question(
    question: Any, *, use_local_model: bool = False,
    consent_local_model: bool = False,
    consent_question_text: bool = False,
) -> dict[str, Any]:
    """Preflight -> optional local model -> source replay -> Guard -> answer."""
    route = preflight_global_question(question)
    if route["status"] != "READY":
        return route
    calls = 0
    model_valid = False
    if use_local_model is True:
        if consent_local_model is not True or consent_question_text is not True:
            return _blocked("TWO_LOCAL_MODEL_CONSENTS_REQUIRED")
        try:
            result = _optional_model_plan(question, route["ticker"],
                                          route["intent"])
            calls = result["local_model_calls"]
            model_valid = result["model_protocol_verified"]
        except (OSError, ValueError, UnicodeError, TypeError,
                KeyError, RecursionError):
            return _blocked("LOCAL_MODEL_PLAN_REJECTED", local_calls=1)
    elif use_local_model is not False:
        return _blocked("INVALID_MODEL_SWITCH")
    report = build_marketless_global_review(ticker=route["ticker"])
    if (report.get("status") != "GLOBAL_ISSUER_B_C_LIMITED_GUARD_HOLD"
            or not verify_marketless_global_review(report)
            or report.get("guard", {}).get("decision") != "HOLD"
            or report.get("source_rights_verified") is not False
            or report.get("full_abc_complete") is not False
            or report.get("external_sharing_allowed") is not False
            or report.get("ai_agent_executed") is not False
            or report.get("market_api_requests") != 0):
        return _blocked("ISSUER_OR_GUARD_SOURCE_REPLAY_FAILED", local_calls=calls)
    content, refs = _answer(route["intent"], report)
    return {
        **_blocked("SOURCE_BOUND_HISTORICAL_HUMAN_ANSWER", local_calls=calls),
        "status": _STATUS,
        "ticker": route["ticker"], "intent": route["intent"],
        "question_sha256": sha256(question.encode("utf-8")).hexdigest(),
        "answer": content, "source_links": refs,
        "issuer_review_sha256": report["integrity_sha256"],
        "tool_calls": 1, "tool_trace": [
            {"step": "PREFLIGHT", "result": "ONE_SUPPORTED_ISSUER_INTENT"},
            {"step": "MODEL_VALIDATION", "result":
                "OPTIONAL_LOCAL_PROTOCOL_VALIDATED" if model_valid else
                "DETERMINISTIC_ROUTE_NO_MODEL"},
            {"step": "SOURCE_REPLAY", "result": "ISSUER_B_C_GUARD_HOLD_VERIFIED"},
            {"step": "ANSWER", "result": "HUMAN_ONLY_EVIDENCE_REFS"},
        ],
        "local_model_protocol_verified": model_valid,
        "answer_source_replay_verified": True,
        "source_rights_verified": False,
        "external_sharing_allowed": False,
        "full_abc_complete": False, "ai_agent_executed": False,
        "trade_executed": False,
    }


def verify_global_question_answer(answer: Any, question: Any) -> bool:
    """Recompute an answer; never use model-generated words for finance."""
    if (type(answer) is not dict or answer.get("status") != _STATUS
            or type(question) is not str
            or answer.get("local_model_calls") not in (0, 1)
            or answer.get("local_model_protocol_verified") not in (True, False)):
        return False
    try:
        result = answer_global_question(question)
        if result.get("status") != _STATUS:
            return False
        if answer["local_model_calls"] == 1:
            # Protocol proof is a separate local trust boundary; the
            # deterministic financial source and authored text are replayed.
            result["local_model_calls"] = 1
            result["local_model_protocol_verified"] = True
            result["tool_trace"][1]["result"] = "OPTIONAL_LOCAL_PROTOCOL_VALIDATED"
        return result == answer
    except (ValueError, TypeError, KeyError, RecursionError):
        return False
