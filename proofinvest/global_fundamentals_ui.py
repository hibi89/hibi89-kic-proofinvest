"""Local-only global US issuer B/C review; no Nasdaq input or network."""
from __future__ import annotations
import json
from .kuodra_local_workspace_ui import local_workspace_enabled
from .global_fundamentals_review import (
    build_marketless_global_review,
    verify_marketless_global_review,
    marketless_global_review_html,
)

def render_global_fundamentals(st) -> None:
    if not local_workspace_enabled(st):
        return
    st.subheader("KUODRA · 글로벌 기업 재무·경쟁사 검증 (나스닥 없이)")
    st.caption("NVIDIA·Dell 발행사 원본 검증 이력과 기존 오프라인 분석을 재계산합니다. "
               "실시간 SEC/시세 API 호출, 외부 LLM, 거래는 실행하지 않습니다.")
    st.warning("시장지수 Engine A는 자료 미확보로 UNAVAILABLE. "
               "발행사 SEC 원본 동일성·동종기업 원문 바이트·대회 공개 시연 이용권은 "
               "미확인입니다. 개별 권한 확인 전 외부 공유 불가.")
    with st.form("kuodra_global_marketless_review"):
        ticker = st.selectbox("미국 발행사", ["NVDA", "DELL"])
        confirmed = st.form_submit_button("발행사·경쟁사 검산 및 Guard")
    st.subheader("질문 → 근거 분석 → Guard 답변 (로컬)")
    st.caption("예: NVDA 재고가 매출보다 빨리 증가했나요? / DELL 영업현금흐름은? "
               "기본 모드는 규칙 기반입니다. 실제 자율 AI Agent로 표기하지 않습니다.")
    with st.form("kuodra_global_question"):
        question=st.text_input(
            "투자 검증 질문", value="NVDA 재고가 매출보다 빠르게 증가했나요?",
            max_chars=180, key="kic_global_question")
        with_model=st.checkbox(
            "선택: 본인 로컬 Qwen2.5 1.5B 의도 검증 (기본 비활성)",
            value=False,key="kic_global_model_toggle")
        c1=st.checkbox(
            "127.0.0.1:11435 서버가 본인 관리 로컬 모델이고 외부 중계가 아님을 확인",
            value=False,key="kic_global_model_owner")
        c2=st.checkbox(
            "입력한 질문 문구만 로컬 모델에 전달하는 데 별도 동의 (공시·숫자 전송 없음)",
            value=False,key="kic_global_question_consent")
        asked=st.form_submit_button("질문 근거 검증 → Guard 답변")
    if asked:
        from .global_question_agent import (
            answer_global_question, verify_global_question_answer)
        answer=answer_global_question(
            question, use_local_model=with_model,
            consent_local_model=c1,consent_question_text=c2)
        if (answer.get("status") != "QUESTION_SOURCE_BOUND_LOCAL_REVIEW_HOLD"
                or not verify_global_question_answer(answer,question)):
            st.warning("요청한 기업·기간·의도 또는 로컬 모델 검증 실패. "
                       "NVDA/DELL의 단일 분석 질문만 허용합니다.")
            st.code(answer.get("reason_code","UNVERIFIED"))
        else:
            st.success("질문 근거 분석 완료 · Guard HOLD · 투자 승인 아님")
            st.info(answer["answer"])
            st.caption("실행 도구: " + answer["intent"] +
                       " · 실제 AI Agent 완료 아님 · 데이터 이용권 미인증")
            st.json({
                "source_refs":answer["source_links"],
                "question_sha256":answer["question_sha256"],
                "tool_trace":answer["tool_trace"],
                "local_model_calls":answer["local_model_calls"],
                "local_model_protocol_verified":
                    answer["local_model_protocol_verified"],
                "source_replay_verified":True,
                "trade_executed":False, "guard":"HOLD",
            })
    if not confirmed:
        return
    report = build_marketless_global_review(ticker=ticker)
    if not verify_marketless_global_review(report):
        st.error("출처·수치·Guard 재검산에 실패했습니다.")
        return
    st.table([
        {"항목": "기업", "결과": report["ticker"]},
        {"항목": "시장 분석 (A)", "결과": report["engine_a"]["status"]},
        {"항목": "매출 증가율 (%) (B)",
         "결과": report["engine_b"]["revenue_growth_pct"]},
        {"항목": "영업현금흐름 / 순이익 (B)",
         "결과": report["engine_b"]["cashflow_to_net_income_ratio"]},
        {"항목": "매출채권 증가율 격차 (pp)",
         "결과": report["engine_b"]["receivables_minus_revenue_growth_pp"]},
        {"항목": "재고 증가율 격차 (pp)",
         "결과": report["engine_b"]["inventory_minus_revenue_growth_pp"]},
        {"항목": "경쟁사 참고 (C)", "결과": report["engine_c"]["status"]},
        {"항목": "Guard", "결과": report["guard"]["decision"]},
    ])
    st.subheader("Engine B · 회계 괴리 검토 후보 (부정 확정 아님)")
    signals = report["engine_b"]["screening_signals"]
    if signals:
        st.table([{"항목": signal["code"],
                   "매출 성장률 대비 격차 (pp)": signal["growth_gap_pp"],
                   "검토 기준 (pp)": signal["threshold_pp"]}
                  for signal in signals])
        st.warning("매출 증가율보다 재고·매출채권 증가율이 크게 높다는 "
                   "탐색용 표시입니다. 산업·사업부·연결범위·회계정책 확인 전 "
                   "회계부정이나 투자 판단을 내릴 수 없습니다.")
    else:
        st.info("이 단일연도 탐색 임계값을 넘는 항목이 없습니다. "
                "정상·안전한 투자라는 뜻은 아닙니다.")
    if report["engine_c"]["peers"]:
        st.table([{"기업": p["ticker"], "기간": p["fiscal_latest_end"],
                   "매출 증가율 (%)": p["revenue_growth_pct"],
                   "원본 SHA 확인": False}
                  for p in report["engine_c"]["peers"]])
    st.json({"source": report["source"], "trace": report["trace"],
             "guard": report["guard"], "limitations": report["limitations"],
             "market_api_requests": 0, "source_rights_verified": False,
             "external_sharing_allowed": False, "ai_agent_executed": False})
    st.download_button(
        "개인 검토용 근거 JSON", data=(json.dumps(
            report, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False)+"\n").encode("utf-8"),
        file_name="KUODRA_GLOBAL_BC_HOLD_UNVERIFIED.json",
        mime="application/json", key="global_marketless_json",
        on_click="ignore")
    st.download_button(
        "개인 검토용 근거 HTML", data=marketless_global_review_html(report),
        file_name="KUODRA_GLOBAL_BC_HOLD_UNVERIFIED.html",
        mime="text/html", key="global_marketless_html",
        on_click="ignore")
