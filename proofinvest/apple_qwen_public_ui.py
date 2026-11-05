"""P233 opt-in Qwen local-model review of TWO public annual cashflow facts."""
from __future__ import annotations


def render_apple_public_qwen_check(st) -> None:
    from .kuodra_local_workspace_ui import local_workspace_enabled
    if not local_workspace_enabled(st):
        return
    st.subheader("공개 FY2026 재무수치 · 로컬 Qwen 모델 독립 검산 (선택)")
    st.caption(
        "Qwen2.5 0.5B Instruct (Apache-2.0)을 본인 PC 127.0.0.1:11435에서 "
        "실행한 경우에만 선택합니다. 공개 재무수치 숫자 두 개 외에 SEC 원본·"
        "주가·NDX·경쟁기업 원문·개인정보는 모델에 보내지 않습니다. "
        "해당 로컬 서버가 외부 프록시가 아닌지는 운영자가 직접 확인해야 합니다."
    )
    consent_local = st.checkbox(
        "내 로컬 Qwen 모델 연결 및 외부 중계 없음 확인",
        value=False, key="p233_qwen_local_consent",
    )
    consent_public = st.checkbox(
        "공개 FY2026 현금흐름·순이익 숫자 두 개만 로컬 비교 동의",
        value=False, key="p233_qwen_public_numeric_consent",
    )
    if not st.button(
        "실제 로컬 Qwen 공개 재무숫자 비교 (한 번만)",
        key="p233_qwen_fact_execute",
        disabled=not(consent_local and consent_public),
    ):
        return
    if not(consent_local and consent_public):
        st.warning("별도 두 가지 동의가 필요합니다.")
        return
    from .apple_qwen_public_claim import run_actual_local_qwen_public_facts
    outcome = run_actual_local_qwen_public_facts(
        explicit_public_local_consent=True)
    if outcome.get("status") != "ACTUAL_LOCAL_MODEL_PUBLIC_NUMERIC_COMPARISON_MATCHED":
        st.warning("로컬 모델 응답이 독립 검산과 일치하지 않아 표시하지 않습니다.")
        st.code(outcome.get("reason_code", "UNVERIFIED"), language="text")
        return
    st.success("로컬 Qwen 실제 응답과 독립 Decimal 수치 비교 일치 (사람 검토 전용)")
    st.json({
        "source_ref": outcome["evidence_id"],
        "factual_numeric_match": True,
        "cashflow_minus_income_usd_millions":
            outcome["cash_minus_net_income_usd_millions"],
        "model_tokens_verified": True,
        "raw_sec_original_authenticated": False,
        "source_use_rights_verified": False,
        "market_ndx_peer_licensed": False,
        "guard_decision": "HOLD",
        "trade_executed": False,
    })
