"""ProofInvest local-only synthetic Streamlit UI; no live data or uploads.

To use stored mode first run:
  python -m proofinvest.snapshot_store --save
then:
  python -m streamlit run streamlit_app.py
"""
from pathlib import Path

from proofinvest.offline_view import load_synthetic_snapshot
from proofinvest.snapshot_store import _fixture_digest, read_synthetic_snapshot_with_provenance

_DIRECT = "합성 fixture 직접 계산"
_STORED = "저장된 결과 재조회 (재계산 없음)"


def render_app(st) -> None:
    st.set_page_config(page_title="ProofInvest | 합성 오프라인", layout="wide")
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
