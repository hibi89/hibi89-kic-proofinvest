"""Owner-supplied arbitrary SEC ticker: 4 originals -> 7 actual tools -> answer.

No network/SEC fetch, data storage, AI investment advice or source entitlement.
A local replay of arbitrary operator files is NOT SEC publisher authentication.
"""
from __future__ import annotations
from datetime import date
from hashlib import sha256
import json
import re
from typing import Any

from .global_question_agent import _TERMS, _optional_model_plan
from .ticker_research_intake import _TICKER
from .ticker_sec_financial_bridge import _KEYS, _LIMITS
from .ticker_local_workflow import run_local_ticker_workflow
from .ticker_local_report import verify_local_report

_SCHEMA = "kuodra.owner-ticker-question.v1"
_STATUS = "LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW"


def _blocked(reason: str, *, calls: int = 0) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "executed_financial_tools": 0, "local_model_calls": calls,
        "source_authenticated": False, "source_rights_verified": False,
        "external_sharing_allowed": False, "ai_agent_executed": False,
        "investment_recommendation": False, "trade_executed": False,
        "full_abc_complete": False, "network_requests": 0,
    }


def _preflight(ticker: Any, as_of: Any, question: Any,
               sources: Any, market_json: Any, industry_json: Any) -> dict:
    if (type(ticker) is not str or _TICKER.fullmatch(ticker) is None
            or type(as_of) is not str
            or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", as_of)):
        return _blocked("INVALID_TICKER_OR_DATE")
    try:
        if date.fromisoformat(as_of).isoformat() != as_of:
            return _blocked("INVALID_CUTOFF_DATE")
    except ValueError:
        return _blocked("INVALID_CUTOFF_DATE")
    if (type(question) is not str or not 4 <= len(question.strip()) <= 180
            or any(ord(c) < 32 or ord(c) == 127 for c in question)
            or any(x in question.casefold() for x in (
                "://", "www.", "@", "<script", ".env", "api_key", "apikey"))):
        return _blocked("QUESTION_INVALID")
    # An explicit year is not a selected filing, nor can it override as_of.
    if re.search(r"(?<!\d)20\d{2}(?!\d)", question):
        return _blocked("UNSUPPORTED_QUESTION_YEAR_USE_CUTOFF")
    if (type(sources) is not dict or set(sources) != set(_KEYS)
            or any(type(sources[k]) is not bytes or
                   not 0 < len(sources[k]) <= _LIMITS[k] for k in _KEYS)
            or (market_json is not None and
                (type(market_json) is not bytes or
                 not 0 < len(market_json) <= 131072))
            or (industry_json is not None and
                (type(industry_json) is not bytes or
                 not 0 < len(industry_json) <= 65536))):
        return _blocked("FOUR_BOUNDED_OPERATOR_FILES_REQUIRED")
    q=question.casefold()
    terms=[x for x,keys in _TERMS if any(key in q for key in keys)]
    if not terms:
        return _blocked("QUESTION_NOT_RESEARCH_INTENT")
    # A primary source identity is supplied separately from the question.
    # Do not silently reassign the issuer from arbitrary question text.
    names=set(re.findall(r"(?<![A-Za-z0-9])(?:NVDA|DELL|AAPL|MSFT|TSLA|AMD|INTC|QCOM)(?![A-Za-z0-9])",
                         question, flags=re.I))
    if any(name.upper()!=ticker for name in names):
        return _blocked("CONFLICTING_TICKER_IN_QUESTION")
    return {"status":"READY","candidate_intents":terms,"default_intent":terms[0]}


def _explain(ticker: str, intent: str, work: dict) -> str:
    revenue=work["revenue"]
    b=work["engine_b"]
    ac=work["supplementary"]
    decision=work["report"]["guard_policy_preview"]
    if intent=="REVENUE":
        result=ticker+" 업로드 원본의 동일 제출기간 매출 성장률: "+str(revenue["growth_pct"])+"%."
    elif intent=="CASHFLOW":
        ratio=b.get("cash_to_net_income_pct")
        result=(ticker+" 업로드 원본의 영업현금흐름/순이익 비율: "+
                (str(ratio)+"%." if ratio is not None and
                 b.get("status")=="REVIEWED_UNVERIFIED"
                 else "UNAVAILABLE (동일 제출기간의 검증 가능한 이익·현금흐름 부족)."))
    elif intent=="WORKING_CAPITAL":
        gap_ar=b.get("receivables_minus_revenue_growth_pp")
        gap_inv=b.get("inventory_minus_revenue_growth_pp")
        result=(ticker+" 매출 대비 운전자본 성장률 격차: "+
                ("매출채권 "+str(gap_ar)+"pp, " if gap_ar is not None else
                 "매출채권 UNAVAILABLE, ")+
                ("재고 "+str(gap_inv)+"pp." if gap_inv is not None else
                 "재고 UNAVAILABLE."))
        result+=" 부정 확정이 아닌 추가 검토 신호입니다."
    elif intent=="PEERS":
        result=ticker+" 비교기업/산업 Engine C: "+str(ac["engine_c"]["status"])+". 출처·동질성 검증 필요."
    elif intent=="MARKET":
        result=ticker+" 시장·지수 Engine A: "+str(ac["engine_a"]["status"])+". 공급자 권리·원본 미인증으로 투자 결론 불가."
    elif intent=="SOURCE":
        result=ticker+" 사용자가 제출한 4개 파일은 SHA/기업·접수번호·기간상 정합성을 재검산했습니다. 실제 SEC 전송 원본 동일성·이용권은 미인증입니다."
    else:
        result=ticker+" 투자 승인·위험 판단을 보류합니다. 출처 진위·이용권·위험 정책의 독립 승인 자료가 없습니다."
    return (result+" Guard "+decision+
            " · 사람 검토 필요 · 투자권고 불가 · 사용자 원본은 SEC 발행처 인증 아님.")


def _execute(ticker: str, as_of: str, question: str,
             sources: dict[str,bytes], market_json: bytes|None,
             industry_json: bytes|None, intent: str, *,
             local_calls: int, protocol: bool) -> dict:
    work=run_local_ticker_workflow(
        ticker=ticker,as_of=as_of,sources=sources,
        market_json=market_json,industry_json=industry_json)
    if (work.get("status")!="READY_FOR_HUMAN_REVIEW_UNVERIFIED"
            or work.get("tool_calls_executed")!=7
            or work.get("source_authenticated") is not False
            or work.get("source_rights_verified") is not False
            or work.get("trade_executed") is not False
            or work.get("network_requests")!=0
            or type(work.get("report")) is not dict
            or work["report"].get("guard_policy_preview") not in ("HOLD","REJECT")):
        return _blocked("ORIGINAL_FILE_WORKFLOW_NOT_VERIFIED",calls=local_calls)
    checked=verify_local_report(work["report"],sources=sources,
                                market_json=market_json,industry_json=industry_json)
    if (checked.get("status")!="PASS"
            or checked.get("report_semantics_recomputed") is not True
            or checked.get("source_rights_verified") is not False):
        return _blocked("INDEPENDENT_SEVEN_STEP_REPLAY_FAILED",calls=local_calls)
    pre=_preflight(ticker,as_of,question,sources,market_json,industry_json)
    if pre["status"]!="READY" or intent not in pre["candidate_intents"]:
        return _blocked("QUESTION_TOOL_BINDING_CHANGED",calls=local_calls)
    # Serialize only bounded redacted results, never operator-supplied originals.
    record={
        "schema":_SCHEMA,"status":_STATUS,
        "ticker":ticker,"as_of":as_of,"intent":intent,
        "allowed_tools":pre["candidate_intents"],
        "question_sha256":sha256(question.encode("utf-8")).hexdigest(),
        "answer":_explain(ticker,intent,work),
        "cik":work["receipt"]["cik"],
        "filing_accession":work["receipt"]["selected_10k_accession"],
        "filing_date":work["receipt"]["selected_10k_filing_date"],
        "sources_sha256":dict(work["receipt"]["source_sha256"]),
        "optional_market_sha256": (
            sha256(market_json).hexdigest() if market_json is not None else None),
        "optional_industry_sha256": (
            sha256(industry_json).hexdigest() if industry_json is not None else None),
        "local_report_sha256":work["report"]["report_sha256"],
        "source_urls":dict(work["receipt"]["source_urls"]),
        "fiscal_revenue_growth_pct":work["revenue"]["growth_pct"],
        "cash_to_net_income_pct":work["engine_b"].get("cash_to_net_income_pct"),
        "engine_b_status":work["engine_b"]["status"],
        "engine_a_status":work["supplementary"]["engine_a"]["status"],
        "engine_c_status":work["supplementary"]["engine_c"]["status"],
        "guard_policy_preview":work["report"]["guard_policy_preview"],
        "executed_financial_tools":7,"local_model_calls":local_calls,
        "model_protocol_verified":protocol,
        "tool_trace":[dict(x) for x in work["tool_trace"]],
        "source_authenticated":False,"source_rights_verified":False,
        "external_sharing_allowed":False,"ai_agent_executed":False,
        "investment_recommendation":False,"trade_executed":False,
        "full_abc_complete":False,"network_requests":0,
    }
    if len(json.dumps(record,ensure_ascii=False,allow_nan=False).encode())>16000:
        return _blocked("OUTPUT_REDaction_LIMIT",calls=local_calls)
    return record


def answer_owner_source_question(
    *,ticker: Any, as_of: Any, question: Any, sources: Any,
    market_json: Any=None,industry_json: Any=None,
    use_local_model: bool=False,consent_local_model: bool=False,
    consent_question_text: bool=False,
) -> dict:
    pre=_preflight(ticker,as_of,question,sources,market_json,industry_json)
    if pre.get("status")!="READY":
        return pre
    if type(use_local_model) is not bool:
        return _blocked("INVALID_LOCAL_MODEL_SWITCH")
    intent=pre["default_intent"]
    calls=0
    protocol=False
    if use_local_model:
        if consent_local_model is not True or consent_question_text is not True:
            return _blocked("TWO_EXPLICIT_LOCAL_MODEL_CONSENTS_REQUIRED")
        try:
            selected=_optional_model_plan(question,ticker,pre["candidate_intents"])
            intent=selected["selected_intent"]
            calls=selected["local_model_calls"]
            protocol=selected["model_protocol_verified"]
        except (ValueError,TypeError,KeyError,OSError,UnicodeError):
            return _blocked("LOCAL_MODEL_NOT_VERIFIED",calls=1)
    try:
        return _execute(ticker,as_of,question,sources,market_json,industry_json,
                        intent,local_calls=calls,protocol=protocol)
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError,
            OverflowError,UnicodeError):
        return _blocked("LOCAL_WORKFLOW_EXECUTION_BLOCKED",calls=calls)


def verify_owner_source_answer(
    packet: Any, *, ticker: Any, as_of: Any, question: Any,
    sources: Any, market_json: Any=None,industry_json: Any=None,
) -> bool:
    """Recompute exact local files; does not claim model provider identity."""
    if (type(packet) is not dict or packet.get("status")!=_STATUS
            or packet.get("local_model_calls") not in (0,1)
            or packet.get("model_protocol_verified") not in (True,False)
            or packet.get("source_rights_verified") is not False):
        return False
    pre=_preflight(ticker,as_of,question,sources,market_json,industry_json)
    if pre.get("status")!="READY":
        return False
    if (packet.get("intent") not in pre["candidate_intents"] or
            (packet["local_model_calls"]==0 and
             (packet["intent"]!=pre["default_intent"] or
              packet["model_protocol_verified"] is not False)) or
            (packet["local_model_calls"]==1 and
             packet["model_protocol_verified"] is not True)):
        return False
    try:
        rebuilt=_execute(ticker,as_of,question,sources,market_json,industry_json,
                         packet["intent"],
                         local_calls=packet["local_model_calls"],
                         protocol=packet["model_protocol_verified"])
        return rebuilt==packet
    except (TypeError,ValueError,KeyError,RecursionError,OverflowError):
        return False
