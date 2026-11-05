"""P234 actual local Qwen publicly derived two-signal discrepancy screen."""
from __future__ import annotations


def render_apple_public_anomaly_model(st) -> None:
    from .kuodra_local_workspace_ui import local_workspace_enabled
    if not local_workspace_enabled(st):
        return
    st.subheader("Qwen 실제 재무 이상징후 2종 교차검산 (선택)")
    st.caption(
        "FY2026 Apple 공개 공시 숫자에서 로컬 계산한 매출·재고·매출채권 "
        "증가율 3개만 127.0.0.1:11435 로컬 모델에 전달하며, "
        "모델의 서로 반대인 두 결과는 Decimal로 재검산합니다. "
        "원본·사용자 파일·API 키·주가·Nasdaq-100·경쟁기업 수치는 "
        "전송하지 않습니다. 로컬 서버의 프록시/원격 중계 여부는 "
        "직접 확인해야 합니다."
    )
    allow_local = st.checkbox(
        "내 로컬 Qwen 서버에만 요청하고 외부 중계가 없음을 확인",
        key="p234_local_model_consent", value=False,
    )
    allow_derived = st.checkbox(
        "공개 수치 유래 증가율 3개 전송 및 2개 재무 신호 비교 동의",
        key="p234_derived_public_consent", value=False,
    )
    if not st.button(
        "실제 재무 이상징후 양성·음성 2종 모델 검산",
        key="p234_anomaly_model_run",
        disabled=not(allow_local and allow_derived),
    ):
        return
    if not(allow_local and allow_derived):
        st.warning("두 가지 독립 동의가 모두 필요합니다.")
        return
    from .apple_qwen_anomaly_screen import run_local_qwen_anomaly_screen
    outcome = run_local_qwen_anomaly_screen(
        explicit_local_model_consent=True,
        explicit_public_derived_consent=True,
    )
    if outcome.get("status") != "REAL_QWEN_TWO_PUBLIC_FINANCIAL_SIGNALS_MATCHED":
        st.warning("Qwen 결과가 독립 재무 검산과 불일치해 결과를 차단했습니다.")
        st.code(outcome.get("reason_code", "UNAVAILABLE"), language="text")
        return
    st.success("재고·매출채권 두 신호의 실제 모델 응답과 독립 재계산 일치")
    st.info(outcome["authored_interpretation"])
    st.json({
        "two_signals": outcome["verified_signals"],
        "growth_yoy_pct": outcome["growth_percentages_derived_locally"],
        "evidence": outcome["evidence_id"],
        "real_model_tokens_observed": True,
        "guard": "HOLD",
        "actual_sec_raw_bytes_verified": False,
        "licensed_market_ndx_peers": False,
        "fraud_proven": False, "human_review_required": True,
        "trading": False,
    })
