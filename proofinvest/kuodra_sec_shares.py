"""Untrusted SEC CompanyFacts outstanding-share snapshots; not dilution proof.

Same CIK, 10-K accession, and as-of gate. No beneficial ownership or issuer
authentication, share split adjustment, capital-raising inference or trading.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import re
from typing import Any, Mapping
from .local_sec_packet import _json_object, _MAX_FILE_BYTES
from .sec_companyfacts import _date, MAX_ROWS

_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACC = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
_MAX_SHARES = 10**12
_TAG = "CommonStockSharesOutstanding"
_DEI = "EntityCommonStockSharesOutstanding"


def _empty(reason: str, raw: bytes | None = None) -> dict[str, Any]:
    return {
        "schema": "kuodra.shares-outstanding-offline.v1",
        "status": "unavailable", "reason_code": reason,
        "concept": None, "basis": None, "shares_outstanding": None,
        "snapshot_date": None, "filing_date": None, "prior_shares": None,
        "prior_snapshot_date": None, "shares_change_pct": None,
        "shares_change_status": "unavailable",
        "shares_change_is_not_dilution_or_issuance": True,
        "stock_split_adjusted": False, "share_classes_aggregated": False,
        "ownership_verified": False, "source_authenticated": False,
        "source_rights_verified": False, "guard_policy_modified": False,
        "trade_executed": False, "live_api_called": False,
        "companyfacts_sha256": sha256(raw).hexdigest() if type(raw) is bytes else None,
    }


def _rows(section: Mapping[str, Any] | None, tag: str) -> list[Any] | None:
    if section is None or tag not in section:
        return None
    fact = section[tag]
    units = fact.get("units") if isinstance(fact, Mapping) else None
    if not isinstance(units, Mapping) or set(units) != {"shares"}:
        raise ValueError("SHARES_UNSUPPORTED_OR_MIXED_UNITS")
    values = units["shares"]
    if type(values) is not list or len(values) > MAX_ROWS:
        raise ValueError("SHARES_ROWS_INVALID_OR_OVERSIZED")
    return values


def _snapshot(rows: list[Any], accession: str, cutoff: date, *,
              end: date | None = None, cover_after: date | None = None
              ) -> tuple[int, date, date] | None:
    found: set[tuple[int, date, date]] = set()
    future = False
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("SHARES_MALFORMED_ROW")
        if row.get("accn") != accession or row.get("form") != "10-K":
            continue
        instant = _date(row.get("end"))
        if end is not None and instant != end:
            continue
        if cover_after is not None and (instant is None
                or not cover_after <= instant <= cover_after + timedelta(days=184)):
            continue
        filed = _date(row.get("filed"))
        val = row.get("val")
        if (instant is None or filed is None or filed < instant
                or row.get("start") is not None or type(val) is not int
                or not 0 < val <= _MAX_SHARES):
            raise ValueError("SHARES_INVALID_INSTANT_OR_AMOUNT")
        if filed > cutoff or instant > cutoff:
            future = True
            continue
        found.add((val, instant, filed))
    if not found:
        if future:
            raise ValueError("SHARES_FILING_AFTER_AS_OF")
        return None
    if len(found) != 1:
        raise ValueError("SHARES_MULTIPLE_SNAPSHOT_AMBIGUOUS")
    return next(iter(found))


def review_sec_shares_outstanding(
    companyfacts_json: bytes, *, cik: str, accession: str,
    period_end: str, prior_end: str | None, as_of: str,
) -> dict[str, Any]:
    """Return fiscal US-GAAP share count or separate dated DEI cover snapshot."""
    res = _empty("INVALID_SHARE_REVIEW_INPUT", companyfacts_json)
    end, cutoff = _date(period_end), _date(as_of)
    prior = _date(prior_end) if prior_end is not None else None
    if (type(cik) is not str or _CIK.fullmatch(cik) is None
            or cik == "0000000000" or type(accession) is not str
            or _ACC.fullmatch(accession) is None
            or not accession.startswith(cik + "-")
            or end is None or cutoff is None or end > cutoff
            or prior_end is not None and (
                prior is None or not 330 <= (end-prior).days <= 380)):
        return res
    facts = _json_object(companyfacts_json, limit=_MAX_FILE_BYTES)
    cik_from_file = facts.get("cik")
    if (type(cik_from_file) not in (str,int)
            or not str(cik_from_file).isascii()
            or not str(cik_from_file).isdecimal()
            or len(str(cik_from_file)) > 10
            or str(int(cik_from_file)).zfill(10) != cik):
        res["reason_code"] = "SHARES_ISSUER_MISMATCH"
        return res
    roots = facts.get("facts")
    gaap = roots.get("us-gaap") if isinstance(roots, Mapping) else None
    dei = roots.get("dei") if isinstance(roots, Mapping) else None
    try:
        usrows = _rows(gaap if isinstance(gaap,Mapping) else None, _TAG)
        deirows = _rows(dei if isinstance(dei,Mapping) else None, _DEI)
        current = (_snapshot(usrows, accession, cutoff, end=end)
                   if usrows is not None else None)
        if current is not None:
            concept, basis = "us-gaap:"+_TAG, "FISCAL_END_INSTANT"
            older = (_snapshot(usrows,accession,cutoff,end=prior)
                     if prior is not None else None)
        else:
            current = (_snapshot(deirows, accession, cutoff, cover_after=end)
                       if deirows is not None else None)
            concept, basis, older = "dei:"+_DEI, "COVER_PAGE_DATE_NOT_FISCAL_END", None
    except ValueError as exc:
        res["reason_code"] = str(exc)
        return res
    if current is None:
        res["reason_code"] = "SHARES_IN_SELECTED_10K_UNAVAILABLE"
        return res
    res.update(
        status="reviewed_unverified", reason_code="SHARE_COUNT_ONLY_NO_DILUTION_PROOF",
        concept=concept, basis=basis,
        shares_outstanding=str(current[0]), snapshot_date=current[1].isoformat(),
        filing_date=current[2].isoformat(),
    )
    if older is not None:
        if older[2] != current[2]:
            res["reason_code"] = "MIXED_SHARES_FILING_DATES_NO_COMPARISON"
        else:
            change = (Decimal(current[0]) / Decimal(older[0]) - Decimal(1))*100
            res.update(
                prior_shares=str(older[0]), prior_snapshot_date=older[1].isoformat(),
                shares_change_pct=str(change.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)),
                shares_change_status="same_filing_two_instants_unverified",
                reason_code="SHARES_CHANGE_NOT_ISSUANCE_OR_DILUTION",
            )
    return res
