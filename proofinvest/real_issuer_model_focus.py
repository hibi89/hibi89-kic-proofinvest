"""P226: local-model review *focus* from actual source-bound issuer A/B/C.

Only three authored evidence-availability enum codes may be sent to a
user-controlled 127.0.0.1 endpoint after two explicit consents and one click.
NO actual company facts, ticker, metric, hashes, source links, raw JSON or
personal evidence enter the model prompt. This is not verified financial
reasoning, permission to use market data, or real model authentication.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .real_issuer_abc_local_review import replay_partial_source_bound_abc
from .real_issuer_abc_fact_review import replay_source_factual_abc_brief
from .ticker_local_model_triage import (
    _call_loopback, _json_no_duplicate, _FOCUS_SCHEMA,
)

_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z", re.ASCII)
_STATUS = "LOCAL_REAL_ISSUER_MODEL_FOCUS_PROTOCOL_ONLY"
_MAX_BYTES = 2048
_TYPES = ("A", "B", "C")


def _blocked(reason: str, *, calls: int = 0) -> dict[str, Any]:
    return {
        "schema": "kuodra.p226-real-issuer-status-only-loopback.v1",
        "status": "BLOCKED", "reason_code": reason,
        "loopback_http_attempts": calls, "external_network_requests": 0,
        "model_protocol_http_verified": False,
        "model_inference_authenticated": False,
        "financial_llm_inference_verified": False,
        "data_model_rights_verified": False, "market_rights_verified": False,
        "source_rights_verified": False, "external_sharing_allowed": False,
        "ai_agent_executed": False, "guard_policy_preview": "HOLD",
        "human_approved": False, "investment_recommendation": False,
        "trade_executed": False,
    }


def _safe_statuses(abc: Any, brief: Any) -> dict[str, str] | None:
    if (type(abc) is not dict or type(brief) is not dict
            or not replay_partial_source_bound_abc(abc)
            or not replay_source_factual_abc_brief(brief, abc)
            or brief.get("guard_policy_preview") != "HOLD"
            or abc.get("guard_policy_preview") != "HOLD"
            or brief.get("external_sharing_allowed") is not False
            or brief.get("llm_invoked") is not False
            or brief.get("source_rights_verified") is not False
            or brief.get("market_rights_verified") is not False
            or abc.get("ai_agent_executed") is not False
            or abc.get("full_abc_complete") is not False):
        return None
    claims = brief.get("claims")
    if (type(claims) is not list or len(claims) != 5
            or [x.get("engine") for x in claims if type(x) is dict]
               != ["A", "B", "B", "C", "C"]
            or claims[0].get("verification") !=
               "UNAVAILABLE_PROVIDER_ORIGIN_AND_RIGHTS"
            or any(x.get("verification") !=
                   "VERIFIED_HISTORICAL_NUMERIC_MATCH_ONLY" for x in claims[1:3])
            or any(x.get("verification") !=
                   "PUBLIC_TEXT_NUMERIC_MATCH_RAW_UNVERIFIED" for x in claims[3:])):
        return None
    return {"A":"UNAVAILABLE","B":"HISTORICAL_NUMBER_ONLY",
            "C":"HISTORICAL_NUMBER_ONLY"}


def review_real_issuer_model_focus(
    abc: Any, brief: Any, *, model: Any = "llama3.2",
    port: Any = 11434, allow_local_model: bool = False,
    confirm_only_status_codes: bool = False,
) -> dict[str, Any]:
    """One redacted local HTTP intent; unavailable A must remain first focus."""
    if allow_local_model is not True or confirm_only_status_codes is not True:
        return _blocked("TWO_EXPLICIT_CONSENTS_REQUIRED")
    if (type(model) is not str or _MODEL.fullmatch(model) is None
            or type(port) is not int or not 1024 <= port <= 65535):
        return _blocked("MODEL_OR_PORT_INVALID")
    try:
        statuses = _safe_statuses(abc,brief)
        if statuses is None:
            return _blocked("SOURCE_OR_REVIEW_REPLAY_INVALID")
        # Absolute allowlist; never interpolate source text or filenames into
        # a local-model prompt. Even a loopback server might proxy outward.
        prompt = (
            "Classify which unverified evidence dimension a human should "
            "inspect first; this is NOT financial reasoning. "
            "Review focus policy: if A is UNAVAILABLE choose A; else "
            "choose earliest unavailable engine. "
            "Return ONLY JSON {\"focus_engine\":\"A\","
            "\"decision\":\"HUMAN_REVIEW_ONLY\"}. "
            "Evidence status enums only: " + json.dumps(
                statuses,sort_keys=True,separators=(",",":"))
        )
        raw = json.dumps({
            "model":model,"prompt":prompt,"stream":False,
            "format":_FOCUS_SCHEMA,
            "options":{"temperature":0,"num_predict":128},
        },ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        if not 0 < len(raw) <= _MAX_BYTES:
            return _blocked("MODEL_REQUEST_TOO_LARGE")
    except (TypeError,ValueError,KeyError,OverflowError,RecursionError):
        return _blocked("PRE_MODEL_VALIDATION_FAILED")
    try:
        reply = _json_no_duplicate(_call_loopback(raw,port=port))
        if (type(reply) is not dict or reply.get("done") is not True
                or reply.get("model") != model
                or type(reply.get("response")) is not str
                or not 0 < len(reply["response"]) <= 512):
            return _blocked("INVALID_MODEL_ENVELOPE",calls=1)
        parsed=_json_no_duplicate(reply["response"].encode("utf-8"))
        if (type(parsed) is not dict or set(parsed) !=
                {"focus_engine","decision"}
                or parsed.get("focus_engine") != "A"
                or parsed.get("decision") != "HUMAN_REVIEW_ONLY"):
            return _blocked("MODEL_OUTPUT_POLICY_MISMATCH",calls=1)
        return {
            **_blocked("VALIDATED_STATUS_ONLY_HUMAN_FOCUS",calls=1),
            "status":_STATUS, "focus_engine":"A",
            "focus_status":"UNAVAILABLE",
            "model_protocol_http_verified":True,
            "model_output_schema_validated":True,
            "human_review_priority_policy_verified":True,
            "safe_existing_interpretation":(
                "A: 주가 및 Nasdaq-100 데이터 제공자·사용권 검증이 "
                "없으므로 시장 분석을 보류하고 사람의 출처 확인을 우선합니다."
            ),
        }
    except (UnicodeError,TypeError,ValueError,KeyError,OverflowError,
            RecursionError, OSError):
        return _blocked("LOCAL_MODEL_PROTOCOL_REJECTED",calls=1)


def render_real_issuer_model_focus_panel(st, abc: Any, brief: Any) -> None:
    """No network without expansion, two consents and explicit button click."""
    st.subheader("실제 발행사 A/B/C · 로컬 AI 검토 우선순위 (기본 차단)")
    st.caption(
        "실제 재무 수치·회사명·원문·SHA·파일 내용은 모델에 주지 않습니다. "
        "검증되지 않은 A/B/C 상태 3개만 로컬 서버에 전달합니다. "
        "127.0.0.1 서버가 원격 프록시가 아닌지 사용자가 확인해야 합니다."
    )
    if not st.checkbox(
        "실제 발행사 로컬 모델 선택기 열기 (기본 비활성)",
        value=False,key="p226_model_expander",
    ):
        return
    model=st.text_input("본인 설치 로컬 모델 이름",value="llama3.2",
                        max_chars=64,key="p226_model_name")
    port=st.text_input("본인 로컬 모델 포트 (1024~65535)",value="11434",
                       max_chars=5,key="p226_model_port")
    c1=st.checkbox(
        "127.0.0.1 서버가 본인 관리 로컬 AI이며 외부 중계하지 않음을 확인",
        value=False,key="p226_local_consent",
    )
    c2=st.checkbox(
        "원본이나 수치가 아닌 A/B/C 상태 세 개만 전달하는 데 별도 동의",
        value=False,key="p226_status_consent",
    )
    if not st.button(
        "실제 발행사 A/B/C 로컬 모델 검토 우선순위 요청 (1회)",
        key="p226_model_call",disabled=not(c1 and c2),
    ):
        return
    if not(c1 and c2) or type(port) is not str or not port.isdecimal():
        st.warning("동의 또는 로컬 모델 포트가 유효하지 않습니다.")
        return
    outcome=review_real_issuer_model_focus(
        abc,brief,model=model,port=int(port),
        allow_local_model=c1,confirm_only_status_codes=c2,
    )
    if outcome["status"] != _STATUS:
        st.warning("모델 응답·로컬 연결·증거 검증이 실패해 결과를 차단했습니다.")
        st.code(outcome["reason_code"])
        return
    st.success("상태코드 전용 로컬 모델 프로토콜 검증 (실제 추론품질 미인증)")
    st.info(outcome["safe_existing_interpretation"])
    st.json({
        "focus_engine":outcome["focus_engine"],
        "protocol_verified":True, "model_inference_authenticated":False,
        "financial_llm_inference_verified":False,
        "source_rights_verified":False,
        "guard_policy_preview":"HOLD", "trade_executed":False,
    })
