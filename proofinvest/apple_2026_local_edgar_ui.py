"""P237 operator-only already-held Apple 2026 SEC HTML offline replay panel."""
from __future__ import annotations


def render_local_apple_sec_html_replay(st) -> None:
    from .kuodra_local_workspace_ui import local_workspace_enabled
    if not local_workspace_enabled(st):
        return
    from .apple_2026_local_edgar_replay import (
        _SIZE, verify_operator_apple_2026_edgar_html,
    )
    with st.expander(
        "보유 중인 Apple FY2026 SEC 원문 HTML · 로컬 iXBRL 6항 검산",
        expanded=False,
    ):
        st.caption(
            "외부 SEC 요청 0회. 이미 보유한 aapl-20260926.htm 단일 원문 파일을 "
            "로컬 PC 메모리에서만 검사합니다. SEC 공식 색인에 표시된 "
            "10-K 파일 크기·발행사·기간·연결 US-GAAP 매출/순이익/현금흐름 "
            "6개 항목을 검산하며 원문/경로는 GitHub·외부 AI에 보내지 않습니다."
        )
        st.warning(
            "파일명·길이·수치·SHA256 일치만으로 SEC TLS 원본 진위, "
            "발행기관 인증 또는 재사용권을 확보할 수 없습니다. "
            "기존 SEC 403 차단 URL을 재시도하지 않습니다."
        )
        uploaded=st.file_uploader(
            "이미 보유한 SEC 2026 10-K HTML만 선택 (새 다운로드 없음)",
            type=["htm", "html"],
            key="p237_existing_sec_html",
        )
        approval=st.checkbox(
            "이 로컬 파일을 읽기 전용으로 1회 검산하는 데 동의",
            value=False, key="p237_local_read_consent",
        )
        submit=st.button(
            "SEC 로컬 HTML 구조·6개 재무값 검산",
            key="p237_run_local_sec_check",
            disabled=not(approval and uploaded is not None),
        )
        if not submit:
            return
        if not approval or uploaded is None:
            st.warning("원문 파일과 명시적 로컬 읽기 동의가 필요합니다.")
            return
        if uploaded.name != "aapl-20260926.htm" or uploaded.size != _SIZE:
            st.error("SEC 색인 상 정확한 파일명·크기가 달라 검산하지 않았습니다.")
            return
        result=verify_operator_apple_2026_edgar_html(
            uploaded.getvalue(), filename=uploaded.name,
        )
        if result.get("status") != "LOCAL_SEC_2026_HTML_6_GAAP_FACTS_MATCH_UNAUTHENTICATED":
            st.warning("문서 iXBRL 컨텍스트·기간·USD 단위 또는 수치 검증 실패.")
            st.code(result.get("reason_code","UNAVAILABLE"))
            return
        # Never st.success: valid *local* content is not authenticated SEC.
        st.info(
            "로컬 HTML의 SEC 공개 색인 파일 크기·내부 CIK/연도와 "
            "연결 6개 iXBRL 수치가 일치합니다. SEC 서버 바이트 인증은 미완료."
        )
        st.json({
            "local_sha256":result["local_html_sha256"],
            "local_file_bytes":result["local_html_size"],
            "fiscal_period_end":result["annual_end_verified"],
            "six_local_gaap_facts_consistent":True,
            "sec_tls_origin_authenticated":False,
            "sec_original_byte_identity_attested":False,
            "source_reuse_and_market_rights_verified":False,
            "network_and_model_requests":0,
            "guard":"HOLD","trades":0,
        })
