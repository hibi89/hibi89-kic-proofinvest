"""Structural peer comparison gate: observed annual windows and tag coverage.

Only SAME REPORTED PERIODS are compared; matching US-GAAP tags or local
SHA-256 cannot prove issuer origin, consolidation policies, distribution
rights, historical vintage, identical accounting policies or investor safety.
No I/O, networks, database or Guard changes.
"""
from __future__ import annotations

import re
from typing import Any

from .sec_companyfacts import REVENUE_TAGS, _date

_SHA = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_VALID_TRENDS = (
    "TWO_YEAR_LOCAL_COMPARISON_ORIGIN_UNVERIFIED",
    "WITHHELD_INCOMPLETE_TWO_YEAR_ACCOUNTING",
)


def assess_peer_period_comparability(
    rows: list[dict[str, Any]], *, prior_end: str, current_end: str,
) -> dict[str, Any]:
    """Gate aggregate cash ratios/changes on actual annual statement windows.

    Revenue facts were already checked against original local uploaded bytes,
    accession and as-of; those observed periods provide an independent
    structural check against operating cashflow and net income periods.
    """
    if (type(rows) is not list or not 2 <= len(rows) <= 9
            or _date(prior_end) is None or _date(current_end) is None
            or not 330 <= (_date(current_end) - _date(prior_end)).days <= 380):
        raise ValueError("PEER_PERIOD_INVALID_COHORT")
    entries = []
    seen = set()
    for index, row in enumerate(rows):
        if (type(row) is not dict
                or row.get("role") != ("TARGET" if index == 0 else "PEER")
                or type(row.get("cik")) is not str
                or _CIK.fullmatch(row["cik"]) is None
                or row["cik"] in seen
                or type(row.get("companyfacts_sha256")) is not str
                or _SHA.fullmatch(row["companyfacts_sha256"]) is None
                or row.get("source_authenticated") is not False
                or row.get("revenue_concept") not in REVENUE_TAGS
                or type(row.get("revenue_period_starts")) is not list
                or len(row["revenue_period_starts"]) != 2
                or any(type(v) is not str or _date(v) is None
                       for v in row["revenue_period_starts"])
                or type(row.get("cash_conversion_trend")) is not dict):
            raise ValueError("PEER_PERIOD_UNTRUSTED_ROW")
        seen.add(row["cik"])
        trend = row["cash_conversion_trend"]
        revenue_prior, revenue_current = row["revenue_period_starts"]
        if not (330 <= (_date(prior_end) - _date(revenue_prior)).days <= 380
                and 330 <= (_date(current_end) - _date(revenue_current)).days <= 380
                and trend.get("status") in _VALID_TRENDS
                and trend.get("companyfacts_sha256") == row["companyfacts_sha256"]
                and trend.get("source_authenticated") is False
                and trend.get("accounting_policy_comparability_verified") is False
                and trend.get("guard_policy_modified") is False
                and trend.get("trade_executed") is False
                and trend.get("prior_end") == prior_end
                and trend.get("current_end") == current_end):
            raise ValueError("PEER_PERIOD_TREND_EVIDENCE_INVALID")

        current_start = trend.get("current_annual_start")
        prior_start = trend.get("prior_annual_start")
        ratio_exists = type(row.get("cash_conversion_pct")) is str
        trend_exists = (
            trend["status"] == "TWO_YEAR_LOCAL_COMPARISON_ORIGIN_UNVERIFIED"
        )
        if (current_start is not None and (
                type(current_start) is not str or _date(current_start) is None
                or not 330 <= (_date(current_end) - _date(current_start)).days <= 380)
                or prior_start is not None and (
                    type(prior_start) is not str or _date(prior_start) is None
                    or not 330 <= (_date(prior_end) - _date(prior_start)).days <= 380)
                or (ratio_exists and current_start is None)
                or (trend_exists and (not ratio_exists or prior_start is None))
                or (trend_exists and type(trend.get("change_pp")) is not str)):
            raise ValueError("PEER_PERIOD_CASH_FACTS_INCONSISTENT")
        current_match = ratio_exists and current_start == revenue_current
        prior_match = trend_exists and prior_start == revenue_prior
        entries.append({
            "role": row["role"], "cik": row["cik"],
            "companyfacts_sha256": row["companyfacts_sha256"],
            "revenue_concept_operator_file": row["revenue_concept"],
            "revenue_annual_start": {
                "prior": revenue_prior, "current": revenue_current,
            },
            "cash_annual_start": {
                "prior": prior_start, "current": current_start,
            },
            "cash_conversion_current_available": ratio_exists,
            "cash_conversion_trend_available": trend_exists,
            "current_revenue_cash_window_match": current_match,
            "prior_revenue_cash_window_match": prior_match,
            "withheld_reason": (
                trend["reason_code"] if not trend_exists else None
            ),
        })

    current_covered = all(e["cash_conversion_current_available"] for e in entries)
    current_same = current_covered and all(
        e["current_revenue_cash_window_match"] for e in entries
    )
    current_window_identical = current_same and len({
        e["cash_annual_start"]["current"] for e in entries
    }) == 1
    if not current_covered:
        current_status = "INCOMPLETE_CURRENT_ACCOUNTING_EVIDENCE"
    elif not current_same:
        current_status = "CASH_REVENUE_CURRENT_WINDOW_MISMATCH"
    elif not current_window_identical:
        current_status = "CROSS_ISSUER_CURRENT_WINDOW_MISMATCH"
    else:
        current_status = "MATCHED_CURRENT_ANNUAL_WINDOW_LOCAL_ONLY"

    all_prior = all(e["cash_conversion_trend_available"] for e in entries)
    prior_same = all_prior and all(
        e["prior_revenue_cash_window_match"] for e in entries
    )
    prior_window_identical = prior_same and len({
        e["cash_annual_start"]["prior"] for e in entries
    }) == 1
    if current_status != "MATCHED_CURRENT_ANNUAL_WINDOW_LOCAL_ONLY":
        trend_status = "CURRENT_WINDOW_BLOCKS_TREND_COMPARISON"
    elif not all_prior:
        trend_status = "INCOMPLETE_PRIOR_OR_CURRENT_CASH_EVIDENCE"
    elif not prior_same:
        trend_status = "CASH_REVENUE_PRIOR_WINDOW_MISMATCH"
    elif not prior_window_identical:
        trend_status = "CROSS_ISSUER_PRIOR_WINDOW_MISMATCH"
    else:
        trend_status = "MATCHED_TWO_YEAR_ANNUAL_WINDOWS_LOCAL_ONLY"

    concepts = sorted({e["revenue_concept_operator_file"] for e in entries})
    return {
        "schema": "kuodra.peer-period-comparability-audit.v1",
        "current_status": current_status,
        "two_year_status": trend_status,
        "current_cash_median_eligible":
            current_status == "MATCHED_CURRENT_ANNUAL_WINDOW_LOCAL_ONLY",
        "two_year_cash_median_eligible":
            trend_status == "MATCHED_TWO_YEAR_ANNUAL_WINDOWS_LOCAL_ONLY",
        "revenue_concept_status": (
            "SAME_US_GAAP_TAG_LOCAL_ONLY" if len(concepts) == 1
            else "DIFFERENT_US_GAAP_REVENUE_TAGS_REVIEW_REQUIRED"
        ),
        "revenue_concepts": concepts,
        "coverage": entries,
        "candidate_count": len(entries),
        "missing_current_count": sum(
            not row["cash_conversion_current_available"] for row in entries
        ),
        "missing_two_year_count": sum(
            not row["cash_conversion_trend_available"] for row in entries
        ),
        "same_annual_dates_not_accounting_policy_equivalence": True,
        "cross_issuer_accounting_policy_verified": False,
        "original_source_authenticated": False,
        "historical_vintage_authenticated": False,
        "data_rights_verified": False,
        "guard_policy_modified": False,
        "audit_written": False,
        "trade_executed": False,
        "limitation": (
            "Period starts and revenue tags are structurally compared in "
            "operator-supplied SEC-shaped files only. Matching periods and "
            "US-GAAP names do not prove issuer origin, release vintage, "
            "consolidation scope, accounting comparability or investment quality."
        ),
    }
