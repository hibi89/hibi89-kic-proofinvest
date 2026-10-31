"""SEC-shaped annual operating cash flow and capex, offline and untrusted.

One exact issuer + 10-K accession, one full fiscal period and as-of filing.
CFO less capital purchases is a simplified non-GAAP free-cash-flow *proxy*,
not a licensed source, issuer authentication, financial safety or trade advice.
"""
from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Mapping

from .local_sec_packet import _json_object, _MAX_FILE_BYTES
from .sec_companyfacts import MAX_AMOUNT, MAX_ROWS, _date

_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACC = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
_CFO = "NetCashProvidedByUsedInOperatingActivities"
_CAPEX = "PaymentsToAcquirePropertyPlantAndEquipment"


def _empty(reason: str, raw: bytes | None = None) -> dict[str, Any]:
    return {
        "schema": "kuodra.sec-annual-cashflow-offline.v1",
        "status": "unavailable", "reason_code": reason,
        "period_start": None, "period_end": None, "filing_date": None,
        "operating_cashflow_usd": None, "capex_payments_usd": None,
        "free_cashflow_proxy_usd": None, "free_cashflow_proxy_status": "unavailable",
        "free_cashflow_proxy_is_non_gaap": True,
        "financial_claim_authenticated": False,
        "source_authenticated": False, "source_rights_verified": False,
        "risk_authenticated": False, "guard_policy_modified": False,
        "trade_executed": False, "live_api_called": False,
        "companyfacts_sha256": sha256(raw).hexdigest() if type(raw) is bytes else None,
    }


class _Blocked(ValueError):
    """Fail closed on malformed or contradictory selected financial facts."""


def _annual(
    usgaap: Mapping[str, Any], tag: str, *, accession: str,
    end: Any, cutoff: Any, optional: bool = False,
) -> tuple[int, str, str] | None:
    if tag not in usgaap and optional:
        return None
    fact = usgaap.get(tag)
    units = fact.get("units") if isinstance(fact, Mapping) else None
    if not isinstance(units, Mapping) or set(units) != {"USD"}:
        raise _Blocked("CASHFLOW_FACT_MISSING_OR_MIXED_UNITS")
    rows = units["USD"]
    if type(rows) is not list or len(rows) > MAX_ROWS:
        raise _Blocked("CASHFLOW_FACT_ROWS_INVALID")
    matches: set[tuple[int, str, str]] = set()
    future = False
    for row in rows:
        if not isinstance(row, Mapping):
            raise _Blocked("CASHFLOW_INVALID_FACT_ROW")
        if row.get("accn") != accession or row.get("form") != "10-K":
            continue
        if _date(row.get("end")) != end:
            continue
        start = _date(row.get("start"))
        if start is None:
            raise _Blocked("CASHFLOW_INVALID_PERIOD")
        # The 10-K also contains short quarters and other comparative facts;
        # only the annual (330-380 day) period is eligible for this metric.
        days=(end-start).days
        if days < 330 or days > 380:
            continue
        filed = _date(row.get("filed"))
        val = row.get("val")
        if (filed is None or filed < end or type(val) is not int
                or abs(val) > MAX_AMOUNT
                or (tag == _CAPEX and val < 0)):
            raise _Blocked("CASHFLOW_INVALID_AMOUNT_OR_FILING")
        if filed > cutoff:
            future = True
            continue
        matches.add((val,start.isoformat(),filed.isoformat()))
    if len(matches)>1:
        raise _Blocked("CASHFLOW_AMBIGUOUS_ANNUAL_FACT")
    if not matches:
        if future:
            raise _Blocked("CASHFLOW_FILING_AFTER_AS_OF")
        if optional:
            return None
        raise _Blocked("CASHFLOW_ANNUAL_FACT_UNAVAILABLE")
    return next(iter(matches))


def review_sec_annual_cashflow(
    companyfacts_json: bytes, *, cik: str, accession: str,
    period_end: str, as_of: str,
) -> dict[str, Any]:
    """Review operating cash and an optional same-period capex proxy."""
    report=_empty("INVALID_CASHFLOW_INPUT",companyfacts_json)
    end,cutoff=_date(period_end),_date(as_of)
    if (type(cik) is not str or _CIK.fullmatch(cik) is None
            or cik=="0000000000" or type(accession) is not str
            or _ACC.fullmatch(accession) is None
            # SEC accession prefix may be a third-party EDGAR submitter;
            # issuer identity is validated via CompanyFacts CIK and exact rows.
            or end is None or cutoff is None or end>cutoff):
        return report
    doc=_json_object(companyfacts_json,limit=_MAX_FILE_BYTES)
    observed=doc.get("cik")
    if (type(observed) not in (str,int) or isinstance(observed,bool)
            or not str(observed).isascii() or not str(observed).isdecimal()
            or len(str(observed))>10 or str(int(observed)).zfill(10)!=cik):
        report["reason_code"]="CASHFLOW_ISSUER_MISMATCH"
        return report
    root=doc.get("facts")
    gaap=root.get("us-gaap") if isinstance(root,Mapping) else None
    if not isinstance(gaap,Mapping):
        report["reason_code"]="CASHFLOW_US_GAAP_UNAVAILABLE"
        return report
    try:
        cfo=_annual(gaap,_CFO,accession=accession,end=end,cutoff=cutoff)
        capex=_annual(gaap,_CAPEX,accession=accession,end=end,cutoff=cutoff,optional=True)
    except _Blocked as exc:
        report["reason_code"]=str(exc)
        return report
    report.update(
        status="reviewed_unverified",
        reason_code="CFO_ONLY_CAPEX_NOT_REPORTED" if capex is None
                    else "NON_GAAP_FCF_PROXY_FROM_SELECTED_ANNUAL_FACTS",
        period_start=cfo[1],period_end=period_end,filing_date=cfo[2],
        operating_cashflow_usd=str(cfo[0]),
    )
    if capex is None:
        return report
    if capex[1]!=cfo[1] or capex[2]!=cfo[2]:
        report["reason_code"]="CFO_CAPEX_PERIOD_OR_FILING_MISMATCH_NO_FCF"
        return report
    report.update(
        capex_payments_usd=str(capex[0]),
        free_cashflow_proxy_usd=str(cfo[0]-capex[0]),
        free_cashflow_proxy_status="same_10k_period_non_gaap_unverified",
    )
    return report
