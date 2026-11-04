"""P192 explicitly consented local-only P191 public Apple issuer model interaction."""
from __future__ import annotations


def render_apple_public_model_check(st) -> None:
    from .kuodra_local_workspace_ui import local_workspace_enabled
    if not local_workspace_enabled(st):
        st.caption("로컬 모델은 127.0.0.1에서 별도 명시적 활성화한 운영자에게만 표시합니다.")
        return
    st.subheader("실제 135M 로컬 모델 · 공개 재무수치 사실 대조")
    st.caption(
        "실제 FY2026 공개 공시 숫자 2개만 127.0.0.1:11435의 사용자 로컬 모델에 "
        "전달합니다. 원본·개인정보·NDX/주가/경쟁사 정보 전송 없음. "
        "기본적으로 모델은 실행되지 않습니다."
    )
    allow_model = st.checkbox(
        "내 PC에서 실행 중인 공개 135M 로컬 모델 연결에 동의",
        value=False, key="kuodra_p192_model_consent",
    )
    allow_public_data = st.checkbox(
        "공개 재무수치 2개를 로컬 모델에서 비교하는 데 동의",
        value=False, key="kuodra_p192_derived_consent",
    )
    clicked = st.button(
        "공개 SEC 숫자 로컬 모델 사실 대조 실행",
        disabled=not (allow_model and allow_public_data),
        key="kuodra_p192_public_model_button",
    )
    if not clicked:
        return
    from .apple_public_model_claim import run_public_issuer_model
    result = run_public_issuer_model(consent=True)
    if (result.get("status") != "REAL_MODEL_PUBLIC_ISSUER_FACT_INDEPENDENTLY_MATCHED"
            or result.get("actual_model_token_count_verified") is not True
            or result.get("actual_model_factual_claim_verified") is not True
            or result.get("publisher_original_bytes_authenticated") is not False
            or result.get("full_market_ndx_peer_rights_verified") is not False
            or result.get("model_free_text_displayed") is not False
            or result.get("guard_policy_preview") != "HOLD"
            or result.get("trade_executed") is not False):
        st.warning("로컬 모델 사실 대조 차단: 응답/증거/숫자 일치 또는 연결을 확인하세요.")
        return
    st.success("로컬 공개 수치 분류 · 독립 검산 일치 (투자 판단 아님)")
    st.info(result["approved_human_review_text"])
    st.json({
        "factual_model_claim": result["model_claim"],
        "source_reference": result["evidence_id"],
        "human_review": "REQUIRED",
        "raw_sec_original_authenticated": False,
        "market_ndx_peer_license_verified": False,
        "guard_policy_preview": "HOLD",
        "trades": 0,
    })
