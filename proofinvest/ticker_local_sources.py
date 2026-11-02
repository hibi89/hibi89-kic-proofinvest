"""P116: local four-file SEC-shaped source intake, zero network.

This records only consistency of caller-provided bytes. It is NOT a SEC
download, publisher authentication, data license, or an approved investment
finding. P105 SEC HTTP403 HOLD is never consulted or bypassed: no HTTP exists.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from .ticker_research_intake import (
    MAP_URL, SEC_API, _cik, _json, build_ticker_source_plan,
)
from .ticker_sec_financial_bridge import _KEYS, _LIMITS


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.local-sec-source-receipt.v1",
        "status": "unavailable", "reason_code": reason,
        "source_kind": "CALLER_SUPPLIED_LOCAL_UNAUTHENTICATED",
        "http_requests_attempted": 0, "network_requests": 0,
        "live_sec_http_called": False, "live_data_retrieved": False,
        "source_authenticated": False, "source_rights_verified": False,
        "point_in_time_verified": False, "full_a_b_c_ready": False,
        "ai_interpretation_ready": False, "trade_executed": False,
        "original_saved": False, "external_ai_called": False,
        "raw_companyfacts_financial_values_verified": False,
    }


def prepare_local_ticker_sources(
    *, ticker: str, as_of: str, sources: dict[str, bytes],
) -> dict[str, Any]:
    """Produce a digest-bound local-only receipt, or fail without partial data.

    This is not a transport adapter: the receipt *cannot* claim HTTP occurred.
    All downstream arithmetic/Guard must retain unavailable/unverified flags.
    """
    try:
        if type(sources) is not dict or set(sources) != set(_KEYS):
            return _blocked("FOUR_LOCAL_SOURCES_REQUIRED")
        for name in _KEYS:
            raw = sources[name]
            if type(raw) is not bytes or not 0 < len(raw) <= _LIMITS[name]:
                return _blocked("LOCAL_SOURCE_BYTES_OR_SIZE_INVALID")
        plan = build_ticker_source_plan(
            ticker=ticker, ticker_map=sources["ticker_map"],
            submissions=sources["submissions"], as_of=as_of,
        )
        if plan.get("status") != "10k_source_plan_unverified":
            return _blocked("LOCAL_ISSUER_10K_PLAN_UNAVAILABLE")
        cik = plan["cik"]
        facts = _json(sources["companyfacts"], _LIMITS["companyfacts"], "COMPANYFACTS")
        if _cik(facts.get("cik")) != cik:
            return _blocked("LOCAL_COMPANYFACTS_CIK_MISMATCH")
        filing = plan["latest_10k"]
        return {
            **_blocked("LOCAL_BYTES_ARE_NOT_AUTHENTICATED"),
            "status": "local_four_sources_unverified",
            "ticker": plan["ticker"],
            "cik": cik,
            "requested_as_of": as_of,
            "selected_10k_accession": filing["accession"],
            "selected_10k_filing_date": filing["filing_date"],
            "source_urls": {
                "ticker_map": MAP_URL,
                "submissions": f"{SEC_API}/submissions/CIK{cik}.json",
                "companyfacts": f"{SEC_API}/api/xbrl/companyfacts/CIK{cik}.json",
                "original_10k": filing["original_filing_url"],
            },
            "source_sha256": {k: sha256(sources[k]).hexdigest() for k in _KEYS},
            "source_bytes": {k: len(sources[k]) for k in _KEYS},
        }
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError,
            RecursionError):
        return _blocked("LOCAL_SOURCE_STRUCTURE_UNAVAILABLE")
