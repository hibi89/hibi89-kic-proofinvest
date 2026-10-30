"""Synthetic-only Streamlit view of the real local SEC -> Guard pipeline.

The input documents and issuer are fictional. No external network, persisted
user DB, file upload, LLM, live source certification or transaction.
"""
from __future__ import annotations

import hashlib
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
from .local_sec_html_report import render_local_sec_html

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


def export_synthetic_guard_json(report: dict[str, Any]) -> bytes:
    """Bounded unverified synthetic report only, never an issuer certificate."""
    required_limits = {
        "external_source_authenticated",
        "source_rights_verified",
        "live_api_called",
        "ai_agent_executed",
        "trade_executed",
        "simulation_authorized",
        "official_contest_submission",
    }
    if (type(report) is not dict
            or report.get("schema") != "proofinvest.local-sec-guard-report.v1"
            or report.get("mode") != "OFFLINE_USER_SUPPLIED_UNAUTHENTICATED"
            or not isinstance(report.get("issuer"), dict)
            or report["issuer"].get("cik") != SYNTHETIC_CIK
            or report["issuer"].get("accession") != SYNTHETIC_ACCESSION
            or not isinstance(report.get("guard"), dict)
            or report["guard"].get("decision") not in ("HOLD", "REJECT")
            or report.get("audit_chain_valid") is not True
            or report.get("human_review_integrity_valid") is not True
            or report.get("human_review") is not None
            or type(report.get("limits")) is not dict
            or set(report["limits"]) != required_limits
            or any(value is not False for value in report["limits"].values())):
        raise ValueError("SYNTHETIC_EXPORT_BLOCKED")
    # Identity flags by themselves do not bind the report to the fixed
    # synthetic fixture. Cross-check hashes, arithmetic, and Guard decisions
    # so a modified numeric or byte-source report cannot be exported as a
    # reproduced judge demo. This is NOT real SEC source authentication.
    expected_submissions = hashlib.sha256(synthetic_submissions()).hexdigest()
    expected_facts = hashlib.sha256(json.dumps(
        synthetic_companyfacts(), sort_keys=True,
    ).encode("utf-8")).hexdigest()
    script_only_html = (
        b"<html><script>" + PHRASE.encode("ascii")
        + b"</script><body>No evidence here</body></html>"
    )
    normal_source_hash = hashlib.sha256(SYNTHETIC_HTML).hexdigest()
    script_source_hash = hashlib.sha256(script_only_html).hexdigest()
    source = report.get("source")
    verify = report.get("verification")
    risk = report.get("risk")
    guard = report.get("guard")
    if not all(type(section) is dict for section in (source, verify, risk, guard)):
        raise ValueError("SYNTHETIC_EXPORT_BLOCKED")
    original_hash = source.get("archived_original_sha256")
    script_only = original_hash == script_source_hash
    if (source.get("submissions_sha256") != expected_submissions
            or source.get("companyfacts_sha256") != expected_facts
            or original_hash not in (normal_source_hash, script_source_hash)
            or source.get("html_text_node_status") != (
                "unavailable" if script_only
                else "untrusted_html_text_node_literal_located"
            )
            or source.get("exact_raw_byte_span_verified") is not (not script_only)
            or verify.get("prior_amount") != "100"
            or verify.get("current_amount") != "200"
            or verify.get("growth_pct") != "100.00"
            or verify.get("status") not in ("calculated_unverified", "conflict")
            or verify.get("reason_code") != (
                "GROWTH_CLAIM_CONFLICT" if verify.get("status") == "conflict"
                else "STRUCTURAL_NUMERIC_COMPARISON_ONLY"
            )
            or risk.get("source_authenticated") is not False
            or risk.get("trade_authorized") is not False
            or guard.get("decision") != (
                "REJECT" if verify.get("status") == "conflict" else "HOLD"
            )
            or guard.get("source_authenticated") is not False
            or guard.get("trade_executed") is not False):
        raise ValueError("SYNTHETIC_EXPORT_BLOCKED")
    payload = {
        "schema": "proofinvest.synthetic-sec-guard-export.v1",
        "evidence_class": "SYNTHETIC_ONLY_UNVERIFIED",
        "external_source_authenticated": False,
        "not_investment_advice": True,
        "report": report,
    }
    try:
        encoded = (json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ) + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError) as exc:
        raise ValueError("SYNTHETIC_EXPORT_BLOCKED") from exc
    if len(encoded) > 65536:
        raise ValueError("SYNTHETIC_EXPORT_TOO_LARGE")
    return encoded


def export_synthetic_guard_markdown(report: dict[str, Any]) -> bytes:
    """Readable judge copy bound to the exact same synthetic export contract."""
    safe = json.loads(export_synthetic_guard_json(report))
    r = safe["report"]
    fin = r["verification"]
    src = r["source"]
    guard = r["guard"]
    decision = guard["decision"]
    caveat = (
        "The literal is within a raw HTML text node, but issuer/source truth "
        "has NOT been authenticated."
        if src["exact_raw_byte_span_verified"] else
        "A literal was found only in script/non-visible markup. The citation "
        "is UNAVAILABLE."
    )
    lines = [
        "# ProofInvest | SYNTHETIC / UNVERIFIED Judge Review",
        "",
        "**This is a fictional offline test, not real SEC issuer evidence, investment "
        "advice, a trained AI agent, or a KIC submission.**",
        "",
        "## 1. Decision and next action",
        f"- Guard result: **{decision}** (never trade/approve)",
        "- Reason codes: " + ", ".join(guard["reason_codes"]),
        "- Human action: independently verify source and missing Risk evidence",
        "",
        "## 2. Artificial financial check",
        f"- Prior year: USD {fin['prior_amount']}",
        f"- Current year: USD {fin['current_amount']}",
        f"- Change: {fin['growth_pct']}%",
        "- Arithmetic status: " + fin["status"],
        "- Reason: " + fin["reason_code"],
        "",
        "## 3. Source byte evidence",
        "- Fictional CIK: " + r["issuer"]["cik"],
        "- Fictional accession: " + r["issuer"]["accession"],
        "- Submissions SHA-256: " + src["submissions_sha256"],
        "- CompanyFacts SHA-256: " + src["companyfacts_sha256"],
        "- Original HTML SHA-256: " + src["archived_original_sha256"],
        "- Text-node check: " + src["html_text_node_status"],
        "- Citation caveat: " + caveat,
        "",
        "## 4. Risk, Guard and audit",
        "- Risk status: " + r["risk"]["status"],
        "- Risk reasons: " + ", ".join(r["risk"]["reason_codes"]),
        "- Audit hash: " + r["audit"]["event_hash"],
        "- SQLite chain verified: YES (local consistency only)",
        "- Human review integrity: YES (local consistency only)",
        "",
        "## 5. Explicit limitations",
        "- Source issuer identity/authenticity: NOT VERIFIED",
        "- Original publication or redistribution rights: NOT VERIFIED",
        "- Live SEC/LLM/real-time financial data: NONE",
        "- Trading, simulation authorization, or official contest upload: NONE",
        "- All source data and financial values in this document are SYNTHETIC.",
        "",
    ]
    result = ("\n".join(lines)).encode("utf-8")
    if len(result) > 32768:
        raise ValueError("SYNTHETIC_MARKDOWN_TOO_LARGE")
    return result


def build_synthetic_case_comparison() -> list[dict[str, Any]]:
    """Execute all three actual local Guard paths only on explicit user click."""
    rows: list[dict[str, Any]] = []
    expected = {
        "matched": ("calculated_unverified", "HOLD",
                    "untrusted_html_text_node_literal_located"),
        "conflict": ("conflict", "REJECT",
                     "untrusted_html_text_node_literal_located"),
        "script": ("calculated_unverified", "HOLD", "unavailable"),
    }
    for label, case in SCENARIOS.items():
        report = run_synthetic_guard_case(case)
        # Reuse the single-case strict export contract before adding the row.
        export_synthetic_guard_json(report)
        financial, decision, citation = expected[case]
        if (report["verification"]["status"] != financial
                or report["guard"]["decision"] != decision
                or report["source"]["html_text_node_status"] != citation
                or report["audit_chain_valid"] is not True
                or report["guard"]["trade_executed"] is not False):
            raise ValueError("SYNTHETIC_COMPARISON_CASE_MISMATCH")
        rows.append({
            "사례": label,
            "매출 검산": financial,
            "원문 인용": "로컬 바이트 확인" if citation != "unavailable" else "사용 불가",
            "Risk": report["risk"]["status"],
            "Guard": decision,
            "SQLite 감사": "PASS",
            "실거래": "없음",
        })
    if len(rows) != 3:
        raise ValueError("SYNTHETIC_COMPARISON_INCOMPLETE")
    return rows


def export_synthetic_comparison_json(rows: list[dict[str, Any]]) -> bytes:
    """Provide a bounded public summary; no user-supplied source bytes."""
    required = {"사례", "매출 검산", "원문 인용", "Risk",
                "Guard", "SQLite 감사", "실거래"}
    if (type(rows) is not list or len(rows) != 3
            or any(type(row) is not dict or set(row) != required
                   or row["SQLite 감사"] != "PASS"
                   or row["실거래"] != "없음" for row in rows)
            or [row["사례"] for row in rows] != list(SCENARIOS)):
        raise ValueError("SYNTHETIC_COMPARISON_EXPORT_BLOCKED")
    expected_decisions = ("HOLD", "REJECT", "HOLD")
    expected_states = ("calculated_unverified", "conflict", "calculated_unverified")
    expected_citations = ("로컬 바이트 확인", "로컬 바이트 확인", "사용 불가")
    if any(row["Guard"] != expected_decisions[i]
           or row["매출 검산"] != expected_states[i]
           or row["원문 인용"] != expected_citations[i]
           or row["Risk"] not in ("reviewed_unverified", "unavailable")
           for i, row in enumerate(rows)):
        raise ValueError("SYNTHETIC_COMPARISON_EXPORT_BLOCKED")
    payload = {
        "schema": "proofinvest.synthetic-guard-compare.v1",
        "evidence_class": "SYNTHETIC_ONLY_UNVERIFIED",
        "source_authenticated": False,
        "live_api_called": False,
        "trade_executed": False,
        "official_contest_submission": False,
        "cases": rows,
    }
    content = (json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ) + "\n").encode("utf-8")
    if len(content) > 8192:
        raise ValueError("SYNTHETIC_COMPARISON_EXPORT_OVERSIZED")
    return content


def render_synthetic_guard_ui(st) -> None:
    """Judge-first overview, with every decision backed by the real offline path."""
    st.title("ProofInvest — SEC 근거부터 Guard 감사까지")
    st.markdown(
        '<div class="pi-eyebrow">CASE REVIEW / 01 — 실증 가능한 오프라인 경로</div>',
        unsafe_allow_html=True,
    )
    st.warning(
        "SYNTHETIC ONLY · 가상 기업·인공 공시 자료입니다. SEC 조회·"
        "실제 원문 인증·AI Agent·투자 권고·거래·DAKER 제출은 없습니다."
    )
    st.caption(
        "연구 → 수치 검증 → Risk 근거 보류 → Guard → SQLite 감사. "
        "원본은 로컬 합성 데이터이며, 실행 후 임시 DB는 삭제됩니다."
    )

    st.markdown(
        """
<div class="pi-judge-hero">
  <div class="pi-judge-kicker">THE EVIDENCE-FIRST DECISION</div>
  <h2>숫자가 맞아도, 근거가 부족하면 승인하지 않는다.</h2>
  <p>ProofInvest는 원문 근거와 수치를 교차 검증하고, 불확실성을
  HOLD 또는 REJECT로 남깁니다. 아래는 실제 SEC 조회가 아닌
  합성 데이터 기반 시연입니다.</p>
</div>
<div class="pi-judge-grid">
  <div class="pi-judge-card">
    <div class="step">CASE 01 / MATCH</div>
    <h3>숫자는 일치</h3>
    <span class="decision">HOLD</span>
    <p>산술 일치만으로 발행사 출처나 Risk 근거를 인증할 수 없습니다.</p>
  </div>
  <div class="pi-judge-card">
    <div class="step">CASE 02 / CONFLICT</div>
    <h3>주장과 계산 불일치</h3>
    <span class="decision reject">REJECT</span>
    <p>성장률 주장이 충돌하면 임의 보정하거나 승인하지 않습니다.</p>
  </div>
  <div class="pi-judge-card">
    <div class="step">CASE 03 / CITATION</div>
    <h3>보이는 원문 근거 없음</h3>
    <span class="decision">HOLD</span>
    <p>스크립트 안의 숫자를 실제 본문 인용으로 인정하지 않습니다.</p>
  </div>
</div>
<div class="pi-judge-steps">SOURCE BYTES → NUMERIC CHECK → RISK REVIEW →
  GUARD DECISION → SQLITE AUDIT → EXPORT</div>
""",
        unsafe_allow_html=True,
    )
    st.caption(
        "위 세 판정은 실행 전 안내용 예상 결과입니다. "
        "시나리오 검증 또는 3개 일괄 비교를 눌러야 실제 로컬 코드가 실행됩니다."
    )

    with st.container(border=True):
        st.markdown("#### 01 / 검증할 상황 선택")
        st.caption("서로 다른 3가지 수치·인용 상태에서 Guard가 어떻게 판단하는지 비교합니다.")
        choice = st.selectbox("검증 시나리오", list(SCENARIOS), key="sec_guard_case")
        first, second = st.columns(2)
        with first:
            clicked = st.button(
                "합성 SEC→Guard 검증 실행",
                key="sec_guard_execute",
                type="primary",
                use_container_width=True,
            )
        with second:
            compare_clicked = st.button(
                "3개 시나리오 일괄 비교",
                key="sec_guard_compare",
                use_container_width=True,
            )
    if compare_clicked:
        try:
            comparison = build_synthetic_case_comparison()
            comparison_json = export_synthetic_comparison_json(comparison)
            # Import only for an explicit three-case click. The pack module
            # imports this UI's validated pure synthetic functions; no cyclic
            # import occurs until the UI module has finished loading.
            from scripts.sec_guard_judge_pack import build_bytes, verify_bytes
            bundle = build_bytes()
            receipt = verify_bytes(bundle)
            if (receipt["cases"] != 3 or receipt["files"] != 10
                    or receipt["external_source_authenticated"] is not False
                    or receipt["official_submission"] is not False):
                raise ValueError("SYNTHETIC_JUDGE_BUNDLE_INTEGRITY_FAILED")
        except (ValueError, OSError, KeyError, TypeError, OverflowError):
            st.error("비교 시나리오의 실제 실행·감사 검증 실패로 결과를 차단했습니다.")
            return
        st.subheader("3가지 사례 · 로컬 실제 코드 실행 비교")
        passed = sum(row["SQLite 감사"] == "PASS" for row in comparison)
        blocked = sum(row["Guard"] == "REJECT" for row in comparison)
        held = sum(row["Guard"] == "HOLD" for row in comparison)
        k1, k2, k3 = st.columns(3)
        k1.metric("로컬 SQLite 무결성", f"{passed}/3 PASS")
        k2.metric("검증 보류", f"{held} HOLD")
        k3.metric("주장 충돌 차단", f"{blocked} REJECT")
        st.dataframe(comparison, use_container_width=True, hide_index=True)
        st.info(
            "심사 포인트: 같은 가상 원문·숫자라도 주장 충돌은 REJECT, "
            "출처 또는 인용 근거가 불충분하면 HOLD로 구분됩니다. "
            "어느 경우에도 실거래와 외부 출처 인증은 수행되지 않습니다."
        )
        st.download_button(
            "합성 비교 매트릭스 JSON",
            data=comparison_json,
            mime="application/json",
            file_name="proofinvest_SYNTHETIC_COMPARISON.json",
            key="sec_guard_comparison_export",
            on_click="ignore",
        )
        st.download_button(
            "전체 합성 증빙 ZIP (시작 페이지 포함)",
            data=bundle,
            mime="application/zip",
            file_name="proofinvest_SYNTHETIC_GUARD_JUDGE.zip",
            key="sec_guard_full_judge_pack",
            on_click="ignore",
        )
        st.caption("ZIP 안의 START_HERE.html을 열면 세 가지 오프라인 보고서를 볼 수 있습니다.")
        st.warning("세 사례 모두 가상 SEC 형식 자료이며, 실제 투자 적격성·출처 인증을 뜻하지 않습니다.")
        return
    if not clicked:
        st.info("실행 전에는 DB를 만들지 않습니다. 파일 업로드·외부 호출 없음.")
        with st.expander("심사 60초 시연 순서", expanded=False):
            st.markdown(
                "1. **수치 일치** 선택 → 검증 실행 → HOLD와 로컬 감사 해시 확인.\n"
                "2. **주장 불일치** 선택 → 검증 실행 → REJECT 이유 확인.\n"
                "3. **3개 시나리오 일괄 비교** → 3/3 감사 영수증과 ZIP 다운로드.\n"
                "이 시연은 가상 SEC 형식 자료이며 실제 SEC 조회·인증·거래가 아닙니다."
            )
        st.markdown(
            '<div class="pi-disclaimer"><strong>검증 대상</strong> · '
            '수치 일치 / 주장 충돌 / 스크립트 인용 차단. '
            '모든 결과는 실데이터 인증이나 투자 판단이 아닌 로컬 동작 재현입니다.</div>',
            unsafe_allow_html=True,
        )
        return

    try:
        report = run_synthetic_guard_case(SCENARIOS[choice])
        safe_json = export_synthetic_guard_json(report)
        safe_markdown = export_synthetic_guard_markdown(report)
        safe_html = render_local_sec_html(report)
    except (ValueError, OSError, KeyError, TypeError, OverflowError):
        st.error("로컬 검증 또는 보고서 안전 검사 실패 — 결과 표시와 내보내기를 차단했습니다.")
        return

    fin = report["verification"]
    source = report["source"]
    guard = report["guard"]
    risk = report["risk"]
    st.markdown(
        '<div class="pi-eyebrow">RESULT / 02 — 숫자보다 중요한 검증 상태</div>',
        unsafe_allow_html=True,
    )
    a, b, c = st.columns(3)
    a.metric("수치 검산", fin["status"])
    b.metric("Guard 판정", guard["decision"])
    c.metric("외부 원문 인증", "미인증")
    desc = {
        "matched": "숫자는 일치하지만 출처와 위험 근거를 인증하지 못해 HOLD",
        "conflict": "주장과 계산이 충돌하여 REJECT; 숫자를 임의로 수정하지 않음",
        "script": "인용이 본문이 아닌 스크립트에만 있어 HOLD; 인용 근거 불가",
    }[SCENARIOS[choice]]
    cls = "pi-case--blocked" if guard["decision"] == "REJECT" else ""
    st.markdown(
        '<div class="pi-case ' + cls + '"><strong>' + guard["decision"]
        + '</strong> — ' + desc + '</div>',
        unsafe_allow_html=True,
    )
    # A judge can see the actionable human handoff without guessing what
    # an unverified result should mean. These are static instructions for
    # fictional cases, NOT approval, investment advice, or an autonomous step.
    human_next_steps = {
        "matched": (
            "다음 조치 / 출처 독립 확인",
            "재무 수치가 일치하더라도 발행사 원본과 사용 권리, "
            "부채·자본 Risk 근거를 별도로 검토해야 합니다.",
        ),
        "conflict": (
            "다음 조치 / 성장률 주장 재검증",
            "원문에 기록된 두 기간의 수치를 재확인하고 주장 입력을 "
            "검토할 때까지 승인하지 않습니다.",
        ),
        "script": (
            "다음 조치 / 본문 인용 근거 요청",
            "HTML 스크립트 안의 문자열은 인용 증거로 인정하지 않고 "
            "사용자가 볼 수 있는 원문 텍스트 근거를 요청합니다.",
        ),
    }
    action_title, action_detail = human_next_steps[SCENARIOS[choice]]
    st.subheader(action_title)
    st.info(action_detail)
    st.caption("검증 코드: " + ", ".join(guard["reason_codes"]))

    with st.container(border=True):
        st.markdown("#### 03 / 실제 모듈 실행 추적")
        st.dataframe(
            [
                {"단계": "Research", "검증 상태": source["evidence_link_status"],
                 "의미": "원문 바이트·SHA 연결 (진위 미확인)"},
                {"단계": "Verification", "검증 상태": fin["reason_code"],
                 "의미": "가상 매출 수치의 산술 비교"},
                {"단계": "Risk", "검증 상태": risk["status"],
                 "의미": "인증된 부채·자본 근거 부족"},
                {"단계": "Guard", "검증 상태": guard["decision"],
                 "의미": "승인·거래를 허용하지 않음"},
                {"단계": "Audit", "검증 상태": "PASS" if report["audit_chain_valid"] else "BLOCKED",
                 "의미": "임시 SQLite 체인 무결성"},
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "HTML 인용 검증: " + source["html_text_node_status"]
            + " · 원문 SHA256: " + source["archived_original_sha256"]
        )

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("#### 04 / 재무 수치")
            st.metric("연매출 변화 · 가상 수치", fin["growth_pct"] + "%")
            st.dataframe([
                {"기간": fin["prior_period_end"], "매출 (USD · 가상)": fin["prior_amount"]},
                {"기간": fin["current_period_end"], "매출 (USD · 가상)": fin["current_amount"]},
            ], use_container_width=True, hide_index=True)
            st.caption("숫자 일치는 독립적인 원문 인증이 아닙니다.")
    with c2:
        with st.container(border=True):
            st.markdown("#### 05 / 감사 영수증")
            st.caption("감사 해시 앞 16자리 (로컬 저장 일치만 확인)")
            st.code(report["audit"]["event_hash"][:16] + "...", language="text")
            st.metric("감사 체인", "PASS" if report["audit_chain_valid"] else "BLOCKED")
            st.caption("모든 Guard 판정은 실제 주문을 실행하지 않습니다.")

    with st.expander("기술 증빙 · 세부 근거와 제한", expanded=False):
        st.json({
            "audit": report["audit"],
            "guard_reasons": guard["reason_codes"],
            "risk_reasons": risk["reason_codes"],
            "source_hashes": {
                "submissions": source["submissions_sha256"],
                "companyfacts": source["companyfacts_sha256"],
                "original": source["archived_original_sha256"],
            },
            "limits": report["limits"],
        })

    st.markdown("#### 06 / 보고서 내보내기")
    left, middle, right = st.columns(3)
    with left:
        st.download_button(
            "합성 감사 JSON",
            data=safe_json,
            file_name="proofinvest_SYNTHETIC_SEC_GUARD_UNVERIFIED.json",
            mime="application/json",
            key="sec_guard_synthetic_export",
            on_click="ignore",
            use_container_width=True,
        )
    with middle:
        st.download_button(
            "심사용 Markdown",
            data=safe_markdown,
            file_name="proofinvest_SYNTHETIC_SEC_GUARD_REVIEW.md",
            mime="text/markdown",
            key="sec_guard_synthetic_markdown",
            on_click="ignore",
            use_container_width=True,
        )
    with right:
        st.download_button(
            "오프라인 HTML 보고서",
            data=safe_html,
            file_name="proofinvest_SYNTHETIC_SEC_GUARD_REVIEW.html",
            mime="text/html",
            key="sec_guard_synthetic_html",
            on_click="ignore",
            use_container_width=True,
        )
    st.caption("세 형식 모두 합성 시연 결과만 포함하며, 공식 SEC·대회 인증 자료가 아닙니다.")
    st.warning("감사 해시 일치는 원문 진위/사용권리/투자 적격성 검증이 아닙니다.")
