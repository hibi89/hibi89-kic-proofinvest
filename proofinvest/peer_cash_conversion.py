"""Offline cash-conversion comparison across a selected issuer and 1-8 peers.

All SEC-shaped CompanyFacts are supplied by a human. Only byte pins,
filing-period arithmetic and declared annual statements are checked.
No source-origin authentication, point-in-time price vintage, LLM, Guard
mutation, financial misconduct finding, investment signal or network.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from statistics import median
from typing import Any

from .accounting_integrity import review_accounting_integrity
from .industry_peer_companyfacts import bind_peer_companyfacts_to_industry
from .industry_vision import parse_industry_vision_json, analyze_industry_vision
from .local_sec_packet import _json_object, _MAX_FILE_BYTES
from .sec_companyfacts import verify_sec_annual_revenue
from .peer_cash_trend import review_two_year_cash_conversion
from .peer_period_comparability import assess_peer_period_comparability

_MAX_TOTAL_BYTES = 48_000_000
_Q = Decimal("0.01")


def compare_peer_cash_conversion(
    industry_raw: bytes, *,
    target_source: tuple[str, str, bytes],
    peer_sources: list[tuple[str, str, bytes]],
) -> dict[str, Any]:
    """Review operating cash / net income only when ALL source inputs are coherent.

    A missing/negative earnings denominator suppresses the group comparison,
    rather than silently dropping firms and biasing the peer median.
    """
    industry = parse_industry_vision_json(industry_raw)
    overview = analyze_industry_vision(industry)
    peers = industry["peers"]
    if (type(target_source) is not tuple or len(target_source) != 3
            or type(peer_sources) is not list
            or not 1 <= len(peer_sources) <= 8
            or len(peer_sources) != len(peers)
            or any(type(row) is not tuple or len(row) != 3
                   for row in peer_sources)):
        raise ValueError("PEER_CASH_SOURCE_SHAPE_INVALID")
    entries = [target_source, *peer_sources]
    if (any(type(cik) is not str or type(acc) is not str
            or type(raw) is not bytes or not 0 < len(raw) <= _MAX_FILE_BYTES
            for cik, acc, raw in entries)
            or sum(len(row[2]) for row in entries) > _MAX_TOTAL_BYTES
            or len({row[0] for row in entries}) != len(entries)
            or target_source[0] != industry["issuer_cik"]):
        raise ValueError("PEER_CASH_SOURCE_IDENTITY_OR_SIZE")
    peer_receipt = bind_peer_companyfacts_to_industry(
        industry_raw, peer_sources=peer_sources,
    )
    if (peer_receipt.get("peer_count") != len(peers)
            or peer_receipt.get("source_authenticated") is not False
            or peer_receipt.get("audit_written") is not False
            or peer_receipt.get("source_rights_verified") is not False
            or peer_receipt.get("live_sec_called") is not False):
        raise ValueError("PEER_CASH_PEER_REVENUE_NOT_BOUND")
    target_cik, target_accession, target_raw = target_source
    target_revenue = verify_sec_annual_revenue(
        _json_object(target_raw, limit=_MAX_FILE_BYTES),
        cik=target_cik, accession=target_accession,
        prior_end=industry["prior_period_end"],
        current_end=industry["current_period_end"],
        as_of=industry["as_of"],
    )
    if (target_revenue.get("status") != "calculated_unverified"
            or target_revenue.get("source_rights_verified") is not False
            or target_revenue.get("authenticated_external_source") is not False
            or target_revenue.get("live_api_called") is not False
            or Decimal(target_revenue["prior_usd"]) !=
               Decimal(industry["target"]["prior_revenue_usd"])
            or Decimal(target_revenue["current_usd"]) !=
               Decimal(industry["target"]["current_revenue_usd"])):
        raise ValueError("PEER_CASH_TARGET_REVENUE_CONFLICT")
    source_index = {s["id"]: s for s in industry["sources"]}
    digest = sha256(target_raw).hexdigest()
    for sid in (industry["target"]["prior_source_id"],
                industry["target"]["current_source_id"]):
        s = source_index[sid]
        if (s["sha256"] != digest
                or s["published_at"] < target_revenue["filing_date"]):
            raise ValueError("PEER_CASH_TARGET_SOURCE_PIN_CONFLICT")
    peer_records = {p["peer_cik"]: p for p in peer_receipt["peer_records"]}
    report_rows = []
    for pos, (cik, accession, raw) in enumerate(entries):
        expected_filing = (target_revenue["filing_date"] if pos == 0
                           else peer_records[cik]["filing_date_self_reported"])
        # Re-read the verified annual-revenue concept and actual start dates
        # from each exact local CompanyFacts file. The peer revenue verifier
        # has already checked issuer, accession and source SHA independently.
        declared = (industry["target"] if pos == 0 else next(
            peer for peer in industry["peers"] if peer["cik"] == cik
        ))
        revenue = target_revenue if pos == 0 else verify_sec_annual_revenue(
            _json_object(raw, limit=_MAX_FILE_BYTES),
            cik=cik, accession=accession,
            prior_end=industry["prior_period_end"],
            current_end=industry["current_period_end"],
            as_of=industry["as_of"],
        )
        if (revenue.get("status") != "calculated_unverified"
                or revenue.get("source_rights_verified") is not False
                or revenue.get("authenticated_external_source") is not False
                or revenue.get("live_api_called") is not False
                or revenue.get("filing_date") != expected_filing
                or Decimal(revenue["prior_usd"]) !=
                Decimal(declared["prior_revenue_usd"])
                or Decimal(revenue["current_usd"]) !=
                Decimal(declared["current_revenue_usd"])
                or type(revenue.get("annual_period_starts")) is not list
                or len(revenue["annual_period_starts"]) != 2
                or type(revenue.get("revenue_concept")) is not str):
            raise ValueError("PEER_CASH_REVENUE_PERIOD_OR_TAG_UNTRUSTED")
        found = review_accounting_integrity(
            raw, cik=cik, accession=accession,
            current_end=industry["current_period_end"],
            prior_end=industry["prior_period_end"], as_of=industry["as_of"],
        )
        if (type(found) is not dict
                or found.get("schema") != "kuodra.accounting-integrity-offline.v1"
                or found.get("source_authenticated") is not False
                or found.get("accounting_fraud_proven") is not False
                or found.get("guard_policy_modified") is not False
                or found.get("ai_generated") is not False
                or found.get("trade_executed") is not False
                or found.get("live_api_called") is not False
                or found.get("companyfacts_sha256") != sha256(raw).hexdigest()
                or found.get("status") not in ("reviewed_unverified", "unavailable")):
            raise ValueError("PEER_CASH_ACCOUNTING_TRUST_CONFLICT")
        if (found["status"] == "reviewed_unverified"
                and (found.get("filing_date") != expected_filing
                     or found.get("period_end") != industry["current_period_end"])):
            raise ValueError("PEER_CASH_INCOMPATIBLE_FILING_PERIOD")
        ratio = found["cash_to_net_income_pct"] if (
            found["status"] == "reviewed_unverified") else None
        if ratio is not None:
            parsed = Decimal(ratio)
            if not parsed.is_finite():
                raise ValueError("PEER_CASH_NONFINITE_RATIO")
        # P92 independent two-year check: current-year P91 comparison survives
        # missing prior CFO/NI, but the trend and its cohort median are WITHHELD.
        trend = review_two_year_cash_conversion(
            raw, cik=cik, accession=accession,
            prior_end=industry["prior_period_end"],
            current_end=industry["current_period_end"],
            as_of=industry["as_of"],
            accounting=found, expected_filing_date=expected_filing,
        )
        report_rows.append({
            "role": "TARGET" if pos == 0 else "PEER",
            "cash_conversion_trend": trend,
            "revenue_concept": revenue["revenue_concept"],
            "revenue_period_starts": list(revenue["annual_period_starts"]),
            "cik": cik, "accession_operator_supplied": accession,
            "companyfacts_sha256": sha256(raw).hexdigest(),
            "revenue_growth_pct_from_source":
                overview["target"]["growth_pct_reported_input"]
                if pos == 0 else next(
                    p["growth_pct_reported_input"]
                    for p in overview["peers"] if p["cik"] == cik),
            "accounting_status": found["status"],
            "accounting_reason_code": found["reason_code"],
            "cash_conversion_pct": ratio,
            "earnings_cash_signal": found["earnings_cash_signal"],
            "receivables_minus_revenue_growth_pp":
                found["receivables_minus_revenue_growth_pp"],
            "inventory_minus_revenue_growth_pp":
                found["inventory_minus_revenue_growth_pp"],
            "working_capital_review_status": found["working_capital_review_status"],
            "working_capital_signals": found["working_capital_signals"],
            "filing_date_self_reported": expected_filing,
            "source_authenticated": False,
        })
    # P93 structural cohort gate: the same labelled fiscal YEAR-END is not
    # proof the selected 10-K annual statements START on the same date.
    comparability = assess_peer_period_comparability(
        report_rows, prior_end=industry["prior_period_end"],
        current_end=industry["current_period_end"],
    )
    # Do not publish a cherry-picked median when data are missing, actual
    # annual windows differ, or CFO/NI annual windows mismatch revenue.
    values_complete = all(
        row["cash_conversion_pct"] is not None for row in report_rows
    )
    complete = values_complete and comparability["current_cash_median_eligible"]
    peer_median = None
    gap = None
    if complete:
        peer_median = Decimal(median(
            Decimal(row["cash_conversion_pct"]) for row in report_rows[1:]
        ))
        gap = (Decimal(report_rows[0]["cash_conversion_pct"]) -
               peer_median).quantize(_Q, rounding=ROUND_HALF_UP)
    # Only compare two-year changes if EVERY selected firm has an eligible
    # prior/current pair; missing peers must not bias the selected cohort.
    trend_values_complete = all(
        r["cash_conversion_trend"]["status"] ==
        "TWO_YEAR_LOCAL_COMPARISON_ORIGIN_UNVERIFIED"
        for r in report_rows
    )
    trends_complete = (
        trend_values_complete and comparability["two_year_cash_median_eligible"]
    )
    trend_median = None
    trend_gap = None
    if trends_complete:
        trend_median = Decimal(median(
            Decimal(row["cash_conversion_trend"]["change_pp"])
            for row in report_rows[1:]
        ))
        trend_gap = (
            Decimal(report_rows[0]["cash_conversion_trend"]["change_pp"])
            - trend_median
        ).quantize(_Q, rounding=ROUND_HALF_UP)
    return {
        "schema": "kuodra.offline-peer-cash-conversion.v1",
        "status": (
            "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED" if complete
            else "PERIOD_WINDOW_COMPARISON_WITHHELD" if values_complete
            else "INCOMPLETE_ACCOUNTING_METRICS_COMPARISON_WITHHELD"
        ),
        "issuer_cik": industry["issuer_cik"], "as_of": industry["as_of"],
        "periods": overview["periods"], "industry": overview["industry"],
        "peer_count": len(peers),
        "eligible_peer_count": sum(row["cash_conversion_pct"] is not None
                                   for row in report_rows[1:]),
        "cash_conversion_target_pct":
            report_rows[0]["cash_conversion_pct"] if complete else None,
        "cash_conversion_peer_median_pct":
            str(peer_median.quantize(_Q, rounding=ROUND_HALF_UP))
            if peer_median is not None else None,
        "target_minus_peer_median_pp": str(gap) if gap is not None else None,
        "rows": report_rows,
        "period_comparability": comparability,
        "two_year_trend_status": (
            "COMPLETE_TWO_YEAR_LOCAL_INPUTS_ORIGIN_UNVERIFIED"
            if trends_complete else
            "PERIOD_WINDOW_TWO_YEAR_COMPARISON_WITHHELD"
            if trend_values_complete else
            "INCOMPLETE_TWO_YEAR_CASH_EVIDENCE_WITHHELD"
        ),
        "two_year_eligible_peer_count": sum(
            r["cash_conversion_trend"]["status"] ==
            "TWO_YEAR_LOCAL_COMPARISON_ORIGIN_UNVERIFIED"
            for r in report_rows[1:]
        ),
        "two_year_target_change_pp": (
            report_rows[0]["cash_conversion_trend"]["change_pp"]
            if trends_complete else None
        ),
        "two_year_peer_median_change_pp": (
            format(trend_median.quantize(_Q, rounding=ROUND_HALF_UP), ".2f")
            if trend_median is not None else None
        ),
        "two_year_target_minus_peer_change_pp": (
            format(trend_gap, ".2f") if trend_gap is not None else None
        ),
        "comparison_is_descriptive_not_ranking": True,
        "cross_issuer_accounting_policy_verified": False,
        "issuer_source_authenticated": False, "data_rights_verified": False,
        "point_in_time_verified": False, "accounting_fraud_proven": False,
        "guard_policy_modified": False, "audit_written": False,
        "live_sec_called": False, "ai_generated": False,
        "trade_executed": False,
        "limitation": (
            "All inputs are operator-supplied SEC-shaped local files; coherent "
            "hashes and arithmetic do not authenticate provider origin, accounting "
            "policy comparability, release vintage or investment safety."
        ),
    }
