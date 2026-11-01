"""P79 interactive Streamlit display for manual SEC WEB -> real DEMO Guard.

All data is committed manually inspected SEC *web-rendered* numbers, NOT SEC
original API bytes, and the Guard is only a simulation. No local audit,
network, persistent write, AI agent, actual investment authorization or trade.
"""
from __future__ import annotations

from decimal import Decimal
import json

from .sec_web_claim_guard_demo import _CLAIM, review_manual_web_growth_claim

_CHOICES = {
    "30% 성장 주장 — 수동 검산과 충돌": "30",
    "6.43% 성장 주장 — 수동 검산과 일치": "6.43",
    "성장률 주장 없음 — 비교 불가": None,
}
_CUSTOM = "직접 입력 — 성장률(%)"
_BASELINE = Decimal("6.43")


def _expected_for_claim(claim: str | None) -> tuple[str, str, str, str | None]:
    """Independently check a free-form claim before showing any Guard verdict."""
    if claim is None:
        return "UNAVAILABLE", "HOLD", "CLAIM_UNAVAILABLE", None
    if type(claim) is not str or _CLAIM.fullmatch(claim) is None:
        raise ValueError("WEB_GUARD_UI_UNTRUSTED_RESULT")
    value = Decimal(claim)
    if not Decimal("-100") <= value <= Decimal("999.99"):
        raise ValueError("WEB_GUARD_UI_UNTRUSTED_RESULT")
    diff = str(value - _BASELINE)
    if value == _BASELINE:
        return "VERIFIED", "HOLD", "RISK_UNAVAILABLE", diff
    return "CONFLICT", "REJECT", "CLAIM_CONFLICT", diff
_SOURCE_URL = (
    "https://www.sec.gov/Archives/edgar/data/"
    "320193/000032019325000079/aapl-20250927.htm"
)
_FALSE_FLAGS = (
    "source_authenticated", "original_sec_bytes_verified",
    "market_and_industry_inputs_verified", "real_sec_a_b_c_end_to_end_verified",
    "rights_verified", "point_in_time_verified", "real_llm_called",
    "external_http_called", "persistent_audit_written", "trade_executed",
    "financial_misconduct_proven", "contest_submitted",
)


def validate_manual_web_guard_ui_result(result: dict, claim: str | None) -> None:
    """Fail closed before a single derived source or decision is rendered."""
    state, decision, reason, difference = _expected_for_claim(claim)
    if type(result) is not dict:
        raise ValueError("WEB_GUARD_UI_UNTRUSTED_RESULT")
    guard = result.get("guard")
    if (type(guard) is not dict
            or result.get("schema") != "kuodra.sec-web-claim-guard-demo.v1"
            or result.get("mode") != "OFFLINE_MANUAL_SEC_WEB_NUMERIC_DEMO_NOT_REAL_SEC_SOURCE"
            or result.get("issuer") != "Apple Inc."
            or result.get("official_web_view_url") != _SOURCE_URL
            or result.get("financial_basis") != "SEC_RENDERED_WEB_TEXT_MANUALLY_CHECKED_NOT_ORIGINAL"
            or result.get("manual_cells_checked") != 28
            or result.get("claim_growth_pct") != claim
            or result.get("manual_web_growth_pct") != "6.43"
            or result.get("numeric_verdict") != state
            or result.get("numeric_verdict_not_issuer_authentication") is not True
            or result.get("guard_performed_only_as_demo") is not True
            or result.get("risk_evidence_present") is not False
            or any(result.get(k) is not False for k in _FALSE_FLAGS)
            or guard.get("schema") != "proofinvest.guard-decision.v1"
            or guard.get("decision") != decision
            or guard.get("source_authenticated") is not False
            or guard.get("trade_executed") is not False
            or guard.get("human_approved") is not False
            or type(guard.get("reason_codes")) is not list
            or reason not in guard["reason_codes"]
            or "RISK_UNAVAILABLE" not in guard["reason_codes"]
            or result.get("claim_minus_manual_web_pp") != difference
            or (("CLAIM_CONFLICT" in guard["reason_codes"]) != (state == "CONFLICT"))
            or (("CLAIM_UNAVAILABLE" in guard["reason_codes"]) != (state == "UNAVAILABLE"))):
        raise ValueError("WEB_GUARD_UI_UNTRUSTED_RESULT")


def export_manual_web_guard_receipt(result: dict, claim: str | None) -> bytes:
    """Deterministic reviewer download; validated subset, NOT SEC provenance proof.

    The receipt contains only fixed reviewed-public-web metadata and user
    numeric claims. No raw SEC bytes, private identity, audit or API payload.
    """
    validate_manual_web_guard_ui_result(result, claim)
    receipt = {
        "schema": "kuodra.manual-sec-web-guard-receipt.v1",
        "status": "OFFLINE_DEMO_ONLY_ORIGINAL_UNVERIFIED",
        "issuer": "Apple Inc.",
        "source": {
            "basis": "SEC_RENDERED_WEB_TEXT_MANUALLY_CHECKED_NOT_ORIGINAL",
            "public_web_url": _SOURCE_URL,
            "manual_cells_checked": 28,
            "issuer_original_authenticated": False,
        },
        "numeric_check": {
            "claim_growth_pct": result["claim_growth_pct"],
            "manually_checked_growth_pct": result["manual_web_growth_pct"],
            "claim_minus_manual_percentage_points": result["claim_minus_manual_web_pp"],
            "numeric_verdict": result["numeric_verdict"],
        },
        "simulated_guard": {
            "decision": result["guard"]["decision"],
            "risk_evidence_present": False,
            "human_approved": False,
        },
        "limits": {
            "rights_verified": False,
            "point_in_time_verified": False,
            "real_sec_original_verified": False,
            "real_abc_e2e_verified": False,
            "live_llm_called": False,
            "external_http_called": False,
            "persistent_audit_written": False,
            "trade_executed": False,
            "official_contest_submission": False,
        },
        "not_investment_advice": True,
    }
    try:
        data = (json.dumps(receipt, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError) as exc:
        raise ValueError("WEB_GUARD_RECEIPT_BLOCKED") from exc
    if len(data) > 4096:
        raise ValueError("WEB_GUARD_RECEIPT_TOO_LARGE")
    return data


def render_manual_web_guard_ui(st) -> None:
    """Only on explicit click: evaluate strictly read-only reviewed web numbers."""
    st.title("KUODRA · Apple SEC 웹 수동검산 → 데모 Guard")
    st.warning(
        "SEC_RENDERED_WEB_TEXT · Apple FY2025/24 SEC 웹페이지의 28개 수치를 "
        "수동 대조한 기록입니다. 원본 HTML·CompanyFacts·Submissions 바이트를 "
        "확보하거나 독립 인증한 결과가 아닙니다. 수치 충돌/Guard 판정은 "
        "시연용이며 실거래·투자권고·AI Agent 호출이 아닙니다."
    )
    choice = st.selectbox(
        "검토할 매출 성장률 주장", [*_CHOICES, _CUSTOM],
        key="manual_web_guard_claim",
    )
    if choice == _CUSTOM:
        claim = st.text_input(
            "직접 입력: 성장률(%)", value="10.00", max_chars=7,
            key="manual_web_guard_custom_claim",
            help="-100부터 999.99까지, 소수 둘째 자리까지. 입력만으로 실행되지 않습니다.",
        )
    else:
        claim = _CHOICES[choice]
    st.caption(
        "고정 수동근거: Apple FY2025/24 매출액 · 실제 SEC 원본/권리/PIT 미검증 · "
        "리스크 증빙 없음 · 외부 네트워크 0회 · SQLite 저장 0건"
    )
    st.markdown("[SEC FY2025 10-K 공개 웹페이지](" + _SOURCE_URL + ")")
    if not st.button("오프라인 수동 검산 → 데모 Guard 실행",
                     key="manual_web_guard_run"):
        st.info("버튼을 누르기 전에는 분석 함수·Guard를 실행하지 않습니다.")
        return
    try:
        result = review_manual_web_growth_claim(claim)
        validate_manual_web_guard_ui_result(result, claim)
    except (ImportError, ValueError, TypeError, KeyError, OSError, ArithmeticError):
        st.error(
            "입력값 또는 수동 근거·Guard 계약이 유효하지 않아 결과를 차단했습니다. "
            "숫자는 -100~999.99 범위이며 소수 둘째 자리까지만 입력할 수 있습니다."
        )
        return
    one, two, three = st.columns(3)
    one.metric("매출 성장률 · 수동 검산", result["manual_web_growth_pct"] + "%")
    two.metric("숫자 주장 비교", result["numeric_verdict"])
    three.metric("데모 Guard 판정", result["guard"]["decision"])
    st.subheader("근거 → 수치 비교 → Guard 정책")
    st.dataframe([
        {"단계": "Research", "결과": "공식 SEC WEB 수동 확인 28셀 · 원본 미인증"},
        {"단계": "Verification", "결과": result["numeric_verdict"]},
        {"단계": "Guard", "결과": result["guard"]["decision"] + " (시연 전용)"},
        {"단계": "Audit / Trade", "결과": "저장 0건 · 거래 0건"},
    ], use_container_width=True, hide_index=True)
    if result["guard"]["decision"] == "REJECT":
        st.error(
            f"가상 {claim}% 성장 주장은 수동 검산 "
            f"{result['manual_web_growth_pct']}%와 충돌 → 데모 REJECT"
        )
    else:
        st.warning("데모 HOLD · 입력/리스크 증거 부족. 숫자 일치는 출처 진위 인증이 아닙니다.")
    st.json({
        "evidence_kind": result["financial_basis"],
        "manual_cells_checked": result["manual_cells_checked"],
        "claim_growth_pct": result["claim_growth_pct"],
        "computed_pct": result["manual_web_growth_pct"],
        "difference_pp": result["claim_minus_manual_web_pp"],
        "reason_codes": result["guard"]["reason_codes"],
        "demo_only": True,
        "source_authenticated": False,
        "original_sec_bytes_verified": False,
        "risk_evidence_present": False,
        "external_http_called": False,
        "persistent_audit_written": False,
        "trade_executed": False,
        "contest_submitted": False,
    })
    try:
        receipt_bytes = export_manual_web_guard_receipt(result, claim)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        st.error("검산 영수증 계약 검증 실패로 다운로드를 차단했습니다.")
        return
    st.download_button(
        "검산 영수증 JSON 다운로드 (데모 전용)",
        data=receipt_bytes,
        file_name="kuodra-sec-web-guard-DEMO.json",
        mime="application/json",
        on_click="ignore",
        key="manual_web_guard_receipt_download",
        help="수동 SEC 웹 검산 + 시연용 Guard 결과만 담습니다. 원본 SEC 인증/공식 제출 증빙이 아닙니다.",
    )
    st.caption(
        "이 결과는 증거 검토용 오프라인 데모이며 실제 SEC 원본 인증, "
        "시장·산업 데이터 검증, 실 LLM, 투자자 승인 또는 DAKER 제출이 아닙니다."
    )
