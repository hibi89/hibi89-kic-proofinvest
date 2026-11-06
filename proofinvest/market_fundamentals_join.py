"""Join a replayed local 3-5 issuer market panel to pinned issuer B/C.

This is a read-only, one-click descriptive evidence display. It does not
authenticate owner JSON, establish chronology of release publication, infer
a price/fundamentals causal link, obtain data rights or approve a trade.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
from typing import Any

from .market_panel_review import verify_local_market_panel
from .global_fundamentals_review import (
    build_marketless_global_review, verify_marketless_global_review,
)

_SCHEMA = "kuodra.local-panel-fundamentals-join.v1"
_VINTAGE = date(2026, 11, 5)
_POSITIVE = frozenset((
    "LOCAL_MARKET_AND_NVDA_B_C_REVIEW_UNVERIFIED",
    "LOCAL_MARKET_ONLY_B_C_UNAVAILABLE",
))


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "issuers": [], "market_api_requests": 0, "llm_requests": 0,
        "guard_decision": "HOLD", "full_abc_complete": False,
        "source_rights_verified": False, "public_display_allowed": False,
        "trade_executed": False,
    }


def build_local_panel_fundamentals_join(
    market_report: dict[str, Any],
    sources: dict[str, bytes],
    symbols: list[str],
    filing_dates: dict[str, str],
    *, as_of: str,
) -> dict[str, Any]:
    """Strictly replay original in-memory price bytes, then B/C issuer ledger.

    A pinned B/C review from 2026-11-05 must not appear in a market report
    whose as-of or final observation predates that review. The market filing
    dates are OPERATOR assertions, not the release-publication evidence for B.
    """
    if not verify_local_market_panel(
            market_report, sources, symbols, filing_dates, as_of=as_of):
        return _blocked("MARKET_PANEL_SOURCE_REPLAY_FAILED")
    try:
        review_day = date.fromisoformat(as_of)
        if (type(as_of) is not str or review_day.isoformat() != as_of
                or market_report.get("as_of") != as_of
                or market_report.get("index_symbol") != "I:NDX"
                or market_report.get("issuer_count") != len(symbols)
                or [r["ticker"] for r in market_report["issuers"]] != symbols
                or market_report.get("guard_decision") != "HOLD"
                or market_report.get("source_authenticated") is not False
                or market_report.get("source_rights_verified") is not False
                or market_report.get("public_display_allowed") is not False
                or market_report.get("full_a_b_c_ready") is not False
                or market_report.get("network_requests") != 0):
            return _blocked("MARKET_PANEL_CROSS_BOUNDARY_INVALID")
        results = []
        bc_count = 0
        for row in market_report["issuers"]:
            ticker = row["ticker"]
            end = date.fromisoformat(row["matched_period_end"])
            start = date.fromisoformat(row["matched_period_start"])
            declared_filing = date.fromisoformat(row["filing_date"])
            if (start > end or end > review_day or
                    declared_filing >= start or
                    row["issuer_cik"] != {
                        "NVDA": "0001045810", "AAPL": "0000320193",
                        "MSFT": "0000789019", "AMZN": "0001018724",
                        "GOOGL": "0001652044",
                    }[ticker]):
                return _blocked("ISSUER_PERIOD_OR_IDENTITY_MISMATCH")
            b, c, origin = None, None, None
            if ticker != "NVDA":
                bc_status = "UNAVAILABLE_NO_PINNED_FIRST_PARTY_B_C_FOR_ISSUER"
            elif review_day < _VINTAGE:
                bc_status = "UNAVAILABLE_B_C_REVIEW_AFTER_MARKET_ASOF"
            elif end < _VINTAGE:
                bc_status = "UNAVAILABLE_MARKET_END_BEFORE_B_C_REVIEW"
            else:
                receipt = build_marketless_global_review(ticker="NVDA")
                if (not verify_marketless_global_review(receipt)
                        or receipt.get("ticker") != ticker
                        or receipt.get("cik") != row["issuer_cik"]
                        or receipt.get("reviewed_as_of") != _VINTAGE.isoformat()
                        or receipt.get("guard", {}).get("decision") != "HOLD"
                        or receipt.get("external_sharing_allowed") is not False
                        or receipt.get("full_abc_complete") is not False
                        or date.fromisoformat(
                            receipt["source"]["fiscal_latest_end"]) >= start):
                    return _blocked("ISSUER_B_C_RECEIPT_OR_FISCAL_PERIOD_FAILED")
                # Historical first-party B and historical peer references C,
                # not verified SEC originals or a licensed, same-date cohort.
                b = receipt["engine_b"]
                c = receipt["engine_c"]
                origin = receipt["source"]
                bc_status = "HISTORICAL_NVDA_B_C_SEPARATE_EVIDENCE_ONLY"
                bc_count += 1
            results.append({
                "ticker": ticker, "issuer_cik": row["issuer_cik"],
                "market_as_of": as_of,
                "market_start": row["matched_period_start"],
                "market_end": row["matched_period_end"],
                "operator_claimed_10k_filing_date": row["filing_date"],
                "market_stock_sha256": row["stock_response_sha256"],
                "market_ndx_sha256": row["index_response_sha256"],
                "engine_a": row["market_analysis"],
                "engine_b": b, "engine_c": c, "issuer_source": origin,
                "bc_status": bc_status,
                "b_and_c_review_as_of": (
                    _VINTAGE.isoformat() if b is not None else None),
                "same_document_as_operator_filing_verified": False,
                "market_fundamental_causal_alignment_verified": False,
                "guard_decision": "HOLD",
            })
        payload = {
            "schema": _SCHEMA,
            "status": (
                "LOCAL_MARKET_AND_NVDA_B_C_REVIEW_UNVERIFIED"
                if bc_count else "LOCAL_MARKET_ONLY_B_C_UNAVAILABLE"),
            "as_of": as_of, "index_symbol": "I:NDX",
            "issuer_count": len(results), "bc_issuer_count": bc_count,
            "ndx_snapshot_sha256": market_report["ndx_snapshot_sha256"],
            "issuers": results,
            "data_alignment_note": (
                "A is operator-supplied, unauthenticated market math; B is a "
                "historical issuer release and C historical unmatched peers. "
                "Operator 10-K dates are not authenticated publication dates. "
                "A/B/C are NOT causal, licensed, or time-matched investment signals."),
            "market_api_requests": 0, "llm_requests": 0,
            "guard_decision": "HOLD", "full_abc_complete": False,
            "market_fundamental_causal_alignment_verified": False,
            "sec_original_authenticated": False,
            "market_vendor_authenticated": False,
            "source_rights_verified": False,
            "public_display_allowed": False,
            "human_approved": False, "trade_executed": False,
        }
        signed = _canonical(payload)
        if len(signed) > 65536:
            return _blocked("JOINED_REPORT_TOO_LARGE")
        payload["derived_sha256"] = sha256(signed).hexdigest()
        return payload
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return _blocked("JOINED_REPORT_VALIDATION_FAILED")


def verify_local_panel_fundamentals_join(
    joined: Any,
    market_report: dict[str, Any],
    sources: dict[str, bytes],
    symbols: list[str],
    filing_dates: dict[str, str],
    *, as_of: str,
) -> bool:
    """Independent complete recalculation; a rehashed forgery still fails."""
    if (type(joined) is not dict or joined.get("status") not in _POSITIVE
            or type(joined.get("derived_sha256")) is not str):
        return False
    try:
        digest = joined["derived_sha256"]
        unsigned = dict(joined)
        del unsigned["derived_sha256"]
        if sha256(_canonical(unsigned)).hexdigest() != digest:
            return False
        return joined == build_local_panel_fundamentals_join(
            market_report, sources, symbols, filing_dates, as_of=as_of)
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError):
        return False
