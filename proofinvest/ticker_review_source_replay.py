"""P166: independently reconstruct a downloaded reviewer packet from local originals.

Explicit offline verifier. No HTTP, file writes, session cache, vendor rights
assertion, LLM, Guard execution or investment/trade authorization. A strict
match certifies only that the exact user-supplied original bytes reproduce
the packet's source-bound local arithmetic; it does not establish publisher
authenticity, data entitlements, acquisition time or redistribution rights.
"""
from __future__ import annotations

from hashlib import sha256
from hmac import compare_digest
import json
from typing import Any

from .market_provider_alpha_vantage import (
    _MAX_BODY as STOCK_LIMIT, parse_daily_close_bytes,
)
from .market_provider_alpha_vantage_index import (
    _MAX_RESPONSE as INDEX_LIMIT, parse_index_daily_bytes,
)
from .ticker_review_packet import (
    _MAX_PACKET_BYTES as PACKET_LIMIT,
    inspect_review_packet_bytes, verify_review_packet_against_sources,
)
from .ticker_sec_financial_bridge import _LIMITS as SEC_LIMITS

_OPTIONAL_LIMITS = {"market_json": 131072, "industry_json": 65536}


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.review-packet-offline-original-replay.v1",
        "status": "FAIL", "reason_code": reason,
        "packet_internal_integrity_passed": False,
        "original_byte_hashes_matched": False,
        "local_source_replay_verified": False,
        "market_math_recomputed": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "market_vintage_authenticated": False,
        "external_sharing_allowed": False,
        "guard_executed": False, "ai_agent_executed": False,
        "trade_executed": False, "network_requests": 0,
    }


def _bounded(raw: Any, ceiling: int) -> bool:
    return type(raw) is bytes and 0 < len(raw) <= ceiling


def replay_review_packet_from_original_bytes(
    raw_packet: Any, *, sources: Any,
    stock_raw: Any, index_raw: Any,
    market_json: bytes | None = None,
    industry_json: bytes | None = None,
) -> dict[str, Any]:
    """Recompute 7-step SEC, A/B/C local math and paired stock/NDX math.

    The packet must be canonical and the extra sources exact-byte matched
    BEFORE any full decoding or processing of the underlying original inputs.
    Optional A/C inputs are required iff referenced by the packet, so
    omitting or substituting a needed file cannot yield a false PASS.
    """
    failed = _result("PACKET_OR_SOURCE_BYTES_INVALID")
    if (not _bounded(raw_packet, PACKET_LIMIT)
            or type(sources) is not dict or set(sources) != set(SEC_LIMITS)
            or any(not _bounded(sources[k], limit)
                   for k, limit in SEC_LIMITS.items())
            or not _bounded(stock_raw, STOCK_LIMIT)
            or not _bounded(index_raw, INDEX_LIMIT)
            or (market_json is not None
                and not _bounded(market_json, _OPTIONAL_LIMITS["market_json"]))
            or (industry_json is not None
                and not _bounded(industry_json, _OPTIONAL_LIMITS["industry_json"]))):
        return failed
    try:
        inspected = inspect_review_packet_bytes(raw_packet)
        if inspected["status"] != "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED":
            return failed
        failed["packet_internal_integrity_passed"] = True
        packet = json.loads(raw_packet.decode("utf-8"))
        linked = packet["linked_evidence"]
        issuer = packet["issuer"]
        expected = linked["four_source_sha256"]
        comparisons = [
            (sources[k], expected[k]) for k in SEC_LIMITS
        ] + [
            (stock_raw, linked["premium_engine_a"]["stock_response_sha256"]),
            (index_raw, linked["premium_engine_a"]["index_response_sha256"]),
        ]
        for key, field in (
            ("market_json", "local_engine_a"),
            ("industry_json", "engine_c"),
        ):
            supplied = market_json if key == "market_json" else industry_json
            digest = linked[field]["input_sha256"]
            if (digest is None) != (supplied is None):
                failed["reason_code"] = "OPTIONAL_SOURCE_COVERAGE_MISMATCH"
                return failed
            if supplied is not None:
                comparisons.append((supplied, digest))
        if not all(
            type(digest) is str and
            compare_digest(sha256(raw).hexdigest(), digest)
            for raw, digest in comparisons
        ):
            failed["reason_code"] = "EXACT_ORIGINAL_BYTES_HASH_MISMATCH"
            return failed
        failed["original_byte_hashes_matched"] = True

        from .ticker_local_workflow import run_local_ticker_workflow
        workflow = run_local_ticker_workflow(
            ticker=issuer["ticker"], as_of=issuer["as_of"],
            sources=sources, market_json=market_json,
            industry_json=industry_json,
        )
        stock = parse_daily_close_bytes(
            stock_raw, ticker=issuer["ticker"], as_of=issuer["as_of"],
        )
        index = parse_index_daily_bytes(
            index_raw, benchmark="NASDAQ_100", as_of=issuer["as_of"],
        )
        verdict = verify_review_packet_against_sources(
            raw_packet, workflow=workflow, sources=sources,
            stock=stock, index=index,
            market_json=market_json, industry_json=industry_json,
        )
        if (verdict.get("status") != "PASS_UNVERIFIED_ORIGIN"
                or verdict.get("packet_internal_integrity_passed") is not True
                or verdict.get("local_source_replay_verified") is not True
                or verdict.get("market_math_recomputed") is not True
                or verdict.get("source_authenticated") is not False
                or verdict.get("source_rights_verified") is not False
                or verdict.get("trade_executed") is not False):
            failed["reason_code"] = "LOCAL_SOURCE_OR_MARKET_MATH_REPLAY_FAILED"
            return failed
        return {
            **failed, "status": "PASS_UNVERIFIED_ORIGIN",
            "reason_code": "EXACT_ORIGINALS_AND_MATH_RECOMPUTED",
            "packet_internal_integrity_passed": True,
            "original_byte_hashes_matched": True,
            "local_source_replay_verified": True,
            "market_math_recomputed": True,
            "ticker": issuer["ticker"],
            "packet_sha256": sha256(raw_packet).hexdigest(),
        }
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError,
            RecursionError, UnicodeError, json.JSONDecodeError):
        failed["reason_code"] = "LOCAL_SOURCE_OR_MARKET_MATH_REPLAY_FAILED"
        return failed
