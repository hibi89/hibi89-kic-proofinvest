"""Explicitly gated one-ticker SEC intake. No implicit network or retention.

MAX FOUR requests: official ticker map, issuer submissions, CompanyFacts,
selected 10-K HTML. One request per source, never retry, redirect or proxy.
A successful HTTPS transport is NOT independent issuer/source/rights/PIT proof.
Existing offline A/B/C/Guard consumers decide how to use the in-memory bytes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import http.client
import re
import time
import urllib.error
import urllib.request

from .local_sec_packet import _MAX_FILE_BYTES
from .sec_api_client import _NoRedirect, _valid_contact
from .ticker_research_intake import (
    MAP_URL, MAX_MAP_BYTES, MAX_SUBMISSIONS_BYTES, SEC_API, SEC_ARCHIVE,
    _cik, _date, _json, build_ticker_source_plan, resolve_sec_ticker,
    select_sec_10k,
)

MAX_FETCH_COUNT = 4
TIMEOUT_SECONDS = 12
PAUSE_SECONDS = 0.35
_MAX_ORIGINAL_BYTES = 24_000_000
_ALLOWED_ORIGINAL_TYPES = {"text/html", "application/xhtml+xml", "text/plain"}
_ALLOWED_JSON_TYPES = {"application/json"}
_ORIGINAL_PATTERN = re.compile(
    r"https://www[.]sec[.]gov/Archives/edgar/data/"
    r"[1-9][0-9]{0,9}/[0-9]{18}/[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z"
)
_SUBMISSIONS_PATTERN = re.compile(
    r"https://data[.]sec[.]gov/submissions/CIK[0-9]{10}[.]json\Z"
)
_FACTS_PATTERN = re.compile(
    r"https://data[.]sec[.]gov/api/xbrl/companyfacts/CIK[0-9]{10}[.]json\Z"
)


class _IntakeFailure(Exception):
    """Static error code only; no exception/URL/raw response disclosure."""


def _source_url_allowed(url: str, kind: str) -> bool:
    # Exact absolute URLs constructed by the trusted planner only; no user-
    # provided host, redirect or query. Original filename is path-safe.
    return type(url) is str and {
        "ticker_map": lambda u: u == MAP_URL,
        "submissions": lambda u: bool(_SUBMISSIONS_PATTERN.fullmatch(u)),
        "companyfacts": lambda u: bool(_FACTS_PATTERN.fullmatch(u)),
        "original_10k": lambda u: bool(_ORIGINAL_PATTERN.fullmatch(u)),
    }[kind](url)


def _open_once(request: urllib.request.Request, *, timeout: int):
    # No environment proxy, no redirects, standard TLS certificate validation.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect()
    )
    return opener.open(request, timeout=timeout)


def _get_sec_bytes(url: str, kind: str, *, user_agent: str, maximum: int) -> bytes:
    """A single bounded request, or a static failure reason. No retries."""
    if not _source_url_allowed(url, kind):
        raise _IntakeFailure("UNEXPECTED_SOURCE_URL")
    if kind == "original_10k" and not url.lower().endswith((".htm", ".html")):
        raise _IntakeFailure("ORIGINAL_DOCUMENT_FORMAT_UNSUPPORTED")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": ("text/html,application/xhtml+xml,text/plain"
                       if kind == "original_10k" else "application/json"),
            "Accept-Encoding": "identity",
        },
        method="GET",
    )
    try:
        with _open_once(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200 or response.geturl() != url:
                raise _IntakeFailure("UNEXPECTED_SOURCE_RESPONSE")
            media = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            allowed = (_ALLOWED_ORIGINAL_TYPES if kind == "original_10k"
                       else _ALLOWED_JSON_TYPES)
            if media not in allowed:
                raise _IntakeFailure("SOURCE_MEDIA_TYPE_UNAVAILABLE")
            size = response.headers.get("Content-Length")
            if size is not None and (
                type(size) is not str or not size.isascii() or not size.isdecimal()
                or int(size) <= 0 or int(size) > maximum
            ):
                raise _IntakeFailure("SOURCE_SIZE_LIMIT")
            raw = response.read(maximum + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise _IntakeFailure("SEC_ACCESS_DENIED_403") from None
        if exc.code == 429:
            raise _IntakeFailure("SEC_RATE_LIMITED_429") from None
        raise _IntakeFailure("SEC_HTTP_ERROR") from None
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError,
            ValueError):
        raise _IntakeFailure("SEC_NETWORK_UNAVAILABLE") from None
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        raise _IntakeFailure("SOURCE_SIZE_LIMIT")
    return raw


def collect_ticker_sec_sources(
    *, ticker: str, as_of: str, user_agent: str = "",
    allow_network: bool = False, acknowledge_four_requests: bool = False,
) -> tuple[dict, dict[str, bytes] | None]:
    """Return redacted source receipt and optional in-memory exact source bytes.

    Only explicit True/True plus a genuine contact enables HTTP. All data
    is discarded on failure; no cross-request caching, persistence or uploads.
    Returned raw bytes must be handled locally by an independently authorized
    consumer; this function does not create Engine/Guard investment decisions.
    """
    receipt = {
        "schema": "kuodra.single-ticker-sec-transport.v1",
        "status": "unavailable", "reason_code": None, "stage": "preflight",
        "http_requests_attempted": 0, "max_requests": MAX_FETCH_COUNT,
        "live_sec_http_called": False, "source_authenticated": False,
        "source_rights_verified": False, "point_in_time_verified": False,
        "full_a_b_c_ready": False, "ai_interpretation_ready": False,
        "trade_executed": False, "original_saved": False,
        "external_ai_called": False,
    }
    def fail(reason, stage):
        return ({**receipt, "status": "unavailable", "stage": stage,
                 "reason_code": reason, "live_sec_http_called":
                 receipt["http_requests_attempted"] > 0}, None)

    if allow_network is not True or acknowledge_four_requests is not True:
        return fail("EXPLICIT_FOUR_REQUEST_APPROVAL_REQUIRED", "preflight")
    if not _valid_contact(user_agent):
        return fail("GENUINE_SEC_CONTACT_REQUIRED", "preflight")
    try:
        # All malformed inputs stop before any network. No unaudited
        # interpolated URL is permitted.
        if type(ticker) is not str or not ticker.strip():
            return fail("INVALID_TICKER", "preflight")
        ticker_name = ticker.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{1,8}(?:[.-][A-Z0-9]{1,3})?", ticker_name):
            return fail("INVALID_TICKER", "preflight")
        _date(as_of)
    except (ValueError, TypeError):
        return fail("INVALID_AS_OF", "preflight")
    sources: dict[str, bytes] = {}
    stage = "ticker_map"
    try:
        receipt["http_requests_attempted"] += 1
        sources[stage] = _get_sec_bytes(
            MAP_URL, stage, user_agent=user_agent, maximum=MAX_MAP_BYTES,
        )
        resolved = resolve_sec_ticker(sources[stage], ticker_name)
        cik = resolved["cik"]

        stage = "submissions"
        time.sleep(PAUSE_SECONDS)
        receipt["http_requests_attempted"] += 1
        submissions_url = f"{SEC_API}/submissions/CIK{cik}.json"
        sources[stage] = _get_sec_bytes(
            submissions_url, stage, user_agent=user_agent,
            maximum=MAX_SUBMISSIONS_BYTES,
        )
        selected = select_sec_10k(sources[stage], cik=cik, as_of=as_of)

        stage = "companyfacts"
        time.sleep(PAUSE_SECONDS)
        receipt["http_requests_attempted"] += 1
        companyfacts_url = f"{SEC_API}/api/xbrl/companyfacts/CIK{cik}.json"
        sources[stage] = _get_sec_bytes(
            companyfacts_url, stage, user_agent=user_agent,
            maximum=_MAX_FILE_BYTES,
        )
        facts = _json(sources[stage], _MAX_FILE_BYTES, "COMPANYFACTS")
        if _cik(facts.get("cik")) != cik:
            raise _IntakeFailure("COMPANYFACTS_CIK_MISMATCH")
        if type(facts.get("facts")) is not dict or not facts["facts"]:
            raise _IntakeFailure("COMPANYFACTS_UNAVAILABLE")
        # This is only a structural issuer match, NOT verification that each
        # annual fact belongs to the chosen 10-K or a validated reporting unit.

        stage = "original_10k"
        original_url = selected["original_filing_url"]
        if not _source_url_allowed(original_url, stage) or not original_url.lower().endswith((".htm", ".html")):
            raise _IntakeFailure("ORIGINAL_DOCUMENT_FORMAT_UNSUPPORTED")
        time.sleep(PAUSE_SECONDS)
        receipt["http_requests_attempted"] += 1
        sources[stage] = _get_sec_bytes(
            original_url, stage, user_agent=user_agent,
            maximum=_MAX_ORIGINAL_BYTES,
        )

        # Source identities come from one exact-issuer plan. These SHA256
        # values prove byte consistency only, not publication authenticity.
        plan = build_ticker_source_plan(
            ticker=ticker_name, ticker_map=sources["ticker_map"],
            submissions=sources["submissions"], as_of=as_of,
        )
        if (plan.get("status") != "10k_source_plan_unverified"
                or plan.get("cik") != cik
                or plan.get("latest_10k", {}).get("accession") != selected["accession"]):
            raise _IntakeFailure("SOURCE_PLAN_INCONSISTENT")
        result = {
            **receipt,
            "status": "four_sec_responses_in_memory_unverified",
            "reason_code": None, "stage": "completed",
            "live_sec_http_called": True,
            "ticker": ticker_name, "cik": cik,
            "selected_10k_accession": selected["accession"],
            "selected_10k_filing_date": selected["filing_date"],
            "requested_as_of": as_of,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_urls": {
                "ticker_map": MAP_URL, "submissions": submissions_url,
                "companyfacts": companyfacts_url, "original_10k": original_url,
            },
            "source_sha256": {key: sha256(raw).hexdigest()
                              for key, raw in sources.items()},
            "source_bytes": {key: len(raw) for key, raw in sources.items()},
            "raw_companyfacts_financial_values_verified": False,
        }
        return result, sources
    except _IntakeFailure as exc:
        return fail(str(exc), stage)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return fail("SOURCE_IDENTITY_OR_DATA_INVALID", stage)
