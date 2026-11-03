"""P127 one-shot fetch of Apple-hosted public FY2025 10-K HTML ONLY.

Never contact sec.gov, use credentials, write files, upload originals, retry,
request paid data, or promote a matching report to SEC-origin authentication.
Run once via an explicitly bounded one-shot GitHub Actions workflow.
"""
from __future__ import annotations

from hashlib import sha256
import json
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from typing import Callable

from .apple_audited_10k_replay import TEN_K
from .apple_local_html_crosscheck import verify_local_apple_10k_html
from .public_primary_baseline import APPLE, CURATED, _read

_URL = ("https://d18rn0p25nwr6d.cloudfront.net/CIK-0000320193/"
        "c636d8a7-8025-47d2-9b13-bcf5465343b3.html")
_HOST = "d18rn0p25nwr6d.cloudfront.net"
_MAX = 5_000_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _default_open(request: Request):
    # HTTPRedirectHandler overridden; zero redirects, requests or retries.
    return build_opener(_NoRedirect()).open(request, timeout=25)


def probe_apple_issuer_original_once(
    *, open_once: Callable[[Request], object] | None = None
) -> dict:
    """One exact HTTPS issuer URL; return redacted metadata, never raw bytes.

    Published HTML and SEC index are distinct domains. Apple-hosted HTTPS
    source is not an SEC-hosted byte capture or authorized redistribution.
    """
    result = {
        "schema": "kuodra.p127-one-shot-issuer-html.v1",
        "status": "UNAVAILABLE",
        "reason_code": "ISSUER_HTML_NOT_FETCHED",
        "origin_host": _HOST,
        "transport": "ISSUER_HOSTED_HTTPS_ONLY_NOT_SEC",
        "sec_http_requests": 0,
        "vendor_market_api_requests": 0,
        "issuer_get_budget": 1,
        "issuer_get_attempted": 0,
        "redirects_allowed": 0,
        "original_html_written_to_disk": False,
        "original_html_uploaded": False,
        "original_html_sha256": None,
        "original_html_bytes": None,
        "matched_numeric_cells": 0,
        "source_authenticated": False,
        "issuer_tls_host_matched": False,
        "sec_original_authenticated": False,
        "sec_companyfacts_authenticated": False,
        "source_rights_verified": False,
        "external_display_allowed": False,
        "ai_processing_allowed": False,
        "guard_executed": False,
        "audit_written": False,
        "trade_executed": False,
        "owner_private_file_transferred": False,
        "official_contest_submission": False,
    }
    parts = urlsplit(_URL)
    if (parts.scheme != "https" or parts.hostname != _HOST
            or parts.username is not None or parts.password is not None
            or parts.port is not None or parts.query or parts.fragment):
        result["reason_code"] = "ISSUER_ALLOWLIST_MISMATCH"
        return result
    request = Request(
        _URL,
        headers={"User-Agent": "KUODRA-P127-Public-Issuer-ReadOnly/1.0",
                 "Accept": "text/html",
                 "Accept-Encoding": "identity",
                 "Cache-Control": "no-store"},
        method="GET",
    )
    try:
        result["issuer_get_attempted"] = 1
        with (open_once or _default_open)(request) as response:
            if response.geturl() != _URL or response.status != 200:
                result["reason_code"] = "ISSUER_REDIRECT_OR_HTTP_STATUS_BLOCKED"
                return result
            content_type = response.headers.get("Content-Type", "").split(";")[0].lower().strip()
            if content_type not in ("text/html", "application/xhtml+xml"):
                result["reason_code"] = "ISSUER_CONTENT_TYPE_UNEXPECTED"
                return result
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                result["reason_code"] = "ISSUER_RESPONSE_ENCODING_UNEXPECTED"
                return result
            declared = response.headers.get("Content-Length")
            if declared is not None and (
                not declared.isascii() or not declared.isdigit()
                or int(declared) > _MAX or int(declared) <= 0
            ):
                result["reason_code"] = "ISSUER_RESPONSE_LENGTH_INVALID"
                return result
            raw = response.read(_MAX + 1)
            if type(raw) is not bytes or not 0 < len(raw) <= _MAX:
                result["reason_code"] = "ISSUER_HTML_SIZE_OR_TYPE_INVALID"
                return result
            if declared is not None and len(raw) != int(declared):
                result["reason_code"] = "ISSUER_HTML_LENGTH_MISMATCH"
                return result
        result["issuer_tls_host_matched"] = True
        result["original_html_bytes"] = len(raw)
        result["original_html_sha256"] = sha256(raw).hexdigest()
        try:
            verified = verify_local_apple_10k_html(
                raw, _read(TEN_K), _read(APPLE), _read(CURATED))
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
            result["reason_code"] = "ACTUAL_ISSUER_HTML_LAYOUT_OR_VALUES_UNVERIFIED"
            result["status"] = "ISSUER_BYTES_FETCHED_NUMERIC_CROSSCHECK_BLOCKED"
            return result
        if (
            verified.get("matched_numeric_cells") != 24
            or verified.get("original_local_html_sha256") != result["original_html_sha256"]
            or verified.get("original_bytes_retained") is not False
            or verified.get("issuer_original_file_authenticated") is not False
            or verified.get("sec_original_file_authenticated") is not False
            or verified.get("network_requests") != 0
            or verified.get("data_rights_verified") is not False
        ):
            result["reason_code"] = "ISSUER_HTML_CROSSCHECK_CONTRACT_INVALID"
            result["status"] = "ISSUER_BYTES_FETCHED_NUMERIC_CROSSCHECK_BLOCKED"
            return result
        result.update(
            status="ISSUER_HTTPS_HTML_24_NUMERIC_CELLS_MATCHED_ORIGIN_UNVERIFIED",
            reason_code="ONE_PUBLISHER_HOSTED_10K_NUMERIC_REPLAY_ONLY",
            matched_numeric_cells=verified["matched_numeric_cells"],
        )
        return result
    except (OSError, TimeoutError, ValueError, TypeError, UnicodeError):
        result["reason_code"] = "ISSUER_ONE_SHOT_GET_OR_PARSE_FAILED_NO_RETRY"
        return result


def main() -> int:
    report = probe_apple_issuer_original_once()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if report["status"].startswith(
        "ISSUER_HTTPS_HTML_24_NUMERIC_CELLS_MATCHED_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
