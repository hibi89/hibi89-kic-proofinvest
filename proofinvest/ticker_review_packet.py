"""P159: single-file local reviewer packet for replayed KUODRA A/B/C evidence.

No network, persistent storage, trade, source authentication, data-rights
grant, or LLM call. This wraps only the already redacted 16KiB evidence and
its deterministic A/B/C interpretation. A SHA256 detects local mutation but
cannot authenticate upstream publishers or independently replay missing raw
sources. The UI must call verify_linked_market_evidence with the original
inputs BEFORE invoking build_review_packet.
"""
from __future__ import annotations

from hashlib import sha256
from hmac import compare_digest
import json
from typing import Any

from .ticker_evidence_explanation import (
    explain_linked_market_receipt, explanation_json_bytes,
)
from .ticker_market_pair_evidence import linked_evidence_json_bytes

_SCHEMA = "kuodra.local-a-b-c-review-packet.v1"
_STATUS = "LOCAL_REPLAYED_REVIEW_ONLY_UNVERIFIED"
_MAX_PACKET_BYTES = 28672


def _canonical(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def build_review_packet(linked: Any) -> dict:
    """Package strictly redacted evidence + its recomputed explanation.

    Caller MUST already have independently replayed linked vs original files.
    This method intentionally does not convert local math replay to publisher,
    vendor-license or investment-signal authentication.
    """
    if type(linked) is not dict:
        raise ValueError("REVIEW_PACKET_LINKED_RECEIPT_REQUIRED")
    linked_evidence_json_bytes(linked)
    explanation = explain_linked_market_receipt(linked)
    explanation_json_bytes(explanation)
    packet = {
        "schema": _SCHEMA, "status": _STATUS,
        "issuer": dict(linked["issuer"]),
        "linked_evidence": linked,
        "explanation": explanation,
        "guard_policy_preview": "HOLD",
        "guard_executed": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "ai_agent_executed": False,
        "investment_recommendation": False,
        "trade_executed": False,
        "external_sharing_allowed": False,
        "notice": (
            "로컬 산술 재검산 자료만 포함합니다. 원문·시장 데이터 공급자 인증, "
            "재배포 권리, AI 해석, 투자 자문 또는 거래 권한을 증명하지 않습니다."
        ),
    }
    packet["packet_sha256"] = sha256(_canonical(packet)).hexdigest()
    if len(_canonical(packet)) > _MAX_PACKET_BYTES:
        raise ValueError("REVIEW_PACKET_TOO_LARGE")
    return packet


def review_packet_json_bytes(packet: Any) -> bytes:
    """Reject forged, extra-field, rights-elevated, or mislinked packet."""
    if (type(packet) is not dict or set(packet) != {
            "schema", "status", "issuer", "linked_evidence", "explanation",
            "guard_policy_preview", "guard_executed", "source_authenticated",
            "source_rights_verified", "ai_agent_executed",
            "investment_recommendation", "trade_executed",
            "external_sharing_allowed", "notice", "packet_sha256"
            }
            or packet.get("schema") != _SCHEMA or packet.get("status") != _STATUS
            or packet.get("guard_policy_preview") != "HOLD"
            or any(packet.get(k) is not False for k in (
                "guard_executed", "source_authenticated",
                "source_rights_verified", "ai_agent_executed",
                "investment_recommendation", "trade_executed",
                "external_sharing_allowed"))):
        raise ValueError("REVIEW_PACKET_CONTRACT_INVALID")
    import re
    digest = packet.get("packet_sha256")
    if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}\Z", digest) is None:
        raise ValueError("REVIEW_PACKET_DIGEST_INVALID")
    linked = packet["linked_evidence"]
    linked_evidence_json_bytes(linked)
    regenerated = explain_linked_market_receipt(linked)
    explanation_json_bytes(regenerated)
    if (type(packet.get("issuer")) is not dict
            or packet["issuer"] != linked["issuer"]
            or type(packet.get("explanation")) is not dict
            or packet["explanation"] != regenerated
            or packet.get("notice") != (
                "로컬 산술 재검산 자료만 포함합니다. 원문·시장 데이터 공급자 인증, "
                "재배포 권리, AI 해석, 투자 자문 또는 거래 권한을 증명하지 않습니다.")):
        raise ValueError("REVIEW_PACKET_EVIDENCE_LINK_INVALID")
    unsigned = {k: v for k, v in packet.items() if k != "packet_sha256"}
    if not compare_digest(digest, sha256(_canonical(unsigned)).hexdigest()):
        raise ValueError("REVIEW_PACKET_CHECKSUM_INVALID")
    raw = _canonical(packet)
    if len(raw) > _MAX_PACKET_BYTES:
        raise ValueError("REVIEW_PACKET_TOO_LARGE")
    return raw


def inspect_review_packet_bytes(raw: Any) -> dict:
    """Offline verification of one downloaded packet's internal integrity.

    This does not verify provider provenance; that still needs the original
    supplied SEC and market inputs and verify_linked_market_evidence.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_PACKET_BYTES:
        raise ValueError("REVIEW_PACKET_BYTES_INVALID")

    def no_duplicates(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("REVIEW_PACKET_DUPLICATE_JSON_KEY")
            obj[key] = value
        return obj

    def no_nonfinite(value):
        raise ValueError("REVIEW_PACKET_NONFINITE_NUMBER")

    try:
        packet = json.loads(
            raw.decode("utf-8"), object_pairs_hook=no_duplicates,
            parse_constant=no_nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("REVIEW_PACKET_JSON_INVALID") from exc
    if review_packet_json_bytes(packet) != raw:
        raise ValueError("REVIEW_PACKET_NONCANONICAL")
    return {
        "schema": "kuodra.local-a-b-c-review-packet-check.v1",
        "status": "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED",
        "packet_sha256": packet["packet_sha256"],
        "linked_evidence_sha256": packet["linked_evidence"]["evidence_sha256"],
        "ticker": packet["issuer"]["ticker"],
        "guard_policy_preview": "HOLD",
        "source_authenticated": False,
        "source_rights_verified": False,
        "external_sharing_allowed": False,
        "trade_executed": False,
    }


def verify_review_packet_against_sources(
    raw_packet: Any, *, workflow: Any, sources: Any, stock: Any, index: Any,
    market_json: bytes | None = None, industry_json: bytes | None = None,
) -> dict[str, Any]:
    """Independently replay a downloaded packet against supplied source inputs.

    Unlike inspect_review_packet_bytes, this requires the actual local SEC
    originals and in-memory stock / index receipts. Neither this replay nor
    a supplied vendor receipt authenticates SEC/provider origin or grants
    legal use, redistribution or trading permission. Never performs network.
    """
    outcome = {
        "schema": "kuodra.review-packet-independent-replay.v1",
        "status": "FAIL",
        "reason_code": "PACKET_OR_ORIGINAL_SOURCES_INVALID",
        "packet_internal_integrity_passed": False,
        "local_source_replay_verified": False,
        "market_math_recomputed": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "ai_agent_executed": False,
        "guard_executed": False,
        "trade_executed": False,
        "external_sharing_allowed": False,
    }
    try:
        # Strict canonical packet validation must precede any source replay.
        inspected = inspect_review_packet_bytes(raw_packet)
        if inspected["status"] != "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED":
            return outcome
        outcome["packet_internal_integrity_passed"] = True
        packet = json.loads(raw_packet.decode("utf-8"))
        from .ticker_market_pair_evidence import verify_linked_market_evidence
        verified = verify_linked_market_evidence(
            packet["linked_evidence"],
            workflow=workflow, sources=sources, stock=stock, index=index,
            market_json=market_json, industry_json=industry_json,
        )
        if (verified.get("status") != "PASS"
                or verified.get("local_replay_verified") is not True
                or verified.get("market_math_recomputed") is not True
                or verified.get("network_requests") != 0
                or verified.get("source_authenticated") is not False
                or verified.get("source_rights_verified") is not False):
            outcome["reason_code"] = "SOURCE_OR_MARKET_REPLAY_MISMATCH"
            return outcome
        outcome.update(
            status="PASS_UNVERIFIED_ORIGIN",
            reason_code="EXACT_LOCAL_AND_MARKET_MATH_REPLAY",
            local_source_replay_verified=True,
            market_math_recomputed=True,
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError,
            UnicodeError, RecursionError, json.JSONDecodeError):
        return outcome
    return outcome
