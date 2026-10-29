"""Deterministic decision brief for the archived SEC-shaped evidence report.

This is a *review brief*, never authentication or investment advice. All
displayable text is authored from a fixed allowlist. No untrusted filings,
local paths, caller-supplied review notes or URLs can become prose.
"""
from __future__ import annotations

import re
from typing import Any

_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)

_ACTIONS = {
    "VERIFY_PROVIDER_ORIGIN_AND_RIGHTS":
        "공식 발행처 원문·수집 시각·재사용 권리를 독립적으로 확인",
    "RECONCILE_FINANCIAL_CLAIM":
        "서로 충돌하는 성장률 주장과 회계기간·단위·수치를 다시 대조",
    "REVIEW_LOCAL_RISK_FLAGS":
        "추가 원문을 확보한 뒤 위험 검토의 누락·충돌 사유를 확인",
    "INSPECT_IXBRL_CONTEXT_AND_UNITS":
        "원문 iXBRL의 계정·기간·단위·수정 공시 여부를 직접 점검",
    "LOCATE_ORIGINAL_NUMERIC_TEXT":
        "공시 본문에서 계산에 사용된 실제 숫자와 출처 위치를 대조",
}
_REASON_CODES = {
    "EXTERNAL_SOURCE_AUTHENTICITY_UNVERIFIED",
    "FINANCIAL_CLAIM_CONFLICT",
    "FINANCIAL_CALCULATION_UNAVAILABLE",
    "RISK_ASSESSMENT_UNAVAILABLE",
    "RISK_REVIEW_MISSING",
    "SOURCE_SPAN_MISSING",
    "FINANCIAL_REVIEW_MISSING",
}
_GUARD_REASONS = {
    "CLAIM_CONFLICT", "RISK_UNAVAILABLE", "INVALID_VERIFICATION",
    "SOURCE_NOT_DEMO_ELIGIBLE", "CLAIM_UNAVAILABLE",
}
_RISK_CODES = {
    "SOURCE_ORIGIN_UNAUTHENTICATED", "INPUT_SECTIONS_MISSING",
    "CLAIMED_GROWTH_CONFLICT", "FINANCIAL_CALCULATION_UNAVAILABLE",
    "SOURCE_DIGEST_MISSING", "SOURCE_SPAN_INVALID",
    "LOCAL_IXBRL_CONTEXT_MATCH_UNVERIFIED", "IXBRL_CONTEXT_NOT_CONFIRMED",
    "LOCAL_NUMERIC_TEXT_MATCH_UNVERIFIED", "NUMERIC_TEXT_MATCH_NOT_CONFIRMED",
    "LOCAL_EVIDENCE_REVIEW_ONLY",
}


def _allowed_codes(value: Any, allowed: set[str]) -> list[str]:
    if (type(value) is not list or len(value) > 30
            or any(type(code) is not str or code not in allowed for code in value)
            or len(set(value)) != len(value)):
        raise ValueError("INVALID_DECISION_BRIEF_CODES")
    return value


def build_archived_decision_brief(report: Any) -> dict[str, Any]:
    """Derive a narrow reviewer-facing decision from the audited report.

    The function rejects a forged cross-stage verdict or display data. Neither
    local SHA-256 nor the report's 'PASS' claims certify actual SEC origin.
    """
    if (not isinstance(report, dict)
            or report.get("schema") != "proofinvest.archived-sec-guard-report.v1"
            or report.get("status") != "local_archive_review_audited_unverified"
            or any(report.get(key) is not False for key in (
                "live_api_called", "source_authenticated", "source_rights_verified",
                "financial_values_authenticated", "model_trained",
                "investment_recommendation", "trade_executed",
                "official_contest_submission",
            ))):
        raise ValueError("UNTRUSTED_DECISION_BRIEF_REPORT")
    try:
        research = report["research"]
        evidence = report["evidence"]
        verification = report["verification"]
        risk = report["risk"]
        guard = report["guard"]
        audit = report["audit"]
        summary = report["review_summary"]
    except (KeyError, TypeError) as exc:
        raise ValueError("INCOMPLETE_DECISION_BRIEF") from exc
    if not all(type(x) is dict for x in (
            research, evidence, verification, risk, guard, audit, summary)):
        raise ValueError("INVALID_DECISION_BRIEF_SECTIONS")
    if (research.get("status") != "offline_local_metadata_only"
            or research.get("origin_authenticated") is not False
            or not isinstance(research.get("issuer_cik"), str)
            or _CIK.fullmatch(research["issuer_cik"]) is None
            or research["issuer_cik"] == "0000000000"
            or not isinstance(research.get("accession"), str)
            or _ACCESSION.fullmatch(research["accession"]) is None
            or not research["accession"].startswith(research["issuer_cik"] + "-")
            or evidence.get("source_span_authenticates_financial_claim") is not False
            or any(not isinstance(evidence.get(key), str)
                   or _SHA.fullmatch(evidence[key]) is None for key in (
                        "submissions_sha256", "companyfacts_sha256",
                        "original_filing_sha256", "evidence_chain_sha256",
                   ))):
        raise ValueError("INVALID_LOCAL_EVIDENCE_SCOPE")
    financial_status = verification.get("status")
    expected = {"calculated_unverified": "HOLD", "conflict": "REJECT"}.get(financial_status)
    if expected is None:
        raise ValueError("FINANCIAL_REVIEW_NOT_ELIGIBLE")
    if (verification.get("arithmetic_is_source_authentication") is not False
            or risk.get("source_authenticated") is not False
            or risk.get("risk_is_investment_recommendation") is not False
            or guard.get("decision") != expected
            or guard.get("source_authenticated") is not False
            or guard.get("trade_executed") is not False
            or guard.get("human_approved") is not False
            or audit.get("verified_against_persisted_request") is not True
            or audit.get("chain_valid") is not True
            or audit.get("human_review_integrity_valid") is not True
            or audit.get("externally_anchored") is not False
            or audit.get("bound_source_evidence_sha256")
                != evidence["evidence_chain_sha256"]
            or audit.get("bound_guard_decision") != expected
            or summary.get("schema") != "proofinvest.offline-review-summary.v1"
            or summary.get("status") != "human_review_required"
            or summary.get("financial_status") != financial_status
            or summary.get("risk_status") != risk.get("status")
            or summary.get("source_authenticated") is not False
            or summary.get("investment_recommendation") is not False
            or summary.get("trade_authorized") is not False
            or summary.get("external_http_called") is not False):
        raise ValueError("DECISION_BRIEF_CROSS_STAGE_MISMATCH")
    codes = _allowed_codes(risk.get("reason_codes"), _RISK_CODES)
    reason_codes = _allowed_codes(guard.get("reason_codes"), _GUARD_REASONS)
    triage_codes = _allowed_codes(summary.get("reason_codes"), _REASON_CODES)
    actions = summary.get("review_actions")
    if (type(actions) is not list or any(
            type(action) is not str or action not in _ACTIONS for action in actions)
            or len(set(actions)) != len(actions)):
        raise ValueError("INVALID_DECISION_BRIEF_ACTIONS")
    if ("SOURCE_ORIGIN_UNAUTHENTICATED" not in codes
            or "RISK_UNAVAILABLE" not in reason_codes
            or summary.get("ixbrl_context_match") not in (True, False)
            or summary.get("numeric_text_match") not in (True, False)):
        raise ValueError("REQUIRED_EVIDENCE_UNAVAILABLE")
    if financial_status == "conflict":
        if (risk.get("status") != "unavailable"
                or summary.get("review_priority") != "high"
                or "CLAIM_CONFLICT" not in reason_codes
                or "CLAIMED_GROWTH_CONFLICT" not in codes
                or "FINANCIAL_CLAIM_CONFLICT" not in triage_codes):
            raise ValueError("CLAIM_CONFLICT_ESCALATION_MISSING")
    elif (risk.get("status") != "reviewed_unverified"
            or summary.get("review_priority") != "normal"
            or "CLAIM_CONFLICT" in reason_codes
            or "FINANCIAL_CLAIM_CONFLICT" in triage_codes):
        raise ValueError("UNVERIFIED_HOLD_ESCALATION_MISSING")
    expected_actions = ["VERIFY_PROVIDER_ORIGIN_AND_RIGHTS"]
    if financial_status == "conflict":
        expected_actions.append("RECONCILE_FINANCIAL_CLAIM")
    if risk.get("status") != "reviewed_unverified":
        expected_actions.append("REVIEW_LOCAL_RISK_FLAGS")
    if summary["ixbrl_context_match"] is False:
        expected_actions.append("INSPECT_IXBRL_CONTEXT_AND_UNITS")
    if summary["numeric_text_match"] is False:
        expected_actions.append("LOCATE_ORIGINAL_NUMERIC_TEXT")
    if actions != expected_actions:
        raise ValueError("REVIEW_ACTIONS_DO_NOT_FOLLOW_EVIDENCE")
    for key in ("event_hash",):
        if not isinstance(audit.get(key), str) or _SHA.fullmatch(audit[key]) is None:
            raise ValueError("INVALID_AUDIT_EVENT_HASH")
    headline = ("원본 인증이 없어 사람 검토 전까지 판단을 보류했습니다."
                if expected == "HOLD" else
                "제시된 성장률 주장이 로컬 재계산과 충돌해 판단을 거절했습니다.")
    detail = ("저장 자료의 산술 계산은 완료됐지만, 출처·수집시각·권리의"
              " 독립 검증이 없어 투자 판단은 승인되지 않습니다."
              if expected == "HOLD" else
              "회계 수치와 비교 주장이 서로 달라 재검증이 필요합니다."
              " 출처 인증 여부와 무관하게 현재 주장은 통과할 수 없습니다.")
    return {
        "schema": "proofinvest.archived-decision-brief.v1",
        "decision": expected,
        "headline": headline,
        "rationale": detail,
        "priority": summary["review_priority"],
        "checks": [
            {"code": "LOCAL_3SOURCE_DIGESTS", "status": "LOCAL_ONLY",
             "meaning": "로컬 ZIP 내부 3원문과 기록된 SHA-256 일치"},
            {"code": "LOCAL_GROWTH_CALCULATION", "status": (
                "CLAIM_CONFLICT" if expected == "REJECT" else "CALCULATED_UNVERIFIED"),
             "meaning": ("성장률 주장과 재계산 수치 불일치" if expected == "REJECT"
                         else "저장된 숫자의 산술 재계산 완료, 실제 회계사실 미인증")},
            {"code": "LOCAL_RISK_SCREEN", "status": "UNVERIFIED",
             "meaning": "독립 인증된 위험 입력이 없어 투자 승인 판단 불가"},
            {"code": "LOCAL_GUARD_AUDIT", "status": "BOUND_LOCAL_ONLY",
             "meaning": "현재 근거 해시·Risk·Guard가 저장된 SQLite 감사 이벤트와 일치"},
        ],
        "unverified": [
            "SEC 원본·기업 실재·접수 식별자 출처 진위",
            "공시 당시 공개 여부와 수집시각의 외부 증빙",
            "원문 데이터의 재사용·재배포 권리",
            "재무제표 금액·iXBRL 계정/기간/단위의 독립 검산",
            "외부에 고정된 변경 불가능한 감사 기록",
        ],
        "next_actions": [
            {"code": action, "meaning": _ACTIONS[action]} for action in actions
        ],
        "audit_scope": "로컬 바이트·산술·SQLite 기록 연결만 확인",
        "financial_advice": False,
        "trade_executed": False,
        "external_source_authenticated": False,
        "official_contest_submission": False,
    }
