"""Read-only independent replay of a P231 local NVDA partial A/B/C Guard receipt.

This checks a downloaded receipt against the SAME derived A/B/C packet and
the local SQLite ledger. It does not authenticate source ownership, license
terms, SEC original bytes, market data, or an external signature. Nothing is
uploaded, and no SQLite table or record is created by this verifier.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any

from .guard_agent import evaluate_guard
from .guard_audit import GuardAuditStore, _canonical
from .guard_review import GuardReviewStore
from .local_sec_guard_report import _check_audit_path
from .real_issuer_abc_local_review import replay_partial_source_bound_abc
from .real_issuer_abc_fact_review import (
    build_source_factual_abc_brief, replay_source_factual_abc_brief,
)
from .real_issuer_abc_guard_audit import _POLICY

_SCHEMA = "kuodra.p232-partial-abc-local-receipt-replay.v1"
_RECEIPT_SCHEMA = "kuodra.p231-partial-abc-hold-receipt.v1"
_RECEIPT_KEYS = frozenset({
    "schema", "run_id", "source_bound_abc_digest",
    "redacted_evidence_digest", "issuer_source_sha256", "guard", "audit",
    "source_origin_and_rights_verified", "market_rights_verified",
    "peer_rights_verified", "full_abc_complete",
    "external_sharing_allowed", "human_review_only", "trade_executed",
})


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "local_chain_valid": False, "receipt_matches_local_source": False,
        "sqlite_written": False, "network_requests": 0,
        "source_authenticated_by_sec": False, "market_rights_verified": False,
        "peer_rights_verified": False, "full_abc_complete": False,
        "trade_executed": False,
    }


def verify_p231_local_receipt(
    *, abc_review: Any, receipt: Any, audit_db_path: str | Path,
) -> dict[str, Any]:
    """Verify source-derived request, HOLD decision, receipt and existing ledger.

    The event and request hash must match the independently recomputed source
    packet. A hash chain detects partial edits, not privileged full-history
    rewrites. The receipt's 'replayed' flag is operational metadata and cannot
    independently be authenticated from the stored event.
    """
    if (type(abc_review) is not dict
            or not replay_partial_source_bound_abc(abc_review)):
        return _blocked("ABC_SOURCE_PACKET_REPLAY_FAILED")
    brief = build_source_factual_abc_brief(abc_review)
    if (brief.get("status") != "LOCAL_A_B_C_CLAIM_REVIEW_FOR_HUMAN_ONLY"
            or not replay_source_factual_abc_brief(brief, abc_review)
            or abc_review.get("ticker") != "NVDA"
            or abc_review.get("as_of") != "2026-11-05"
            or any(abc_review.get(k) is not False for k in (
                "market_rights_verified", "peer_rights_verified",
                "sec_edgar_original_bytes_verified", "full_abc_complete",
                "ai_agent_executed", "trade_executed"))
            or any(brief.get(k) is not False for k in (
                "market_source_authenticated", "legal_model_use_approved",
                "external_sharing_allowed"))):
        return _blocked("ABC_FACT_OR_RIGHTS_REPLAY_FAILED")
    if (type(receipt) is not dict or set(receipt) != _RECEIPT_KEYS
            or receipt.get("schema") != _RECEIPT_SCHEMA
            or any(receipt.get(k) is not False for k in (
                "source_origin_and_rights_verified", "market_rights_verified",
                "peer_rights_verified", "full_abc_complete",
                "external_sharing_allowed", "trade_executed"))
            or receipt.get("human_review_only") is not True):
        return _blocked("RECEIPT_SCHEMA_OR_GUARD_RIGHTS_INVALID")

    try:
        digest = abc_review["derived_sha256"]
        source_sha = abc_review["source_linked_issuer_sha256"]
        run_id = "p231_" + digest
        evidence = {
            "ticker": "NVDA", "reviewed_as_of": "2026-11-05",
            "issuer_publisher_sha256": source_sha,
            "operator_stock_file_sha256": abc_review["stock_uploaded_sha256"],
            "operator_ndx_file_sha256": abc_review["ndx_uploaded_sha256"],
            "unkeyed_partial_abc_sha256": digest,
            "historical_source_brief_sha256": brief["brief_sha256"],
            "engine_availability": {
                "A": "UNAVAILABLE_PROVIDER_ORIGIN_AND_RIGHTS",
                "B": "VERIFIED_HISTORICAL_NUMERIC_MATCH_ONLY",
                "C": "PUBLIC_TEXT_NUMERIC_MATCH_RAW_UNVERIFIED",
            },
            "engine_c_manual_reference_peers": ["AMD", "INTC"],
            "publisher_original_seen_not_sec_attested": True,
            "source_rights_verified": False, "market_rights_verified": False,
            "peer_rights_verified": False, "full_abc_complete": False,
            "trade_executed": False,
        }
        evidence_hash = sha256(_canonical(evidence)).hexdigest()
        decision = evaluate_guard(
            [{"status": "UNAVAILABLE",
              "source_kind": "MANUALLY_CURATED_UNVERIFIED"}],
            policy=_POLICY, risk=None,
        )
        if (decision.get("schema") != "proofinvest.guard-decision.v1"
                or decision.get("decision") != "HOLD"
                or decision.get("reason_codes") !=
                   ["CLAIM_UNAVAILABLE", "RISK_UNAVAILABLE"]
                or decision.get("source_authenticated") is not False
                or decision.get("human_approved") is not False
                or decision.get("trade_executed") is not False):
            return _blocked("GUARD_HOLD_INVARIANT_BROKEN")
        request = {
            "schema": "kuodra.p231-partial-source-abc-local-hold-request.v1",
            "evidence": evidence, "evidence_digest": evidence_hash,
            "source_approved_for_external_use": False,
            "market_provider_authenticated": False,
            "risk_authenticated": False, "trade_executed": False,
        }
        request_hash = sha256(_canonical(request)).hexdigest()
        expected_payload = _canonical({
            "request_hash": request_hash, "decision": decision,
        }).decode("utf-8")
        event = receipt.get("audit")
        if (receipt.get("run_id") != run_id
                or receipt.get("source_bound_abc_digest") != digest
                or receipt.get("redacted_evidence_digest") != evidence_hash
                or receipt.get("issuer_source_sha256") != source_sha
                or receipt.get("guard") != decision
                or type(event) is not dict
                or set(event) != {"event_id", "event_hash", "replayed"}
                or type(event["event_id"]) is not int or event["event_id"] < 1
                or type(event["event_hash"]) is not str
                or len(event["event_hash"]) != 64
                or any(c not in "0123456789abcdef" for c in event["event_hash"])
                or type(event["replayed"]) is not bool):
            return _blocked("RECEIPT_SOURCE_OR_EVENT_MISMATCH")

        dest = _check_audit_path(audit_db_path)
        if not dest.is_file():
            return _blocked("LOCAL_AUDIT_DB_MISSING")
        # Read-only SQLite URI: never implicitly create a missing database.
        # A single read transaction gives one consistent view across chain and
        # event checks even if another local process is appending audit rows.
        with closing(sqlite3.connect(dest.resolve().as_uri() + "?mode=ro",
                                     uri=True, timeout=5)) as db:
            db.execute("BEGIN")
            store = GuardAuditStore(dest)
            if (not store.verify_chain(conn=db)
                    or not GuardReviewStore(dest).verify_reviews(conn=db)):
                return _blocked("LOCAL_AUDIT_CHAIN_INVALID")
            row = db.execute(
                "SELECT payload_json, event_hash FROM guard_audit_events "
                "WHERE run_id=? AND event_id=?",
                (run_id, event["event_id"]),
            ).fetchone()
            registry = db.execute(
                "SELECT request_hash, decision, event_id FROM guard_run_registry "
                "WHERE run_id=?", (run_id,),
            ).fetchone()
            if (row is None or registry is None
                    or row[0] != expected_payload
                    or row[1] != event["event_hash"]
                    or registry != (request_hash, expected_payload,
                                    event["event_id"])):
                return _blocked("RECEIPT_NOT_MATCHING_LOCAL_AUDIT_EVENT")
    except (KeyError, TypeError, ValueError, OSError, sqlite3.Error,
            OverflowError, RecursionError, UnicodeError):
        return _blocked("INVALID_SOURCE_RECEIPT_OR_SQLITE")

    return {
        **_blocked("SOURCE_AND_LOCAL_LEDGER_ONLY"),
        "status": "VERIFIED_LOCAL_RECEIPT_MATCH_ONLY",
        "reason_code": "NO_EXTERNAL_OR_LICENSE_ATTESTATION",
        "local_chain_valid": True, "receipt_matches_local_source": True,
        "event_hash": event["event_hash"],
        "historical_replayed_flag_attested": False,
    }
