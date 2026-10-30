"""Local caller-supplied SEC files -> deterministic checks -> Guard -> audit report.

Explicit opt-in local SQLite persistence only. No SEC HTTP/LLM, no trades,
issuer/source authentication, rights attestation or investment advice.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import stat
from pathlib import Path
from typing import Any

from disclosure_lightning.core import MAX_JSON_BYTES
from disclosure_lightning.originals import MAX_FILING_BYTES
from .guard_audit import GuardAuditStore
from .guard_review import GuardReviewStore
from .guard_workflow import run_guard_review
from .local_risk_screen import screen_local_evidence
from .kuodra_sec_balance import review_sec_balance_sheet
from .local_sec_packet import (
    _MAX_FILE_BYTES,
    _read_regular_local,
    build_local_sec_review_packet,
)

_REVIEW_ACTIONS = frozenset(("ACKNOWLEDGE", "REQUEST_EXCEPTION"))


def _check_audit_path(path: str | Path) -> Path:
    """Refuse obvious unsafe destinations; SQLite still needs local OS ACLs."""
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError("INVALID_AUDIT_DESTINATION")
    candidate = Path(path).expanduser()
    if str(candidate) == ":memory:" or candidate.is_symlink():
        raise ValueError("AUDIT_DESTINATION_NOT_PERSISTENT_OR_SYMLINK")
    if candidate.exists() and not stat.S_ISREG(candidate.stat().st_mode):
        raise ValueError("AUDIT_DESTINATION_NOT_REGULAR")
    if not candidate.parent.is_dir():
        raise ValueError("AUDIT_PARENT_DIRECTORY_REQUIRED")
    return candidate


def review_local_sec_with_guard(
    *,
    submissions_json: bytes,
    companyfacts_json: bytes,
    original_filing: bytes,
    cik: str,
    accession: str,
    as_of: str,
    collected_at: str,
    current_end: str,
    prior_end: str,
    needle: str,
    audit_db_path: str | Path,
    run_id: str,
    claimed_growth_pct: str | None = None,
    history_page_json: bytes | None = None,
    history_page_name: str | None = None,
    reviewer: str | None = None,
    action: str | None = None,
    reason: str | None = None,
    required_review_intent: str | None = None,
) -> dict[str, Any]:
    """Read three local inputs, emit a safe report and persist explicit audit.

    No caller-provided numeric Risk is allowed to authorize a simulation.
    Even structurally matching SEC-shaped facts are not authenticated. The
    legacy Guard remains unchanged; this path can only HOLD or REJECT.
    """
    db_path = _check_audit_path(audit_db_path)
    if required_review_intent not in (None, "SOURCE_REVIEW", "RISK_CHECK"):
        raise ValueError("UNSUPPORTED_SEC_REVIEW_INTENT")
    if action is not None and action not in _REVIEW_ACTIONS:
        raise ValueError("LOCAL_SOURCE_CANNOT_AUTHORIZE_SIMULATION")
    # Reject incomplete reviews before any local SQLite side effects.
    wants_review = any(value is not None for value in (reviewer, action, reason))
    if wants_review and not (
        isinstance(reviewer, str) and 1 <= len(reviewer.strip()) <= 80
        and isinstance(action, str) and action in _REVIEW_ACTIONS
        and isinstance(reason, str) and 5 <= len(reason.strip()) <= 1000
    ):
        raise ValueError("INVALID_EXPLICIT_LOCAL_REVIEW")
    packet = build_local_sec_review_packet(
        submissions_json=submissions_json,
        companyfacts_json=companyfacts_json,
        original_filing=original_filing,
        cik=cik, accession=accession, as_of=as_of,
        collected_at=collected_at, current_end=current_end,
        prior_end=prior_end, needle=needle,
        claimed_growth_pct=claimed_growth_pct,
        history_page_json=history_page_json,
        history_page_name=history_page_name,
    )
    if (packet.get("schema") != "proofinvest.offline-local-sec-review.v1"
            or packet.get("status") != "reviewable_untrusted_local_evidence"
            or packet.get("mode") != "LOCAL_FILES_OFFLINE_UNAUTHENTICATED"
            or any(value is not False for value in packet["attestations"].values())):
        raise ValueError("LOCAL_SOURCE_TRUST_CONTRACT_INVALID")
    financial = packet["financial"]
    # Separate descriptive SEC balance-sheet view. This is untrusted data,
    # never a verified Risk input, never a Guard policy change.
    balance_sheet = review_sec_balance_sheet(
        companyfacts_json, cik=cik, accession=accession,
        period_end=current_end, as_of=as_of,
    )
    if (balance_sheet["source_authenticated"] is not False
            or balance_sheet["risk_authenticated"] is not False
            or balance_sheet["guard_policy_modified"] is not False):
        raise ValueError("SEC_BALANCE_TRUST_CONTRACT_FAILURE")
    source = packet["source"]
    text_node = source["html_text_node_literal_check"]
    text_ok = (
        text_node.get("status") == "untrusted_html_text_node_literal_located"
        and text_node.get("exact_raw_byte_span_verified") is True
        and text_node.get("source_authenticated") is False
    )
    local_risk = screen_local_evidence(
        financial,
        {
            "original_sha256": source["archived_filing_sha256"],
            "start_byte": source["span_start_byte"],
            "end_byte_exclusive": source["span_end_byte_exclusive"],
            "ixbrl_context": source["ixbrl_revenue_context_review"],
            "numeric_literals": source["numeric_literal_crosscheck"],
        },
    )
    # A proposal is NOT permission to persist a spurious result. Refuse
    # the operator's requested review BEFORE the Guard/SQLite side effect
    # when its essential locally checked evidence is unavailable.
    if required_review_intent == "SOURCE_REVIEW" and not text_ok:
        raise ValueError("SOURCE_REVIEW_EXACT_TEXT_EVIDENCE_REQUIRED")
    if (required_review_intent == "RISK_CHECK" and
            (balance_sheet["status"] != "reviewed_unverified"
             or balance_sheet["balance_identity_match"] is not True)):
        raise ValueError("RISK_REVIEW_RECONCILED_BALANCE_REQUIRED")
    # The local risk screen is informational, NOT approved financial risk
    # data. It must never be passed as eligible risk to evaluate_guard.
    if (local_risk.get("source_authenticated") is not False
            or local_risk.get("trade_authorized") is not False
            or local_risk.get("status") not in ("unavailable", "reviewed_unverified")):
        raise ValueError("LOCAL_RISK_TRUST_CONTRACT_INVALID")
    guard_status = financial["status"]
    if not text_ok and guard_status != "conflict":
        guard_status = "unavailable"
    evidence = {
        "status": guard_status,
        "numeric_status": financial["status"],
        "numeric_reason_code": financial["reason_code"],
        "issuer_cik": packet["issuer"]["cik"],
        "accession": packet["issuer"]["accession"],
        "as_of": packet["issuer"]["as_of"],
        "submissions_sha256": source["submissions_sha256"],
        "history_page_sha256": source["history_page_sha256"],
        "companyfacts_sha256": source["companyfacts_sha256"],
        "original_sha256": source["archived_filing_sha256"],
        "source_span": {
            "start_byte": source["span_start_byte"],
            "end_byte_exclusive": source["span_end_byte_exclusive"],
            "text_node_status": text_node["status"],
        },
        "current_usd": financial["current_amount"],
        "prior_usd": financial["prior_amount"],
        "growth_pct": financial["growth_pct"],
        "source_authenticated": False,
        "risk_authenticated": False,
    }
    result = run_guard_review(
        evidence, run_id=run_id, database_path=db_path,
        risk=None,
        reviewer=reviewer, action=action, reason=reason,
    )
    if (result["guard"]["decision"] not in ("HOLD", "REJECT")
            or result["guard"]["source_authenticated"] is not False
            or result["trade_executed"] is not False
            or not GuardAuditStore(db_path).verify_chain()
            or not GuardReviewStore(db_path).verify_reviews()):
        raise ValueError("GUARD_LOCAL_INTEGRITY_OR_POLICY_BLOCKED")
    return {
        "schema": "proofinvest.local-sec-guard-report.v1",
        "mode": "OFFLINE_USER_SUPPLIED_UNAUTHENTICATED",
        "issuer": packet["issuer"],
        "source": {
            "submissions_sha256": source["submissions_sha256"],
            "history_page_sha256": source["history_page_sha256"],
            "source_index_kind": source["source_index_kind"],
            "companyfacts_sha256": source["companyfacts_sha256"],
            "archived_original_sha256": source["archived_filing_sha256"],
            "evidence_link_status": source["link_status"],
            "html_text_node_status": text_node["status"],
            "exact_raw_byte_span_verified": text_ok,
        },
        "verification": financial,
        "risk": local_risk,
        "balance_sheet": balance_sheet,
        "guard": result["guard"],
        "human_review": result["review"],
        "audit": result["audit"],
        "audit_chain_valid": True,
        "human_review_integrity_valid": True,
        "limits": {
            "external_source_authenticated": False,
            "source_rights_verified": False,
            "live_api_called": False,
            "ai_agent_executed": False,
            "trade_executed": False,
            "simulation_authorized": False,
            "official_contest_submission": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Opt-in local SEC triple-file to Guard audit; offline/untrusted only."
    )
    for option in ("submissions-json", "companyfacts-json", "original-file"):
        parser.add_argument("--" + option, required=True, type=Path)
    for option in (
        "cik", "accession", "as-of", "collected-at",
        "current-end", "prior-end", "needle", "run-id",
    ):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--audit-db", required=True, type=Path)
    parser.add_argument("--acknowledge-local-audit-persistence",
                        action="store_true", required=True)
    parser.add_argument("--claimed-growth-pct")
    parser.add_argument("--history-page-json", type=Path)
    parser.add_argument("--history-page-name")
    parser.add_argument("--report-html", type=Path, help="Explicit new local HTML report; never overwrites")
    parser.add_argument("--reviewer")
    parser.add_argument("--action", choices=sorted(_REVIEW_ACTIONS))
    parser.add_argument("--reason")
    args = parser.parse_args(argv)
    # Resolve paths before touching input data or a persistent audit: a
    # destination must never alias any source, nor may HTML and the audit
    # database share an uncreated destination (SQLite otherwise wins race).
    try:
        input_locations = {
            path.expanduser().resolve(strict=False)
            for path in (args.submissions_json, args.companyfacts_json,
                         args.original_file) + ((args.history_page_json,) if args.history_page_json is not None else ())
        }
        audit_location = args.audit_db.expanduser().resolve(strict=False)
        html_location = (
            args.report_html.expanduser().resolve(strict=False)
            if args.report_html is not None else None
        )
    except (OSError, RuntimeError, ValueError):
        parser.exit(2, "Local SEC Guard report blocked: INVALID_DESTINATION\n")
    if audit_location in input_locations:
        parser.exit(2, "Local SEC Guard report blocked: AUDIT_INPUT_PATH_COLLISION\n")
    if html_location is not None:
        if html_location in input_locations or html_location == audit_location:
            parser.exit(2, "Local SEC Guard report blocked: HTML_PATH_COLLISION\n")
        # Do not touch the Guard audit if the optional HTML destination
        # already exists. open('xb') also guards against a later path race.
        output = args.report_html.expanduser()
        if (output.is_symlink() or output.exists()
                or not output.parent.is_dir()):
            parser.exit(2, "Local SEC Guard report blocked: HTML_DESTINATION_UNAVAILABLE\n")
    try:
        report = review_local_sec_with_guard(
            submissions_json=_read_regular_local(args.submissions_json, MAX_JSON_BYTES),
            companyfacts_json=_read_regular_local(args.companyfacts_json, _MAX_FILE_BYTES),
            original_filing=_read_regular_local(args.original_file, MAX_FILING_BYTES),
            cik=args.cik, accession=args.accession, as_of=args.as_of,
            collected_at=args.collected_at, current_end=args.current_end,
            prior_end=args.prior_end, needle=args.needle,
            run_id=args.run_id, audit_db_path=args.audit_db,
            claimed_growth_pct=args.claimed_growth_pct,
            history_page_json=(_read_regular_local(args.history_page_json, MAX_JSON_BYTES)
                               if args.history_page_json is not None else None),
            history_page_name=args.history_page_name,
            reviewer=args.reviewer, action=args.action, reason=args.reason,
        )
    except (ValueError, OSError, TypeError, OverflowError, RecursionError,
            sqlite3.DatabaseError) as exc:
        parser.exit(2, f"Local SEC Guard report blocked: {type(exc).__name__}\n")
    if args.report_html is not None:
        from .local_sec_html_report import render_local_sec_html
        try:
            html_payload = render_local_sec_html(report)
            with args.report_html.expanduser().open("xb") as output:
                output.write(html_payload)
        except (ValueError, TypeError, OverflowError, OSError) as exc:
            parser.exit(2, "Local SEC Guard HTML blocked: " + type(exc).__name__ + "\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
