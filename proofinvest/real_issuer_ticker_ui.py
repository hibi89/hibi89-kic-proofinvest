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
    # P229: issuer-bound license/entitlement gap inspection, user-clicked
    # without vendor credentials, data fetch, paid operation or rights grant.
    from .real_issuer_ndx_license_gap import render_issuer_ndx_license_gap_panel
    render_issuer_ndx_license_gap_panel(st, ticker=result["ticker"])
    if result["ticker"] == "NVDA":
        # P222: independent audited AMD filing + press-release arithmetic
        # crosscheck; intentionally separate from licensed/full Engine C.
        from .amd_10k_peer_bridge import compare_nvda_amd_audited_10k_peer
        peer = compare_nvda_amd_audited_10k_peer(ticker=result["ticker"])
        if peer["status"] == "ONE_REAL_AUDITED_10K_PEER_CROSSCHECK_ONLY":
            st.subheader("Engine C · AMD 공식 10-K 감사 재무 교차검산 (단일 동종기업)")
            st.markdown(
                f'[AMD 2025 10-K]({peer["amd_audited_10k_filing"]}) · '
                f'[AMD 공식 연간 실적발표]({peer["amd_press_release"]})'
            )
            st.caption("AMD FY2025와 NVIDIA FY2026 결산일 차이 29일 · "
                       "단일 비교기업이며 사업구성·이용권·완전한 Engine C는 미검증")
            peer_left, peer_right = st.columns(2)
            peer_left.metric("AMD 매출 증가율 (공식 10-K·발표 검산)",
                             peer["amd_revenue_growth_pct"] + "%")
            peer_right.metric("NVDA-AMD 연매출 성장률 관측 차이 (pp)",
                              peer["observed_growth_gap_pp_not_sector_rank"])
            st.metric("AMD FY2025 GAAP 순이익률 (%)",
                      peer["amd_gaap_net_margin_2025_pct"])
            st.download_button(
                "AMD 10-K 교차검산 개인용 JSON (이용권 미인증)",
                data=json.dumps(peer, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False).encode("utf-8"),
                file_name="kuodra-nvda-amd-audited-peer-UNVERIFIED.json",
                mime="application/json",
                key="p222_audited_peer_export",
            )
            st.warning("공식 자료 수치의 수동 교차검산일 뿐, AMD 10-K 원본 바이트·"
                       "라이선스·동종기업 대표성·시장 데이터는 인증되지 않았습니다. "
                       "Engine C 전체 완료 아님 · Guard HOLD.")
        else:
            st.warning("AMD 독립 10-K/실적발표 교차검산이 실패하여 "
                       "동종기업 비교를 표시하지 않습니다.")
    if result["ticker"] == "NVDA":
        from .intel_amd_peer_cohort import review_two_official_10k_peers
        cohort = review_two_official_10k_peers(ticker=result["ticker"])
        if cohort["status"] == "TWO_DISTINCT_AUDITED_PEER_REFERENCES_LIMITED":
            st.subheader("Engine C · NVIDIA / AMD / Intel 3개사 원문 비교 (제한)")
            st.caption("AMD 및 Intel 2025 감사 10-K와 각각 독립 실적발표 자료 교차검산. "
                       "NVDA 결산일과 각 29일 차이. Intel Altera 연결 제외 효과, "
                       "기업별 사업구성 차이로 산업 대표성·동일 회계비교·예측 불가.")
            st.dataframe([
                {"기업": item["ticker"], "결산일": item["fy_latest"],
                 "연매출 성장률 관측 (%)": item["revenue_growth_pct"]}
                for item in cohort["revenue_growth_observations_not_sector_rank"]
            ], hide_index=True, use_container_width=True)
            st.markdown(
                f'[Intel 감사 10-K]({cohort["intel_audited_10k_url"]}) · '
                f'[Intel 독립 실적발표]({cohort["intel_separate_release_url"]})'
            )
            st.metric("Intel 2025 GAAP 매출총이익률 (%)",
                      cohort["intel_2025_gross_margin_pct"])
            st.download_button(
                "NVDA·AMD·INTC 2개 동종기업 교차검산 JSON (제한)",
                data=json.dumps(cohort, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False).encode("utf-8"),
                file_name="kuodra-nvda-two-official-peers-UNVERIFIED.json",
                mime="application/json", key="p223_two_peer_cohort_export",
            )
            st.warning("2개사 10-K 공개 숫자의 별도 수동 대조일 뿐 외부 공급자 원본 "
                       "바이트 SHA·재사용권·정확한 대표성·Engine C 완료 아님. Guard HOLD.")
            # P227: independent issuer-10-K AMD Data Center business-segment
            # trend, separate from total-company growth and unlicensed full C.
            from .amd_datacenter_segment_bridge import review_amd_datacenter_segment
            dc = review_amd_datacenter_segment(ticker=result["ticker"])
            if dc["status"] == "AMD_DATACENTER_ACTUAL_10K_SEGMENT_HUMAN_REVIEW_ONLY":
                st.subheader("Engine C · AMD 데이터센터 부문 실제 10-K 변화 (제한)")
                st.caption(
                    "AMD의 2025/2024 데이터센터 부문 GAAP 수치만 독립 검산. "
                    "NVIDIA 전체 매출과 동질 비교하거나 업종 순위·전망을 내릴 수 없습니다. "
                    "NVDA 결산일 29일 차이, 원문 SHA·이용권·모델 처리권 미확인."
                )
                left, right = st.columns(2)
                left.metric("AMD 데이터센터 FY2025 성장률 (%)",
                            dc["segment_growth_pct"])
                right.metric("AMD 전체 매출 중 데이터센터 비중 (%)",
                             dc["segment_share_of_amd_revenue_2025_pct"])
                st.metric("데이터센터 비중 전년 대비 변화 (pp)",
                          dc["segment_share_change_pp"])
                st.markdown(
                    f'[AMD 감사 10-K]({dc["amd_10k_url"]}) · '
                    f'[AMD 독립 실적발표]({dc["amd_independent_release_url"]})'
                )
                st.download_button(
                    "AMD 데이터센터 실제 10-K 수치 검산 JSON (개인 검토)",
                    data=json.dumps(dc, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8"),
                    file_name="kuodra-amd-data-center-source-UNVERIFIED.json",
                    mime="application/json", key="p227_amd_datacenter_export",
                )
                st.warning("사업부·기업 간 직접 비교 불가 · Engine C 미완료 · Guard HOLD.")
            else:
                st.warning("AMD 데이터센터 원문 수치 검산이 실패하여 부문 비교를 표시하지 않습니다.")

            # P228: cross-replayed AMD audited operating-profit history
            # distinct from P227 segment mix and P222 total revenue trend.
            from .amd_operating_profit_review import review_amd_operating_profit
            op = review_amd_operating_profit(ticker=result["ticker"])
            if op["status"] == "AMD_AUDITED_OPERATING_MARGIN_HUMAN_ONLY":
                st.subheader("Engine C · AMD 영업이익률 원문 2개 연도 검산 (제한)")
                st.caption(
                    "AMD 감사 10-K 및 독립 실적발표 GAAP 영업이익·매출만 검산. "
                    "2025년 MI308 수출통제 관련 재고비용 효과 미조정. "
                    "NVIDIA 전체기업과 직접 비교·투자 예측 불가, 결산일 29일 차이. "
                    "원문 SHA·사용권 미검증, Guard HOLD."
                )
                op_left, op_right = st.columns(2)
                op_left.metric("AMD FY2025 GAAP 영업이익률 (%)",
                               op["operating_margin_2025_pct"])
                op_right.metric("AMD FY2024 GAAP 영업이익률 (%)",
                                op["operating_margin_2024_pct"])
                st.metric("AMD GAAP 영업이익률 변화 (pp)",
                          op["operating_margin_change_pp"])
                st.markdown(
                    f'[AMD 2025 감사 10-K]({op["amd_10k_url"]}) · '
                    f'[AMD 독립 실적발표]({op["amd_release_url"]})'
                )
                st.download_button(
                    "AMD 감사 영업이익률 검산 JSON (원본·시장 데이터 제외)",
                    data=json.dumps(op, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8"),
                    file_name="kuodra-amd-operating-margin-UNVERIFIED.json",
                    mime="application/json", key="p228_amd_gaap_op_export",
                )
                st.warning("순이익률·매출총이익률과 구분. 시장/AI/라이선스 인증 안 됨 · Engine C 미완료.")
            else:
                st.warning("AMD 감사 영업이익률 재검산 실패: 미인증 결과를 숨깁니다.")

        else:
            st.warning("두 동종기업의 공식 10-K 검산이 실패해 종합 비교를 표시하지 않습니다.")
    # P219: independent model-data calculation only when the operator
    # explicitly supplies locally held market responses. No provider GET.
    from .real_issuer_local_market import render_real_issuer_local_market_panel
    render_real_issuer_local_market_panel(st, ticker=result["ticker"])
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
