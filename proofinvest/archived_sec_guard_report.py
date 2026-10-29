"""ProofInvest offline SEC-shaped ZIP -> source review -> Guard -> SQLite report.

The archive may be user-supplied or self-reported. A matching SHA256 validates
local bytes only; it NEVER validates SEC provenance, publication timing, issuer
truth, redistribution rights, financial facts, or a trading recommendation.
No external network, broker, model or contest endpoint is called.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from .guard_audit import GuardAuditStore
from .guard_bound_audit import verify_bound_guard_audit
from .decision_brief import build_archived_decision_brief
from .guard_sec_adapter import evaluate_sec_guard
from .guard_review import GuardReviewStore
from .guard_workflow import run_guard_review
from .sec_bundle_replay import replay_local_capture

_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_RUN = re.compile(r"[A-Za-z0-9_-]{1,128}\Z", re.ASCII)
_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
_UTC_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z", re.ASCII)
_REVIEW_ACTIONS = ("ACKNOWLEDGE", "REQUEST_EXCEPTION")
_RISK_CODES = frozenset({
    "SOURCE_ORIGIN_UNAUTHENTICATED", "INPUT_SECTIONS_MISSING",
    "CLAIMED_GROWTH_CONFLICT", "FINANCIAL_CALCULATION_UNAVAILABLE",
    "SOURCE_DIGEST_MISSING", "SOURCE_SPAN_INVALID",
    "LOCAL_IXBRL_CONTEXT_MATCH_UNVERIFIED", "IXBRL_CONTEXT_NOT_CONFIRMED",
    "LOCAL_NUMERIC_TEXT_MATCH_UNVERIFIED", "NUMERIC_TEXT_MATCH_NOT_CONFIRMED",
    "LOCAL_EVIDENCE_REVIEW_ONLY",
})


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _validate_replay(replay: Any) -> tuple[str, dict[str, Any]]:
    """Reject inconsistent end-to-end receipts before any SQLite write."""
    if not isinstance(replay, dict) or replay.get("status") != "offline_capture_replayed_unverified":
        raise ValueError("LOCAL_CAPTURE_REPLAY_NOT_REVIEWABLE")
    for key in ("source_authenticated", "financial_values_authenticated",
                "source_rights_verified", "external_http_called",
                "official_contest_submission"):
        if replay.get(key) is not False:
            raise ValueError("SOURCE_TRUST_BOUNDARY_VIOLATED")
    integrity = replay.get("local_integrity")
    financial = replay.get("offline_financial_review")
    risk = replay.get("risk")
    span = replay.get("source_span")
    summary = replay.get("review_summary")
    triage = replay.get("human_review_triage")
    if not all(isinstance(x, dict) for x in (
        integrity, financial, risk, span, summary, triage,
    )):
        raise ValueError("EVIDENCE_CHAIN_INCOMPLETE")
    checksums = integrity.get("sha256")
    if (integrity.get("status") != "bundle_integrity_pass_origin_unverified"
            or integrity.get("local_bytes_and_manifest_match") is not True
            or not isinstance(checksums, dict)
            or set(checksums) != {"submissions", "companyfacts", "original_filing"}
            or any(not isinstance(value, str) or _SHA.fullmatch(value) is None
                   for value in checksums.values())
            or span.get("original_sha256") != checksums["original_filing"]):
        raise ValueError("ARCHIVED_EVIDENCE_DIGEST_INVALID")
    for key in ("source_authenticated", "financial_values_authenticated",
                "investment_recommendation", "trade_authorized", "external_http_called"):
        if triage.get(key) is not False:
            raise ValueError("TRIAGE_TRUST_BOUNDARY_VIOLATED")
    for key in ("source_authenticated", "investment_recommendation",
                "trade_authorized", "external_http_called"):
        if summary.get(key) is not False:
            raise ValueError("SUMMARY_TRUST_BOUNDARY_VIOLATED")
    if (summary.get("schema") != "proofinvest.offline-review-summary.v1"
            or summary.get("status") != "human_review_required"
            or summary.get("financial_status") != financial.get("status")
            or summary.get("risk_status") != risk.get("status")
            or summary.get("review_priority") not in ("normal", "high")):
        raise ValueError("INCONSISTENT_REVIEW_SUMMARY")
    financial_status = financial.get("status")
    if financial_status not in ("calculated_unverified", "conflict"):
        raise ValueError("NO_VALID_FINANCIAL_REVIEW")
    if (financial_status == "conflict"
            and (summary["review_priority"] != "high"
                 or triage.get("priority") != "high"
                 or risk.get("status") != "unavailable")):
        raise ValueError("CONFLICT_MUST_ESCALATE")
    codes = risk.get("reason_codes")
    if (risk.get("source_authenticated") is not False
            or risk.get("investment_recommendation") is not False
            or risk.get("trade_authorized") is not False
            or risk.get("status") not in ("reviewed_unverified", "unavailable")
            or type(codes) is not list or not codes
            or any(not isinstance(code, str) or code not in _RISK_CODES
                   for code in codes)
            or "SOURCE_ORIGIN_UNAUTHENTICATED" not in codes):
        raise ValueError("RISK_TRUST_BOUNDARY_VIOLATED")
    issuer, accession, day = (replay.get(key) for key in (
        "issuer_cik", "accession", "as_of_self_reported",
    ))
    if (not isinstance(issuer, str) or _CIK.fullmatch(issuer) is None
            or not isinstance(accession, str)
            or _ACCESSION.fullmatch(accession) is None
            or not accession.startswith(issuer + "-")
            or not isinstance(day, str) or _UTC_DAY.fullmatch(day) is None):
        raise ValueError("EVIDENCE_ISSUER_OR_CLOCK_INVALID")
    # Reuse the source-derived, allowlisted review summary. No raw filing text
    # or caller-defined HTML/Markdown is added to the returned report.
    return financial_status, replay


def run_archived_sec_guard_report(
    *,
    bundle_path: str | Path,
    audit_db_path: str | Path,
    current_end: str,
    prior_end: str,
    needle: str,
    run_id: str,
    claimed_growth_pct: str | None = None,
    reviewer: str | None = None,
    action: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Run the real offline source -> finance -> risk -> Guard -> audit pipeline.

    Guard treats all local-source arithmetic as UNAUTHENTICATED. A conflicting
    claim gives REJECT; consistent unverified calculations give HOLD. Human
    ACKNOWLEDGE or REQUEST_EXCEPTION are separate, never authorization.
    """
    wants_review = any(v is not None for v in (reviewer, action, reason))
    if wants_review and (
        not all(isinstance(v, str) and v.strip() for v in (
            reviewer, action, reason
        ))
        or action not in _REVIEW_ACTIONS
        or not 1 <= len(reviewer.strip()) <= 80
        or not 5 <= len(reason.strip()) <= 1000
    ):
        raise ValueError("INVALID_EXPLICIT_HUMAN_REVIEW")
    if not isinstance(run_id, str) or _RUN.fullmatch(run_id) is None:
        raise ValueError("INVALID_AUDIT_RUN_ID")
    if (not isinstance(bundle_path, (str, Path))
            or not isinstance(audit_db_path, (str, Path))):
        raise ValueError("LOCAL_PATH_REQUIRED")
    archive = Path(bundle_path).expanduser()
    audit = Path(audit_db_path).expanduser()
    if (not archive.is_file() or archive.is_symlink()
            or audit == archive or audit.resolve() == archive.resolve()
            or audit.is_symlink()
            or (audit.exists() and not audit.is_file())
            or audit.parent.is_symlink() or not audit.parent.is_dir()):
        raise ValueError("SEPARATE_LOCAL_ARCHIVE_AND_AUDIT_REQUIRED")
    # Important: untrusted bytes are fully checked before creating the audit DB.
    replay = replay_local_capture(
        archive, current_end=current_end, prior_end=prior_end, needle=needle,
        claimed_growth_pct=claimed_growth_pct,
    )
    status, receipt = _validate_replay(replay)
    evidence_hash = _canonical_sha256({
        "schema": "proofinvest.offline-sec-guard-bound-evidence.v1",
        "replay": receipt,
        "current_end": current_end,
        "prior_end": prior_end,
        "needle_sha256": hashlib.sha256(needle.encode("utf-8")).hexdigest(),
        "claimed_growth_pct": claimed_growth_pct,
    })
    # Bind the actual locally reviewed risk status/codes into the stored
    # request. Missing independently verified ratios must NEVER be promoted
    # into an investment or model-based decision.
    risk_evidence = {
        "risk_calculated": False,
        "status": receipt["risk"]["status"],
        "reason_codes": sorted(set(receipt["risk"]["reason_codes"])),
        "source_authenticated": False,
        "financial_values_authenticated": False,
        "source_rights_verified": False,
    }
    expected = "REJECT" if status == "conflict" else "HOLD"
    preview = evaluate_sec_guard({"status": status}, risk=risk_evidence)["guard"]
    if (preview.get("decision") != expected
            or preview.get("human_approved") is not False
            or preview.get("trade_executed") is not False
            or preview.get("source_authenticated") is not False):
        raise ValueError("GUARD_UNVERIFIED_EVIDENCE_DECISION_INVALID")
    guard_run = run_guard_review(
        {"status": status}, run_id=run_id, database_path=audit,
        source_evidence_digest=evidence_hash, risk=risk_evidence,
        reviewer=reviewer, action=action, reason=reason,
    )
    guard = guard_run["guard"]
    if (guard.get("decision") != expected
            or guard.get("source_authenticated") is not False
            or guard.get("trade_executed") is not False
            or guard.get("human_approved") is not False):
        raise ValueError("GUARD_UNVERIFIED_EVIDENCE_DECISION_INVALID")
    verified_readback = verify_bound_guard_audit(
        audit, run_id=run_id, source_evidence_digest=evidence_hash,
        financial_status=status, risk_evidence=risk_evidence,
        event_id=guard_run["audit"]["event_id"],
        event_hash=guard_run["audit"]["event_hash"],
        guard_decision=guard, human_review=guard_run["review"],
    )
    if (verified_readback.get("verified_against_persisted_request") is not True
            or verified_readback.get("source_evidence_digest") != evidence_hash
            or verified_readback.get("guard_decision") != expected
            or verified_readback.get("audit_chain_valid") is not True
            or verified_readback.get("human_review_chain_valid") is not True):
        raise ValueError("LOCAL_GUARD_EVIDENCE_BINDING_FAILED")
    hashes = receipt["local_integrity"]["sha256"]
    financial = receipt["offline_financial_review"]
    summary = receipt["review_summary"]
    span = receipt["source_span"]
    report = {
        "schema": "proofinvest.archived-sec-guard-report.v1",
        "status": "local_archive_review_audited_unverified",
        "research": {
            "status": "offline_local_metadata_only",
            "issuer_cik": receipt["issuer_cik"],
            "accession": receipt["accession"],
            "observed_utc_day_self_reported": receipt["as_of_self_reported"],
            "origin_authenticated": False,
        },
        "evidence": {
            "submissions_sha256": hashes["submissions"],
            "companyfacts_sha256": hashes["companyfacts"],
            "original_filing_sha256": hashes["original_filing"],
            "evidence_chain_sha256": evidence_hash,
            "source_span_start_byte": span["start_byte"],
            "source_span_end_byte_exclusive": span["end_byte_exclusive"],
            "source_span_authenticates_financial_claim": False,
        },
        "verification": {
            "status": status,
            "growth_pct_recalculated_unverified": financial.get("growth_pct"),
            "arithmetic_is_source_authentication": False,
        },
        "risk": {
            "status": receipt["risk"]["status"],
            "reason_codes": risk_evidence["reason_codes"],
            "source_authenticated": False,
            "risk_is_investment_recommendation": False,
        },
        "review_summary": summary,
        "guard": guard,
        "audit": {
            "run_id": run_id,
            "event_id": guard_run["audit"]["event_id"],
            "event_hash": guard_run["audit"]["event_hash"],
            "replayed": guard_run["audit"]["replayed"],
            "chain_valid": True,
            "human_review_integrity_valid": True,
            "verified_against_persisted_request": True,
            "bound_source_evidence_sha256": evidence_hash,
            "bound_guard_decision": expected,
            "bound_review_id": verified_readback["review_id"],
            "externally_anchored": False,
        },
        "human_review": guard_run["review"],
        "limitations": [
            "Archived local SHA-256 values do not prove provider origin or financial truth.",
            "Reported collection timestamps are self-reported and may be backdated.",
            "Calculated values are unverified; risk cannot authorize investment.",
            "Guard is deterministic and local; no LLM inference or real trade.",
            "SQLite audit chain is tamper-evident locally, not externally immutable.",
            "Not the official KIC submission or a live SEC research result.",
        ],
        "live_api_called": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "financial_values_authenticated": False,
        "model_trained": False,
        "investment_recommendation": False,
        "trade_executed": False,
        "official_contest_submission": False,
    }
    report["decision_brief"] = build_archived_decision_brief(report)
    return report


def render_archived_sec_guard_markdown(report: Any) -> str:
    """Render only allowlisted metadata, never filing text or unsafe URL."""
    if (not isinstance(report, dict)
            or report.get("schema") != "proofinvest.archived-sec-guard-report.v1"
            or report.get("status") != "local_archive_review_audited_unverified"
            or any(report.get(key) is not False for key in (
                "live_api_called", "source_authenticated", "source_rights_verified",
                "financial_values_authenticated", "investment_recommendation",
                "trade_executed", "official_contest_submission",
            ))
            or not isinstance(report.get("research"), dict)
            or not isinstance(report.get("evidence"), dict)
            or not isinstance(report.get("verification"), dict)
            or not isinstance(report.get("guard"), dict)
            or not isinstance(report.get("audit"), dict)
            or report["audit"].get("chain_valid") is not True
            or report["audit"].get("human_review_integrity_valid") is not True
            or report["audit"].get("verified_against_persisted_request") is not True
            or report["audit"].get("bound_source_evidence_sha256")
                != report["evidence"].get("evidence_chain_sha256")
            or report["audit"].get("bound_guard_decision") != report["guard"].get("decision")
            or report["guard"].get("decision") not in ("HOLD", "REJECT")
            or report["verification"].get("status") not in (
                "calculated_unverified", "conflict",
            )
            or (report["verification"]["status"] == "conflict")
                != (report["guard"]["decision"] == "REJECT")):
        raise ValueError("INVALID_UNVERIFIED_SEC_AUDIT_REPORT")
    source, evidence, verification, guard, audit = (
        report[key] for key in ("research", "evidence", "verification", "guard", "audit")
    )
    # This renderer is also a public callable function: reject forged metadata
    # before Markdown interpolation (a direct caller can bypass the pipeline).
    if (source.get("origin_authenticated") is not False
            or verification.get("arithmetic_is_source_authentication") is not False
            or report.get("model_trained") is not False
            or report.get("risk", {}).get("source_authenticated") is not False
            or report.get("risk", {}).get("risk_is_investment_recommendation") is not False
            or audit.get("externally_anchored") is not False
            or guard.get("source_authenticated") is not False
            or guard.get("trade_executed") is not False
            or guard.get("human_approved") is not False):
        raise ValueError("INVALID_UNVERIFIED_SEC_AUDIT_REPORT")
    if (not isinstance(source.get("issuer_cik"), str)
            or _CIK.fullmatch(source["issuer_cik"]) is None
            or not isinstance(source.get("accession"), str)
            or _ACCESSION.fullmatch(source["accession"]) is None
            or not source["accession"].startswith(source["issuer_cik"] + "-")
            or not isinstance(source.get("observed_utc_day_self_reported"), str)
            or _UTC_DAY.fullmatch(source["observed_utc_day_self_reported"]) is None
            or not isinstance(audit.get("run_id"), str)
            or _RUN.fullmatch(audit["run_id"]) is None):
        raise ValueError("INVALID_UNVERIFIED_SEC_AUDIT_REPORT")
    for key in ("submissions_sha256", "companyfacts_sha256",
                "original_filing_sha256", "evidence_chain_sha256"):
        value = evidence.get(key)
        if not isinstance(value, str) or _SHA.fullmatch(value) is None:
            raise ValueError("INVALID_UNVERIFIED_SEC_AUDIT_REPORT")
    if not isinstance(audit.get("event_hash"), str) or _SHA.fullmatch(audit["event_hash"]) is None:
        raise ValueError("INVALID_UNVERIFIED_SEC_AUDIT_REPORT")
    # Independent deterministic regeneration detects tampering of the
    # narrative/priority/action copy; no arbitrary untrusted prose is rendered.
    brief = build_archived_decision_brief(report)
    if report.get("decision_brief") != brief:
        raise ValueError("DECISION_BRIEF_TAMPERED_OR_OUTDATED")
    # No freeform source, claim or review reason embedded in Markdown.
    return "\n".join([
        "# ProofInvest — Offline evidence audit (UNVERIFIED)",
        "",
        "**No SEC attestation, model-based investment advice, trading, or contest submission.**",
        "",
        "## 검토 결론 / Decision brief",
        f"- 판정: **{brief['decision']}**",
        f"- 결론: {brief['headline']}",
        f"- 사유: {brief['rationale']}",
        f"- 검토 우선순위: **{brief['priority']}** (실제 금융 위험등급 아님)",
        "",
        "### 확인한 것 — 오직 로컬 범위",
        *[f"- {row['meaning']} ({row['status']})" for row in brief["checks"]],
        "",
        "### 확인하지 못한 것 — 외부 출처 미인증",
        *[f"- {item}" for item in brief["unverified"]],
        "",
        "### 다음 수동 검토 작업",
        *[f"- {index}. {item['meaning']}" for index, item in
          enumerate(brief["next_actions"], start=1)],
        "",
        "## Research / local source identity",
        f"- CIK (self-reported): `{source['issuer_cik']}`",
        f"- Accession (self-reported): `{source['accession']}`",
        f"- Collected date (self-reported): `{source['observed_utc_day_self_reported']}`",
        "",
        "## Pinned evidence (local-byte integrity only)",
        f"- Submissions SHA-256: `{evidence['submissions_sha256']}`",
        f"- CompanyFacts SHA-256: `{evidence['companyfacts_sha256']}`",
        f"- Original filing SHA-256: `{evidence['original_filing_sha256']}`",
        f"- Bound evidence SHA-256: `{evidence['evidence_chain_sha256']}`",
        "",
        "## Verification -> Risk -> Guard",
        f"- Financial arithmetic: **{verification['status']}**",
        "- Risk: **UNVERIFIED; NO TRADE AUTHORIZATION**",
        f"- Guard: **{guard['decision']}**",
        f"- Audit event SHA-256: `{audit['event_hash']}`",
        "- Persisted evidence fingerprint / financial verdict / risk / Guard cross-check: PASS",
        "- Local audit chain + human review integrity: PASS",
        "- External audit anchoring: NO",
        "",
        "No untrusted HTML, source URL, reviewer notes or arbitrary excerpts are reproduced.",
        "This is not the official organizer submission PDF.",
        "",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OFFLINE ONLY: archived SEC-shaped ZIP -> Guard -> SQLite -> report",
    )
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--audit-db", required=True, type=Path)
    parser.add_argument("--current-end", required=True)
    parser.add_argument("--prior-end", required=True)
    parser.add_argument("--needle", required=True)
    parser.add_argument("--claimed-growth-pct")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--reviewer")
    parser.add_argument("--action", choices=_REVIEW_ACTIONS)
    parser.add_argument("--reason")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        report = run_archived_sec_guard_report(
            bundle_path=args.bundle, audit_db_path=args.audit_db,
            current_end=args.current_end, prior_end=args.prior_end,
            needle=args.needle, claimed_growth_pct=args.claimed_growth_pct,
            run_id=args.run_id, reviewer=args.reviewer, action=args.action,
            reason=args.reason,
        )
        content = (render_archived_sec_guard_markdown(report)
                   if args.format == "markdown" else
                   json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        # Never log local file paths, extracted filing text, review notes or SQL.
        print(json.dumps({"status": "SEC_ARCHIVE_AUDIT_FAILED",
                          "reason_code": "INVALID_LOCAL_INPUT_OR_INTEGRITY"}),
              file=sys.stderr)
        return 2
    print(content, end="" if args.format == "markdown" else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
