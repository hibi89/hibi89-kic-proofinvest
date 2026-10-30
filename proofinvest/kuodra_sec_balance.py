"""KUODRA SEC CompanyFacts balance-sheet ratios from local untrusted bytes.

No network, model, claimed authenticity or Guard authorization. Liabilities
are TOTAL obligations, not interest-bearing debt. Require the SAME accession,
instant period, USD, 10-K and filing date for all three facts; refuse mixed
filings, future vintages, conflicting values, or unreconciled balances.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping

from .local_sec_packet import _json_object, _MAX_FILE_BYTES
from .sec_companyfacts import MAX_AMOUNT, MAX_ROWS, _date

_TAGS = ("Assets", "Liabilities", "StockholdersEquity")
_RATIO_THRESHOLD = Decimal("200")


def _out(reason: str, raw: bytes | None = None) -> dict[str, Any]:
    return {
        "schema": "kuodra.sec-balance-sheet-offline.v1",
        "status": "unavailable", "reason_code": reason,
        "period_end": None, "filing_date": None,
        "inputs_usd": None, "liabilities_to_equity_pct": None,
        "exploratory_ratio_200pct_signal": None,
        "balance_identity_match": None, "comparison_is_unrounded": True,
        "ratio_is_total_liabilities_not_interest_bearing_debt": True,
        "source_bytes_sha256": sha256(raw).hexdigest() if type(raw) is bytes else None,
        "source_authenticated": False, "source_rights_verified": False,
        "risk_authenticated": False, "guard_policy_modified": False,
        "trade_executed": False, "live_api_called": False,
    }


def review_sec_balance_sheet(
    companyfacts_json: bytes, *, cik: str, accession: str,
    period_end: str, as_of: str,
) -> dict[str, Any]:
    """Calculate descriptive liabilities/equity only from a matched balance sheet.

    The balance identity check uses stockholders' equity without NCI, so a
    company reporting noncontrolling interests may be unavailable: fail closed
    rather than present an unqualified ratio from incomplete accounting facts.
    """
    result = _out("INVALID_INPUT", companyfacts_json)
    end, cutoff = _date(period_end), _date(as_of)
    if (type(cik) is not str or len(cik) != 10 or not cik.isascii() or
            not cik.isdecimal() or cik == "0000000000" or
            type(accession) is not str or accession[:10] != cik or
            len(accession) != 20 or end is None or cutoff is None or end > cutoff):
        return result
    facts = _json_object(companyfacts_json, limit=_MAX_FILE_BYTES)
    raw_cik = facts.get("cik")
    if (type(raw_cik) not in (int, str) or not str(raw_cik).isascii()
            or not str(raw_cik).isdecimal() or len(str(raw_cik)) > 10
            or str(int(raw_cik)).zfill(10) != cik):
        result["reason_code"] = "COMPANYFACTS_ISSUER_MISMATCH"
        return result
    root = facts.get("facts")
    us = root.get("us-gaap") if isinstance(root, Mapping) else None
    if not isinstance(us, Mapping):
        result["reason_code"] = "US_GAAP_BALANCE_FACTS_UNAVAILABLE"
        return result

    values: dict[str, int] = {}
    dates: dict[str, str] = {}
    for tag_name in _TAGS:
        tag = us.get(tag_name)
        units = tag.get("units") if isinstance(tag, Mapping) else None
        if not isinstance(units, Mapping) or set(units) != {"USD"}:
            result["reason_code"] = "BALANCE_FACT_UNAVAILABLE_OR_MIXED_UNITS"
            return result
        rows = units.get("USD")
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            result["reason_code"] = "BALANCE_FACT_UNAVAILABLE_OR_OVERSIZED"
            return result
        matches: set[tuple[int, str]] = set()
        future = False
        for row in rows:
            if not isinstance(row, Mapping):
                result["reason_code"] = "INVALID_BALANCE_FACT_RECORD"
                return result
            if row.get("accn") != accession or row.get("form") != "10-K":
                continue
            row_end = _date(row.get("end"))
            if row_end != end:
                continue
            filed = _date(row.get("filed"))
            value = row.get("val")
            if (row.get("start") is not None or filed is None or filed < end
                    or type(value) is not int or abs(value) > MAX_AMOUNT):
                result["reason_code"] = "INVALID_INSTANT_FACT_OR_AMOUNT"
                return result
            if tag_name in ("Assets", "Liabilities") and value < 0:
                result["reason_code"] = "NEGATIVE_ASSETS_OR_LIABILITIES"
                return result
            if filed > cutoff:
                future = True
                continue
            matches.add((value, filed.isoformat()))
        if len(matches) != 1:
            result["reason_code"] = (
                "BALANCE_FILING_AFTER_AS_OF" if not matches and future else
                "AMBIGUOUS_BALANCE_FACT" if len(matches) > 1 else
                "BALANCE_FACT_NOT_IN_SELECTED_FILING"
            )
            return result
        values[tag_name], dates[tag_name] = next(iter(matches))
    if len(set(dates.values())) != 1:
        result["reason_code"] = "MIXED_BALANCE_FILING_DATES"
        return result
    result["inputs_usd"] = {k: str(v) for k, v in values.items()}
    result["period_end"] = period_end
    result["filing_date"] = next(iter(dates.values()))
    identity = values["Assets"] == values["Liabilities"] + values["StockholdersEquity"]
    result["balance_identity_match"] = identity
    if not identity:
        result["reason_code"] = "BALANCE_IDENTITY_NOT_RECONCILED"
        return result
    equity = values["StockholdersEquity"]
    if equity <= 0:
        result["reason_code"] = "NON_POSITIVE_EQUITY_RATIO_UNDEFINED"
        return result
    try:
        ratio = Decimal(values["Liabilities"]) / Decimal(equity) * Decimal(100)
        result["liabilities_to_equity_pct"] = str(
            ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
        result["exploratory_ratio_200pct_signal"] = ratio >= _RATIO_THRESHOLD
    except (InvalidOperation, ArithmeticError, ZeroDivisionError, OverflowError):
        result["reason_code"] = "BALANCE_RATIO_ARITHMETIC_UNAVAILABLE"
        return result
    result["status"] = "reviewed_unverified"
    result["reason_code"] = "LOCAL_SEC_FORMAT_BALANCE_ARITHMETIC_ONLY"
    return result
