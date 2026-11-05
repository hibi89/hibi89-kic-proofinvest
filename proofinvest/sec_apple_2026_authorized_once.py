"""P238: one owner-authorized Apple FY2026 SEC-original HTTPS read.

Zero SEC requests before manual owner approval, or during CI tests.
Exactly one pinned GET; TLS hostname validation; no proxies/redirects/retry.
One successful URL response is transport evidence, NOT an SEC-signed digest,
market-data permission, full A/B/C verification, or public authorization.
No original files, credentials, contact email or raw responses persisted.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import re

from .sec_api_client import _valid_contact
from .apple_2026_local_edgar_replay import (
    _DOC, _SIZE, verify_operator_apple_2026_edgar_html,
)

_APPROVAL = "READ SEC APPLE 2026"
_LIMIT_SECONDS = 15
_EMAIL = re.compile(
    r"[A-Za-z0-9_.+%-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\Z",
    re.ASCII,
)


class _StopRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("SEC_REDIRECT_FORBIDDEN_NO_RETRY")


def _failure(reason: str, *, attempted: int = 0) -> dict[str, Any]:
    return {
        "schema": "kuodra.p238-owner-sec-apple-once.v1",
        "status": "BLOCKED", "reason_code": reason,
        "http_requests_attempted": attempted, "http_get_budget": 1,
        "redirects_followed": 0, "retries": 0, "proxy_used": False,
        "contact_or_user_agent_logged": False,
        "original_html_saved": False, "original_html_uploaded": False,
        "original_bytes_sent_to_external_model": False,
        "sec_transport_observed": False,
        "sec_original_byte_identical_independently_certified": False,
        "independent_sec_signed_sha256_available": False,
        "third_party_vendor_data_rights_verified": False,
        "ndx_stock_peer_licensed": False,
        "commercial_financial_ai_licensed": False,
        "public_production_authorized": False,
        "guard_policy_preview": "HOLD", "trades_executed": 0,
    }


def _official_open(request: Request):
    return build_opener(ProxyHandler({}), _StopRedirect()).open(
        request, timeout=_LIMIT_SECONDS)


def read_apple_2026_sec_original_once(
    *, authorized: Any = False,
    user_agent: Any = None,
    opener: Callable[[Request], Any] | None = None,
) -> dict[str, Any]:
    """Bounded single transport observation; no retries or persistence.

    Test-injected opener simulates HTTP, never constitutes real TLS evidence.
    Only owner-run unmocked HTTPS capture can be claimed as observed.
    """
    if authorized is not True:
        return _failure("EXPLICIT_OWNER_APPROVAL_REQUIRED")
    if (type(user_agent) is not str or len(user_agent) > 210
            or not _valid_contact(user_agent)):
        return _failure("REACHABLE_SEC_CONTACT_REQUIRED")
    request = Request(_DOC, method="GET", headers={
        "User-Agent": user_agent,
        "Accept": "text/html", "Accept-Encoding": "identity",
    })
    attempted = 1
    try:
        with (opener or _official_open)(request) as response:
            if response.status != 200 or response.geturl() != _DOC:
                return _failure("SEC_STATUS_OR_ORIGIN_URL_MISMATCH",attempted=attempted)
            headers = response.headers
            mime = headers.get("Content-Type", "").split(";")[0].lower().strip()
            encoding = headers.get("Content-Encoding", "identity").lower().strip()
            declared = headers.get("Content-Length")
            if (mime not in ("text/html", "application/xhtml+xml")
                    or encoding != "identity"
                    or (declared is not None and
                        (not declared.isascii() or not declared.isdigit()
                         or int(declared) != _SIZE))):
                return _failure("SEC_CONTENT_TYPE_ENCODING_OR_SIZE_INVALID",attempted=attempted)
            raw = response.read(_SIZE + 1)
        if type(raw) is not bytes or len(raw) != _SIZE:
            return _failure("SEC_ACTUAL_BODY_LENGTH_MISMATCH",attempted=attempted)
        replay = verify_operator_apple_2026_edgar_html(raw)
        if (replay.get("status") !=
                "LOCAL_SEC_2026_HTML_6_GAAP_FACTS_MATCH_UNAUTHENTICATED"
                or replay.get("local_html_sha256") != sha256(raw).hexdigest()
                or replay.get("local_html_size") != _SIZE
                or replay.get("guard_policy_preview") != "HOLD"
                or replay.get("sec_http_requests") != 0
                or replay.get("sec_edgar_original_byte_identical_authenticated") is not False):
            return _failure("SEC_DIRECT_RECEIVED_BYTES_FAILED_IXBRL_REPLAY",
                            attempted=attempted)
        return {
            **_failure("ONE_BOUNDED_SEC_HTTPS_RESPONSE_MATCHED",attempted=attempted),
            "status": "SEC_DIRECT_HTTPS_APPLE_2026_SIX_FACTS_OBSERVED",
            "sec_transport_observed": True,
            "actual_sec_response_sha256": replay["local_html_sha256"],
            "actual_sec_response_bytes": _SIZE,
            "checked_gaap_facts": 6,
            "fiscal_period_end": replay["annual_end_verified"],
            "sec_official_url": _DOC,
            "origin_proof_scope": "RUNTIME_TLS_HOST_VERIFIED_NOT_SIGNED_DIGEST",
            "network_attempt_source": "OPERATOR_EXPLICIT_APPROVAL",
        }
    except HTTPError as exc:
        if exc.code in (403, 429):
            return _failure("SEC_DENIED_" + str(exc.code) + "_STOP_NO_RETRY",
                            attempted=attempted)
        return _failure("SEC_HTTP_ERROR_STOP_NO_RETRY",attempted=attempted)
    except (URLError,OSError,TimeoutError,ValueError,TypeError,
            OverflowError,UnicodeError):
        return _failure("SEC_TRANSPORT_OR_PARSE_ERROR_STOP_NO_RETRY",
                        attempted=attempted)


def validate_owner_contact(contact: Any) -> str | None:
    if type(contact) is not str or len(contact) > 120 or not _EMAIL.fullmatch(contact):
        return None
    ua = "KUODRA Owner-Limited Apple Original Research " + contact
    return ua if _valid_contact(ua) else None
