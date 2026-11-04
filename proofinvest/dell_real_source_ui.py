"""P196 actually verified first-party Dell 10-K evidence in human-only UI."""
from __future__ import annotations


def render_dell_real_source_evidence(st) -> None:
    st.subheader("Dell FY2026 · 실제 발행사 10-K 원본 검증")
    from .dell_2026_publisher_evidence import (
        actual_p195_source_receipt, review_verified_dell_first_party_raw_evidence,
    )
    result = review_verified_dell_first_party_raw_evidence(
        as_of="2026-11-05", receipt=actual_p195_source_receipt())
    if (result.get("status") !=
            "DELL_REAL_FIRST_PARTY_ORIGINAL_NUMERIC_REVIEW_READY_LIMITED"
            or result.get("publisher_https_original_seen") is not True
            or result.get("sec_edgar_original_byte_equivalence_verified") is not False
            or result.get("source_rights_verified") is not False
            or result.get("full_engine_b_authenticated") is not False
            or result.get("guard_policy_preview") != "HOLD"
            or result.get("trade_executed") is not False):
        st.error("실제 발행사 원본의 증거 연결을 검증할 수 없습니다.")
        return
    from .dell_2026_ixbrl_review import observed_ixbrl_receipt, review_observed_real_dell_ixbrl
    actual = review_observed_real_dell_ixbrl(
        as_of="2026-11-05", receipt=observed_ixbrl_receipt())
    if (actual.get("status") != "PUBLISHER_IXBRL_REAL_ANNUAL_REVENUE_CONFIRMED_LIMITED"
            or actual.get("publisher_xbrl_fact_correctly_replayed") is not True
            or actual.get("sec_edgar_original_authenticated") is not False
            or actual.get("source_commercial_rights_verified") is not False
            or actual.get("guard_policy_preview") != "HOLD"
            or actual.get("trade_executed") is not False):
        st.error("발행사 실제 XBRL 회계기간·매출 원본 검증을 확인할 수 없습니다.")
        return
    from .dell_regulator_index_match import reviewed_real_dell_regulator_issuer_evidence
    regulator = reviewed_real_dell_regulator_issuer_evidence()
    if (regulator.get("status") !=
            "INDEPENDENT_SEC_FILING_INDEX_MATCHED_WITH_LIVE_ISSUER_XBRL"
            or regulator.get("independent_regulator_index_metadata_reconciled") is not True
            or regulator.get("issuer_xbrl_fiscal_context_matched") is not True
            or regulator.get("sec_original_bytes_obtained") is not False
            or regulator.get("raw_sec_edgar_original_authenticated") is not False
            or regulator.get("commercial_and_model_processing_rights_proven") is not False
            or regulator.get("guard_policy_preview") != "HOLD"
            or regulator.get("trade_executed") is not False):
        st.error("SEC 색인과 발행사 실제 원본의 종목·기간 대응을 확인하지 못했습니다.")
        return
    r=result["evidence"]
    st.success("공식 Dell 투자자관계 10-K 원본 바이트·재무수치 CI 검증 완료")
    st.markdown(f'[Dell 공식 원문]({r["source_url"]}) / '
                f'[실제 단일 GET 검증 실행 기록]({r["actual_source_ci_run"]})')
    st.caption(
        f'2026년 10-K 원문 {r["raw_original_byte_count"]:,}바이트 · '
        f'SHA-256 {r["raw_original_bytes_sha256"]}'
    )
    a, b, c = st.columns(3)
    a.metric("FY2026 매출 증가율 (실자료)", r["revenue_yoy_pct"] + "%")
    b.metric("영업현금흐름/순이익 (실자료)",
             r["cash_flow_to_net_income_ratio"])
    c.metric("Guard 정책", "HOLD")
    # P199: independent real XBRL context/unit fact extracted by the
    # publisher-only one-shot job. Never assert EDGAR identical bytes or rights.
    proof = actual["evidence"]
    st.subheader("실제 Inline XBRL 원문 컨텍스트 검증")
    st.caption(f'[{proof["xbrl_concept"]}] 실제 2026/2025 원문 태그 · '
               f'[실증 CI 원본 대조]({proof["ci_run"]})')
    st.dataframe([{
        "회계연도": period,
        "연결 매출 (USD 백만)": row["amount_usd_millions"],
        "XBRL 컨텍스트": row["context"],
        "시작": row["period_start"],
        "종료": row["period_end"],
    } for period, row in proof["xbrl_facts"].items()],
        use_container_width=True, hide_index=True)
    st.caption("원본 XBRL에서 직접 확인한 매출 증가율: "
               + proof["annual_revenue_growth_pct"] + "%")
    # P204 SEC public filing INDEX and actual issuer raw/XBRL independent
    # source reconciled; NEVER claim exact SEC raw bytes or provider rights.
    sec = regulator["evidence"]
    st.subheader("SEC 제출 색인 × 발행사 실제 원문 교차 검증")
    st.markdown(f'[SEC 공식 제출 색인]({sec["regulator_index_url"]})')
    st.caption(f'CIK {sec["cik"]} · 접수번호 {sec["accession"]} · '
               f'문서 {sec["form"]} · 회계종료 {sec["report_end"]}')
    st.warning(
        "SEC 공식 색인 메타데이터와 발행사 공시의 CIK·접수번호·기간은 일치합니다. "
        "하지만 원문 바이트 크기가 달라 SEC 원본 동일성은 인증되지 않았으며, "
        "재배포·AI 처리 이용권도 확보되지 않았습니다."
    )
    # P207: optional genuine issuer-source working capital screening.
    # Preserve earlier valid P195/P199/P203 display even if this panel
    # is unavailable or a future independent receipt is rejected.
    from .dell_working_capital_review import (
        actual_working_capital_receipt, review_real_working_capital,
    )
    working = review_real_working_capital(
        reviewed_as_of="2026-11-05", receipt=actual_working_capital_receipt()
    )
    if (working.get("status") == "P207_ACTUAL_ISSUER_WORKING_CAPITAL_REVIEW_LIMITED"
            and working.get("real_issuer_working_capital_source_seen") is True
            and working.get("sec_original_identical") is False
            and working.get("rights_verified") is False
            and working.get("full_engine_b_complete") is False
            and working.get("full_abc_ready") is False
            and working.get("guard_policy_preview") == "HOLD"
            and working.get("trade_executed") is False
            and type(working.get("evidence")) is dict):
        w=working["evidence"]
        st.subheader("실제 매출채권·재고 증가율 vs 매출 — Engine B 제한 검증")
        st.caption(
            f'[Dell 공식 실적발표 원문]({w["source_url"]}) · '
            f'[실제 HTML 단일 GET 검증 기록]({w["actual_one_shot_ci"]})'
        )
        st.dataframe([{
            "FY 원본 항목": name,
            "FY2025 (USD 백만)": row["fy2025_usd_millions"],
            "FY2026 (USD 백만)": row["fy2026_usd_millions"],
            "증가율 (%)": row["growth_pct"],
            "매출 성장 대비 (pp)": row["growth_minus_revenue_pp"],
        } for name,row in w["asset_rows"].items()],
            use_container_width=True,hide_index=True)
        st.caption(f'매출 증가율 원문 비교 기준: {w["revenue_growth_pct"]}%')
        st.warning(
            "이 표는 Dell 발행사 미감사 실적발표 원문의 시점별 자산 수치를 "
            "10-K 매출 증가율과 비교한 검토 신호입니다. 차이만으로 "
            "회계 부정이나 투자 판단을 확정하지 않으며, SEC 원본 바이트 동일성·"
            "상업/AI 이용권·NDX 및 동종기업 자료는 미검증입니다. Guard HOLD."
        )
    else:
        st.warning("매출채권·재고 실원문 비교 검증 불가: 신규 Engine B 지표를 표시하지 않습니다.")
    st.warning(
        "이 검증은 발행사 공식 HTTPS 원본과 원문 내 실제 수치 확인입니다. "
        "SEC EDGAR 원본과의 동일 바이트 인증, 데이터 이용권, NDX 및 "
        "동종업계 동일 기간 비교는 미완료입니다. 투자 판단이 아닙니다."
    )
