"""P210 AMD genuine issuer FY2025 peer first-party financial release one-shot.

Single HTTPS GET only on an explicitly path-triggered workflow. Extracts GAAP
yearly revenue/profit and actual annual AMD Data Center segment revenue. AMD
2025-12-27 vs NVIDIA FY2026 2026-01-25 is a 29-day fiscal cutoff mismatch;
neither source grants commercial/AI rights or authenticated SEC 10-K bytes.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Any, Callable
from urllib.request import HTTPRedirectHandler, Request, build_opener

_URL = ("https://ir.amd.com/news-events/press-releases/detail/1276/"
        "amd-reports-fourth-quarter-and-full-year-2025-financial-results")
_MAX = 4_000_000
_EXPECTED_GAAP = {
    "revenue": (34639, 25785),
    "net_income": (4335, 1641),
    "operating_income": (3694, 1900),
}
_EXPECTED_DATA_CENTER = (5380, 4341, 3859, 16635, 12579)
_EXPECTED_TOTAL = (10270, 9246, 7658, 34639, 25785)


def _norm(s: str) -> str:
    return " ".join(s.replace("\u200b", "").replace("\xa0", " ").split()).strip()


class _Tables(HTMLParser):
    """Collect leaf table rows with only builtin parser, no DOM/network helpers."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, Any]] = []
        self.tables: list[list[list[str]]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.stack.append({"rows": [], "row": None, "cell": None})
        elif self.stack and tag == "tr":
            self.stack[-1]["row"] = []
        elif self.stack and tag in ("td", "th") and self.stack[-1]["row"] is not None:
            self.stack[-1]["cell"] = []

    def handle_data(self, value):
        if self.stack and self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"].append(value)

    def handle_endtag(self, tag):
        if not self.stack:
            return
        t = self.stack[-1]
        if tag in ("td", "th") and t["cell"] is not None:
            if t["row"] is not None:
                t["row"].append(_norm(" ".join(t["cell"])))
            t["cell"] = None
        elif tag == "tr" and t["row"] is not None:
            t["rows"].append(t["row"])
            t["row"] = None
        elif tag == "table":
            complete = self.stack.pop()["rows"]
            if complete:
                self.tables.append(complete)


def _numbers(cells: list[str]) -> tuple[int, ...]:
    # Currency and 2025/2024 year headers are separate elements; select only
    # thousands-formatted dollar amounts, never YoY rates/footnotes/quarters.
    nums = []
    for cell in cells:
        item = _norm(cell).strip(" $")
        if re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})+", item):
            nums.append(int(item.replace(",", "")))
        elif re.fullmatch(r"(?i)(up|down)\s+[0-9]+%", item):
            continue
        elif item in ("", "-", "—", "–"):
            continue
        elif re.fullmatch(r"(?i)[0-9]+%|[0-9]+ ppt?s?", item):
            continue
        # Unknown labels/figures never become a guessed number.
    return tuple(nums)


def _row(t: list[list[str]], label: str) -> tuple[int, ...] | None:
    found = []
    for cells in t:
        for i, v in enumerate(cells):
            if _norm(v).casefold() == label:
                found.append(_numbers(cells[i + 1:]))
                break
    return found[0] if len(found) == 1 else None


def _unique(tables: list[list[list[str]]], required: dict[str, tuple[int, ...]],
            *, headers: tuple[str, ...] = ()) -> dict[str, tuple[int, ...]]:
    matches = []
    for t in tables:
        alltext = " ".join(" ".join(row) for row in t).lower()
        if not all(word in alltext for word in headers):
            continue
        values = {key: _row(t, key) for key in required}
        if all(v is not None for v in values.values()):
            if values != required:
                raise ValueError("AMD_ACTUAL_GAAP_OR_SEGMENT_VALUES_CONFLICT")
            matches.append(values)
    if len(matches) != 1:
        raise ValueError("AMD_ANNUAL_GAAP_OR_SEGMENT_TABLE_NOT_UNIQUE")
    return matches[0]


def _pct(a: int, b: int) -> str:
    if a <= 0 or b <= 0:
        raise ValueError("AMD_INVALID_REVENUE_DENOMINATOR")
    return str(((Decimal(a)/Decimal(b)-1)*100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_amd_issuer_2025(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX:
        raise ValueError("AMD_ORIGINAL_SIZE_INVALID")
    html = raw.decode("utf-8")
    # Release publication and period anchors must all be present; an unrelated
    # dated article or non-GAAP-only quarterly table is not acceptable.
    check = html.casefold()
    if not all(x in check for x in ("amd", "feb. 03, 2026",
                                     "annual financial results",
                                     "december 27", "december 28", "2025", "2024")):
        raise ValueError("AMD_ISSUER_PUBLICATION_OR_FISCAL_ANCHOR_MISMATCH")
    parser = _Tables()
    parser.feed(html)
    table_text = " ".join(
        " ".join(" ".join(row) for row in table)
        for table in parser.tables
    ).casefold()
    # Require both complete fiscal dates *within table content*, not two
    # unrelated year numbers in an article introduction or stale press note.
    if (re.search(r"december\s+27,?\s+2025", table_text) is None
            or re.search(r"december\s+28,?\s+2024", table_text) is None):
        raise ValueError("AMD_GAAP_TABLE_FISCAL_YEAR_IDENTITY_CHANGED")
    gaap = _unique(parser.tables, {
        "revenue ($m)": _EXPECTED_GAAP["revenue"] * 2,
        "net income ($m)": (4335, 1641, 6831, 5420),
        "operating income ($m)": (3694, 1900, 7768, 6138),
    }, headers=("gaap", "non-gaap", "2025", "2024"))
    segment = _unique(parser.tables, {
        "data center segment": _EXPECTED_DATA_CENTER,
        "total net revenue": _EXPECTED_TOTAL,
    }, headers=("net revenue:", "data center segment"))
    return {
        "ticker": "AMD", "issuer": "Advanced Micro Devices, Inc.",
        "release_date": "2026-02-03",
        "fiscal_current_end": "2025-12-27",
        "fiscal_prior_end": "2024-12-28",
        "currency": "USD", "unit": "millions",
        "source_is_unaudited": True,
        "annual_gaap": {
            "revenue_current": str(gaap["revenue ($m)"][0]),
            "revenue_prior": str(gaap["revenue ($m)"][1]),
            "net_income_current": str(gaap["net income ($m)"][0]),
            "net_income_prior": str(gaap["net income ($m)"][1]),
            "operating_income_current": str(gaap["operating income ($m)"][0]),
            "operating_income_prior": str(gaap["operating income ($m)"][1]),
            "revenue_yoy_pct": _pct(*_EXPECTED_GAAP["revenue"]),
        },
        "data_center": {
            "revenue_current": str(segment["data center segment"][3]),
            "revenue_prior": str(segment["data center segment"][4]),
            "revenue_yoy_pct": _pct(
                segment["data center segment"][3],
                segment["data center segment"][4]),
        },
        "gaap_non_gaap_conflated": False,
        "quarter_annual_conflated": False,
        "peer_same_fiscal_end_as_nvda": False,
        "comparable_industry_accounting_policies_verified": False,
        "trade_executed": False,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open(request: Request):
    return build_opener(_NoRedirect()).open(request, timeout=18)


def fetch_amd_official_2025_once(*, open_once: Callable | None = None) -> dict:
    out = {
        "schema": "kuodra.p210-real-amd-firstparty-annual-financials-once.v1",
        "status": "BLOCKED", "reason_code": "NOT_ATTEMPTED",
        "issuer": "AMD", "source_url": _URL,
        "source_sha256": None, "source_bytes": None, "facts": None,
        "actual_issuer_original_observed": False,
        "get_attempted": 0, "get_budget": 1, "redirects_followed": 0,
        "sec_calls": 0, "market_provider_calls": 0,
        "source_raw_saved": False, "original_uploaded": False,
        "sec_10k_original_byte_authenticated": False,
        "commercial_ai_rights_verified": False,
        "licensed_real_peer_feed": False, "true_ndx_data_licensed": False,
        "same_fiscal_cohort_verified": False,
        "full_engine_c_ready": False, "full_abc_ready": False,
        "guard_preview": "HOLD", "trade_executed": False,
    }
    req=Request(_URL, method="GET", headers={
        "User-Agent": "KUODRA-P210-PublicIssuerReadOnly/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity",
    })
    try:
        out["get_attempted"] = 1
        with (open_once or _open)(req) as response:
            if response.status != 200 or response.geturl() != _URL:
                raise ValueError("AMD_URL_OR_STATUS_NOT_TRUSTED")
            if response.headers.get("Content-Type", "").split(";")[0].lower() != "text/html":
                raise ValueError("AMD_MIME_UNEXPECTED")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("AMD_ENCODING_UNEXPECTED")
            declared=response.headers.get("Content-Length")
            if declared is not None and (not declared.isascii() or not declared.isdigit()
                                         or not 0 < int(declared) <= _MAX):
                raise ValueError("AMD_DECLARED_LENGTH_INVALID")
            raw=response.read(_MAX+1)
            if not 0 < len(raw) <= _MAX or (declared is not None and
                                            len(raw)!=int(declared)):
                raise ValueError("AMD_RECEIVED_ORIGINAL_LENGTH_INVALID")
        facts=parse_amd_issuer_2025(raw)
        out.update(
            status="REAL_AMD_2025_2024_OFFICIAL_ISSUER_GAAP_SEGMENT_FACTS_LIMITED",
            reason_code="REAL_UNAUDITED_ISSUER_ANNUAL_NOT_A_LICENSED_SECTOR_CONCLUSION",
            source_bytes=len(raw),source_sha256=sha256(raw).hexdigest(),
            facts=facts,actual_issuer_original_observed=True,
        )
    except (ValueError, OSError, UnicodeError, TypeError, OverflowError,
            RecursionError) as exc:
        reason=str(exc)
        out["reason_code"]=reason if re.fullmatch(r"[A-Z0-9_]{3,90}",reason) else "AMD_OFFICIAL_SOURCE_UNAVAILABLE"
    return out


def main() -> int:
    x=fetch_amd_official_2025_once()
    print(json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False))
    return 0 if x["actual_issuer_original_observed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
