"""P185: no-network numerical claim guard for a human-reviewed A/B/C packet.

A local model draft can only assert the exact observed return difference from
a canonical review receipt. Matching an unsigned local source is NOT proof of
SEC/vendor provenance, data license, financial correctness or agent quality.

The caller is responsible for independent original-source replay and permitted
use before supplying any real data; this function never transmits anything.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .ticker_review_packet import inspect_review_packet_bytes
from .ticker_source_clearance_packet import inspect_source_clearance_packet

_SCHEMA = "kuodra.local-model-numeric-claim.v1"
_CLAIM = "OBSERVED_PRICE_RETURN_GAP_PP"
_ACCEPTED = "LOCAL_MODEL_NUMERIC_MATCH_TO_UNSIGNED_REVIEW_ONLY"
_MAX_DRAFT = 1024
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]{0,5})\.[0-9]{4}\Z", re.ASCII)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.local-model-numeric-claim-check.v1",
        "status": "BLOCKED",
        "reason_code": reason,
        "local_numeric_claim_recomputed": False,
        "publisher_source_authenticated": False,
        "source_rights_verified": False,
        "model_origin_authenticated": False,
        "ai_agent_executed": False,
        "external_sharing_allowed": False,
        "guard_policy_preview": "HOLD",
        "investment_recommendation": False,
        "trade_executed": False,
        "external_network_requests": 0,
    }


def _parse_exact_json(data: bytes) -> Any:
    def strict_pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError("NUMERIC_DRAFT_DUPLICATE_KEY")
            obj[key] = value
        return obj

    def deny_nonfinite(_):
        raise ValueError("NUMERIC_DRAFT_NONFINITE")

    return json.loads(data.decode("utf-8"), object_pairs_hook=strict_pairs,
                      parse_constant=deny_nonfinite)


def verify_local_model_numeric_claim(
    review_packet: bytes, clearance_report: bytes, proposal_json: bytes,
) -> dict[str, Any]:
    """Check a proposed *descriptive* price gap against trusted local replay.

    A valid report is for HUMAN_REVIEW_ONLY, not an LLM-sourced conclusion.
    No free-text model explanation is exported. The output uses only the
    pre-existing vetted deterministic statement in the review packet.
    """
    if (type(proposal_json) is not bytes or not 0 < len(proposal_json) <= _MAX_DRAFT):
        return _blocked("NUMERIC_MODEL_DRAFT_MISSING_OR_OVERSIZED")
    try:
        checked = inspect_review_packet_bytes(review_packet)
        rights = inspect_source_clearance_packet(
            clearance_report, review_packet=review_packet,
        )
        if (checked.get("status") != "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED"
                or rights.get("status") != "MATCHED_REPORT_EXTERNAL_CLEARANCES_STILL_PENDING"
                or checked.get("source_rights_verified") is not False
                or rights.get("source_rights_verified") is not False
                or checked.get("guard_policy_preview") != "HOLD"):
            return _blocked("UNVERIFIED_MATCHED_SOURCE_RECEIPTS_REQUIRED")
        proposal = _parse_exact_json(proposal_json)
        if (type(proposal) is not dict or set(proposal) != {
            "schema", "engine", "claim_kind", "gap_pp", "decision",
        } or proposal.get("schema") != _SCHEMA
                or proposal.get("engine") != "A"
                or proposal.get("claim_kind") != _CLAIM
                or proposal.get("decision") != "HUMAN_REVIEW_ONLY"):
            return _blocked("MODEL_NUMERIC_SCHEMA_OR_ADVICE_REJECTED")
        packet = _parse_exact_json(review_packet)
        finding = packet["explanation"]["findings"][0]
        evidence = packet["linked_evidence"]["premium_engine_a"]
        if (finding.get("basis") != "PRICE_ONLY_CLOSE_VS_ACTUAL_NASDAQ_100"
                or finding.get("engine") != "A"
                or packet["guard_policy_preview"] != "HOLD"
                or evidence.get("benchmark") != "NASDAQ_100"
                or evidence.get("basis") != "PRICE_ONLY_CLOSE"
                or finding.get("simple_return_gap_pp") is None):
            return _blocked("OBSERVED_GAP_NOT_AVAILABLE")
        expected_gap = finding["simple_return_gap_pp"]
        actual_gap = proposal["gap_pp"]
        if (type(expected_gap) is not str or type(actual_gap) is not str
                or _DECIMAL.fullmatch(actual_gap) is None
                or _DECIMAL.fullmatch(expected_gap) is None
                or expected_gap != actual_gap):
            return _blocked("MODEL_NUMERIC_CLAIM_NOT_SUPPORTED")
        # Independently check the two return operands, not only the
        # deterministic explanation's precomputed result.
        try:
            a = evidence["security_return_pct"]
            b = evidence["benchmark_return_pct"]
            if type(a) is not str or type(b) is not str:
                return _blocked("GAP_OPERANDS_UNAVAILABLE")
            recomputed = str((Decimal(a) - Decimal(b)).quantize(
                Decimal("0.0001")
            ))
        except (InvalidOperation, ValueError, OverflowError):
            return _blocked("GAP_OPERANDS_INVALID")
        if (recomputed != actual_gap or not Decimal(recomputed).is_finite()):
            return _blocked("INDEPENDENT_GAP_RECOMPUTE_MISMATCH")
        return {
            **_blocked(""),
            "status": _ACCEPTED,
            "reason_code": "LOCAL_DECIMAL_REPLAY_ONLY_NOT_PUBLISHER_TRUTH",
            "local_numeric_claim_recomputed": True,
            "review_packet_sha256": checked["packet_sha256"],
            "linked_evidence_sha256": checked["linked_evidence_sha256"],
            "engine": "A",
            "basis": "PRICE_ONLY_CLOSE_VS_ACTUAL_NASDAQ_100",
            "simple_return_gap_pp": recomputed,
            "safe_existing_interpretation": finding["interpretation"],
        }
    except (ValueError, TypeError, KeyError, AttributeError,
            UnicodeError, OverflowError, RecursionError, MemoryError):
        return _blocked("MODEL_OR_REVIEW_RECEIPT_INVALID")
