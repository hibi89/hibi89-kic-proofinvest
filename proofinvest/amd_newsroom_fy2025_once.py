"""P210 pivot: AMD Newsroom HTML visible annual GAAP & Data Center row extraction.

Different official first-party host and parser strategy from failed AMD IR
raw HTML table-cell method. This is a scoped offline parser until the actual
source GET is independently verified. No SEC, financial advice, price feed,
commercial/LLM license claim, persistence or securities trading.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Any, Callable
from urllib.request import HTTPRedirectHandler, Request, build_opener

_URL = "https://newsroom.amd.com/news/amd-reports-fourth-quarter-and-full-year-2025-fina/"
_MAX_BYTES = 4_000_000
_ANNUAL_ROWS = {
    "revenue": ("revenue ($m)", "gross profit ($m)", (34639, 25785, 34639, 25785)),
    "operating_income": ("operating income ($m)", "operating margin", (3694, 1900, 7768, 6138)),
    "net_income": ("net income ($m)", "diluted earnings per share", (4335, 1641, 6831, 5420)),
}
_DATA_CENTER = (5380, 4341, 3859, 16635, 12579)
_TOTAL_REVENUE = (10270, 9246, 7658, 34639, 25785)
_MONEY = re.compile(r"(?<![0-9])([0-9]{1,3}(?:,[0-9]{3})+)(?![0-9])")


class _VisibleHTML(HTMLParser):
    """Plain article human-visible text; ignores scripts, style and attributes."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "svg", "noscript"):
            self.skip += 1
        elif not self.skip and tag in ("td", "th", "tr", "p", "h1", "h2", "h3", "li", "br"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg", "noscript") and self.skip > 0:
            self.skip -= 1
        elif not self.skip and tag in ("td", "th", "tr", "p", "h1", "h2", "h3", "li", "br"):
            self.parts.append(" ")

    def handle_data(self, text):
        if not self.skip:
            self.parts.append(text)

    def get_text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def _bounded(text: str, start: str, end: str) -> str:
    lower = text.casefold()
    a = lower.find(start.casefold())
    if a < 0:
        raise ValueError("AMD_NEWSROOM_REQUIRED_HEADING_MISSING")
    b = lower.find(end.casefold(), a + len(start))
    if b <= a:
        raise ValueError("AMD_NEWSROOM_SECTION_BOUNDARY_MISSING")
    # Prevent a quote, metadata listing or a future news widget from
    # accidentally feeding much later financial numbers into this range.
    if b - a > 16000:
        raise ValueError("AMD_NEWSROOM_SECTION_TOO_LARGE")
    return lower[a + len(start):b]


def _values(section: str, label: str, after: str, count: int) -> tuple[int, ...]:
    fragment = _bounded(section, label, after)
    numbers = tuple(int(x.replace(",", "")) for x in _MONEY.findall(fragment))
    if len(numbers) != count:
        raise ValueError("AMD_NEWSROOM_GAAP_ROW_LENGTH_OR_CONTEXT_INVALID")
    return numbers


def _pct(a: int, b: int) -> str:
    if a <= 0 or b <= 0:
        raise ValueError("AMD_NEWSROOM_ZERO_BASELINE")
    return str(((Decimal(a) / Decimal(b) - 1)*100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_amd_newsroom_2025(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_BYTES:
        raise ValueError("AMD_NEWSROOM_ORIGINAL_BYTES_SIZE_INVALID")
    visible = _VisibleHTML()
    visible.feed(raw.decode("utf-8"))
    text = visible.get_text()
    lower = text.casefold()
    if not all(x in lower for x in (
        "amd reports fourth", "full-year 2025 financial results",
        "feb. 03, 2026", "december 27,", "december 28,")):
        raise ValueError("AMD_NEWSROOM_ISSUER_PUBLICATION_IDENTITY_INVALID")
    annual = _bounded(text, "annual financial results", "segment summary")
    if not all(token in annual for token in ("gaap", "non-gaap", "2025", "2024")):
        raise ValueError("AMD_NEWSROOM_GAAP_YEAR_LABELS_MISSING")
    gaap = {}
    for key, (label, after, expected) in _ANNUAL_ROWS.items():
        values = _values(annual, label, after, 4)
        if values != expected:
            raise ValueError("AMD_NEWSROOM_REPORTED_GAAP_FACT_CONFLICT")
        gaap[key] = values

    segment = _bounded(
        text, "segment and disaggregated revenue information",
        "operating income (loss)")
    if not (re.search(r"december\s+27,\s*2025", segment)
            and re.search(r"december\s+28,\s*2024", segment)
            and "net revenue:" in segment):
        raise ValueError("AMD_NEWSROOM_SEGMENT_FISCAL_ENDS_MISMATCH")
    dc = _values(segment, "data center segment", "client and gaming segment", 5)
    total = _values(segment, "total net revenue", "operating income (loss)", 5) if (
        "operating income (loss)" in segment) else None
    # Section already ends at "operating income (loss)"; extract final totals
    # within a short window before the last segment header instead.
    if total is None:
        after_total = segment.split("total net revenue", 1)
        if len(after_total) != 2:
            raise ValueError("AMD_NEWSROOM_TOTAL_GAAP_REVENUE_MISSING")
        total = tuple(int(x.replace(",", "")) for x in
                      _MONEY.findall(after_total[1]))
    if dc != _DATA_CENTER or total != _TOTAL_REVENUE:
        raise ValueError("AMD_NEWSROOM_DATA_CENTER_ANNUAL_CROSSCHECK_CONFLICT")
    if total[3:5] != gaap["revenue"][:2]:
        raise ValueError("AMD_NEWSROOM_SEGMENT_TO_GAAP_TOTAL_CONFLICT")
    return {
        "issuer": "ADVANCED MICRO DEVICES INC.", "ticker": "AMD",
        "fiscal_current_end": "2025-12-27",
        "fiscal_prior_end": "2024-12-28",
        "publication_day": "2026-02-03",
        "is_issuer_unaudited_release": True,
        "unit": "USD_millions",
        "gaap": {
            "revenue_2025": str(gaap["revenue"][0]),
            "revenue_2024": str(gaap["revenue"][1]),
            "net_income_2025": str(gaap["net_income"][0]),
            "net_income_2024": str(gaap["net_income"][1]),
            "operating_income_2025": str(gaap["operating_income"][0]),
            "operating_income_2024": str(gaap["operating_income"][1]),
            "revenue_growth_pct": _pct(gaap["revenue"][0], gaap["revenue"][1]),
        },
        "data_center": {
            "revenue_2025": str(dc[3]), "revenue_2024": str(dc[4]),
            "revenue_growth_pct": _pct(dc[3], dc[4]),
        },
        "q4_2025_revenue_usdm": str(total[0]),
        "gaap_non_gaap_mixed": False,
        "quarter_annual_mixed": False,
        "same_period_and_business_mix_as_nvidia": False,
        "source_licensed_for_model_or_public_redistribution": False,
        "guard_preview": "HOLD", "trade_executed": False,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open(req: Request):
    return build_opener(_NoRedirect()).open(req, timeout=18)


def fetch_amd_newsroom_once(*, opener: Callable | None = None) -> dict:
    out = {
        "schema": "kuodra.p210-amd-newsroom-real-peer-firstparty-once.v1",
        "status": "BLOCKED", "reason_code": "NOT_ATTEMPTED",
        "source_url": _URL, "ticker": "AMD",
        "actual_publisher_html_verified": False,
        "source_bytes": None, "source_sha256": None, "facts": None,
        "network_get_attempted": 0, "get_budget": 1,
        "redirects_followed": 0, "sec_calls": 0, "market_calls": 0,
        "original_bytes_persisted": False,
        "raw_uploaded": False,
        "sec_original_byte_identity": False,
        "commercial_ai_rights_verified": False,
        "peer_market_license_verified": False,
        "fiscal_windows_identical": False,
        "engine_c_final_peer_verdict_available": False,
        "full_abc_ready": False, "guard_preview": "HOLD",
        "trade_executed": False,
    }
    req = Request(_URL, method="GET", headers={
        "User-Agent": "KUODRA-P210-AMDOfficialNewsroomReadOnly/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity",
    })
    try:
        out["network_get_attempted"] = 1
        with (opener or _open)(req) as response:
            if response.status != 200 or response.geturl() != _URL:
                raise ValueError("AMD_NEWSROOM_HOST_OR_STATUS_CHANGED")
            if response.headers.get("Content-Type","").split(";")[0].lower() != "text/html":
                raise ValueError("AMD_NEWSROOM_MIME_INVALID")
            if response.headers.get("Content-Encoding","identity").lower() != "identity":
                raise ValueError("AMD_NEWSROOM_ENCODING_INVALID")
            size=response.headers.get("Content-Length")
            if size is not None and (not size.isascii() or not size.isdigit()
                                     or not 0 < int(size) <= _MAX_BYTES):
                raise ValueError("AMD_NEWSROOM_DECLARED_SIZE_INVALID")
            raw=response.read(_MAX_BYTES + 1)
            if (type(raw) is not bytes or not 0 < len(raw) <= _MAX_BYTES
                    or size is not None and len(raw) != int(size)):
                raise ValueError("AMD_NEWSROOM_CONTENT_SIZE_INVALID")
        facts=parse_amd_newsroom_2025(raw)
        out.update(
            status="REAL_AMD_2025_FIRSTPARTY_GAAP_AND_DATACENTER_PEER_LIMITED",
            reason_code="REAL_HISTORICAL_ISSUER_NUMBERS_ONLY_NO_LICENSED_SECTOR",
            actual_publisher_html_verified=True,
            source_bytes=len(raw),source_sha256=sha256(raw).hexdigest(),
            facts=facts,
        )
    except (ValueError, OSError, TypeError, UnicodeError, OverflowError,
            RecursionError) as exc:
        val=str(exc)
        out["reason_code"]=(val if re.fullmatch(r"[A-Z0-9_]{3,90}", val)
                            else "AMD_NEWSROOM_SOURCE_OR_PARSE_UNAVAILABLE")
    return out


def main() -> int:
    x=fetch_amd_newsroom_once()
    print(json.dumps(x, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if x["actual_publisher_html_verified"] else 2


if __name__=="__main__":
    raise SystemExit(main())
