"""Strict offline *structural* iXBRL annual-revenue context crosscheck.

Accept only small, well-formed UTF-8 XHTML with standard iXBRL, XBRL
instance contexts/units and a US-GAAP namespace. Ordinary EDGAR HTML may
not satisfy this profile and explicitly yields "unavailable".

This is neither authenticated SEC data nor proof of accounting meaning,
reporting accuracy, XBRL taxonomy compliance, issuer identity, or SEC origin.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
import xml.etree.ElementTree as ET
from typing import Any, Mapping

from proofinvest.sec_companyfacts import TAG

IX = "http://www.xbrl.org/2013/inlineXBRL"
XBRLI = "http://www.xbrl.org/2003/instance"
ISO4217 = "http://www.xbrl.org/2003/iso4217"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
REVENUE = "us-gaap:" + TAG
_MAX_BYTES = 8_000_000
_CIK = re.compile(r"[0-9]{10}\Z", flags=re.ASCII)
_US_GAAP_NS = re.compile(r"http://fasb\.org/us-gaap/20[0-9]{2}\Z", re.ASCII)
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?\Z", re.ASCII)
_GROUPED = re.compile(r"[1-9][0-9]{0,2}(?:,[0-9]{3})+(?:\.[0-9]{1,6})?\Z", re.ASCII)
_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z", re.ASCII)


def _missing(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason_code": reason,
        "method": "WELL_FORMED_XHTML_IX_NONFRACTION_CONTEXT_UNIT",
        "periods": None,
        "source_authenticated": False,
        "financial_facts_authenticated": False,
        "xbrl_taxonomy_validated": False,
        "context_origin_authenticated": False,
        "precision_independently_verified": False,
        "sec_network_called": False,
    }


def _date(value: Any) -> date | None:
    if not isinstance(value, str) or _DAY.fullmatch(value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _windows(companyfacts: Any, verdict: Any) -> dict[str, tuple[str, str, int]] | None:
    """Resolve one explicit CompanyFacts period each; do not invent start dates."""
    if not isinstance(companyfacts, Mapping) or not isinstance(verdict, Mapping):
        return None
    data = companyfacts.get("facts")
    usgaap = data.get("us-gaap") if isinstance(data, Mapping) else None
    tag = usgaap.get(TAG) if isinstance(usgaap, Mapping) else None
    units = tag.get("units") if isinstance(tag, Mapping) else None
    rows = units.get("USD") if isinstance(units, Mapping) else None
    ends = verdict.get("annual_period_ends")
    if not isinstance(rows, list) or len(rows) > 10000 or not isinstance(ends, list) or len(ends) != 2:
        return None
    out = {}
    for label, end_key, amount_key in (
        ("prior", ends[0], "prior_usd"), ("current", ends[1], "current_usd")
    ):
        val = verdict.get(amount_key)
        if not isinstance(val, str) or re.fullmatch(r"(?:0|[1-9][0-9]{0,17})", val) is None:
            return None
        matching = [
            row for row in rows
            if isinstance(row, Mapping)
            and row.get("accn") == verdict.get("accession")
            and row.get("form") == "10-K"
            and row.get("end") == end_key
            and row.get("filed") == verdict.get("filing_date")
            and type(row.get("val")) is int and str(row["val"]) == val
        ]
        if len(matching) != 1:
            return None
        start_day, end_day = _date(matching[0].get("start")), _date(end_key)
        if (start_day is None or end_day is None or not start_day < end_day
                or not 330 <= (end_day - start_day).days <= 380):
            return None
        out[label] = (start_day.isoformat(), end_day.isoformat(), int(val))
    return out


def _text(node: ET.Element) -> str | None:
    if len(node) != 0 or node.text is None:
        return None
    return node.text.strip()


def _measure(node: ET.Element) -> str | None:
    text = _text(node)
    return text if text else None


def _context_metadata(root: ET.Element, cik: str) -> dict[str, tuple[str, str]] | None:
    contexts: dict[str, tuple[str, str]] = {}
    for context in root.iter("{"+XBRLI+"}context"):
        cid = context.get("id")
        if not isinstance(cid, str) or not 1 <= len(cid) <= 128 or cid in contexts:
            return None
        entity = context.find("{"+XBRLI+"}entity")
        period = context.find("{"+XBRLI+"}period")
        if entity is None or period is None:
            return None
        if len(entity) != 1 or len(period) != 2:
            return None  # Explicitly no segment/scenario/instant/forever.
        identifier = entity.find("{"+XBRLI+"}identifier")
        start = period.find("{"+XBRLI+"}startDate")
        end = period.find("{"+XBRLI+"}endDate")
        if identifier is None or start is None or end is None:
            return None
        identity = _text(identifier)
        if (identifier.get("scheme") != "http://www.sec.gov/CIK"
                or identity is None
                or re.fullmatch(r"[0-9]{1,10}", identity, re.ASCII) is None
                or identity.zfill(10) != cik):
            return None
        sd, ed = _text(start), _text(end)
        if _date(sd) is None or _date(ed) is None or sd >= ed:
            return None
        contexts[cid] = (sd, ed)
    return contexts


def _unit_ids(root: ET.Element, namespaces: dict[str, str]) -> set[str] | None:
    units = set()
    if namespaces.get("iso4217") != ISO4217:
        return None
    for unit in root.iter("{"+XBRLI+"}unit"):
        uid = unit.get("id")
        if (not isinstance(uid, str) or not 1 <= len(uid) <= 128
                or uid in units or len(unit) != 1):
            return None
        measure = unit.find("{"+XBRLI+"}measure")
        if measure is None or _measure(measure) != "iso4217:USD":
            continue  # Unsupported non-USD units can exist, but are not eligible.
        units.add(uid)
    return units


def _amount(nonfraction: ET.Element) -> tuple[int, int, str] | None:
    if nonfraction.get("{"+XSI+"}nil") in ("true", "1") or nonfraction.get("nil") in ("true", "1"):
        return None
    if len(nonfraction):
        return None  # No hidden ix:exclude, footnote or nested numbers.
    shown = (nonfraction.text or "").strip()
    if not (_DECIMAL.fullmatch(shown) or _GROUPED.fullmatch(shown)):
        return None
    if nonfraction.get("sign") not in (None, "+"):
        return None  # SEC revenue verifier here supports nonnegative integers only.
    scale = nonfraction.get("scale")
    if not isinstance(scale, str) or re.fullmatch(r"(?:0|[1-9]|1[0-2])", scale) is None:
        return None
    precision = nonfraction.get("decimals")
    if (precision is None or precision != "INF" and
            re.fullmatch(r"-?(?:0|[1-9]|1[0-8])", precision) is None):
        return None
    if nonfraction.get("format") not in (None, "ixt:numdotdecimal"):
        return None
    try:
        value = Decimal(shown.replace(",", "")) * (Decimal(10) ** int(scale))
        if value != value.to_integral_value() or value < 0 or value > 10**17:
            return None
    except (ArithmeticError, InvalidOperation, OverflowError):
        return None
    return int(value), int(scale), precision


def review_inline_annual_revenue(
    original: bytes, *, companyfacts: Any, verdict: Any, cik: str,
) -> dict[str, Any]:
    """Fail-closed local statement markup association, NEVER source certification."""
    if (type(original) is not bytes or not 0 < len(original) <= _MAX_BYTES
            or not isinstance(cik, str) or _CIK.fullmatch(cik) is None):
        return _missing("INVALID_OR_OVERSIZED_INPUT")
    windows = _windows(companyfacts, verdict)
    if windows is None:
        return _missing("COMPANYFACTS_PERIODS_AMBIGUOUS")
    if (re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", original, re.I)
            or b"\x00" in original):
        return _missing("FORBIDDEN_XML_DECLARATION")
    try:
        ns: dict[str, str] = {}
        for _, (prefix, uri) in ET.iterparse(BytesIO(original), events=("start-ns",)):
            if prefix in ns and ns[prefix] != uri:
                return _missing("AMBIGUOUS_XML_NAMESPACE_PREFIX")
            ns[prefix] = uri
        root = ET.fromstring(original)
    except (ET.ParseError, ValueError, UnicodeDecodeError, RecursionError):
        return _missing("NOT_STRICT_WELL_FORMED_XHTML")
    if (ns.get("ix") != IX or ns.get("xbrli") != XBRLI
            or not _US_GAAP_NS.fullmatch(ns.get("us-gaap", ""))):
        return _missing("UNSUPPORTED_IXBRL_NAMESPACES")
    contexts = _context_metadata(root, cik)
    units = _unit_ids(root, ns)
    if contexts is None or units is None:
        return _missing("MALFORMED_CONTEXT_OR_CURRENCY_UNIT")
    matched: dict[str, list[dict[str, Any]]] = {"prior": [], "current": []}
    for fact in root.iter("{"+IX+"}nonFraction"):
        if fact.get("name") != REVENUE:
            continue
        ref, unit_ref = fact.get("contextRef"), fact.get("unitRef")
        if not isinstance(ref, str) or contexts.get(ref) is None:
            continue
        annual = [key for key, (start, end, _) in windows.items()
                  if contexts[ref] == (start, end)]
        if not annual:
            continue
        # All revenue facts in the selected period must be unambiguous.
        if unit_ref not in units:
            return _missing("UNSUPPORTED_IXBRL_CURRENCY_UNIT")
        parsed = _amount(fact)
        if parsed is None:
            return _missing("UNSUPPORTED_IXBRL_VALUE_SCALE_OR_FORMAT")
        value, scale, precision = parsed
        for key in annual:
            expected = windows[key][2]
            if value != expected:
                return _missing("CONFLICTING_IXBRL_COMPANYFACTS_AMOUNT")
            matched[key].append({
                "period_start": windows[key][0],
                "period_end": windows[key][1],
                "amount_matches_companyfacts_input": True,
                "scale_exponent": scale,
                "reported_decimals": precision,
                "unit": "USD",
                "cik_matches_local_context": True,
            })
    if len(matched["prior"]) != 1 or len(matched["current"]) != 1:
        return _missing("MISSING_OR_AMBIGUOUS_INLINE_REVENUE_FACTS")
    return {
        **_missing("STRUCTURAL_LOCAL_MATCH_NOT_AUTHENTICATION"),
        "status": "local_ixbrl_revenue_context_match_unverified",
        "periods": matched["prior"] + matched["current"],
    }
