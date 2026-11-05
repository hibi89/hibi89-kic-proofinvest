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
         "결과": report["engine_b"]["cfo_to_net_income_ratio"]},
        {"항목": "매출채권 증가율 격차 (pp)",
         "결과": report["engine_b"]["receivables_minus_revenue_growth_pp"]},
        {"항목": "재고 증가율 격차 (pp)",
         "결과": report["engine_b"]["inventory_minus_revenue_growth_pp"]},
        {"항목": "경쟁사 참고 (C)", "결과": report["engine_c"]["status"]},
        {"항목": "Guard", "결과": report["guard"]["decision"]},
    ])
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
