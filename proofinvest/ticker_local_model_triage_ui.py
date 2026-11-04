"""P180 local-only optional A/B/C model triage inside the ticker review screen.

This panel consumes only the two already-redacted canonical reviewer exports.
No raw SEC/stock/NDX original enters a model request or is cached in session.
No HTTP before TWO checkboxes plus a deliberate button click. The endpoint is
always local 127.0.0.1, but users must confirm their local service isn't a
remote forwarding proxy. No genuine model or provider rights are asserted.
"""
from __future__ import annotations

import re

from .kuodra_local_workspace_ui import local_workspace_enabled

_VALID_PORT = re.compile(r"[1-9][0-9]{3,4}\Z", re.ASCII)


def _uploaded(upload, maximum: int) -> bytes:
    if (upload is None or type(getattr(upload, "size", None)) is not int
            or not 0 < upload.size <= maximum):
        raise ValueError("P180_UPLOADED_BYTES_INVALID")
    value = upload.getvalue()
    if type(value) is not bytes or len(value) != upload.size:
        raise ValueError("P180_UPLOAD_IDENTITY_CHANGED")
    return value


def render_local_model_triage_ui(st) -> None:
    """Render an independently actionable panel, not a one-run transient UI.

    Human downloads P167/P178 canonical pair and reuploads REDACTED receipts.
    No dangerous session_state caching or nested buttons disappearing on rerun.
    """
    if not local_workspace_enabled(st):
        return
    st.subheader("로컬 AI 검토 우선순위 · 별도 실행 (실제 모델 미검증)")
    st.caption(
        "내려받은 A/B/C 검토 패킷과 권리 미확인표만 사용합니다. "
        "원본 SEC·주가·NDX·티커·원본 해시를 모델에 전달하지 않습니다. "
        "패킷 내부 무결성 통과는 발행자 인증이나 이용권한이 아닙니다."
    )
    if not st.checkbox(
        "로컬 AI 선택 기능 펼치기 (기본 비활성)",
        value=False, key="kuodra_p180_panel",
    ):
        return
    review = st.file_uploader(
        "로컬 AI 입력용 A/B/C 검토 패킷 JSON (미인증)",
        type=["json"], key="kuodra_p180_review",
    )
    rights = st.file_uploader(
        "로컬 AI 입력용 권리 미확인표 JSON (미인증)",
        type=["json"], key="kuodra_p180_rights",
    )
    model = st.text_input(
        "로컬 AI 모델 이름 (사용자 설치 모델)",
        value="llama3.2", max_chars=64, key="kuodra_p180_model",
    )
    port_text = st.text_input(
        "로컬 AI 서버 포트 (1024~65535)",
        value="11434", max_chars=5, key="kuodra_p180_port",
    )
    consent_local = st.checkbox(
        "127.0.0.1의 본인 관리 모델 서버임을 확인했습니다 (원격 중계 사용 금지)",
        value=False, key="kuodra_p180_consent_local",
    )
    consent_derived = st.checkbox(
        "원본이 아닌 A/B/C 미인증 상태 코드만 로컬 모델로 전달하는 데 동의합니다",
        value=False, key="kuodra_p180_consent_derived",
    )
    ready = bool(
        review is not None and rights is not None
        and consent_local and consent_derived
    )
    clicked = st.button(
        "A/B/C 로컬 AI 검토 우선순위 요청 (명시적 1회)",
        disabled=not ready, key="kuodra_p180_model_run",
    )
    if not clicked:
        return
    # Fail closed even when a mocked/malformed UI incorrectly reports a
    # click for an inaccessible control. Never call a model without both.
    if (not ready or type(port_text) is not str
            or not _VALID_PORT.fullmatch(port_text)
            or not 1024 <= int(port_text) <= 65535):
        st.warning("로컬 AI 명시적 동의 또는 포트 입력이 올바르지 않습니다.")
        st.code("LOCAL_MODEL_CONSENT_OR_PORT_INVALID", language="text")
        return
    from .ticker_local_model_triage import triage_review
    try:
        result = triage_review(
            _uploaded(review, 28672), _uploaded(rights, 9216),
            model=model, port=int(port_text),
            allow_local_model=True,
            confirm_local_derivative_processing=True,
        )
    except (ValueError, OSError, TypeError, KeyError, AttributeError,
            UnicodeError, OverflowError, RecursionError):
        st.warning("로컬 AI 입력 파일을 확인할 수 없습니다. 원본을 전송하지 않습니다.")
        st.code("LOCAL_MODEL_INPUT_INVALID", language="text")
        return
    if (result.get("status")
            != "LOCAL_MODEL_TRIAGE_PROTOCOL_UNVERIFIED_MODEL_ORIGIN"
            or result.get("model_protocol_http_verified") is not True
            or result.get("source_rights_verified") is not False
            or result.get("model_inference_authenticated") is not False
            or result.get("ai_agent_executed") is not False
            or result.get("guard_policy_preview") != "HOLD"
            or result.get("trade_executed") is not False):
        st.warning("로컬 모델 요청 차단 또는 미확인 응답. 검토 결과를 채택하지 않습니다.")
        st.code(result.get("reason_code", "LOCAL_MODEL_TRIAGE_BLOCKED"),
                language="text")
        return
    st.success("로컬 모델 선택 프로토콜 PASS (실제 모델 추론 미검증)")
    st.json({
        "status": "LOCAL_MODEL_TRIAGE_PROTOCOL_UNVERIFIED_MODEL_ORIGIN",
        "focus_engine": result["focus_engine"],
        "focus_status": result["focus_status"],
        "guard_policy_preview": "HOLD",
        "model_inference_authenticated": False,
        "ai_agent_executed": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "external_sharing_allowed": False,
        "trade_executed": False,
    })
    # Only fixed deterministic text from the validated packet, not model text.
    st.info(result["safe_existing_interpretation"])
    st.warning(
        "실제 모델의 정체·추론 품질, SEC/NDX 공급자 권리·시점, 투자 권고, "
        "공식 제출과 공개 배포는 검증되지 않았습니다."
    )
