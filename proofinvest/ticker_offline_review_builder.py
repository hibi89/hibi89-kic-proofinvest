"""P167: one-click, user-supplied SEC + stock + NDX -> downloadable review.

This is the previously missing *initial* offline A/B/C packet production path:
P166 could only replay a packet already created by an approved paid-provider
fetch. This route never fetches SEC or vendor endpoints, never caches originals,
executes no AI/Guard/trade, and never upgrades origin or license claims.
"""
from __future__ import annotations

from typing import Any

from .market_provider_alpha_vantage import (
    _MAX_BODY as STOCK_LIMIT, parse_daily_close_bytes,
)
from .market_provider_alpha_vantage_index import (
    _MAX_RESPONSE as INDEX_LIMIT, parse_index_daily_bytes,
)
from .ticker_sec_financial_bridge import _LIMITS as SEC_LIMITS

_MARKET_LIMIT = 131072
_INDUSTRY_LIMIT = 65536


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.offline-initial-a-b-c-review.v1",
        "status": "BLOCKED", "reason_code": reason,
        "network_requests": 0, "paid_requests": 0,
        "local_replay_verified": False,
        "market_math_recomputed": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "market_vintage_authenticated": False,
        "external_sharing_allowed": False,
        "guard_executed": False, "ai_agent_executed": False,
        "trade_executed": False,
    }


def _within(raw: Any, limit: int) -> bool:
    return type(raw) is bytes and 0 < len(raw) <= limit


def build_offline_initial_review(
    *, ticker: Any, as_of: Any, sources: Any, stock_raw: Any,
    index_raw: Any, market_json: Any = None, industry_json: Any = None,
) -> dict[str, Any]:
    """Build and independently replay the whole A/B/C+Guard HOLD package.

    Price data must be user-supplied provider-format raw bytes with Nasdaq-100
    symbol NDX, not an ETF substitute. No issuer, provider or license
    authentication is possible from these unsigned local data.
    """
    if (type(ticker) is not str or type(as_of) is not str
            or type(sources) is not dict or set(sources) != set(SEC_LIMITS)
            or any(not _within(sources[k], limit)
                   for k, limit in SEC_LIMITS.items())
            or not _within(stock_raw, STOCK_LIMIT)
            or not _within(index_raw, INDEX_LIMIT)
            or (market_json is not None
                and not _within(market_json, _MARKET_LIMIT))
            or (industry_json is not None
                and not _within(industry_json, _INDUSTRY_LIMIT))):
        return _blocked("ORIGINAL_SOURCE_INPUTS_REQUIRED")
    try:
        from .ticker_local_workflow import run_local_ticker_workflow
        from .ticker_market_pair_evidence import (
            build_linked_market_evidence, verify_linked_market_evidence,
            linked_evidence_json_bytes,
        )
        from .ticker_review_packet import (
            build_review_packet, review_packet_json_bytes,
        )
        from .ticker_review_source_replay import (
            replay_review_packet_from_original_bytes,
        )

        workflow = run_local_ticker_workflow(
            ticker=ticker, as_of=as_of, sources=sources,
            market_json=market_json, industry_json=industry_json,
        )
        if (workflow.get("status") != "READY_FOR_HUMAN_REVIEW_UNVERIFIED"
                or workflow.get("network_requests") != 0
                or workflow.get("guard_executed") is not False
                or workflow.get("source_authenticated") is not False):
            return _blocked("SEC_OR_GUARD_SOURCE_REPLAY_INELIGIBLE")
        issuer = workflow["report"]["issuer"]
        if (issuer.get("ticker") != ticker
                or issuer.get("as_of") != as_of
                or workflow["report"]["guard_policy_preview"] != "HOLD"):
            return _blocked("ISSUER_PERIOD_OR_GUARD_NOT_ELIGIBLE")

        stock = parse_daily_close_bytes(
            stock_raw, ticker=ticker, as_of=as_of,
        )
        index = parse_index_daily_bytes(
            index_raw, benchmark="NASDAQ_100", as_of=as_of,
        )
        linked = build_linked_market_evidence(
            workflow=workflow, sources=sources, stock=stock, index=index,
            market_json=market_json, industry_json=industry_json,
        )
        if (linked.get("status") != "LOCAL_AND_MARKET_MATH_REPLAYED_UNVERIFIED"
                or verify_linked_market_evidence(
                    linked, workflow=workflow, sources=sources,
                    stock=stock, index=index,
                    market_json=market_json,
                    industry_json=industry_json,
                ).get("status") != "PASS"):
            return _blocked("PRICE_INDEX_OR_FILING_CUTOFF_REPLAY_FAILED")

        linked_evidence_json_bytes(linked)
        packet_bytes = review_packet_json_bytes(build_review_packet(linked))
        replay = replay_review_packet_from_original_bytes(
            packet_bytes, sources=sources,
            stock_raw=stock_raw, index_raw=index_raw,
            market_json=market_json, industry_json=industry_json,
        )
        if (replay.get("status") != "PASS_UNVERIFIED_ORIGIN"
                or replay.get("local_source_replay_verified") is not True
                or replay.get("market_math_recomputed") is not True
                or replay.get("source_rights_verified") is not False):
            return _blocked("INDEPENDENT_PACKET_REPLAY_FAILED")

        return {
            **_blocked(""),
            "status": "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED",
            "reason_code": "LOCAL_SEC_AND_NDX_MATH_REPLAYED_NO_ORIGIN_PROOF",
            "ticker": issuer["ticker"],
            "as_of": issuer["as_of"],
            "accession": issuer["accession"],
            "matched_sessions": linked["premium_engine_a"]["matched_observation_count"],
            "guard_policy_preview": "HOLD",
            "local_replay_verified": True,
            "market_math_recomputed": True,
            "review_packet": packet_bytes,
        }
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError,
            RecursionError, OverflowError):
        return _blocked("INVALID_SOURCE_OR_MARKET_RESPONSE")
