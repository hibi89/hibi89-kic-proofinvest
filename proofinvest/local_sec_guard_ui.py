"""Synthetic-only Streamlit view of the real local SEC -> Guard pipeline.

The input documents and issuer are fictional. No external network, persisted
user DB, file upload, LLM, live source certification or transaction.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from .kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from .local_sec_guard_report import review_local_sec_with_guard

SCENARIOS = {
    "수치 일치 → HOLD": "matched",
    "주장 불일치 → REJECT": "conflict",
    "스크립트에만 있는 인용 → HOLD": "script",
}


def run_synthetic_guard_case(case: str) -> dict[str, Any]:
    """Actually run source validation, Guard and SQLite with disposable bytes."""
    if case not in SCENARIOS.values():
        raise ValueError("INVALID_SYNTHETIC_CASE")
    claimed = "300.00" if case == "conflict" else "100.00"
    original = (
        b"<html><script>" + PHRASE.encode("ascii")
        + b"</script><body>No evidence here</body></html>"
        if case == "script" else SYNTHETIC_HTML
    )
    with TemporaryDirectory(prefix="kic-sec-guard-synthetic-") as tmp:
        report = review_local_sec_with_guard(
            submissions_json=synthetic_submissions(),
            companyfacts_json=json.dumps(
                synthetic_companyfacts(), sort_keys=True
            ).encode("utf-8"),
            original_filing=original,
            cik=SYNTHETIC_CIK,
            accession=SYNTHETIC_ACCESSION,
            as_of=AS_OF, collected_at=COLLECTED_AT,
            current_end="2025-09-30",
            prior_end="2024-09-30",
            needle=PHRASE, claimed_growth_pct=claimed,
            audit_db_path=Path(tmp) / "audit.sqlite",
            run_id="synthetic-ui-demo",
        )
    if (report.get("schema") != "proofinvest.local-sec-guard-report.v1"
            or report.get("mode") != "OFFLINE_USER_SUPPLIED_UNAUTHENTICATED"
            or not report.get("audit_chain_valid")
            or not report.get("human_review_integrity_valid")
            or any(v is not False for v in report.get("limits", {}).values())):
        raise ValueError("SYNTHETIC_GUARD_INTEGRITY_UNAVAILABLE")
    expected = "REJECT" if case == "conflict" else "HOLD"
    if report["guard"]["decision"] != expected:
        raise ValueError("SYNTHETIC_GUARD_DECISION_MISMATCH")
    if case == "script" and report["source"]["html_text_node_status"] != "unavailable":
        raise ValueError("SCRIPT_CITATION_NOT_BLOCKED")
    return report


def render_synthetic_guard_ui(st) -> None:
    st.title("ProofInvest — SEC 근거부터 Guard 감사까지")
    st.warning(
        "SYNTHETIC ONLY · 가상 기업·인공 공시 자료입니다. SEC 조회·"
        "실제 원문 인증·AI Agent·투자 권고·거래·DAKER 제출은 없습니다."
    )
    st.caption(
        "출처 연결 → 숫자 검산 → 미인증 Risk → Guard → SQLite 감사 → 보고서. "
        "버튼을 눌렀을 때만 실행하며, 감사 DB는 임시 생성 후 삭제됩니다."
    )
    choice = st.selectbox("검증 시나리오", list(SCENARIOS), key="sec_guard_case")
    if not st.button("합성 SEC→Guard 검증 실행", key="sec_guard_execute"):
        st.info("실행 전에는 DB를 만들지 않습니다. 파일 업로드·외부 호출 없음.")
        return
    try:
        report = run_synthetic_guard_case(SCENARIOS[choice])
    except (ValueError, OSError, KeyError, TypeError, OverflowError):
        st.error("로컬 원문·검산·감사 연결 검증에 실패하여 결과를 표시하지 않습니다.")
        return
    x, y, z = st.columns(3)
    x.metric("수치 검산", report["verification"]["status"])
    y.metric("Guard 판정", report["guard"]["decision"])
    z.metric("외부 원문 인증", "미인증")
    st.subheader("단계별 감사 추적")
    st.dataframe([
        {"단계": "Research", "상태": report["source"]["evidence_link_status"],
         "설명": "가상 출처 식별자·원문 해시 연결"},
        {"단계": "Verification", "상태": report["verification"]["reason_code"],
         "설명": "합성 수치의 산술 검산"},
        {"단계": "Risk", "상태": report["risk"]["status"],
         "설명": "인증된 위험 수치 없어 보류"},
        {"단계": "Guard", "상태": report["guard"]["decision"],
         "설명": "HOLD 또는 REJECT — 실행 불가"},
        {"단계": "Audit", "상태": "PASS" if report["audit_chain_valid"] else "BLOCKED",
         "설명": "임시 SQLite 해시 체인 검증"},
    ], use_container_width=True, hide_index=True)
    st.caption(
        "HTML 인용 검증: " + report["source"]["html_text_node_status"]
        + " · 원문 SHA256: " + report["source"]["archived_original_sha256"]
    )
    with st.expander("합성 감사 영수증", expanded=False):
        st.json({
            "audit": report["audit"],
            "guard_reasons": report["guard"]["reason_codes"],
            "source_hashes": {
                "submissions": report["source"]["submissions_sha256"],
                "companyfacts": report["source"]["companyfacts_sha256"],
                "original": report["source"]["archived_original_sha256"],
            },
            "limitations": report["limits"],
        })
    st.warning("감사 해시 일치는 원문 진위/사용권리/투자 적격성 검증이 아닙니다.")
