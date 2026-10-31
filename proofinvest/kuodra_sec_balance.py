"""KUODRA offline US-GAAP SEC balance-sheet descriptive risk checks.

The source is a caller-supplied SEC-shaped blob, never authenticated. Assets,
total liabilities, stockholders' equity, and optional noncontrolling interests
must be mutually reconcilable in one 10-K accession/as-of. No network, Guard
policy change, trading, or independent provenance attestation.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from hashlib import sha256
import re
from typing import Any, Mapping

from .local_sec_packet import _json_object, _MAX_FILE_BYTES
from .sec_companyfacts import MAX_AMOUNT, MAX_ROWS, _date

_PARENT = "StockholdersEquity"
_TOTAL = "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
_NCI = "MinorityInterest"
_RATIO_THRESHOLD = Decimal("200")


class _FactBlocked(ValueError):
    """Internal fail-closed code; never includes filing text or amounts."""


def _out(reason: str, raw: bytes | None = None) -> dict[str, Any]:
    return {
        "schema": "kuodra.sec-balance-sheet-offline.v1",
        "status": "unavailable", "reason_code": reason,
        "period_end": None, "filing_date": None,
        "inputs_usd": None, "liabilities_to_equity_pct": None,
        "exploratory_ratio_200pct_signal": None,
        "balance_identity_match": None, "comparison_is_unrounded": True,
        "ratio_is_total_liabilities_not_interest_bearing_debt": True,
        "equity_denominator_usd": None,
        "equity_denominator_basis": None,
        "noncontrolling_interest_usd": None,
        "source_bytes_sha256": sha256(raw).hexdigest() if type(raw) is bytes else None,
        "source_authenticated": False, "source_rights_verified": False,
        "risk_authenticated": False, "guard_policy_modified": False,
        "trade_executed": False, "live_api_called": False,
    }


def _single_instant(
    usgaap: Mapping[str, Any], tag_name: str, *,
    accession: str, end: Any, cutoff: Any, optional: bool = False,
) -> tuple[int, str] | None:
    """Only one exact USD instant amount from target 10-K, no cross-accession join."""
    if tag_name not in usgaap and optional:
        return None
    tag = usgaap.get(tag_name)
    units = tag.get("units") if isinstance(tag, Mapping) else None
    if not isinstance(units, Mapping) or set(units) != {"USD"}:
        raise _FactBlocked("BALANCE_FACT_UNAVAILABLE_OR_MIXED_UNITS")
    rows = units.get("USD")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise _FactBlocked("BALANCE_FACT_UNAVAILABLE_OR_OVERSIZED")
    matches: set[tuple[int, str]] = set()
    future = False
    for row in rows:
        if not isinstance(row, Mapping):
            raise _FactBlocked("INVALID_BALANCE_FACT_RECORD")
        if row.get("accn") != accession or row.get("form") != "10-K":
            continue
        if _date(row.get("end")) != end:
            continue
        filed = _date(row.get("filed"))
        value = row.get("val")
        if (row.get("start") is not None or filed is None or filed < end
                or type(value) is not int or abs(value) > MAX_AMOUNT):
            raise _FactBlocked("INVALID_INSTANT_FACT_OR_AMOUNT")
        if tag_name in ("Assets", "Liabilities") and value < 0:
            raise _FactBlocked("NEGATIVE_ASSETS_OR_LIABILITIES")
        if filed > cutoff:
            future = True
            continue
        matches.add((value, filed.isoformat()))
    if len(matches) != 1:
        if not matches and future:
            raise _FactBlocked("BALANCE_FILING_AFTER_AS_OF")
        if len(matches) > 1:
            raise _FactBlocked("AMBIGUOUS_BALANCE_FACT")
        if optional:
            return None
        raise _FactBlocked("BALANCE_FACT_NOT_IN_SELECTED_FILING")
    return next(iter(matches))


def review_sec_balance_sheet(
    companyfacts_json: bytes, *, cik: str, accession: str,
    period_end: str, as_of: str,
) -> dict[str, Any]:
    """Reconcile SEC-supplied consolidated equity including NCI where declared.

    Using parent-attributable equity as total consolidated equity when NCI is
    present can misstate the denominator. Parent+NCI or explicit total equity
    must reconcile exactly. Any contradictory optional row blocks the ratio.
    This is descriptive, untrusted arithmetic, not a credit rating or trade.
    """
    result = _out("INVALID_INPUT", companyfacts_json)
    end, cutoff = _date(period_end), _date(as_of)
    if (type(cik) is not str or re.fullmatch(r"[0-9]{10}", cik) is None
            or cik == "0000000000"
            or type(accession) is not str
            or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession) is None
            # EDGAR submitter accession prefix is not always issuer CIK.
            # Exact accession facts and CompanyFacts issuer still gate this view.
            or end is None or cutoff is None or end > cutoff):
        return result
    facts = _json_object(companyfacts_json, limit=_MAX_FILE_BYTES)
    raw_cik = facts.get("cik")
    if (type(raw_cik) not in (int, str) or not str(raw_cik).isascii()
            or not str(raw_cik).isdecimal() or len(str(raw_cik)) > 10
            or str(int(raw_cik)).zfill(10) != cik):
        result["reason_code"] = "COMPANYFACTS_ISSUER_MISMATCH"
        return result
    root = facts.get("facts")
    usgaap = root.get("us-gaap") if isinstance(root, Mapping) else None
    if not isinstance(usgaap, Mapping):
        result["reason_code"] = "US_GAAP_BALANCE_FACTS_UNAVAILABLE"
        return result

    try:
        assets = _single_instant(usgaap, "Assets", accession=accession, end=end, cutoff=cutoff)
        liabilities = _single_instant(usgaap, "Liabilities", accession=accession, end=end, cutoff=cutoff)
        parent = _single_instant(usgaap, _PARENT, accession=accession, end=end, cutoff=cutoff, optional=True)
        total = _single_instant(usgaap, _TOTAL, accession=accession, end=end, cutoff=cutoff, optional=True)
        nci = _single_instant(usgaap, _NCI, accession=accession, end=end, cutoff=cutoff, optional=True)
    except _FactBlocked as exc:
        result["reason_code"] = str(exc)
        return result
    if parent is None and total is None:
        result["reason_code"] = "BALANCE_EQUITY_FACT_UNAVAILABLE"
        return result
    present = [x for x in (assets, liabilities, parent, total, nci) if x is not None]
    if len({x[1] for x in present}) != 1:
        result["reason_code"] = "MIXED_BALANCE_FILING_DATES"
        return result

    values = {"Assets": assets[0], "Liabilities": liabilities[0]}
    if parent is not None:
        values[_PARENT] = parent[0]
    if total is not None:
        values[_TOTAL] = total[0]
    if nci is not None:
        values[_NCI] = nci[0]
    result["inputs_usd"] = {k: str(v) for k, v in values.items()}
    result["period_end"] = period_end
    result["filing_date"] = assets[1]
    if nci is not None:
        result["noncontrolling_interest_usd"] = str(nci[0])

    # Three safe cases: (1) explicit consolidated total; (2) parent + NCI;
    # (3) parent only when no NCI exists. Never silently choose between
    # contradictory parent and total values.
    if parent is not None and total is not None:
        if total[0] != parent[0]:
            if nci is None:
                result["reason_code"] = "NCI_BRIDGE_UNAVAILABLE"
                return result
            if total[0] != parent[0] + nci[0]:
                result["reason_code"] = "NCI_EQUITY_COMPONENT_CONFLICT"
                return result
        elif nci is not None and nci[0] != 0:
            result["reason_code"] = "NCI_EQUITY_COMPONENT_CONFLICT"
            return result
    if total is not None:
        equity = total[0]
        result["equity_denominator_basis"] = "CONSOLIDATED_EQUITY_INCLUDING_NCI"
    elif nci is not None:
        equity = parent[0] + nci[0]
        result["equity_denominator_basis"] = "PARENT_EQUITY_PLUS_EXPLICIT_NCI"
    else:
        equity = parent[0]
        result["equity_denominator_basis"] = "PARENT_EQUITY_WITH_NO_REPORTED_NCI"
    if abs(equity) > MAX_AMOUNT:
        result["reason_code"] = "EQUITY_DENOMINATOR_OUT_OF_BOUNDS"
        return result
    result["equity_denominator_usd"] = str(equity)
    identity = assets[0] == liabilities[0] + equity
    result["balance_identity_match"] = identity
    if not identity:
        result["reason_code"] = "BALANCE_IDENTITY_NOT_RECONCILED"
        return result
    if equity <= 0:
        result["reason_code"] = "NON_POSITIVE_EQUITY_RATIO_UNDEFINED"
        return result

    try:
        ratio = Decimal(liabilities[0]) / Decimal(equity) * Decimal(100)
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
