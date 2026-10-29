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

    if submitted:
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

    st.divider()
    st.subheader("모의 LLM 제안 → 사전 검증 → 로컬 실행")
    st.warning(
        "MOCK_MODEL_RESPONSE · 실제 Gemini API 또는 LLM 추론은 실행하지 않습니다. "
        "모의 모델 출력과 원래 질문을 독립 비교하고, 일치할 때만 "
        "기존 오프라인 검산을 허용합니다."
    )
    proposal_choices = {
        "일치 제안: GROWTH_CHECK": {"action": "RUN", "intent": "GROWTH_CHECK"},
        "불일치 제안: SOURCE_REVIEW": {"action": "RUN", "intent": "SOURCE_REVIEW"},
        "모델 재질문: ASK": {"action": "ASK", "intent": None},
        "비허용 도구: run_shell": {"action": "RUN", "intent": "run_shell"},
    }
    with st.form("intent_mock_llm_form", clear_on_submit=False):
        proposal_label = st.selectbox(
            "모의 모델 응답", list(proposal_choices), key="intent_mock_proposal"
        )
        run_mock = st.form_submit_button(
            "모의 LLM 제안 검증", key="intent_mock_run"
        )
    if not run_mock:
        st.caption(
            "안전 게이트는 모델이 제안한 함수·파라미터를 직접 실행하지 않습니다. "
            "외부 네트워크 호출과 데이터베이스 저장 모두 0회."
        )
        return

    from .llm_proposal_gate import evaluate_model_proposal

    checked = evaluate_model_proposal(
        question, proposal_choices[proposal_label], llm_attempted=False,
    )
    if checked["model_proposal_accepted"]:
        disposition = "ACCEPTED"
        st.success(
            "도구 제안 일치 — 기존 로컬 검산 실행 완료. "
            "Guard의 REJECT는 재무 주장을 차단한 정상 판정입니다."
        )
    elif checked["status"] == "needs_clarification":
        disposition = "ASK"
        st.warning("모의 모델이 재질문을 요청해 도구를 실행하지 않았습니다.")
    else:
        disposition = "BLOCKED"
        st.error(
            "모델 제안이 안전 검증을 통과하지 못했습니다. "
            "재무 원자료 및 Guard 도구 호출을 차단했습니다."
        )
    st.metric("모의 제안 게이트", disposition)
    st.caption("게이트 결과 코드: " + checked["reason_code"])
    if checked["selected_intent"]:
        st.metric("게이트가 허용한 경로", checked["selected_intent"])
    local = checked["local_result"]
    if local is not None:
        st.caption("실행된 오프라인 도구: " + ", ".join(local["tool_calls"]))
        if local["guard"]:
            st.metric("모의 제안 경로 Guard", local["guard"]["decision"])
        st.json({
            "selected_intent": local["selected_intent"],
            "guard_decision": (
                local["guard"]["decision"] if local["guard"] else None
            ),
            "reason_code": local["reason_code"],
            "evidence": local["evidence"],
        })
    else:
        st.caption("로컬 도구 실행 0회 · 추출 데이터 없음")
    st.caption(
        "모의 응답 검증일 뿐 실제 모델 추론이 아닙니다. "
        "SEC 외부 조회·LLM API·투자 주문·영구 감사 기록 저장 없음."
    )
