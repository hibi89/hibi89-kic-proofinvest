"""P123 explicit human acknowledgement of an OFFLINE unverified ticker report.

This receipt is NOT identity verification, source permission, human approval,
audited investment decision, a signature, or external execution authorization.
No network, persistent state, trade, original retention or DAKER submission.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

_ALIAS = re.compile(r"[A-Za-z0-9가-힣_-]{2,40}\Z")
_MAX_REASON = 240


def _bytes(record: dict) -> bytes:
    return (json.dumps(record, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def acknowledge_local_ticker_report(
    report: dict, *, sources: dict[str, bytes],
    reviewer_alias: str, review_note: str,
    explicit_acknowledgement: bool,
    market_json: bytes | None = None,
    industry_json: bytes | None = None,
) -> dict[str, Any]:
    """Recompute original bytes and record a user's limited acknowledgement.

    Human cannot override HOLD/REJECT or missing publisher/usage rights. A
    returned digest is merely a self-consistency marker, not an authentication
    signature. No file is written here; user must explicitly download.
    """
    if explicit_acknowledgement is not True:
        raise ValueError("EXPLICIT_ACKNOWLEDGEMENT_REQUIRED")
    if type(reviewer_alias) is not str or _ALIAS.fullmatch(reviewer_alias) is None:
        raise ValueError("LOCAL_REVIEWER_ALIAS_INVALID")
    if (type(review_note) is not str
            or not 10 <= len(review_note) <= _MAX_REASON
            or any(ord(c) < 32 or ord(c) == 127 for c in review_note)):
        raise ValueError("LOCAL_REVIEW_REASON_INVALID")
    if type(report) is not dict:
        raise ValueError("LOCAL_REPORT_REQUIRED")
    limits = report.get("limits")
    rights = report.get("source_rights_ledger")
    if (type(limits) is not dict or type(rights) is not dict
            or limits.get("source_authenticated") is not False
            or limits.get("source_rights_verified") is not False
            or limits.get("audit_written") is not False
            or limits.get("guard_executed") is not False
            or limits.get("human_approved") is not False
            or limits.get("trade_executed") is not False
            or limits.get("official_contest_submission") is not False
            or rights.get("status") != "EXTERNAL_USE_BLOCKED_RIGHTS_NOT_VERIFIED"
            or rights.get("external_sharing_allowed") is not False
            or rights.get("contest_public_submission_allowed") is not False
            or rights.get("commercial_reuse_allowed") is not False
            or report.get("guard_policy_preview") not in ("HOLD", "REJECT")):
        raise ValueError("LOCAL_HUMAN_REVIEW_TRUST_CONTRACT_INVALID")

    from .ticker_local_report import verify_local_report
    replay = verify_local_report(
        report, sources=sources, market_json=market_json,
        industry_json=industry_json)
    if replay.get("status") != "PASS":
        raise ValueError("EXACT_ORIGINAL_BYTES_REPLAY_REQUIRED")

    receipt = {
        "schema": "kuodra.local-human-acknowledgement.v1",
        "status": "ACKNOWLEDGED_UNVERIFIED_LOCAL_ONLY",
        "action": "ACKNOWLEDGE_FOR_LOCAL_REVIEW",
        "report_sha256": report["report_sha256"],
        "source_sha256": dict(report["source_sha256"]),
        "reviewer_alias_unverified": reviewer_alias,
        "review_note": review_note,
        "guard_policy_preview_unchanged": report["guard_policy_preview"],
        "report_replay_verified": True,
        "publisher_origin_authenticated": False,
        "reviewer_identity_authenticated": False,
        "source_rights_verified": False,
        "external_sharing_allowed": False,
        "contest_submission_allowed": False,
        "human_approved": False,
        "guard_executed": False,
        "audit_written": False,
        "trade_executed": False,
        "ai_agent_executed": False,
        "external_http_requests": 0,
    }
    receipt["receipt_sha256"] = sha256(_bytes(receipt)).hexdigest()
    return receipt


def acknowledgement_json_bytes(receipt: dict) -> bytes:
    """Serialize only in response to explicit local browser download."""
    return _bytes(receipt)
