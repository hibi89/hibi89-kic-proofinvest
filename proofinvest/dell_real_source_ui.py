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
    st.warning(
        "이 검증은 발행사 공식 HTTPS 원본과 원문 내 실제 수치 확인입니다. "
        "SEC EDGAR 원본과의 동일 바이트 인증, 데이터 이용권, NDX 및 "
        "동종업계 동일 기간 비교는 미완료입니다. 투자 판단이 아닙니다."
    )
