"""P194 human-only public first-party FY2026 comparisons, never a peer license."""
from __future__ import annotations


def render_public_fy2026_reference_peers(st) -> None:
    st.subheader("2026년 공개 실적 참고 비교 · Apple / Microsoft / Dell")
    st.caption(
        "세 기업의 실제 FY2026·FY2025 연결 연매출 참고치 (USD 백만). "
        "FY2026 회계 종료일이 다르고, 회사의 제품·사업구조도 다릅니다."
    )
    from .apple_public_peer_reality import (
        public_primary_revenue_values, review_public_fiscal_peers,
    )
    result = review_public_fiscal_peers(
        as_of="2026-11-05",
        revenue_values=public_primary_revenue_values(),
    )
    if (result.get("status") !=
            "INDICATIVE_REAL_PRIMARY_PUBLIC_YOY_FISCAL_REVENUE_ONLY"
            or result.get("reference_count") != 3
            or result.get("fiscal_cutoffs_differ") is not True
            or result.get("business_models_differ") is not True
            or result.get("aligned_fiscal_periods_verified") is not False
            or result.get("same_sector_comparability_verified") is not False
            or result.get("provider_peer_license_verified") is not False
            or result.get("guard_policy_preview") != "HOLD"
            or result.get("trade_executed") is not False):
        st.error("실제 매출 비교의 출처·기간 계약이 맞지 않아 표시하지 않습니다.")
        return
    st.warning(
        "회계연도 종료일과 매출 구성이 다르므로 성장률을 단순 순위화하거나 "
        "동일 업종 대비 우위·거품·투자 결론으로 연결할 수 없습니다."
    )
    st.dataframe([
        {
            "기업": row["ticker"],
            "FY2026 종료": row["fy2026_end"],
            "FY2025 종료": row["fy2025_end"],
            "FY2026 매출 (USD 백만)": row["fy2026_revenue_usd_millions"],
            "FY2025 매출 (USD 백만)": row["fy2025_revenue_usd_millions"],
            "자체 전년 대비 증가율 (%)": row["yoy_revenue_growth_pct"],
        } for row in result["issuer_rows"]
    ], use_container_width=True, hide_index=True)
    for row in result["issuer_rows"]:
        st.markdown(
            f'[{row["ticker"]} 공식 공시·연차보고서 원문]({row["primary_public_report"]})'
        )
    from .dell_real_source_ui import render_dell_real_source_evidence
    render_dell_real_source_evidence(st)

    st.json({
        "state": result["status"],
        "genuine_public_revenue_rows": 3,
        "true_ndx_available": False,
        "independently_licensed_comparable_peer_set": False,
        "fiscal_period_alignment_verified": False,
        "engine_c_sector_verdict": result["sector_rank_or_growth_conclusion"],
        "guard_policy_preview": "HOLD",
        "investment_recommendation": False,
        "trade_executed": False,
    })
