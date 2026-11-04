"""P202 second US ticker from actual Microsoft official FY2026 issuer IR result.

One bounded Microsoft.com HTTPS GET, zero sec.gov/paid or user private data.
Microsoft FY26 Q4 annual GAAP *earnings release*, not audited 10-K/SEC source.
Never misrepresent non-GAAP adjusted OpenAI investment rows as GAAP.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Any, Callable
from urllib.request import Request, HTTPRedirectHandler, build_opener

_URL = "https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast"
_MAX_HTML = 5_000_000
_MAX_VISIBLE = 1_000_000
_REQUIRED = {
    "fy2026_revenue_usd_millions": "331839",
    "fy2025_revenue_usd_millions": "281724",
    "fy2026_gaap_net_income_usd_millions": "133749",
    "fy2025_gaap_net_income_usd_millions": "101832",
    "fy2026_non_gaap_adjusted_net_income_usd_millions": "128786",
    "fy2025_non_gaap_adjusted_net_income_usd_millions": "105452",
}
_SOURCE_RELEASE_DATE = "2026-07-29"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _open(req: Request):
    return build_opener(_NoRedirect()).open(req, timeout=25)


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.total = 0
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script","style","noscript","svg"):
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script","style","noscript","svg") and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            return
        self.total += len(data)
        if self.total > _MAX_VISIBLE:
            raise ValueError("MICROSOFT_VISIBLE_HTML_TOO_LONG")
        self.parts.append(data)


def _num_exists(text: str, value: str) -> bool:
    with_commas = f"{int(value):,}"
    return bool(re.search(r"(?<!\d)"+re.escape(with_commas)+r"(?!\d)",text))


def inspect_microsoft_actual_fy2026_issuer_release(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_HTML:
        raise ValueError("ISSUER_HTML_SIZE_OR_TYPE_INVALID")
    p = _VisibleText()
    p.feed(raw.decode("utf-8"))
    visible = re.sub(r"\s+", " ", " ".join(p.parts))
    begin = visible.find("Fiscal Year 2026 Results")
    end = visible.find("Business Outlook", begin+1)
    if not 0 <= begin < end or end-begin > 35000:
        raise ValueError("FY2026_ANNUAL_RELEASE_SECTION_NOT_FOUND")
    opening = visible[:begin]
    scope = visible[begin:end]
    if ("Microsoft" not in opening or "July 29, 2026" not in opening
            or "fiscal year ended June 30, 2026" not in scope.lower().replace(
                "fiscal year ended june", "fiscal year ended June")):
        # Direct check via case-insensitive normalized lookups below.
        if not ("microsoft" in opening.lower()
                and "july 29, 2026" in opening.lower()
                and "fiscal year ended june 30, 2026" in scope.lower()):
            raise ValueError("ISSUER_OR_FISCAL_CONTEXT_INVALID")
    # Don't accept generic "non-GAAP" prose as proof a GAAP column exists.
    # The table must explicitly distinguish both statement bases.
    if ("twelve months ended june 30" not in scope.lower()
            or "as reported (gaap)" not in scope.lower()
            or "as adjusted (non-gaap)" not in scope.lower()
            or "net income" not in scope.lower()):
        raise ValueError("GAAP_VS_ADJUSTED_STATEMENT_HEADERS_MISSING")
    for field, amount in _REQUIRED.items():
        if not _num_exists(scope, amount):
            raise ValueError("PUBLIC_FY2026_REPORT_FACT_MISSING_"+field.upper())
    # Include a very small FY GAAP-positive magnitude check, never assert
    # raw SEC filing authenticity or AI rights from an issuer press release.
    cur, prev = Decimal("331839"), Decimal("281724")
    ni, pni = Decimal("133749"), Decimal("101832")
    gain = ((cur / prev - 1)*100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    profit = ((ni / pni - 1)*100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "issuer": "Microsoft Corporation", "ticker": "MSFT",
        "fiscal_end_2026": "2026-06-30",
        "fiscal_end_2025": "2025-06-30",
        "source_document_type": "ISSUER_FY2026_Q4_EARNINGS_RELEASE_UNAUDITED_NOT_10K",
        "source_published_date": _SOURCE_RELEASE_DATE,
        "values_usd_millions": dict(_REQUIRED),
        "gaap_revenue_yoy_pct": str(gain),
        "gaap_net_income_yoy_pct": str(profit),
        "gaap_non_gaap_separated": True,
        "rights_for_external_ai_or_commercial_redistribution_proven": False,
        "financial_audit_opinion_authenticated": False,
        "sec_edgar_original_authenticated": False,
        "no_source_html_saved_or_uploaded": True,
    }


def verify_microsoft_public_annual_release_once(*, opener: Callable | None = None) -> dict:
    result = {
        "schema": "kuodra.p202-msft-fy2026-firstparty-one-shot.v1",
        "status": "BLOCKED", "reason_code": "NOT_ATTEMPTED",
        "ticker": "MSFT", "official_issuer_url": _URL,
        "http_get_attempted": 0, "http_get_budget": 1,
        "external_sec_requests": 0, "paid_requests": 0,
        "redirects_followed": 0,
        "raw_html_saved": False, "raw_html_uploaded": False,
        "actual_issuer_primary_source_https_verified": False,
        "actual_second_ticker_issuer_financials_verified": False,
        "source_html_sha256": None, "source_bytes": None,
        "sec_original_authenticated": False,
        "same_sector_peer_comparability": False, "stock_ndx_licensed": False,
        "external_ai_rights_proven": False, "guard_policy_preview": "HOLD",
        "trade_executed": False, "financial_fraud_concluded": False,
        "issuer_financial_facts": None,
    }
    request = Request(_URL, method="GET", headers={
        "User-Agent": "KUODRA-P202-PublicMSFTSourceReadOnly/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity"
    })
    try:
        result["http_get_attempted"] = 1
        with (opener or _open)(request) as response:
            if response.status != 200 or response.geturl() != _URL:
                raise ValueError("ISSUER_OFFICIAL_HTTPS_OR_REDIRECT_REJECTED")
            if response.headers.get("Content-Type","").split(";")[0].strip().lower() not in (
                "text/html","application/xhtml+xml"
            ) or response.headers.get("Content-Encoding","identity").lower() != "identity":
                raise ValueError("ISSUER_HTML_MIME_OR_ENCODING_INVALID")
            size=response.headers.get("Content-Length")
            if size and (not size.isdigit() or not 0 < int(size) <= _MAX_HTML):
                raise ValueError("ISSUER_HTML_DECLARED_SIZE_INVALID")
            raw=response.read(_MAX_HTML+1)
            if not 0 < len(raw) <= _MAX_HTML or (size and len(raw)!=int(size)):
                raise ValueError("ISSUER_HTML_RECEIVED_SIZE_INVALID")
        result["source_html_sha256"]=sha256(raw).hexdigest()
        result["source_bytes"]=len(raw)
        result["issuer_financial_facts"]=inspect_microsoft_actual_fy2026_issuer_release(raw)
        result.update(status="ACTUAL_SECOND_ISSUER_MSFT_PUBLIC_FY2026_GAAP_FACTS_RECOMPUTED",
                      reason_code="MICROSOFT_FIRSTPARTY_RELEASE_NOT_SEC_10K_OR_RIGHTS",
                      actual_issuer_primary_source_https_verified=True,
                      actual_second_ticker_issuer_financials_verified=True)
    except (ValueError, TypeError, UnicodeError, OSError, OverflowError, RecursionError) as e:
        code=str(e)
        result["reason_code"]=code if re.fullmatch("[A-Z0-9_]{3,100}",code) else "MSFT_SOURCE_READ_OR_REPORT_PARSE_UNAVAILABLE"
        result["issuer_financial_facts"]=None
    return result


def main() -> int:
    result=verify_microsoft_public_annual_release_once()
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if result["status"]=="ACTUAL_SECOND_ISSUER_MSFT_PUBLIC_FY2026_GAAP_FACTS_RECOMPUTED" else 2


if __name__=="__main__":
    raise SystemExit(main())
