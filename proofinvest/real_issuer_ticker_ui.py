"""Read-only native single-ticker review from two genuinely observed issuers.

Works offline without operator uploads; supports only NVIDIA and Dell pinned
first-party historical receipts. No claims of live SEC or stock data.
"""
from __future__ import annotations

import json

from .real_issuer_ticker_review import review_supported_real_ticker


def render_real_issuer_ticker_lookup(st) -> None:
    from .kuodra_local_workspace_ui import local_workspace_enabled
    if not local_workspace_enabled(st):
        st.warning("이 발행사 원문 검산 경로는 명시적 로컬 실행에서만 사용할 수 있습니다.")
        return
    st.title("KUODRA · 종목 입력 → 실제 발행사 제한 재무검토")
    st.warning(
        "현재 원문 검증 기록이 있는 종목은 NVDA와 DELL 두 개뿐입니다. "
        "실시간 SEC 검색·주가·Nasdaq-100·동종기업 분석은 제공되지 않습니다."
    )
    ticker = st.text_input(
        "미국 종목코드 입력 (NVDA 또는 DELL)",
        value="", max_chars=12, key="p218_real_issuer_input",
    )
    if not ticker.strip():
        st.info("검토할 종목코드를 입력하면 발행사 원문 검증 기록을 조회합니다.")
        return
    result = review_supported_real_ticker(ticker, as_of="2026-11-05")
    if result["status"] != "REAL_ISSUER_HUMAN_REVIEW_ONLY":
        st.warning("실제 발행사 검증 기록이 없거나 기간·원문 계약이 일치하지 않습니다.")
        st.code(result["reason_code"], language="text")
        return
    st.success(result["ticker"] + " · 실제 발행사 수치 독립 검산 (이용권/SEC 미인증)")
    st.caption(
        "원문 수집 및 수치 검증 당시의 고정 기록을 재검토합니다. "
        "현재 시세나 새 공시를 조회하지 않습니다."
    )
    st.markdown(
        f'[공식 발행사 자료]({result["source_url"]}) · '
        f'[원문 수집·검증 CI]({result["source_ci_run"]})'
    )
    if result.get("sec_index_metadata_reconciled") is True:
        st.markdown(
            f'[SEC 제출 색인 (원문 바이트 인증 아님)]({result["sec_index_url"]}) '
            f'· CIK {result["cik"]} · 접수 {result["filing_accession"]}'
        )
    if result.get("supplementary_source_url"):
        st.markdown(
            f'[추가 실적발표 원문]({result["supplementary_source_url"]}) · '
            f'[독립 검증 CI]({result["supplementary_source_ci_run"]})'
        )
    st.caption(
        "비교 연도: " + result["fiscal_prior_end"] + " → " +
        result["fiscal_latest_end"] + " · 원문 SHA-256 " + result["source_sha256"]
    )
    a, b, c = st.columns(3)
    a.metric("연매출 성장률 (발행사 근거)", result["issuer_revenue_growth_pct"] + "%")
    b.metric("영업현금/순이익 (로컬 재검산)", result["cashflow_to_net_income_ratio"])
    c.metric("Guard 정책 (실행 아님)", result["guard_policy_preview"])
    st.subheader("Engine B · 매출 대비 운전자본 증가율 차이")
    st.dataframe([
        {"항목": "매출채권 증가율 - 매출 증가율 (pp)",
         "관측": result["receivables_minus_revenue_growth_pp"]},
        {"항목": "재고 증가율 - 매출 증가율 (pp)",
         "관측": result["inventory_minus_revenue_growth_pp"]},
    ], hide_index=True, use_container_width=True)
    st.subheader("Engine A / Engine C · 데이터 상태")
    st.json({
        "market": result["market_price_status"],
        "nasdaq_100": result["ndx_benchmark_status"],
        "peer_evidence": result["peer_evidence_status"],
        "engine_a_complete": False,
        "engine_c_complete": False,
        "full_abc_complete": False,
    })
    st.warning(
        "발행사 홈페이지 원본 확인은 SEC EDGAR 원본 바이트 인증과 다릅니다. "
        "데이터 이용권·모델 처리권·진짜 주가/지수/동종기업 공급자는 미확인입니다. "
        "회계부정 확정·투자 추천·매매 허가는 제공하지 않습니다. Guard HOLD."
    )
    st.download_button(
        "현재 종목 원본 해시·수치 검토 JSON (본인 로컬 검토만)",
        data=json.dumps(result, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"), allow_nan=False).encode("utf-8"),
        file_name="kuodra-" + result["ticker"].lower() + "-real-source-UNVERIFIED.json",
        mime="application/json", key="p218_real_issuer_export",
    )
