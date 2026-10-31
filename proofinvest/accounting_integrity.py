"""KUODRA Engine B: bounded SEC-shaped cash/earnings quality signal review.

Read-only, no network, LLM, trades, Guard mutation, or financial-source authentication.
Ratios are descriptive heuristic review candidates, NEVER fraud findings.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import re
from typing import Any, Mapping

from .local_sec_packet import _json_object, _MAX_FILE_BYTES
from .sec_companyfacts import _date, verify_sec_annual_revenue
from .kuodra_sec_cashflow import _annual, _Blocked, _CFO
from .kuodra_sec_balance import _single_instant, _FactBlocked

_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
_Q = Decimal("0.01")
_RECEIVABLES = "AccountsReceivableNetCurrent"
_INVENTORY = "InventoryNet"
_NI = "NetIncomeLoss"
_OI = "OperatingIncomeLoss"
_REVIEW_GAP_PP = Decimal("10")  # Exploratory review trigger, not statistical proof.


def _fmt(number: Decimal) -> str:
    return str(number.quantize(_Q, rounding=ROUND_HALF_UP))


def _pct_change(previous: int, current: int) -> Decimal | None:
    return (Decimal(current - previous) / Decimal(previous) * 100
            if previous > 0 else None)


def _base(reason: str, source: bytes | None = None) -> dict[str, Any]:
    return {
        "schema": "kuodra.accounting-integrity-offline.v1",
        "status": "unavailable", "reason_code": reason,
        "period_end": None, "filing_date": None,
        "net_income_usd": None, "operating_income_usd": None,
        "operating_cashflow_usd": None, "earnings_less_cash_usd": None,
        "cash_to_net_income_pct": None, "earnings_cash_signal": "NOT_CHECKED",
        "receivables_growth_pct": None, "inventory_growth_pct": None,
        "revenue_growth_pct": None,
        "receivables_minus_revenue_growth_pp": None,
        "inventory_minus_revenue_growth_pp": None,
        "working_capital_signals": [],
        "working_capital_review_status": "NOT_CHECKED",
        "working_capital_reason": None,
        "fact_source_tags": {"net_income": _NI, "operating_income": _OI,
                             "operating_cashflow": _CFO,
                             "receivables": _RECEIVABLES, "inventory": _INVENTORY},
        "companyfacts_sha256": sha256(source).hexdigest() if type(source) is bytes else None,
        "source_authenticated": False, "accounting_fraud_proven": False,
        "guard_policy_modified": False, "ai_generated": False, "trade_executed": False,
        "live_api_called": False,
        "limitations": [
            "A one-year cash-flow discrepancy does not establish accounting fraud.",
            "Receivables and inventory growth are sensitive to sector, M&A, seasonality and accounting changes.",
            "Issuer, filing, release timing, footnotes and data rights are not independently authenticated.",
            "Review thresholds are exploratory heuristics, not investment advice or probabilities.",
        ],
    }


def _instant_pair(gaap: Mapping[str, Any], tag: str, *, accession: str,
                  current: Any, prior: Any, cutoff: Any, filed: str):
    """Two exact same-accession instant balance-sheet facts, same filing date."""
    now = _single_instant(gaap, tag, accession=accession, end=current, cutoff=cutoff,
                          optional=True)
    then = _single_instant(gaap, tag, accession=accession, end=prior, cutoff=cutoff,
                           optional=True)
    if now is None or then is None:
        return None
    if now[1] != filed or then[1] != filed or now[0] < 0 or then[0] < 0:
        raise ValueError("WORKING_CAPITAL_FACT_DATE_OR_SIGN_MISMATCH")
    return (then[0], now[0])


def review_accounting_integrity(
    companyfacts_json: bytes, *, cik: str, accession: str,
    current_end: str, prior_end: str, as_of: str,
) -> dict[str, Any]:
    """Compare selected filing's NI, operating CFO, revenue and WC growth.

    Optional working-capital fields cannot contaminate the core earnings check.
    Never merge different filings or derive balance-sheet fraud conclusions.
    """
    result = _base("INVALID_INPUT", companyfacts_json)
    current, prior, cutoff = _date(current_end), _date(prior_end), _date(as_of)
    if (type(cik) is not str or not _CIK.fullmatch(cik) or cik == "0000000000"
            or type(accession) is not str or not _ACCESSION.fullmatch(accession)
            or current is None or prior is None or cutoff is None
            or not 330 <= (current - prior).days <= 380 or current > cutoff):
        return result
    doc = _json_object(companyfacts_json, limit=_MAX_FILE_BYTES)
    raw_cik = doc.get("cik")
    if (type(raw_cik) not in (str, int)
            or not str(raw_cik).isascii() or not str(raw_cik).isdecimal()
            or not 0 < int(raw_cik) < 10 ** 10
            or str(int(raw_cik)).zfill(10) != cik):
        result["reason_code"] = "COMPANYFACTS_CIK_MISMATCH"
        return result
    facts = doc.get("facts")
    gaap = facts.get("us-gaap") if isinstance(facts, Mapping) else None
    if not isinstance(gaap, Mapping):
        result["reason_code"] = "US_GAAP_UNAVAILABLE"
        return result
    try:
        cash = _annual(gaap, _CFO, accession=accession, end=current, cutoff=cutoff)
        income = _annual(gaap, _NI, accession=accession, end=current, cutoff=cutoff)
        operating = _annual(gaap, _OI, accession=accession, end=current,
                            cutoff=cutoff, optional=True)
    except _Blocked as exc:
        result["reason_code"] = str(exc)
        return result
    if cash[1:] != income[1:] or (operating is not None and operating[1:] != cash[1:]):
        result["reason_code"] = "MIXED_ANNUAL_PERIOD_OR_FILING_DATE"
        return result

    ni, cfo = Decimal(income[0]), Decimal(cash[0])
    result.update({
        "status": "reviewed_unverified", "reason_code": "DESCRIPTIVE_EARNINGS_CASH_REVIEW",
        "period_end": current_end, "filing_date": cash[2],
        "net_income_usd": str(income[0]), "operating_cashflow_usd": str(cash[0]),
        "operating_income_usd": str(operating[0]) if operating is not None else None,
        "earnings_less_cash_usd": str(income[0] - cash[0]),
    })
    if ni > 0:
        result["cash_to_net_income_pct"] = _fmt(cfo / ni * 100)
        result["earnings_cash_signal"] = (
            "POSITIVE_EARNINGS_NEGATIVE_CFO" if cfo < 0
            else "CFO_BELOW_POSITIVE_EARNINGS" if cfo < ni
            else "NO_SINGLE_YEAR_CASH_GAP_SIGNAL"
        )
    else:
        result["earnings_cash_signal"] = "NON_POSITIVE_NET_INCOME_RATIO_UNDEFINED"

    # Annual revenue cross-check reuses the existing strict SEC revenue verifier:
    # same accession, one revenue concept, two annual periods, no future filing.
    rev = verify_sec_annual_revenue(
        doc, cik=cik, accession=accession,
        current_end=current_end, prior_end=prior_end, as_of=as_of,
    )
    if rev["status"] != "calculated_unverified" or rev.get("filing_date") != cash[2]:
        result["working_capital_review_status"] = "UNAVAILABLE"
        result["working_capital_reason"] = "REVENUE_NOT_COHERENT_WITH_CFO_FILING"
        return result
    revenue_growth = _pct_change(int(rev["prior_usd"]), int(rev["current_usd"]))
    if revenue_growth is None:
        result["working_capital_review_status"] = "UNAVAILABLE"
        result["working_capital_reason"] = "ZERO_PRIOR_REVENUE"
        return result
    result["revenue_growth_pct"] = _fmt(revenue_growth)

    usable = 0
    for tag, growth_key, gap_key, signal in (
        (_RECEIVABLES, "receivables_growth_pct",
         "receivables_minus_revenue_growth_pp", "RECEIVABLES_OUTPACED_REVENUE"),
        (_INVENTORY, "inventory_growth_pct",
         "inventory_minus_revenue_growth_pp", "INVENTORY_OUTPACED_REVENUE"),
    ):
        try:
            pair = _instant_pair(gaap, tag, accession=accession,
                                 current=current, prior=prior,
                                 cutoff=cutoff, filed=cash[2])
        except (_FactBlocked, ValueError):
            # Invalid optional information must NOT be treated as healthy.
            result["working_capital_review_status"] = "PARTIAL_OR_CONFLICT"
            result["working_capital_reason"] = "OPTIONAL_FACT_INVALID_OR_MISMATCHED"
            continue
        if pair is None:
            continue
        growth = _pct_change(*pair)
        if growth is None:
            result["working_capital_review_status"] = "PARTIAL_OR_CONFLICT"
            result["working_capital_reason"] = "ZERO_PRIOR_BALANCE"
            continue
        usable += 1
        result[growth_key] = _fmt(growth)
        delta = growth - revenue_growth
        result[gap_key] = _fmt(delta)
        if delta >= _REVIEW_GAP_PP:
            result["working_capital_signals"].append(signal)
    if result["working_capital_review_status"] != "PARTIAL_OR_CONFLICT":
        result["working_capital_review_status"] = (
            "REVIEWED_UNVERIFIED" if usable == 2
            else "PARTIAL_UNVERIFIED" if usable else "UNAVAILABLE"
        )
        result["working_capital_reason"] = (
            "HEURISTIC_REVIEW_ONLY" if usable else "OPTIONAL_BALANCE_FACTS_MISSING"
        )
    return result
