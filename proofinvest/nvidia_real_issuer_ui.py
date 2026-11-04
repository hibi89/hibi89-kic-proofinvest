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
    # P210: same-industry PUBLIC GAAP annual reference. This is a newly
    # disclosed first-party web-text transcription for AMD, NOT another
    # verified original-byte file or a licensed/true period-matched peer.
    from .amd_nvidia_public_reference import (
        actual_amd_public_newsroom_receipt,
        compare_nvda_amd_public_annual_reference,
    )
    reference = compare_nvda_amd_public_annual_reference(
        reviewed_as_of="2026-11-05",
        amd_receipt=actual_amd_public_newsroom_receipt(),
        nvidia_receipt=actual_nvidia_issuer_receipt(),
    )
    if (reference.get("status") ==
            "HUMAN_REFERENCE_NVDA_AMD_GAAP_GROWTH_DIFFERENT_PERIODS"
            and reference.get("actual_nvda_issuer_raw_verified") is True
            and reference.get("amd_web_text_reference_validated") is True
            and reference.get("amd_original_raw_bytes_verified") is False
            and reference.get("licensed_representative_same_sector_peer") is False
            and reference.get("source_commercial_ai_rights_verified") is False
            and reference.get("fiscal_windows_identical") is False
            and reference.get("engine_c_completed") is False
            and reference.get("guard_policy_preview") == "HOLD"
            and reference.get("trade_executed") is False
            and type(reference.get("evidence")) is dict):
        p = reference["evidence"]
        st.subheader("AMD·NVIDIA 공식 공개 GAAP 매출 참고 비교 — 동일 기간 아님")
        st.markdown(
            f'[AMD 공식 FY2025 뉴스룸 발표]({p["issuer_rows"][1]["first_party_report"]}) · '
            f'[NVIDIA 공식 FY2026 발표]({p["issuer_rows"][0]["first_party_report"]})'
        )
        st.dataframe([
            {"기업": item["ticker"],
             "최신 회계연도 종료일": item["fiscal_latest_end"],
             "최신 연간 매출 (USD 백만)": item["annual_gaap_revenue_latest_usdm"],
             "직전 연간 매출 (USD 백만)": item["annual_gaap_revenue_prior_usdm"],
             "매출 증가율 (%)": item["annual_gaap_revenue_growth_pct"],
             "원문 검증 수준": item["provenance"]}
            for item in p["issuer_rows"]
        ], hide_index=True, use_container_width=True)
        st.warning(
            f'비교 제한: 회계연도 종료일 {p["current_fiscal_end_gap_days"]}일 차이, '
            "기업별 제품 및 데이터센터 부문 구성 차이. AMD는 공식 홈페이지 공개 "
            "GAAP 수치 수동 대조만 완료했고 원문 HTML 바이트 해시·이용권 미확인입니다. "
            "NVIDIA 원문 바이트는 별도 CI에서 검증했습니다. "
            "시장점유율·경쟁 순위·투자 판단을 추정하지 않습니다. Guard HOLD."
        )
        st.json({
            "public_issuer_reference_status": reference["status"],
            "nvidia_actual_issuer_raw_verified": True,
            "amd_issuer_public_web_gaap_only": True,
            "amd_raw_html_authenticated": False,
            "same_fiscal_period": False,
            "licensed_peer_data": False,
            "sector_rank": "UNAVAILABLE",
            "cross_issuer_accounting_policy_comparable": False,
            "commercial_ai_rights_verified": False,
            "industry_engine_c_complete": False,
            "guard_decision": "HOLD",
            "trade_executed": False,
            "network_calls_on_view": 0,
        })
    else:
        st.warning("AMD 동종업계 공식 웹텍스트 참조 검증 실패: 비교 수치를 표시하지 않습니다.")
    st.warning(
        "발행사 미감사 실적발표와 실제 원문 수치 검증입니다. SEC 10-K와 "
        "원문 바이트 동일성·상업/AI 이용권·주가/Nasdaq-100 및 동종기업 "
        "벤치마크는 미검증입니다. 투자 승인이나 회계 부정 판정이 아닙니다. Guard HOLD."
    )

    st.subheader("NVIDIA · 실제 발행사 데이터 → Guard HOLD 감사 (로컬)")
    st.caption(
        "P209 원문 해시로 추적 가능한 계산값만 로컬 임시 SQLite에 감사 기록합니다. "
        "SEC 원본·상업 이용권·지수·동종업체 데이터·AI 판단은 미인증이며 "
        "거래/외부 전송은 실행하지 않습니다. 동의하지 않으면 파일을 만들지 않습니다."
    )
    consent = st.checkbox(
        "NVIDIA 제한적 실자료 계산값을 임시 로컬 감사 DB에 기록하는 데 동의",
        value=False, key="p211_nvda_local_audit_ack",
    )
    if st.button(
        "NVIDIA Guard HOLD 감사 1회 실행",
        key="p211_nvda_run_once", disabled=not consent,
    ):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from .nvidia_real_guard_audit import run_nvidia_guard_audit
        with TemporaryDirectory(prefix="kuodra-nvda-audit-") as tmp:
            audit = run_nvidia_guard_audit(
                run_id="p211-nvda-human-review",
                audit_db_path=Path(tmp) / "guard.sqlite",
                acknowledge_local_persistence=True,
                source_receipt=actual_nvidia_issuer_receipt(),
            )
        report = audit.get("report")
        if (audit.get("status") == "REAL_NVDA_ENGINE_B_GUARD_HOLD_AUDIT_RECORDED"
                and audit.get("audit_written") is True
                and audit.get("audit_chain_valid") is True
                and audit.get("issuer_publisher_original_seen") is True
                and audit.get("sec_original_authenticated") is False
                and audit.get("source_commercial_ai_rights_verified") is False
                and audit.get("guard_policy_preview") == "HOLD"
                and audit.get("trade_executed") is False
                and type(report) is dict
                and report.get("source_sha256") == e["issuer_source_sha256"]
                and report.get("source_rights_verified") is False
                and report.get("guard", {}).get("decision") == "HOLD"
                and report.get("trade_executed") is False):
            st.success("NVIDIA 실자료 Guard HOLD 감사 체인 검증 완료 (임시 DB 자동 삭제)")
            st.json({
                "issuer": "NVDA", "source_sha256": report["source_sha256"],
                "financial_evidence_sha256": report["financial_evidence_sha256"],
                "audit_event_hash": report["audit"]["event_hash"],
                "decision": "HOLD", "audit_chain_verified": True,
                "sec_original_authenticated": False,
                "commercial_ai_rights_verified": False,
                "trade_executed": False, "external_network_requests": 0,
            })
        else:
            st.error("NVIDIA 실자료 감사 거부: 원본·동의·Guard·감사 무결성을 재확인하십시오.")
