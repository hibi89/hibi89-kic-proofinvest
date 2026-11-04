"""P186 independent offline UI for a bounded numeric-claim reviewer draft.

Only reopens the immutable P178 review+clearance pair with one saved model
draft. Does not call Ollama, SEC, vendors, exchange APIs, or trading systems.
No original bytes, API keys, downloaded data, or user sessions are persisted.
A local matching number remains UNVERIFIED for publisher source and license.
"""
from __future__ import annotations

from .kuodra_local_workspace_ui import local_workspace_enabled


def _bounded_upload(upload, limit: int) -> bytes:
    if (upload is None or type(getattr(upload, "size", None)) is not int
            or not 0 < upload.size <= limit):
        raise ValueError("NUMERIC_UI_UPLOAD_SIZE_INVALID")
    data = upload.getvalue()
    if type(data) is not bytes or len(data) != upload.size:
        raise ValueError("NUMERIC_UI_UPLOAD_CHANGED_OR_NON_BYTES")
    return data


def render_local_numeric_claim_ui(st) -> None:
    """Explicit one-click offline decimal cross-check, default closed."""
    if not local_workspace_enabled(st):
        return
    st.subheader("오프라인 AI 수치 대조 · 원본 미인증")
    st.caption(
        "기존 로컬 A/B/C 검토 패킷·권리 미확인표·숫자 초안 JSON을 "
        "각각 업로드하여 단순 주가-실제 NDX 수익률 차이를 재검산합니다. "
        "모델 실행이나 외부 HTTP 없이 진행하며, 정확한 출처·이용권한·"
        "AI 추론 품질이 인증되는 것은 아닙니다."
    )
    if not st.checkbox(
        "오프라인 AI 수치 대조 열기 (기본 비활성)",
        value=False, key="kuodra_p186_numeric_panel",
    ):
        return
    review = st.file_uploader(
        "수치 대조 A/B/C 검토 패킷 JSON (미인증)",
        type=["json"], key="kuodra_p186_review",
    )
    rights = st.file_uploader(
        "수치 대조 권리 미확인표 JSON (미인증)",
        type=["json"], key="kuodra_p186_rights",
    )
    draft = st.file_uploader(
        "수치 대조 AI 초안 JSON (모델 원문 아님)",
        type=["json"], key="kuodra_p186_draft",
    )
    ready = review is not None and rights is not None and draft is not None
    clicked = st.button(
        "오프라인 수치 일치 검증 (외부 API 없음)",
        disabled=not ready, key="kuodra_p186_verify",
    )
    if not clicked:
        return
    if not ready:
        st.warning("검토 패킷, 권리 확인표, 수치 초안이 모두 필요합니다.")
        st.code("NUMERIC_UI_THREE_INPUTS_REQUIRED", language="text")
        return
    from .ticker_local_model_numeric_claim import verify_local_model_numeric_claim
    try:
        result = verify_local_model_numeric_claim(
            _bounded_upload(review, 28672),
            _bounded_upload(rights, 9216),
            _bounded_upload(draft, 1024),
        )
    except (ValueError, TypeError, OSError, AttributeError, KeyError,
            UnicodeError, OverflowError, RecursionError):
        st.warning("입력 JSON 크기나 바이트 일치 조건을 충족하지 못했습니다.")
        st.code("NUMERIC_UI_INVALID_BYTES", language="text")
        return
    if (
        result.get("status") != "LOCAL_MODEL_NUMERIC_MATCH_TO_UNSIGNED_REVIEW_ONLY"
        or result.get("local_numeric_claim_recomputed") is not True
        or result.get("publisher_source_authenticated") is not False
        or result.get("source_rights_verified") is not False
        or result.get("model_origin_authenticated") is not False
        or result.get("ai_agent_executed") is not False
        or result.get("external_sharing_allowed") is not False
        or result.get("investment_recommendation") is not False
        or result.get("trade_executed") is not False
        or result.get("guard_policy_preview") != "HOLD"
        or result.get("external_network_requests") != 0
    ):
        st.warning("AI 숫자 또는 근거 무결성 검증 실패: 검토 결과를 채택하지 않습니다.")
        st.code(result.get("reason_code", "NUMERIC_UI_REJECTED"), language="text")
        return
    st.success("로컬 수익률 차이 Decimal 재검산 PASS (발행기관·이용권한 미인증)")
    st.json({
        "status": "LOCAL_MODEL_NUMERIC_MATCH_TO_UNSIGNED_REVIEW_ONLY",
        "engine": "A",
        "basis": "PRICE_ONLY_CLOSE_VS_ACTUAL_NASDAQ_100",
        "simple_return_gap_pp": result["simple_return_gap_pp"],
        "guard_policy_preview": "HOLD",
        "publisher_source_authenticated": False,
        "source_rights_verified": False,
        "ai_agent_executed": False,
        "investment_recommendation": False,
        "trade_executed": False,
    })
    st.info(result["safe_existing_interpretation"])
    st.warning(
        "계산 결과는 로컬 입력과만 일치합니다. 외부 출처·NDX 라이선스·"
        "모델의 실제 추론 품질·공개 배포·공식 제출은 별도 검증이 필요합니다."
    )
