"""ProofInvest local-only synthetic Streamlit UI; no live data or uploads.

To use stored mode first run:
  python -m proofinvest.snapshot_store --save
then:
  python -m streamlit run streamlit_app.py
"""
from pathlib import Path

from proofinvest.offline_view import load_synthetic_snapshot
from proofinvest.manual_case_demo import run_manual_case
from proofinvest.snapshot_store import _fixture_digest, read_synthetic_snapshot_with_provenance

_SOURCE_SYNTHETIC = "합성 데이터 시연"
_SOURCE_MANUAL = "삼성전자 공개 재무제표 수동검산 (2024/2023)"

_DIRECT = "합성 fixture 직접 계산"
_STORED = "저장된 결과 재조회 (재계산 없음)"


def _render_manual_case(st) -> None:
    """Show a pinned manual historical statement example, never a live API result."""
    st.warning(
        "MANUAL_PRIMARY_SOURCE_VERIFICATION · 삼성전자 2024/2023 매출액 수동 전사 검산. "
        "현재 DART 직접 열람·OpenDART API·PDF 원문 재인증·AI Agent 실행 없음. "
        "투자 권고나 최신 실적 분석이 아닙니다."
    )
    claims = {
        "16.20% — 기록과 일치": "16.20",
        "30% — 불일치 사례": "30",
        "주장 없음 — 판정 보류": "",
    }
    choice = st.selectbox("검증할 성장률 주장", list(claims))
    try:
        result = run_manual_case(claims[choice])
    except (ValueError, OSError, TypeError, KeyError):
        st.error("수동 검증 기록이 없거나 변경되었습니다. 산출 결과를 표시하지 않습니다.")
        return
    verification = result["verification"]
    st.info(
        "출처: 삼성전자 공식 IR 2024 연결재무제표 (게시 2025-02-18) · "
        "과거 수동 검수 기록만 재사용; 현재 원문 열람·자동 추출하지 않음"
    )
    st.markdown(f"[발행기관 IR 게시 페이지]({result['issuer_ir_listing']})")
    a, b, c = st.columns(3)
    a.metric("보고 연도", str(result["report_year"]))
    b.metric("매출 성장률(수동기록 계산)", (verification["computed_pct"] or "계산 불가") + ("%"
             if verification["computed_pct"] is not None else ""))
    c.metric("외부 원문 독립 인증", "미인증")

    state = verification["state"]
    if state == "verified":
        st.success("일치 — 수동으로 기록한 매출 수치의 산술 검산 결과입니다. 원문 진위 인증이 아닙니다.")
    elif state == "conflict":
        st.error("불일치 — 주장과 수동기록 재계산 결과의 차이가 허용범위를 초과했습니다.")
    else:
        st.warning("검증 보류 — 유효한 성장률 주장이 없어 판정하지 않았습니다.")

    research = result["research"]
    st.subheader("Research → Verification → Risk")
    st.dataframe(
        [
            {"단계": "Research", "판정": research["status"],
             "근거": "발행기관 URL·기업식별자·연도 연결 (실제 출처 인증 아님)"},
            {"단계": "Verification", "판정": state,
             "근거": "2024·2023 연결매출의 수동기록 산술 비교"},
            {"단계": "Risk", "판정": result["risk"]["status"],
             "근거": "검증된 부채·자본 두 항목이 없어 계산 보류"},
        ],
        use_container_width=True, hide_index=True,
    )
    st.info("Risk 산출 보류: 부채·자본의 검증된 원문 수치가 없습니다. 위험도 0 또는 안전 판정으로 대체하지 않습니다.")
    st.caption(
        "출처 권리/재배포 미확인 · 실제 DART 뷰어 미검증 · AI/LLM·실 API 호출 없음 · "
        "산술 'verified'는 회사 재무자료의 현재 진위 또는 대회 제출 인증이 아닙니다."
    )


def render_app(st) -> None:
    st.set_page_config(page_title="ProofInvest | 오프라인 출처 시연", layout="wide")
    source = st.selectbox("자료 유형", [_SOURCE_SYNTHETIC, _SOURCE_MANUAL])
    if source == _SOURCE_MANUAL:
        st.title("ProofInvest — 실제 발행사 수동기록 검산")
        _render_manual_case(st)
        return
    st.title("ProofInvest — 오프라인 합성 데이터")
    st.warning(
        "SYNTHETIC_FIXTURE · 교육용 가상 데이터 · 외부 공시 원본 미인증. "
        "실제 기업 분석, 투자 권고, DAKER 공식 제출물이 아닙니다."
    )
    mode = st.radio("조회 방식", [_DIRECT, _STORED], horizontal=True)
    if mode == _STORED:
        try:
            bundle = read_synthetic_snapshot_with_provenance(
                Path.home() / ".proofinvest-synthetic-cache"
            )
        except (ValueError, OSError):
            st.error(
                "저장된 합성 결과를 확인할 수 없습니다. "
                "먼저 'python -m proofinvest.snapshot_store --save'를 명시적으로 실행하거나 "
                "손상된 로컬 캐시를 확인하세요. 자동 재계산·덮어쓰기는 하지 않습니다."
            )
            return
        view = bundle["view"]
        source_hash = bundle["provenance"]["fixture_sha256"]
        st.success("저장된 합성 계산 결과 조회 성공 · 재계산하지 않음")
        st.caption(
            "저장된 결과 체크섬(SHA-256): "
            + bundle["provenance"]["snapshot_payload_sha256"]
        )
    else:
        view = load_synthetic_snapshot()
        source_hash = _fixture_digest()

    st.info(
        "출처: fixtures/synthetic_annual.json (로컬 합성 fixture) · "
        f"원본 SHA-256: {source_hash} · "
        "무결성 확인은 실제 공시 진위 검증이 아닙니다."
    )
    left, middle, right = st.columns(3)
    left.metric("데이터 유형", view["source_kind"])
    middle.metric("기준 연도", str(view["year"]))
    right.metric("외부 출처 인증", "미인증")

    st.subheader("재무 자료 — 원본 합성 fixture")
    st.caption("CFS(연결)/OFS(별도) 구분 표시 · 금액 단위: KRW · 합성 출처 링크 없음")
    st.dataframe(view["financial_rows"], use_container_width=True, hide_index=True)
    st.subheader("Verification — 합성 데이터 계산")
    st.dataframe(view["checks"], use_container_width=True, hide_index=True)
    st.caption(
        "여기서 verified는 제공된 합성 수치에 대한 산술 일치만 뜻합니다. "
        "실제 원문 인증이 아닙니다."
    )
    st.subheader("Risk — 시연용 탐색 신호")
    risk = view["risk"]
    st.metric("부채/자본 비율", risk["표시 비율"])
    st.info(f'{risk["판정"]} · 보류 코드: {risk["보류 사유"]}')
    st.caption(
        "임계값 200%는 시연용 탐색 기준이며 투자 판단 기준이 아닙니다. "
        "이 화면의 구형 CLI 탐색 결과는 verified-only Risk 인증 경로와 별개입니다."
    )


if __name__ == "__main__":
    import streamlit as st
    render_app(st)
