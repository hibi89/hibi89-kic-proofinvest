"""P193: Apple OFFICIAL IR FY2026 report link and issuer bytes, at most two GET.

Explicit one-shot CI only. NO sec.gov request, paid APIs, credentials, raw
persisted files, uploads, retries, mirrors, trades or approval escalation.
A link from issuer's site alone is not SEC-hosted original attestation.
"""
from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
import json
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from typing import Callable

_IR = "https://investor.apple.com/investor-relations/default.aspx"
_SOURCE_HOST = "investor.apple.com"
_ALLOWED = frozenset(("investor.apple.com", "www.apple.com",
                      "d18rn0p25nwr6d.cloudfront.net", "s2.q4cdn.com"))
_CATALOG_LIMIT = 2_500_000
_ORIGINAL_LIMIT = 16_000_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _open(request: Request):
    return build_opener(_NoRedirect()).open(request, timeout=18)


def _allowed(url: str, *, listing: bool) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == (_SOURCE_HOST if listing else parsed.hostname)
        and (listing or parsed.hostname in _ALLOWED)
        and parsed.username is None and parsed.password is None
        and parsed.port is None and not parsed.query and not parsed.fragment
        and bool(parsed.path)
        and ".." not in parsed.path
    )


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list[tuple[str, str]] = []
        self.href: str | None = None
        self.title: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and self.href is None:
            self.href = dict(attrs).get("href")
            self.title = []

    def handle_data(self, data):
        if self.href is not None:
            self.title.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.items.append((self.href, " ".join(self.title)))
            self.href = None
            self.title = []


def _candidate_urls(raw: bytes) -> list[str]:
    parser = _Links()
    parser.feed(raw.decode("utf-8"))
    result: list[str] = []
    for href, text in parser.items:
        compact = " ".join(text.upper().replace("-", " ").split())
        url = urljoin(_IR, href)
        # Require FY2026 explicitly in the same anchor label OR target path.
        if ("10 K" not in compact and "FORM 10 K" not in compact):
            continue
        if "2026" not in compact and "2026" not in url:
            continue
        if not _allowed(url, listing=False):
            continue
        if not urlsplit(url).path.lower().endswith((".pdf", ".html", ".htm")):
            continue
        result.append(url)
    return sorted(set(result))


def probe_issuer_ir_fy2026_once(*, open_once: Callable | None = None) -> dict:
    out = {
        "schema": "kuodra.apple-issuer-2026-ir-byte-probe.v1",
        "status": "UNAVAILABLE",
        "reason_code": "OFFICIAL_IR_NOT_ATTEMPTED",
        "network_get_budget": 2,
        "network_get_attempted": 0,
        "sec_http_requests": 0,
        "redirects_allowed": 0,
        "raw_bytes_persisted": False,
        "raw_bytes_uploaded": False,
        "source_2026_report_html_or_pdf_sha256": None,
        "source_2026_report_bytes": None,
        "issuer_link_discovered_from_first_party_page": False,
        "issuer_document_bytes_seen": False,
        "sec_edgar_original_authenticated": False,
        "source_license_verified": False,
        "ai_commercial_use_rights_verified": False,
        "ndx_stock_peer_data_verified": False,
        "trade_executed": False,
        "official_contest_submitted": False,
    }
    if not _allowed(_IR, listing=True):
        out["reason_code"] = "IR_LISTING_HOST_INVALID"
        return out
    reader = open_once or _open

    def fetch(url: str, max_size: int, mime: tuple[str, ...]):
        if not _allowed(url, listing=url == _IR):
            raise ValueError("HTTPS_ALLOWLIST_REJECTED")
        req = Request(url, method="GET", headers={
            "User-Agent": "KUODRA-P193-ApplePublicIRResearch/1.0",
            "Accept": ",".join(mime), "Accept-Encoding": "identity",
        })
        out["network_get_attempted"] += 1
        with reader(req) as res:
            if res.status != 200 or res.geturl() != url:
                raise ValueError("NON_200_OR_REDIRECT_BLOCKED")
            if res.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("ENCODING_NOT_IDENTITY")
            actual_mime = res.headers.get("Content-Type", "").lower().split(";")[0].strip()
            if actual_mime not in mime:
                raise ValueError("UNEXPECTED_MIME")
            length = res.headers.get("Content-Length")
            if length is not None and (not length.isascii()
                                       or not length.isdigit()
                                       or not 0 < int(length) <= max_size):
                raise ValueError("UNEXPECTED_CONTENT_LENGTH")
            raw = res.read(max_size + 1)
            if not 0 < len(raw) <= max_size:
                raise ValueError("RESPONSE_SIZE_INVALID")
            if length is not None and len(raw) != int(length):
                raise ValueError("LENGTH_MISMATCH")
            return raw, actual_mime

    try:
        catalog, _mime = fetch(_IR, _CATALOG_LIMIT, ("text/html",))
        out["official_ir_listing_sha256"] = sha256(catalog).hexdigest()
        links = _candidate_urls(catalog)
        out["official_2026_document_link_count"] = len(links)
        if len(links) != 1:
            out["reason_code"] = "UNIQUE_OFFICIAL_2026_10K_LINK_NOT_OBSERVED"
            return out
        target = links[0]
        out["issuer_link_discovered_from_first_party_page"] = True
        raw, mime = fetch(target, _ORIGINAL_LIMIT,
                          ("text/html", "application/pdf", "application/xhtml+xml"))
        if mime == "application/pdf" and not raw.startswith(b"%PDF-"):
            out["reason_code"] = "PDF_HEADER_INVALID"
            return out
        if mime != "application/pdf":
            first = raw[:150_000].lower()
            if b"10-k" not in first and b"form 10" not in first:
                out["reason_code"] = "HTML_FORM_10K_NOT_OBSERVED"
                return out
        out.update(
            status="ISSUER_IR_REFERENCED_REAL_2026_DOCUMENT_BYTES_FETCHED_UNVERIFIED",
            reason_code="ISSUER_LINK_AND_HASH_ONLY_NOT_SEC_ORIGINAL_AUTH",
            source_2026_report_html_or_pdf_sha256=sha256(raw).hexdigest(),
            source_2026_report_bytes=len(raw),
            issuer_document_bytes_seen=True,
            public_report_url=target,
            content_type=mime,
        )
        return out
    except (ValueError, TypeError, OSError, UnicodeError, TimeoutError,
            RecursionError):
        out["reason_code"] = "OFFICIAL_IR_ONE_SHOT_FAILED_NO_RETRY"
        return out


def main() -> int:
    result = probe_issuer_ir_fy2026_once()
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if result["status"].startswith("ISSUER_IR_REFERENCED_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
