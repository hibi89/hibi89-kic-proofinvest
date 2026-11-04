"""P195: bounded genuine Dell issuer IR 2026 10-K original-byte research.

At most ONE GET from exact first-party HTTPS Dell investor-relations URL.
No SEC.gov retry, redirects, customer originals, persistence, uploads, paid
providers, retries or advice. Issuer HTTPS is not a cryptographic SEC EDGAR
original equivalence proof or redistribution / AI-rights license.
"""
from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

_URL = (
    "https://investors.delltechnologies.com/sec-filings/all-sec-filings/"
    "content/0001571996-26-000008/dell-20260130.htm"
)
_HOST = "investors.delltechnologies.com"
_ACCESSION = "0001571996-26-000008"
_FY2026_END = "2026-01-30"
_FY2025_END = "2025-01-31"
_MAX_HTML = 12_000_000

# Publicly visible 2026/2025 issuer-filed GAAP values in USD millions,
# independently reviewed 2026-11-05 on Dell IR (not original byte hash).
_EXPECTED_VISIBLE = {
    "issuer": ("dell technologies",),
    "document": ("form 10-k", "10-k"),
    "fy2026_end": ("january 30, 2026",),
    "fy2025_end": ("january 31, 2025",),
    "net_revenue_2026": ("113,538",),
    "net_revenue_2025": ("95,567",),
    "net_income_2026": ("5,936",),
    "operating_cash_flow_2026": ("11,185",),
}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _open(request: Request):
    return build_opener(_NoRedirect()).open(request, timeout=25)


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.ignore += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.ignore:
            self.ignore -= 1

    def handle_data(self, data):
        if not self.ignore:
            self.parts.append(data)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p195-first-party-dell-2026-10k-one-shot.v1",
        "status": "UNAVAILABLE", "reason_code": reason,
        "public_issuer_report_url": _URL,
        "ticker": "DELL",
        "accession_in_official_issuer_url": _ACCESSION,
        "fy2026_end": _FY2026_END,
        "fy2025_end": _FY2025_END,
        "issuer_https_get_budget": 1,
        "issuer_https_get_attempted": 0,
        "sec_http_requests": 0,
        "redirects_followed": 0,
        "original_bytes_written_to_disk": False,
        "original_bytes_uploaded": False,
        "source_original_sha256": None,
        "source_original_bytes": None,
        "issuer_https_host_verified": False,
        "issuer_html_10k_numbers_crosschecked": False,
        "sec_edgar_identical_original_verified": False,
        "source_rights_verified": False,
        "model_processing_rights_verified": False,
        "market_ndx_peer_rights_verified": False,
        "guard_policy_preview": "HOLD",
        "trade_executed": False,
        "financial_misconduct_proven": False,
        "external_paid_requests": 0,
    }


def _check_report_html(raw: bytes) -> bool:
    """Reject wrong issuer/year and altered financials, not a SEC attestation."""
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_HTML:
        return False
    try:
        html = raw.decode("utf-8")
        parser = _TextOnly()
        parser.feed(html)
        visible = re.sub(r"\s+", " ", " ".join(parser.parts)).lower()
    except (UnicodeError, ValueError, OverflowError):
        return False
    return all(
        any(alias in visible for alias in possibilities)
        for possibilities in _EXPECTED_VISIBLE.values()
    )


def probe_dell_official_2026_10k_once(
    *, open_once: Callable[[Request], object] | None = None,
) -> dict[str, Any]:
    out = _blocked("NOT_FETCHED")
    parsed = urlsplit(_URL)
    if (parsed.scheme != "https" or parsed.hostname != _HOST
            or parsed.username is not None or parsed.password is not None
            or parsed.port is not None or parsed.query or parsed.fragment
            or parsed.path != (
                "/sec-filings/all-sec-filings/content/"
                "0001571996-26-000008/dell-20260130.htm"
            )):
        out["reason_code"] = "EXACT_FIRST_PARTY_URL_ALLOWLIST_FAILED"
        return out
    request = Request(_URL, method="GET", headers={
        "User-Agent": "KUODRA-P195-Research-ReadOnly/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity",
    })
    try:
        out["issuer_https_get_attempted"] = 1
        with (open_once or _open)(request) as response:
            if response.status != 200 or response.geturl() != _URL:
                out["reason_code"] = "STATUS_OR_REDIRECT_REJECTED"
                return out
            media = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if media not in ("text/html", "application/xhtml+xml"):
                out["reason_code"] = "HTML_MIME_REQUIRED"
                return out
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                out["reason_code"] = "NONIDENTITY_ENCODING_REJECTED"
                return out
            declared = response.headers.get("Content-Length")
            if declared is not None and (
                not declared.isascii() or not declared.isdigit()
                or not 0 < int(declared) <= _MAX_HTML
            ):
                out["reason_code"] = "DECLARED_SIZE_INVALID"
                return out
            raw = response.read(_MAX_HTML + 1)
            if not 0 < len(raw) <= _MAX_HTML:
                out["reason_code"] = "RAW_BYTES_INVALID_SIZE"
                return out
            if declared is not None and len(raw) != int(declared):
                out["reason_code"] = "DECLARED_AND_RECEIVED_SIZE_MISMATCH"
                return out
        out["issuer_https_host_verified"] = True
        out["source_original_sha256"] = sha256(raw).hexdigest()
        out["source_original_bytes"] = len(raw)
        if not _check_report_html(raw):
            out["reason_code"] = "REAL_ISSUER_10K_TEXT_OR_NUMBERS_NOT_CROSSCHECKED"
            return out
        out.update(
            status="ISSUER_HTTPS_REAL_DELL_2026_10K_BYTES_CROSSCHECKED",
            reason_code="ISSUER_TLS_AND_REAL_FINANCIAL_CELLS_NOT_SEC_BYTE_PROOF",
            issuer_html_10k_numbers_crosschecked=True,
            verified_visible_issuer_financial_cells=len(_EXPECTED_VISIBLE) - 2,
            annual_net_revenue_2026_usd_millions="113538",
            annual_net_revenue_2025_usd_millions="95567",
        )
        return out
    except (OSError, TimeoutError, ValueError, UnicodeError, TypeError,
            RecursionError):
        out["reason_code"] = "ONE_ISSUER_GET_UNAVAILABLE_NO_RETRY"
        return out


def main() -> int:
    # One and ONLY one request; single result and accurate CLI exit code.
    result = probe_dell_official_2026_10k_once()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return (0 if result["status"] ==
            "ISSUER_HTTPS_REAL_DELL_2026_10K_BYTES_CROSSCHECKED" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
