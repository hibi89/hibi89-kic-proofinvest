"""Explicit, offline-only DL -> Guard -> SQLite report Streamlit screen.

No provider network, real investment approval, or implicit persistence.
Local saved filing mode only writes a separate Guard audit after form submit;
the synthetic demonstration creates disposable databases.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .dl_vendor_audit_report import (
    render_dl_audit_markdown, run_saved_dl_audit_report,
)

SYNTHETIC = "합성 E2E 시연 (임시 DB, 저장 안 함)"
LOCAL = "기존 로컬 DL 증빙 DB (명시적 감사 기록)"
_MODES = (SYNTHETIC, LOCAL)
_CACHE = "_kic_dl_guard_ui_result"


def _safe_report(result: Any) -> bool:
    """The UI must never display an unverified result as authorized."""
    if not isinstance(result, dict):
        return False
    source, audit, evidence, guard = (
        result.get("source"), result.get("audit"),
        result.get("evidence"), result.get("guard"),
    )
    if not all(isinstance(x, dict) for x in (source, audit, evidence, guard)):
        return False
    return (
        result.get("schema") == "proofinvest.dl-saved-audit-report.v1"
        and result.get("status") == "unverified_evidence_audited_for_human_review"
        and result.get("live_api_called") is False
        and result.get("trade_executed") is False
        and result.get("investment_recommendation") is False
        and result.get("official_contest_submission") is False
        and source.get("source_authenticated") is False
        and evidence.get("financial_claim_verified") is False
        and audit.get("chain_valid") is True
        and audit.get("human_review_integrity_valid") is True
        and audit.get("independently_anchored") is False
        and guard.get("decision") == "HOLD"
        and guard.get("trade_executed") is False
        and guard.get("human_approved") is False
    )


def _show_report(st, result: dict[str, Any], *, synthetic: bool) -> None:
    if not _safe_report(result):
        st.error("신뢰 경계 또는 감사 검증 실패 — 보고서 표시 및 내보내기를 차단했습니다.")
        return
    try:
        markdown = render_dl_audit_markdown(result)
        encoded = json.dumps(
            result, ensure_ascii=False, sort_keys=True,
            allow_nan=False, indent=2,
        )
    except (ValueError, TypeError, KeyError):
        st.error("보고서 형식 검증 실패 — 다운로드를 차단했습니다.")
        return

    st.success("합성 자료 E2E 실행 및 임시 감사 검증 완료" if synthetic
               else "선택한 로컬 DL 증빙의 Guard 감사·보고서 검증 완료")
    st.subheader("DL 근거 → Guard 판정 → SQLite 감사")
    first, middle, last = st.columns(3)
    first.metric("Guard 판정", "HOLD")
    middle.metric("근거 후보", str(result["evidence"]["candidate_count"]))
    last.metric("SQLite 감사 무결성", "PASS")
    st.info(
        "원문 내용은 재무 사실 인증이 아닙니다. 승인·실거래·외부 SEC 요청 0회. "
        "감사 해시는 외부 고정 원장이 아니며 로컬 수정 방지 보장이 없습니다."
    )
    src, audit = result["source"], result["audit"]
    st.dataframe([
        {"항목": "기업 CIK (미인증)", "값": src["issuer_cik"]},
        {"항목": "접수번호 (미인증)", "값": src["accession"]},
        {"항목": "기준일 UTC", "값": src["as_of"]},
        {"항목": "공시 파일 SHA-256", "값": src["filing_sha256"]},
        {"항목": "감사 실행 ID", "값": audit["run_id"]},
        {"항목": "감사 이벤트 SHA-256", "값": audit["event_hash"]},
    ], use_container_width=True, hide_index=True)
    if result["evidence"]["references"]:
        st.caption("원문 인용이 아닌 후보 위치와 해시만 표시합니다.")
        st.dataframe([
            {"위치": str(row["source_locator"]),
             "텍스트 SHA-256": row["text_sha256"],
             "상태": row["citation_status"]}
            for row in result["evidence"]["references"]
        ], use_container_width=True, hide_index=True)
    st.subheader("출처·판정 제한사항")
    st.markdown(markdown)
    prefix = "proofinvest_SYNTHETIC_DL_GUARD" if synthetic else "proofinvest_LOCAL_UNVERIFIED_DL_GUARD"
    st.download_button(
        "검증된 요약 JSON 다운로드", data=encoded,
        file_name=prefix + ".json", mime="application/json",
        key="dl_guard_download_json",
    )
    st.download_button(
        "검증된 요약 Markdown 다운로드", data=markdown,
        file_name=prefix + ".md", mime="text/markdown",
        key="dl_guard_download_md",
    )
    if synthetic:
        st.caption("시연 후 임시 SQLite DB는 자동 폐기됩니다. 감사 기록이 영구 저장된 것은 아닙니다.")
    else:
        st.caption("명시적으로 입력한 로컬 감사 DB에 기록했습니다. 이 화면은 거래 승인 UI가 아닙니다.")


def render_dl_guard_report(st) -> None:
    """New source mode; requires a deliberate click or form submit to execute."""
    st.title("ProofInvest — DL → Guard 감사 보고서")
    st.warning(
        "OFFLINE_UNVERIFIED · 합성 시연 또는 사용자가 저장한 로컬 공시 원문만 사용. "
        "외부 SEC 인증·금융 수치 진위 검증·AI 투자 권고·실거래·공식 대회 제출 아님."
    )
    mode = st.radio("DL 감사 자료 실행 방식", _MODES,
                    key="dl_guard_run_mode", horizontal=True)
    if mode == SYNTHETIC:
        st.caption("버튼 클릭 전에는 DB 생성이나 감사 기록이 발생하지 않습니다.")
        if st.button("합성 DL → Guard 감사·보고서 실행", key="dl_guard_demo_run"):
            st.session_state.pop(_CACHE, None)
            try:
                from .kic_dl_guard_demo import run_synthetic_demo
                demo = run_synthetic_demo()
                if (demo.get("schema") != "proofinvest.kic-dl-guard-synthetic-demo.v1"
                        or demo.get("synthetic_only") is not True
                        or demo.get("real_sec_source_authenticated") is not False
                        or demo.get("database_persisted_after_demo") is not False
                        or demo.get("official_contest_submission") is not False
                        or not _safe_report(demo.get("report"))):
                    raise ValueError("Untrusted synthetic demo result")
                st.session_state[_CACHE] = {"mode": SYNTHETIC, "result": demo["report"]}
            except (ImportError, OSError, ValueError, TypeError, KeyError, sqlite3.Error):
                st.error("합성 통합 시연 검증 실패 — 결과·다운로드를 차단했습니다.")
    else:
        st.caption(
            "기존에 저장한 DL SQLite 파일과 별도의 Guard 감사 SQLite 경로를 명시하세요. "
            "경로·원문은 다운로드 보고서에 포함되지 않습니다. 실행 버튼만 DB에 기록합니다."
        )
        with st.form("dl_guard_local_form", clear_on_submit=False):
            dl_db = st.text_input("DL 증빙 SQLite 경로", key="dl_guard_dl_db", max_chars=1024)
            audit_db = st.text_input("별도 Guard 감사 SQLite 경로", key="dl_guard_audit_db",
                                     max_chars=1024)
            cik = st.text_input("기업 CIK 10자리", key="dl_guard_cik", max_chars=10)
            accession = st.text_input("공시 접수번호", key="dl_guard_accession", max_chars=20)
            sha = st.text_input("저장된 원문 SHA-256", key="dl_guard_sha", max_chars=64)
            as_of = st.text_input("증빙 기준일 UTC (YYYY-MM-DD)",
                                  key="dl_guard_as_of", max_chars=10)
            term = st.text_input("검토할 원문 검색어", key="dl_guard_term", max_chars=80)
            run_id = st.text_input("감사 실행 ID", key="dl_guard_run_id", max_chars=128)
            review_mode = st.selectbox(
                "사람 검토 기록 (선택)", ("기록 없음", "ACKNOWLEDGE", "REQUEST_EXCEPTION"),
                key="dl_guard_review_mode",
            )
            reviewer = st.text_input("검토자 식별명 (검토 기록 시 필수)",
                                     key="dl_guard_reviewer", max_chars=80)
            reason = st.text_area("검토 사유 (검토 기록 시 5자 이상)",
                                  key="dl_guard_reason", max_chars=1000)
            submitted = st.form_submit_button("로컬 DL 감사·보고서 실행",
                                               key="dl_guard_local_run")
        if submitted:
            st.session_state.pop(_CACHE, None)
            try:
                if (not dl_db.strip() or not audit_db.strip() or not cik.strip()
                        or not accession.strip() or not sha.strip() or not as_of.strip()
                        or not term.strip() or not run_id.strip()):
                    raise ValueError("Missing required local evidence fields")
                requested_review = review_mode != "기록 없음"
                if not requested_review and (reviewer.strip() or reason.strip()):
                    raise ValueError("Explicit review action required")
                result = run_saved_dl_audit_report(
                    dl_db_path=Path(dl_db), audit_db_path=Path(audit_db),
                    cik=cik, accession=accession, sha256=sha,
                    as_of=as_of, term=term, run_id=run_id,
                    reviewer=reviewer if requested_review else None,
                    action=review_mode if requested_review else None,
                    reason=reason if requested_review else None,
                )
                if not _safe_report(result):
                    raise ValueError("Local evidence report trust boundary failed")
                st.session_state[_CACHE] = {"mode": LOCAL, "result": result}
            except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
                st.error("로컬 증빙·감사 검증 실패 — 승인 또는 보고서 내보내기 불가.")
    cached = st.session_state.get(_CACHE)
    if isinstance(cached, dict) and cached.get("mode") == mode:
        _show_report(st, cached.get("result"), synthetic=(mode == SYNTHETIC))
