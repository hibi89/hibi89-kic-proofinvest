"""P198: one issuer-firstparty 2026 10-K GET, actual undimensioned iXBRL replay.

SEC.gov never contacted. Raw bytes are ephemeral, neither saved nor uploaded.
Publisher TLS is NOT SEC EDGAR identical-byte proof, copyright license, or
authorization for third-party AI. Model, NDX, trades and user originals untouched.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Any, Callable
from urllib.request import Request

from .dell_issuer_2026_10k_once import _URL, _MAX_HTML, _check_report_html, _open

_TAGS = frozenset({
    "us-gaap:revenuefromcontractwithcustomerexcludingassessedtax",
    "us-gaap:revenuefromcontractwithcustomerincludingassessedtax",
    "us-gaap:revenues", "us-gaap:salesrevenuenet",
    "us-gaap:revenuefromcontractwithcustomerexcludingassessedtaxnet",
    "dell:netrevenue",
})
_PERIODS = {
    "FY2026": ("2025-02-01", "2026-01-30", Decimal("113538")),
    "FY2025": ("2024-02-03", "2025-01-31", Decimal("95567")),
}


class _Ix(HTMLParser):
    """Consume XBRL contexts, currency measures and nonfraction facts only."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.contexts: dict[str, dict] = {}
        self.units: dict[str, list[str]] = {}
        self.facts: list[dict] = []
        self.context: str | None = None
        self.unit: str | None = None
        self.field: str | None = None
        self.fact_stack: list[dict] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag in ("xbrli:context", "context"):
            key = d.get("id")
            if key and len(key) <= 100 and len(self.contexts) < 100000:
                self.context = key
                self.contexts[key] = {"start": None, "end": None, "segmented": False}
            else:
                self.context = None
        elif tag in ("xbrli:unit", "unit"):
            key = d.get("id")
            if key and len(key) <= 100 and len(self.units) < 100000:
                self.unit = key
                self.units[key] = []
        elif tag in ("xbrli:segment", "xbrli:scenario", "segment", "scenario"):
            if self.context is not None:
                self.contexts[self.context]["segmented"] = True
        elif tag in ("xbrli:startdate", "xbrli:enddate", "xbrli:measure",
                     "startdate", "enddate", "measure"):
            self.field = tag.split(":")[-1]
        elif tag == "ix:nonfraction":
            # Actual Dell inline HTML nests iXBRL nonfractions in some blocks.
            # Keep the innermost fact isolated, rather than reject the whole
            # filing or concatenate unrelated child/parent financial values.
            if len(self.fact_stack) >= 16 or len(self.facts) >= 100000:
                raise ValueError("XBRL_NEST_DEPTH_OR_FACT_COUNT_EXCEEDED")
            self.fact_stack.append(dict(
                name=d.get("name", "").lower(), ctx=d.get("contextref"),
                unit=d.get("unitref"), scale=d.get("scale", "0"),
                sign=d.get("sign"), text=""
            ))

    def handle_data(self, data):
        if self.fact_stack:
            top = self.fact_stack[-1]
            if len(top["text"]) + len(data) > 512:
                raise ValueError("XBRL_FACT_OVERLONG")
            top["text"] += data
        if self.context is not None and self.field in ("startdate", "enddate"):
            self.contexts[self.context][
                "start" if self.field == "startdate" else "end"
            ] = data.strip()
        if self.unit is not None and self.field == "measure":
            self.units[self.unit].append(data.strip().lower())

    def handle_endtag(self, tag):
        if tag == "ix:nonfraction" and self.fact_stack:
            self.facts.append(self.fact_stack.pop())
        elif tag in ("xbrli:context", "context"):
            self.context = None
        elif tag in ("xbrli:unit", "unit"):
            self.unit = None
        elif tag in ("xbrli:startdate", "xbrli:enddate", "xbrli:measure",
                     "startdate", "enddate", "measure"):
            self.field = None


def _amount(fact: dict, units: dict[str, list[str]]) -> Decimal | None:
    if fact["name"] not in _TAGS or units.get(fact["unit"]) != ["iso4217:usd"]:
        return None
    if fact["sign"] not in (None, "+"):
        return None
    text = fact["text"].strip()
    scale = fact["scale"]
    if (not re.fullmatch(r"\d{1,3}(?:,\d{3})*|\d+", text)
            or not isinstance(scale, str) or not re.fullmatch("[0-9]", scale)):
        return None
    try:
        return Decimal(text.replace(",", "")) * Decimal(10) ** int(scale) / 1000000
    except (ValueError, InvalidOperation, OverflowError):
        return None


def extract_dell_ixbrl_2026(raw: bytes) -> dict[str, Any]:
    """Reject period/unit/segment/source mismatches; no fabricated values."""
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_HTML or not _check_report_html(raw):
        raise ValueError("RAW_ISSUER_REPORT_TEXT_MISMATCH")
    parser = _Ix()
    parser.feed(raw.decode("utf-8"))
    if not parser.contexts or not parser.units or not parser.facts:
        raise ValueError("REAL_INLINE_XBRL_STRUCTURE_MISSING")
    out = {}
    for period, (start, end, expected) in _PERIODS.items():
        matches = []
        for fact in parser.facts:
            c = parser.contexts.get(fact["ctx"])
            if (not c or c["segmented"] is not False
                    or c["start"] != start or c["end"] != end):
                continue
            value = _amount(fact, parser.units)
            if value is not None:
                matches.append((value, fact))
        if not matches:
            raise ValueError(period + "_ANNUAL_IXBRL_REVENUE_NOT_FOUND")
        if any(v != expected for v, _fact in matches):
            raise ValueError(period + "_REVENUE_VALUE_CONFLICT")
        out[period] = {
            "revenue_usd_millions": str(expected),
            "period_start": start, "period_end": end,
            "xbrl_concept": matches[0][1]["name"],
            "xbrl_context": matches[0][1]["ctx"],
            "undimensioned_fact_count": len(matches),
        }
    return out


def verify_dell_issuer_ixbrl_once(*, opener: Callable | None = None) -> dict:
    result = {
        "schema": "kuodra.p198-firstparty-real-ixbrl.v1",
        "status": "BLOCKED", "reason_code": "NOT_ATTEMPTED",
        "source_url": _URL, "issuer": "DELL",
        "http_get_budget": 1, "http_get_attempted": 0,
        "sec_http_calls": 0, "redirects": 0, "paid_calls": 0,
        "raw_html_saved": False, "raw_html_uploaded": False,
        "origin_sec_edgar_byte_identical": False,
        "stock_ndx_peer_rights_verified": False,
        "commercial_model_rights_verified": False,
        "full_abc_ready": False, "guard": "HOLD", "trades": 0,
        "original_sha256": None, "original_size": None,
        "xbrl_facts": None,
    }
    req = Request(_URL, method="GET", headers={
        "User-Agent": "KUODRA-P198-Public-Issuer-ReadOnly/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity",
    })
    try:
        result["http_get_attempted"] = 1
        with (opener or _open)(req) as response:
            if response.status != 200 or response.geturl() != _URL:
                raise ValueError("PUBLISHER_HTTPS_RESPONSE_NOT_EXACT")
            if response.headers.get("Content-Type", "").split(";")[0].lower() not in (
                    "text/html", "application/xhtml+xml"):
                raise ValueError("NON_HTML_RESPONSE")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("ENCODING_REJECTED")
            n = response.headers.get("Content-Length")
            if n is not None and (not n.isdigit() or not 0 < int(n) <= _MAX_HTML):
                raise ValueError("DECLARED_SIZE_REJECTED")
            raw = response.read(_MAX_HTML + 1)
            if not 0 < len(raw) <= _MAX_HTML or (n is not None and int(n) != len(raw)):
                raise ValueError("RECEIVED_SIZE_REJECTED")
        result["original_sha256"] = sha256(raw).hexdigest()
        result["original_size"] = len(raw)
        result["xbrl_facts"] = extract_dell_ixbrl_2026(raw)
        result.update(status="REAL_ISSUER_2026_IXBRL_REVENUES_RECOMPUTED",
                      reason_code="FIRSTPARTY_STRUCTURED_FACT_NOT_SEC_BYTE_OR_LICENSE")
    except (OSError, ValueError, TypeError, UnicodeError, OverflowError,
            RecursionError) as e:
        reason = str(e)
        if not (reason.isascii() and re.fullmatch(r"[A-Z0-9_]{3,95}", reason)):
            reason = "ONE_SHOT_PUBLISHER_PARSE_FAILED"
        result["reason_code"] = reason
    return result


def main() -> int:
    result = verify_dell_issuer_ixbrl_once()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "REAL_ISSUER_2026_IXBRL_REVENUES_RECOMPUTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
