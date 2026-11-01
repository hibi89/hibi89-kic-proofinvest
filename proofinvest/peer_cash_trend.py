"""Optional two-year CFO / net-income trajectory from one pinned 10-K.

This is an OFFLINE comparison of operator-uploaded SEC-shaped CompanyFacts.
It does not certify issuer origin, rights, point-in-time vintage, peer
accounting policies, wrongdoing, financial safety, or investment returns.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import re
from typing import Any

from .accounting_integrity import _NI
from .kuodra_sec_cashflow import _annual, _Blocked, _CFO
from .local_sec_packet import _json_object, _MAX_FILE_BYTES
from .sec_companyfacts import _date

_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACC = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
_Q = Decimal("0.01")
_TRUST_FALSE = (
    "source_authenticated", "accounting_fraud_proven",
    "guard_policy_modified", "ai_generated", "trade_executed",
    "live_api_called",
)


def _pct(cfo: int, income: int) -> str:
    if income <= 0:
        raise ValueError("TREND_INCOME_NON_POSITIVE")
    value = (Decimal(cfo) / Decimal(income) * Decimal("100"))
    return format(value.quantize(_Q, rounding=ROUND_HALF_UP), ".2f")


def review_two_year_cash_conversion(
    companyfacts_json: bytes, *, cik: str, accession: str,
    prior_end: str, current_end: str, as_of: str,
    accounting: dict[str, Any], expected_filing_date: str,
) -> dict[str, Any]:
    """Same accession, same annual reporting periods, same 10-K filing date.

    Missing historical CFO/NI is a WITHHELD trend, not an absent-risk verdict.
    Current signed values are re-read independently and checked against the
    previously verified current-year Engine B review.
    """
    if (type(companyfacts_json) is not bytes
            or not 0 < len(companyfacts_json) <= _MAX_FILE_BYTES
            or type(cik) is not str or not _CIK.fullmatch(cik)
            or cik == "0000000000"
            or type(accession) is not str or not _ACC.fullmatch(accession)
            or type(accounting) is not dict
            or any(accounting.get(k) is not False for k in _TRUST_FALSE)
            or accounting.get("schema") != "kuodra.accounting-integrity-offline.v1"
            or accounting.get("companyfacts_sha256") !=
            sha256(companyfacts_json).hexdigest()):
        raise ValueError("PEER_TREND_INPUT_OR_TRUST_CONFLICT")
    earlier = _date(prior_end)
    later = _date(current_end)
    cutoff = _date(as_of)
    published = _date(expected_filing_date)
    if (earlier is None or later is None or cutoff is None or published is None
            or not 330 <= (later - earlier).days <= 380
            or later > published or published > cutoff):
        raise ValueError("PEER_TREND_TIME_OR_FILING_INVALID")
    if accounting.get("status") == "reviewed_unverified":
        if (accounting.get("period_end") != current_end
                or accounting.get("filing_date") != expected_filing_date):
            raise ValueError("PEER_TREND_SELECTED_FILING_MISMATCH")
    elif accounting.get("status") != "unavailable":
        raise ValueError("PEER_TREND_ACCOUNTING_STATUS_INVALID")

    result = {
        "status": "WITHHELD_INCOMPLETE_TWO_YEAR_ACCOUNTING",
        "reason_code": "CURRENT_ACCOUNTING_UNAVAILABLE",
        "prior_conversion_pct": None,
        "current_conversion_pct": None,
        "change_pp": None,
        "prior_net_income_usd": None,
        "prior_operating_cashflow_usd": None,
        "prior_end": prior_end,
        "current_end": current_end,
        "filing_date_operator_supplied": expected_filing_date,
        "companyfacts_sha256": sha256(companyfacts_json).hexdigest(),
        "same_accession_and_filing_date_checked": False,
        "source_authenticated": False,
        "accounting_policy_comparability_verified": False,
        "guard_policy_modified": False,
        "trade_executed": False,
    }
    if accounting["status"] == "unavailable":
        return result
    now = accounting.get("cash_to_net_income_pct")
    if now is None:
        result["reason_code"] = "CURRENT_NON_POSITIVE_NET_INCOME"
        return result
    doc = _json_object(companyfacts_json, limit=_MAX_FILE_BYTES)
    observed = doc.get("cik")
    if (type(observed) not in (int, str) or type(observed) is bool
            or not str(observed).isascii() or not str(observed).isdecimal()
            or str(int(observed)).zfill(10) != cik):
        raise ValueError("PEER_TREND_ISSUER_MISMATCH")
    facts = doc.get("facts")
    usgaap = facts.get("us-gaap") if type(facts) is dict else None
    if type(usgaap) is not dict:
        raise ValueError("PEER_TREND_US_GAAP_INVALID")

    try:
        current_cfo = _annual(usgaap, _CFO, accession=accession,
                              end=later, cutoff=cutoff)
        current_income = _annual(usgaap, _NI, accession=accession,
                                 end=later, cutoff=cutoff)
    except _Blocked as exc:
        raise ValueError("PEER_TREND_CURRENT_FACT_CONFLICT") from exc
    if (current_cfo[1:] != current_income[1:]
            or current_cfo[2] != expected_filing_date
            or str(current_cfo[0]) != accounting.get("operating_cashflow_usd")
            or str(current_income[0]) != accounting.get("net_income_usd")
            or _pct(current_cfo[0], current_income[0]) != now):
        raise ValueError("PEER_TREND_CURRENT_FACT_CONFLICT")

    try:
        prior_cfo = _annual(usgaap, _CFO, accession=accession,
                            end=earlier, cutoff=cutoff)
        prior_income = _annual(usgaap, _NI, accession=accession,
                               end=earlier, cutoff=cutoff)
    except _Blocked:
        result["reason_code"] = "PRIOR_CASH_OR_EARNINGS_MISSING_OR_CONFLICT"
        return result
    if (prior_cfo[1:] != prior_income[1:]
            or prior_cfo[2] != expected_filing_date):
        result["reason_code"] = "PRIOR_PERIOD_OR_FILING_DATE_CONFLICT"
        return result
    if prior_income[0] <= 0:
        result["reason_code"] = "PRIOR_NON_POSITIVE_NET_INCOME"
        return result
    old_pct = _pct(prior_cfo[0], prior_income[0])
    change = (Decimal(now) - Decimal(old_pct)).quantize(
        _Q, rounding=ROUND_HALF_UP,
    )
    result.update({
        "status": "TWO_YEAR_LOCAL_COMPARISON_ORIGIN_UNVERIFIED",
        "reason_code": "SAME_10K_ANNUAL_FACTS_ARITHMETIC_ONLY",
        "prior_conversion_pct": old_pct,
        "current_conversion_pct": now,
        "change_pp": format(change, ".2f"),
        "prior_net_income_usd": str(prior_income[0]),
        "prior_operating_cashflow_usd": str(prior_cfo[0]),
        "same_accession_and_filing_date_checked": True,
    })
    return result
