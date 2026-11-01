"""Explicit-click, offline Engine B UI; independent of simulated Guard."""
from __future__ import annotations


def validate_engine_b_review(r: dict) -> None:
    if type(r) is not dict:
        raise ValueError("WEB_B_UI_UNTRUSTED")
    expected = {
        "schema": "kuodra.web-manual-accounting-triage.v1",
        "issuer": "Apple Inc.",
        "basis": "SEC_RENDERED_WEB_TEXT_MANUALLY_CHECKED_NOT_ORIGINAL",
        "manual_cells": 28, "years": ["FY2024", "FY2025"],
        "currency": "USD", "amount_unit": "millions",
        "review_prompt_count": 3, "guard_unchanged": True,
        "thresholds_heuristic_not_standards": True,
        "fcf_proxy_non_gaap": True,
    }
    if any(type(r.get(k)) is not type(v) or r.get(k) != v
           for k, v in expected.items()):
        raise ValueError("WEB_B_UI_UNTRUSTED")
    if any(r.get(k) is not False for k in (
        "misconduct_proven", "source_authenticated",
        "original_sec_bytes_verified", "rights_verified",
        "point_in_time_verified", "real_llm_called",
        "investment_risk_certified", "external_http_called",
        "audit_written", "trade_executed", "officially_submitted",
    )):
        raise ValueError("WEB_B_UI_UNTRUSTED")
    checks = (
        ("AR_VS_SALES", "value_pp", "12.63", True),
        ("CFO_TO_INCOME_DROP", "change_pp", "-26.63", True),
        ("FCF_PROXY_VS_SALES", "difference_pp", "-15.66", True),
        ("TOTAL_LIABILITIES_TO_EQUITY", "current_pct", "387.22", False),
    )
    p = r.get("prompts")
    if (type(p) is not list or len(p) != len(checks) or
            any(type(item) is not dict or item.get("code") != code
                or item.get(field) != value or item.get("review") is not review
                for item, (code, field, value, review) in zip(p, checks))):
        raise ValueError("WEB_B_UI_UNTRUSTED")


def render_manual_web_accounting_review(st) -> None:
    st.subheader("Engine B · 회계 신호 별도 검토")
    st.caption(
        "Apple FY2024/25 · SEC 웹텍스트 수동 확인 28셀 · "
        "원본 인증/권리/시점 미검증 · 비GAAP FCF 프록시 포함. "
        "탐색 지표는 회계부정·투자위험 판정이 아닙니다."
    )
    if not st.button("Engine B 오프라인 회계 신호 계산",
                     key="manual_web_engine_b_run"):
        st.info("별도 버튼을 누르기 전에는 Engine B를 실행하지 않습니다.")
        return
    try:
        from .sec_web_accounting_signals import triage_manual_sec_web
        r = triage_manual_sec_web()
        validate_engine_b_review(r)
    except (ValueError, TypeError, KeyError, ImportError, OSError, ArithmeticError):
        st.error("Engine B 수동 근거·계산 검증에 실패하여 결과를 차단했습니다.")
        return
    p = r["prompts"]
    st.metric("회계 검토 질문 · 이상행위 확정 아님", "3건")
    st.dataframe([
        {"지표": "매출채권 증가율 − 매출 성장률",
         "값": p[0]["value_pp"] + "pp", "구분": "추가 확인"},
        {"지표": "영업현금흐름/순이익 비율 변화",
         "값": p[1]["change_pp"] + "pp", "구분": "추가 확인"},
        {"지표": "FCF 비GAAP 프록시 성장 − 매출 성장",
         "값": p[2]["difference_pp"] + "pp", "구분": "추가 확인"},
        {"지표": "총부채/자본 · 이자부채 아님",
         "값": p[3]["current_pct"] + "%", "구분": "참고만"},
    ], use_container_width=True, hide_index=True)
    # Canvas dataframes do not expose values to all screen readers/browsers.
    # Keep explicit value labels for the actual Chromium and human review.
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("매출채권 성장 격차", p[0]["value_pp"] + "pp")
    c2.metric("현금전환 변화", p[1]["change_pp"] + "pp")
    c3.metric("FCF 성장 격차", p[2]["difference_pp"] + "pp")
    c4.metric("총부채/자본 · 참고", p[3]["current_pct"] + "%")
    st.warning("3건은 검토 질문이며 회계부정 증거가 아닙니다. Guard·매매에 반영하지 않습니다.")
    st.json({
        "schema": r["schema"], "source_basis": r["basis"], "manual_cells": 28,
        "source_authenticated": False, "original_sec_bytes_verified": False,
        "rights_verified": False, "point_in_time_verified": False,
        "real_llm_called": False, "audit_written": False, "trade_executed": False,
        "guard_unchanged": True, "officially_submitted": False,
    })
