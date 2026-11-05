"""P190 public SEC text transcribed Apple 2026 financial check — no network."""
from __future__ import annotations


def render_apple_fy2026_public_review(st) -> None:
    st.title("KUODRA — Apple FY2026 공식 공시 수치 검산")
    st.warning(
        "PUBLIC TEXT TRANSCRIPTION · SEC 공개 10-K를 2026-11-05 수동 대조한 "
        "실제 과거 수치. 원본 HTML 바이트·발행 원본/이용권 인증, "
        "NDX/시장/동종업계 자료와 투자 권고는 미지원. "
        "로컬 모델은 기본 미실행이며 별도 2단계 동의 후에만 활성화됩니다."
    )
    from .apple_fy2026_public_filing_review import (
        review_apple_2026_public_financials, public_2026_values,
    )
    result = review_apple_2026_public_financials(
        ticker="AAPL", accession="0000320193-26-000026",
        as_of="2026-11-05", values=public_2026_values())
    if (result.get("status") !=
            "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED"
            or result.get("source_rights_verified") is not False
            or result.get("original_bytes_authenticated") is not False
            or result.get("guard_policy_preview") != "HOLD"
            or result.get("trade_executed") is not False):
        st.error("원본 출처/산술 계약 오류: 모든 표시를 차단합니다.")
        return
    st.markdown("[SEC 2026-11-03 원문 출처 확인](" + result["public_filing_url"] + ")")

    # P236: first-party official EDGAR public *policy* evidence only;
    # independent of specific raw SEC file authentication and API permissions.
    from .sec_public_filing_policy_ui import render_sec_public_filing_policy
    render_sec_public_filing_policy(st, result)

    # P237: only already-held local SEC HTML, operator opt-in;
    # zero SEC GET and no source-authentication promotion.
    from .apple_2026_local_edgar_ui import render_local_apple_sec_html_replay
    render_local_apple_sec_html_replay(st)
    st.caption("연결재무제표 · USD 백만 · FY2026 2026-09-26 · FY2025 2025-09-27")
    rows = [
        {"지표": name, "FY2026 (USD 백만)": row["2026_usd_millions"],
         "FY2025 (USD 백만)": row["2025_usd_millions"],
         "10-K 페이지": row["form_10k_page"]}
        for name, row in result["transcribed_financial_statement_values"].items()
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    metrics = result["derived_metrics"]
    a, b, c = st.columns(3)
    a.metric("매출 증가율 (산술)", metrics["revenue_growth_pct"] + "%")
    b.metric("재고 증가율 (산술)", metrics["inventory_growth_pct"] + "%")
    c.metric("영업현금흐름/순이익", metrics["operating_cash_flow_to_net_income_2026"])
    st.warning(
        "재고 증가율이 매출 증가율보다 큽니다. "
        "사기·분식회계 확정이 아닌 사람 검토용 탐색 신호입니다."
    )
    st.json({
        "fiscal_evidence_status": result["status"],
        "signals": result["signals"],
        "source_rights_verified": False,
        "source_original_bytes_authenticated": False,
        "ndx_and_peer_live_data_verified": False,
        "guard_preview": "HOLD",
        "human_review_required": True,
        "trade_executed": False,
    })
    st.caption(
        "별도 유료 데이터 사용이나 SEC API 직접 재시도 없음. "
        "개별 원본·유료시장 데이터는 출처/권한 확인 전 재배포·외부 AI 전송 금지. "
        "SEC 공개 EDGAR 일반 재사용 정책은 위 공식 근거 안내를 참조하세요. "
        "아래 공개 숫자 2개만 동의 후 로컬에서 처리."
    )

    # P192: only appears on explicitly enabled loopback local workspace.
    # No remote model, no user originals; two opt-ins and a single real click.
    from .apple_public_peer_ui import render_public_fy2026_reference_peers
    render_public_fy2026_reference_peers(st)

    from .apple_public_model_ui import render_apple_public_model_check
    render_apple_public_model_check(st)

    # Optional stronger P233 Qwen check: separate two consents, no auto model call.
    from .apple_qwen_public_ui import render_apple_public_qwen_check
    render_apple_public_qwen_check(st)

    # P235: multi-fact issuer public evidence report; real model is default off.
    from .apple_qwen_public_brief_ui import render_public_evidence_model_summary
    render_public_evidence_model_summary(st)

    # P234 intentionally NOT exposed: real 0.5B/1.5B negative-control
    # financial signal evaluation disagreed with independent Decimal math.
    # Keep failed experimental code only for offline diagnostics. P233 works.
