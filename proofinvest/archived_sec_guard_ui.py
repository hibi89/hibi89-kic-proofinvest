"""Local saved SEC-format archive -> financial verification -> Guard audit UI.

This deliberately never fetches SEC data. A ZIP or its self-reported receipt is
not independently authenticated, so every result remains non-executing.
No writing occurs until the operator explicitly submits the form.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .archived_sec_guard_report import (
    render_archived_sec_guard_markdown,
    run_archived_sec_guard_report,
)

_CACHE = "_kic_archived_sec_guard_ui_last_report"
_ACTIONS = ("기록 없음", "ACKNOWLEDGE", "REQUEST_EXCEPTION")


def _safe_archived_report(value: Any) -> bool:
    """Fail closed if any claimed authorization or report structure is forged."""
    if not isinstance(value, dict):
        return False
    if value.get("schema") != "proofinvest.archived-sec-guard-report.v1":
        return False
    if value.get("status") != "local_archive_review_audited_unverified":
        return False
    for key in ("live_api_called", "source_authenticated", "source_rights_verified",
                "financial_values_authenticated", "model_trained",
                "investment_recommendation", "trade_executed",
                "official_contest_submission"):
        if value.get(key) is not False:
            return False
    verification = value.get("verification")
    risk = value.get("risk")
    guard = value.get("guard")
    audit = value.get("audit")
    research = value.get("research")
    evidence = value.get("evidence")
    review_summary = value.get("review_summary")
    if not all(isinstance(x, dict) for x in (
        verification, risk, guard, audit, research, evidence, review_summary,
    )):
        return False
    status = verification.get("status")
    expected = {"calculated_unverified": "HOLD", "conflict": "REJECT"}.get(status)
    if (expected is None or guard.get("decision") != expected
            or research.get("origin_authenticated") is not False
            or verification.get("arithmetic_is_source_authentication") is not False
            or risk.get("source_authenticated") is not False
            or risk.get("risk_is_investment_recommendation") is not False
            or guard.get("trade_executed") is not False
            or guard.get("human_approved") is not False
            or guard.get("source_authenticated") is not False
            or audit.get("chain_valid") is not True
            or audit.get("human_review_integrity_valid") is not True
            or audit.get("verified_against_persisted_request") is not True
            or audit.get("bound_source_evidence_sha256")
                != evidence.get("evidence_chain_sha256")
            or audit.get("bound_guard_decision") != guard.get("decision")
            or audit.get("externally_anchored") is not False
            or review_summary.get("schema") != "proofinvest.offline-review-summary.v1"
            or review_summary.get("status") != "human_review_required"
            or review_summary.get("financial_status") != status
            or review_summary.get("risk_status") != risk.get("status")
            or review_summary.get("review_priority") not in ("high", "normal")):
        return False
    if status == "conflict" and (
        risk.get("status") != "unavailable"
        or review_summary.get("review_priority") != "high"
    ):
        return False
    if not isinstance(evidence.get("evidence_chain_sha256"), str):
        return False
    try:
        # Independent hardened metadata renderer validates SHA/CIK/accession
        # and rejects untrusted strings before any Markdown interpolation.
        render_archived_sec_guard_markdown(value)
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
    return True


def _display_report(st, report: dict[str, Any]) -> None:
    if not _safe_archived_report(report):
        st.error("보고서 신뢰 경계·감사 무결성 검증 실패 — 표시와 다운로드를 차단했습니다.")
        return
    try:
        markdown = render_archived_sec_guard_markdown(report)
        # Export only backend allowlisted fields. Never include a supplied
        # ZIP path, raw original text, HTTP credentials or arbitrary metadata.
        export = {
            "schema": report["schema"],
            "status": report["status"],
            "research": report["research"],
            "evidence": report["evidence"],
            "verification": report["verification"],
            "risk": report["risk"],
            "review_summary": report["review_summary"],
            "guard": report["guard"],
            "audit": report["audit"],
            "human_review": report["human_review"],
            "source_authenticated": False,
            "financial_values_authenticated": False,
            "live_api_called": False,
            "trade_executed": False,
            "official_contest_submission": False,
        }
        encoded = json.dumps(export, ensure_ascii=False, sort_keys=True,
                             indent=2, allow_nan=False)
    except (TypeError, KeyError, ValueError):
        st.error("안전한 결과 포맷 검증 실패 — 내보내기를 차단했습니다.")
        return

    st.success("로컬 ZIP 검산 → Risk → Guard → SQLite 감사 기록 완료 (외부 출처 미인증)")
    a, b, c = st.columns(3)
    a.metric("검산", report["verification"]["status"])
    b.metric("Guard 판정", report["guard"]["decision"])
    c.metric("SQLite 감사·근거 연결", "PASS")
    st.warning(
        "로컬 ZIP·SHA 일치는 SEC 공식 원문 인증이 아닙니다. "
        "기관 투자 판단·수익률 예측·실거래·제출이 아닙니다."
    )
    source = report["research"]
    evidence = report["evidence"]
    audit = report["audit"]
    st.dataframe([
        {"항목": "기업 CIK (미인증)", "값": source["issuer_cik"]},
        {"항목": "접수번호 (미인증)", "값": source["accession"]},
        {"항목": "기준일 (자체 기록, 미인증)", "값": source["observed_utc_day_self_reported"]},
        {"항목": "원문 SHA-256", "값": evidence["original_filing_sha256"]},
        {"항목": "교차 근거 SHA-256", "값": evidence["evidence_chain_sha256"]},
        {"항목": "감사 실행 ID", "값": audit["run_id"]},
        {"항목": "감사 이벤트 SHA-256", "값": audit["event_hash"]},
        {"항목": "저장된 근거·Risk·Guard 재검증", "값": "PASS (로컬 SHA-256 연결)"},
    ], use_container_width=True, hide_index=True)
    st.subheader("사람 검토 후속 조치 (자동 승인 없음)")
    # The backend summary contains only predefined action/reason codes.
    summary = report["review_summary"]
    st.json({
        "priority": summary["review_priority"],
        "reason_codes": summary["reason_codes"],
        "review_actions": summary["review_actions"],
    })
    st.subheader("출처 → 검산 → 위험 → Guard → 감사 보고서")
    st.markdown(markdown)
    st.download_button(
        "미인증 로컬 감사 JSON 다운로드", data=encoded,
        file_name="proofinvest_LOCAL_SEC_GUARD_UNVERIFIED.json",
        mime="application/json", key="archived_sec_guard_json",
    )
    st.download_button(
        "미인증 로컬 감사 Markdown 다운로드", data=markdown,
        file_name="proofinvest_LOCAL_SEC_GUARD_UNVERIFIED.md",
        mime="text/markdown", key="archived_sec_guard_md",
    )


def render_archived_sec_guard(st) -> None:
    """Explicit local ZIP review. No implicit database creation or API calls."""
    st.title("ProofInvest — 저장 공시 ZIP → 검산·Risk·Guard 감사")
    st.warning(
        "OFFLINE_UNVERIFIED · 사용자가 이미 보관한 SEC 형식 ZIP만 읽습니다. "
        "출처·수집시각·권리·재무 사실은 외부 독립 인증되지 않았습니다. "
        "외부 SEC 조회·AI 매매·투자 권고·공식 제출은 실행하지 않습니다."
    )
    st.caption(
        "ZIP은 미리 로컬에 저장된 자료여야 합니다. 실행 버튼 전에는 "
        "DB 쓰기·원문 조회·네트워크 호출을 하지 않습니다. "
        "조회/판정 결과는 이전 제출 입력과 구분해 표시합니다."
    )
    with st.form("archived_sec_guard_local_form", clear_on_submit=False):
        bundle = st.text_input("로컬 3원문 ZIP 전체 경로", key="archived_sec_guard_bundle",
                               max_chars=1024)
        db = st.text_input("별도 SQLite 감사 DB 경로 (새 파일 가능)",
                           key="archived_sec_guard_db", max_chars=1024)
        current_end = st.text_input("당기 회계기간 종료일", value="2025-09-30",
                                    key="archived_sec_guard_current", max_chars=10)
        prior_end = st.text_input("전기 회계기간 종료일", value="2024-09-30",
                                  key="archived_sec_guard_prior", max_chars=10)
        needle = st.text_input("원문 바이트 앵커 (원문에서 찾을 문구)",
                               key="archived_sec_guard_needle", max_chars=128)
        claim = st.text_input("비교할 성장률 주장 % (선택)",
                              key="archived_sec_guard_claim", max_chars=100)
        run_id = st.text_input("감사 실행 ID (재실행 시 중복 기록 방지)",
                               key="archived_sec_guard_run_id", max_chars=128)
        action = st.selectbox("사람 검토 (선택)", _ACTIONS,
                              key="archived_sec_guard_action")
        reviewer = st.text_input("검토자 별칭 (검토 기록 시 필수)",
                                 key="archived_sec_guard_reviewer", max_chars=80)
        reason = st.text_area("검토 이유 (검토 기록 시 5자 이상)",
                              key="archived_sec_guard_reason", max_chars=1000)
        submitted = st.form_submit_button(
            "로컬 ZIP 검산·Risk·Guard 감사 실행",
            key="archived_sec_guard_submit",
        )
    if submitted:
        st.session_state.pop(_CACHE, None)
        try:
            if any(not text.strip() for text in (
                bundle, db, current_end, prior_end, needle, run_id
            )):
                raise ValueError("MISSING_REQUIRED_FIELDS")
            wants_review = action != "기록 없음"
            if not wants_review and (reviewer.strip() or reason.strip()):
                raise ValueError("REVIEW_ACTION_REQUIRED")
            report = run_archived_sec_guard_report(
                bundle_path=Path(bundle), audit_db_path=Path(db),
                current_end=current_end, prior_end=prior_end, needle=needle,
                run_id=run_id, claimed_growth_pct=claim.strip() or None,
                reviewer=reviewer if wants_review else None,
                action=action if wants_review else None,
                reason=reason if wants_review else None,
            )
            if not _safe_archived_report(report):
                raise ValueError("TRUST_BOUNDARY_FAILED")
            st.session_state[_CACHE] = report
        except (OSError, ValueError, TypeError, KeyError, ImportError, sqlite3.Error) as exc:
            # Exception messages can contain the user's Windows path or
            # untrusted source text; expose only a stable error category.
            allowed = {"FileNotFoundError", "PermissionError", "ValueError",
                       "TypeError", "KeyError", "OperationalError", "IntegrityError"}
            code = type(exc).__name__
            st.error(
                "로컬 공시 ZIP·검산·Guard 감사 검증 실패. "
                "결과·다운로드를 차단했습니다. 진단 코드: "
                + (code if code in allowed else "LOCAL_EVIDENCE_ERROR")
            )
    cached = st.session_state.get(_CACHE)
    if isinstance(cached, dict):
        _display_report(st, cached)
