"""P101 read-only SEC transport -> same-10-K annual revenue bridge.

Consumes only P99's in-memory source bytes and exact SHA-pinned receipt.
Does NOT authenticate SEC origin, inspect full 10-K text, forecast, execute
Guard/AI/trades, or infer A/C indicators from a single issuer's revenue.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from typing import Any

from .sec_companyfacts import REVENUE_TAGS, MAX_ROWS, verify_sec_annual_revenue, _date as sec_date
from .ticker_research_intake import (
    MAP_URL, MAX_MAP_BYTES, MAX_SUBMISSIONS_BYTES, SEC_API, _cik, _json,
    build_ticker_source_plan,
)
from .local_sec_packet import _MAX_FILE_BYTES

_MAX_HTML_BYTES = 24_000_000
_KEYS = ("ticker_map", "submissions", "companyfacts", "original_10k")
_LIMITS = dict(ticker_map=MAX_MAP_BYTES, submissions=MAX_SUBMISSIONS_BYTES,
               companyfacts=_MAX_FILE_BYTES, original_10k=_MAX_HTML_BYTES)


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.single-ticker-sec-revenue-bridge.v1",
        "status": "UNAVAILABLE",
        "reason_code": reason,
        "issuer_cik": None, "ticker": None, "accession": None,
        "current_end": None, "prior_end": None,
        "current_usd": None, "prior_usd": None, "growth_pct": None,
        "revenue_concept": None,
        "source_authenticated": False, "source_rights_verified": False,
        "original_10k_text_verified": False, "financial_values_authenticated": False,
        "engine_a_ready": False, "engine_b_full_ready": False,
        "engine_c_ready": False, "guard_executed": False,
        "ai_interpretation_ready": False, "trade_executed": False,
    }


def inspect_collected_annual_revenue(
    receipt: dict, raw_sources: dict[str, bytes] | None,
) -> dict[str, Any]:
    """Bounded, deterministic arithmetic. Fails closed without partial metrics.

    Intentionally no networking or source writes; all references are checked
    against a recomputed issuer/10-K plan and the transport's source digests.
    """
    try:
        if type(receipt) is not dict or type(raw_sources) is not dict:
            return _unavailable("SOURCE_RECEIPT_MISSING")
        if (receipt.get("schema") != "kuodra.single-ticker-sec-transport.v1"
                or receipt.get("status") != "four_sec_responses_in_memory_unverified"
                or receipt.get("http_requests_attempted") != 4
                or receipt.get("live_sec_http_called") is not True
                or any(receipt.get(key) is not False for key in (
                    "source_authenticated", "source_rights_verified",
                    "point_in_time_verified", "full_a_b_c_ready",
                    "ai_interpretation_ready", "trade_executed",
                    "original_saved", "external_ai_called",
                ))):
            return _unavailable("TRANSPORT_TRUST_CONTRACT_FAILED")
        if (set(raw_sources) != set(_KEYS)
                or type(receipt.get("source_sha256")) is not dict
                or type(receipt.get("source_bytes")) is not dict
                or set(receipt["source_sha256"]) != set(_KEYS)
                or set(receipt["source_bytes"]) != set(_KEYS)):
            return _unavailable("SOURCE_SET_INCOMPLETE")
        for name in _KEYS:
            raw = raw_sources[name]
            if (type(raw) is not bytes or not 0 < len(raw) <= _LIMITS[name]
                    or sha256(raw).hexdigest() != receipt["source_sha256"][name]
                    or len(raw) != receipt["source_bytes"][name]):
                return _unavailable("SOURCE_BYTES_OR_SHA_CHANGED")

        ticker, as_of = receipt.get("ticker"), receipt.get("requested_as_of")
        plan = build_ticker_source_plan(
            ticker=ticker, ticker_map=raw_sources["ticker_map"],
            submissions=raw_sources["submissions"], as_of=as_of,
        )
        if plan.get("status") != "10k_source_plan_unverified":
            return _unavailable("TICKER_ISSUER_OR_10K_UNAVAILABLE")
        filing = plan["latest_10k"]
        cik, accession = plan["cik"], filing["accession"]
        expected_urls = {
            "ticker_map": MAP_URL,
            "submissions": f"{SEC_API}/submissions/CIK{cik}.json",
            "companyfacts": f"{SEC_API}/api/xbrl/companyfacts/CIK{cik}.json",
            "original_10k": filing["original_filing_url"],
        }
        if (ticker != plan["ticker"] or receipt.get("cik") != cik
                or receipt.get("selected_10k_accession") != accession
                or receipt.get("selected_10k_filing_date") != filing["filing_date"]
                or receipt.get("source_urls") != expected_urls):
            return _unavailable("SOURCE_ISSUER_FILING_BIND_MISMATCH")

        facts = _json(raw_sources["companyfacts"], _MAX_FILE_BYTES, "COMPANYFACTS")
        if _cik(facts.get("cik")) != cik:
            return _unavailable("COMPANYFACTS_ISSUER_MISMATCH")
        us_gaap = facts.get("facts", {}).get("us-gaap")
        if type(us_gaap) is not dict:
            return _unavailable("US_GAAP_UNAVAILABLE")
        current_end = filing.get("report_date")
        cur = sec_date(current_end)
        if cur is None or cur > sec_date(as_of):
            return _unavailable("FISCAL_REPORT_END_MISSING")
        candidates: set[str] = set()
        for concept in REVENUE_TAGS:
            tag = us_gaap.get(concept)
            if tag is None:
                continue
            units = tag.get("units") if type(tag) is dict else None
            rows = units.get("USD") if type(units) is dict else None
            if type(rows) is not list or len(rows) > MAX_ROWS:
                return _unavailable("REVENUE_ROWS_MISSING_OR_TOO_LARGE")
            for row in rows:
                if type(row) is not dict:
                    return _unavailable("INVALID_REVENUE_ROW")
                if row.get("accn") != accession or row.get("form") != "10-K":
                    continue
                prior = sec_date(row.get("end"))
                if prior is None:
                    return _unavailable("INVALID_FISCAL_END_DATE")
                if 330 <= (cur - prior).days <= 380:
                    candidates.add(prior.isoformat())
        if not candidates:
            return _unavailable("SAME_FILING_ANNUAL_PERIODS_UNAVAILABLE")
        if len(candidates) > 4:
            return _unavailable("ANNUAL_PERIOD_COHORT_AMBIGUOUS")

        verified = []
        for prior_end in sorted(candidates):
            checked = verify_sec_annual_revenue(
                facts, cik=cik, accession=accession,
                current_end=current_end, prior_end=prior_end,
                as_of=as_of,
            )
            if checked.get("status") == "calculated_unverified":
                verified.append((prior_end, checked))
        if len(verified) != 1:
            return _unavailable("ANNUAL_REVENUE_MISSING_OR_AMBIGUOUS")
        prior_end, result = verified[0]
        if (result.get("filing_date") != filing["filing_date"]
                or result.get("cik") != cik or result.get("accession") != accession
                or result.get("annual_period_ends") != [prior_end, current_end]
                or result.get("authenticated_external_source") is not False
                or result.get("source_rights_verified") is not False):
            return _unavailable("REVENUE_PERIOD_OR_TRUST_MISMATCH")
        return {
            **_unavailable(""),
            "status": "REVENUE_CALCULATED_UNVERIFIED",
            "reason_code": "SAME_10K_STRUCTURAL_ARITHMETIC_ONLY",
            "ticker": ticker, "issuer_cik": cik, "accession": accession,
            "filing_date": filing["filing_date"], "as_of": as_of,
            "current_end": current_end, "prior_end": prior_end,
            "current_usd": result["current_usd"],
            "prior_usd": result["prior_usd"],
            "growth_pct": result["growth_pct"],
            "revenue_concept": result["revenue_concept"],
            "companyfacts_sha256": receipt["source_sha256"]["companyfacts"],
            "original_10k_sha256": receipt["source_sha256"]["original_10k"],
            "original_10k_url": filing["original_filing_url"],
            "sec_filing_index": result["sec_filing_index"],
        }
    except (ValueError, TypeError, KeyError, OverflowError,
            RecursionError, AttributeError):
        return _unavailable("SOURCE_STRUCTURE_UNAVAILABLE")
