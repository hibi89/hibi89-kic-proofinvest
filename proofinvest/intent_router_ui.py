"""Streamlit presentation of the deterministic offline question router.

This is intentionally separate from human-review persistence. The router
does not write SQLite, initiate network calls, or authorize investments.
"""
from __future__ import annotations

from .intent_router import route_question


def render_router(st) -> None:
    st.title("ProofInvest — 질문별 로컬 도구 선택")
    st.warning(
        "RULE_BASED_OFFLINE_NOT_LLM · 한국어/영어 키워드 기반 시연입니다. "
        "자율 LLM Planner, 실제 SEC API 자동 수집, 원문 인증, 실거래 기능이 아닙니다."
    )
    st.caption(
        "예시: Apple 2025 매출 성장률 20% 검산 / "
        "Apple 공시 원문 근거 / Apple 부채비율 위험 진단"
    )
    with st.form("intent_router_form", clear_on_submit=False):
        question = st.text_area(
            "검토 질문 (240자 이내)",
            value="Apple 2025 매출 성장률 20% 검산",
            max_chars=240,
            key="intent_router_question",
        )
        submitted = st.form_submit_button("로컬 도구 선택·검증", key="intent_router_run")
    if not submitted:
        st.info("명시적으로 실행할 때까지 도구 호출·감사 기록 저장 없음.")
        return

    result = route_question(question)
    st.subheader("PLAN → SELECT → EXECUTE → GUARD → REPORT")
    st.metric("라우팅 상태", result["status"])
    if result["selected_intent"]:
        st.metric("선택한 경로", result["selected_intent"])
        st.caption("실행된 로컬 도구: " + ", ".join(result["tool_calls"]))
    if result["guard"]:
        st.metric("Guard 판정 (모의)", result["guard"]["decision"])
        st.json({"reason_codes": result["guard"]["reason_codes"],
                 "trade_executed": False})
    if result["question_to_user"]:
        st.warning(result["question_to_user"])
    elif result["status"] == "blocked":
        st.error("요청을 차단했습니다: " + result["reason_code"])
    else:
        st.info("처리 결과: " + result["reason_code"])

    st.dataframe(result["trace"], use_container_width=True, hide_index=True)
    if result["evidence"] is not None:
        st.json(result["evidence"])
    st.caption(
        "수동 발췌/로컬 데이터 · 외부 출처 진위 인증 없음 · "
        "외부 HTTP/LLM 0회 · 승인/실거래 0회 · "
        "규칙 기반 도구 선택은 LLM Planner 구현을 의미하지 않습니다."
    )
