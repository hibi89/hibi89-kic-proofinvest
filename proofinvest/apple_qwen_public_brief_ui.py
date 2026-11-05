"""P235 default-off local model summary of actual public issuer evidence cards."""
from __future__ import annotations


def render_public_evidence_model_summary(st) -> None:
    from .kuodra_local_workspace_ui import local_workspace_enabled
    if not local_workspace_enabled(st):
        return
    st.subheader("실제 공개 재무근거 3종 · 로컬 AI 설명 검증 (선택)")
    st.caption(
        "기존 Decimal 엔진이 검증한 공개 재무 사실의 상태 코드만 "
        "127.0.0.1:11435의 로컬 Qwen2.5 1.5B에 전달합니다. "
        "모델이 숫자를 계산하거나 자유 문장을 제시하지 못하며, "
        "해당 사실의 원문 재사용권·시세 사용권은 인증되지 않았습니다."
    )
    local=st.checkbox(
        "로컬 Qwen 서버 직접 운영, 외부 중계 없음 확인",
        key="p235_local_model_confirmed",value=False,
    )
    public=st.checkbox(
        "공개 근거 상태 3종의 로컬 AI 요약에 별도 동의",
        key="p235_public_summary_consent",value=False,
    )
    if not st.button(
        "공개 근거 3종 → AI 요약 및 근거 일치 검증 (1회)",
        key="p235_model_brief_run",disabled=not(local and public),
    ):
        return
    if not(local and public):
        st.warning("로컬 모델과 공개 상태 전송 동의가 모두 필요합니다.")
        return
    from .apple_qwen_public_brief import run_local_public_evidence_summary
    result=run_local_public_evidence_summary(
        local_model_confirmed=True,public_fact_summary_consent=True)
    if result.get("status") != "REAL_LOCAL_MODEL_MULTI_PUBLIC_FACT_BRIEF_VERIFIED":
        st.warning("모델 근거·검증·판정이 일치하지 않아 공개 설명을 차단했습니다.")
        st.code(result.get("reason_code","UNAVAILABLE"))
        return
    st.success("실제 모델의 공개 근거 3종 연결과 독립 검증 일치")
    st.info(result["approved_human_only_text"])
    st.json({
        "evidence_refs":result["source_refs"],
        "issuer_public_reference":result["public_filing_reference"],
        "review_period_end":result["fiscal_period_end"],
        "model_tokens_confirmed":True,
        "model_free_text_displayed":False,
        "SEC_raw_original_authenticated":False,
        "licensed_market_ndx_peers":False,
        "guard":"HOLD","human_review_required":True,
        "trades":0,
    })
