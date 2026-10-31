"""Opt-in local-only Streamlit interface for operator-supplied SEC-shaped files.

Must NOT run on a publicly reachable Streamlit server. Both an explicit
environment switch and an explicit loopback server bind are mandatory.
No file path inputs, no network calls, no original persistence beyond the
existing temporary source-span checker. Downloading a report is optional.
"""
from __future__ import annotations

import os
import json

from disclosure_lightning.core import MAX_JSON_BYTES
from disclosure_lightning.originals import MAX_FILING_BYTES

from .local_sec_packet import _MAX_FILE_BYTES
from .kuodra_local_workspace import preview_uploaded_triplet, review_uploaded_triplet


def local_workspace_enabled(st) -> bool:
    if os.environ.get("KUODRA_ENABLE_LOCAL_SOURCE_UI") != "1":
        return False
    try:
        return st.get_option("server.address") in ("127.0.0.1", "localhost")
    except (KeyError, AttributeError, RuntimeError):
        return False


def _uploaded_sources(files) -> dict[str, bytes]:
    caps = {
        "submissions": MAX_JSON_BYTES,
        "companyfacts": _MAX_FILE_BYTES,
        "original_filing": MAX_FILING_BYTES,
    }
    if set(files) != set(caps) or any(
        files[k] is None or type(files[k].size) is not int
        or not 0 < files[k].size <= caps[k]
        for k in caps
    ):
        raise ValueError("THREE_BOUNDED_UPLOADS_REQUIRED")
    return {key: files[key].getvalue() for key in caps}


def render_local_workspace(st) -> None:
    if not local_workspace_enabled(st):
        st.error("로컬 파일 분석은 localhost 전용 명시적 설정이 없으면 비활성화됩니다.")
        return
    st.title("KUODRA · 로컬 SEC 원본 3종 검토")
    st.warning(
        "로컬 PC에서만 사용하십시오. 파일은 브라우저에서 실행 중인 Streamlit "
        "서버로 전달됩니다. 다른 PC/클라우드에 배포한 서버에는 올리지 마십시오. "
        "원문 출처·시간·권리 모두 미인증이며, 실거래·투자권고가 아닙니다."
    )
    st.caption("Preview → 명시적 임시 감사 동의 → HOLD/REJECT → JSON/HTML 다운로드. "
               "외부 SEC/Gemini 호출 및 영구 SQLite 저장 없음.")

    uploads = {
        "submissions": st.file_uploader("1. submissions.json", type=["json"],
                                        key="kuodra_submissions"),
        "companyfacts": st.file_uploader("2. companyfacts.json", type=["json"],
                                         key="kuodra_companyfacts"),
        "original_filing": st.file_uploader("3. 원문 10-K HTML", key="kuodra_original"),
    }
    left, right = st.columns(2)
    with left:
        cik = st.text_input("CIK 10자리", key="kuodra_cik", max_chars=10)
        accession = st.text_input("SEC 접수번호", key="kuodra_accession", max_chars=20)
        as_of = st.text_input("기준일 (YYYY-MM-DD)", key="kuodra_asof", max_chars=10)
        collected_at = st.text_input("사용자 주장 수집시각 (UTC ISO8601)",
                                     key="kuodra_collected", max_chars=40)
    with right:
        current_end = st.text_input("현재 회계기간 종료일", key="kuodra_current", max_chars=10)
        prior_end = st.text_input("직전 회계기간 종료일", key="kuodra_prior", max_chars=10)
        needle = st.text_input("원문 본문에서 고유한 인용 문구",
                               key="kuodra_needle", max_chars=240)
        claim = st.text_input("성장률 주장 % (선택)", key="kuodra_claim", max_chars=100)
    request = {
        "cik": cik, "accession": accession,
        "as_of": as_of, "collected_at": collected_at,
        "current_end": current_end, "prior_end": prior_end,
        "needle": needle, "claimed_growth_pct": claim.strip() or None,
    }
    if st.button("1단계 · 원본 대조 미리보기", key="kuodra_preview"):
        st.session_state.pop("kuodra_preview_receipt", None)
        try:
            raw = _uploaded_sources(uploads)
            preview = preview_uploaded_triplet(raw, request)
            st.session_state["kuodra_preview_receipt"] = preview
        except (ValueError, TypeError, OSError, KeyError, OverflowError,
                RecursionError):
            st.error("미리보기 차단: 입력 원본·기간·인용·식별자 검증 실패")
    receipt = st.session_state.get("kuodra_preview_receipt")
    if receipt is None:
        st.info("세 파일과 사용자가 확인한 기간/인용을 입력한 후 미리보기를 실행하십시오.")
        return
    st.subheader("출처 메타데이터 대조 · 아직 감사 DB 기록 없음")
    st.json({
        "issuer_cik_operator_supplied": receipt["issuer_cik_operator_supplied"],
        "accession_operator_supplied": receipt["accession_operator_supplied"],
        "verification_status": receipt["verification_status"],
        "growth_pct_unverified": receipt["growth_pct_unverified"],
        "text_node_status": receipt["text_node_status"],
        "source_sha256": receipt["source_sha256"],
        "source_authenticated": False,
        "audit_written": False,
    })
    consent = st.checkbox("임시 로컬 SQLite 생성·검증 후 자동 삭제에 동의",
                          key="kuodra_ephemeral_consent", value=False)
    if st.button("2단계 · Guard 로컬 검증 실행", disabled=not consent,
                 key="kuodra_run", type="primary"):
        try:
            raw = _uploaded_sources(uploads)
            report, html = review_uploaded_triplet(
                raw, request, expected_preview=receipt, consent=consent,
            )
        except (ValueError, TypeError, OSError, KeyError, OverflowError,
                RecursionError):
            st.error("Guard 실행 차단: 미리보기 이후 원본/입력이 변경됐거나 감사 실패. "
                     "미리보기를 다시 수행하고 로컬 상태를 확인하십시오.")
            return
        st.success("로컬 Guard 완료 · 임시 SQLite 삭제 · 외부 출처 미인증")
        a, b, c = st.columns(3)
        a.metric("재무 주장", report["verification"]["status"])
        b.metric("Guard", report["guard"]["decision"])
        c.metric("로컬 감사 체인", "PASS")
        st.json({
            "guard_reasons": report["guard"]["reason_codes"],
            "balance_sheet": report["balance_sheet"]["status"],
            "share_capital": report["share_capital"]["status"],
            "capital_filing_watch": report["capital_filing_watch"]["status"],
            "cashflow": report["cashflow"]["status"],
            "audit_hash": report["audit"]["event_hash"],
            "source_authenticated": False, "trade_executed": False,
            "audit_retained": False,
        })
        payload = json.dumps(
            report, ensure_ascii=False, sort_keys=True, indent=2,
            allow_nan=False,
        ).encode("utf-8")
        st.download_button(
            "오프라인 분석 보고서 JSON",
            data=payload, file_name="KUODRA_LOCAL_UNVERIFIED.json",
            mime="application/json", on_click="ignore",
        )
        st.download_button(
            "오프라인 분석 보고서 HTML",
            data=html, file_name="KUODRA_LOCAL_UNVERIFIED.html",
            mime="text/html", on_click="ignore",
        )
        st.caption("감사 SHA는 다운로드 보고서의 로컬 계산 증거이며 "
                   "삭제된 임시 DB의 영구 감사 보증서가 아닙니다.")
