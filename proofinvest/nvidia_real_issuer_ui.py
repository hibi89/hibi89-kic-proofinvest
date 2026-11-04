"""NVIDIA genuine FY2026 issuer financial originals human-only Streamlit route."""
from __future__ import annotations


def render_nvidia_fy2026_real_issuer(st) -> None:
    from .nvidia_real_issuer_review import (
        actual_nvidia_issuer_receipt, review_nvidia_actual_release,
    )
    st.title("KUODRA — NVIDIA FY2026 공식 발행사 실적 원문 검증")
    r = review_nvidia_actual_release(
        as_of="2026-11-05", receipt=actual_nvidia_issuer_receipt()
    )
    if (r.get("status") != "REAL_NVDA_FY2026_2025_ISSUER_GAAP_REVIEW_LIMITED"
            or r.get("issuer_original_publisher_seen") is not True
            or r.get("sec_original_identical") is not False
            or r.get("commercial_ai_rights_verified") is not False
            or r.get("licensed_stock_ndx_peer_available") is not False
            or r.get("full_abc_ready") is not False
            or r.get("guard_policy_preview") != "HOLD"
            or r.get("trade_executed") is not False
            or type(r.get("evidence")) is not dict):
        st.error("NVIDIA 실제 발행사 원문 검증 증거가 일치하지 않습니다. 재무수치를 표시하지 않습니다.")
        return
    e = r["evidence"]
    m = e["metrics"]
    st.success("NVIDIA 실제 발행사 FY2026·FY2025 분기/연간 GAAP 실자료 확인 (제한)")
    st.markdown(
        f'[NVIDIA 발행사 공식 실적발표]({e["issuer_source_url"]}) · '
        f'[실제 원문 단일 HTTPS 검증 CI]({e["source_ci_run"]})'
    )
    st.caption(
        f'FY2026 {e["fiscal_2026_end"]} / FY2025 {e["fiscal_2025_end"]} · '
        f'발행사 HTML {e["source_bytes"]:,} bytes · '
        f'SHA-256 {e["issuer_source_sha256"]}'
    )
    st.subheader("NVIDIA 발행사 재무제표 — 연간 수치 (USD 백만)")
    st.dataframe([
        {"지표": "연결 매출", "FY2026": m["revenue_2026_usdm"],
         "FY2025": m["revenue_2025_usdm"]},
        {"지표": "매출채권", "FY2026": m["trade_receivables_2026_usdm"],
         "FY2025": m["trade_receivables_2025_usdm"]},
        {"지표": "재고자산", "FY2026": m["inventory_2026_usdm"],
         "FY2025": m["inventory_2025_usdm"]},
    ], use_container_width=True, hide_index=True)
    a, b, c = st.columns(3)
    a.metric("실제 매출 증가율", m["revenue_growth_pct"] + "%")
    b.metric("재고 증가율", m["inventory_growth_pct"] + "%")
    c.metric("영업현금흐름/순이익", m["cfo_to_net_income_2026"])
    st.json({
        "source_status": r["status"],
        "stock_ticker": e["ticker"],
        "receivables_growth_minus_revenue_pp": m["ar_growth_minus_revenue_pp"],
        "inventory_growth_minus_revenue_pp": m["inventory_growth_minus_revenue_pp"],
        "issuer_original_sha256": e["issuer_source_sha256"],
        "sec_original_identical": False,
        "commercial_ai_rights_verified": False,
        "stock_ndx_peer_licensed": False,
        "financial_misconduct_proven": False,
        "guard_policy_preview": "HOLD",
        "trade_executed": False,
        "external_network_requests_on_view": 0,
    })
    st.warning(
        "발행사 미감사 실적발표와 실제 원문 수치 검증입니다. SEC 10-K와 "
        "원문 바이트 동일성·상업/AI 이용권·주가/Nasdaq-100 및 동종기업 "
        "벤치마크는 미검증입니다. 투자 승인이나 회계 부정 판정이 아닙니다. Guard HOLD."
    )
