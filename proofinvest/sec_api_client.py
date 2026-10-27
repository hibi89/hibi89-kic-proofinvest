"""Explicit, single-request SEC CompanyConcept HTTP adapter.

NETWORK IS OFF BY DEFAULT. Only the documented SEC HTTPS endpoint is allowed.
Never requests credentials, trades, automatically retries, crawls, or writes data.
Successful HTTPS JSON retrieval is not an independent filing/source-rights audit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Mapping

from .sec_companyfacts import TAG, verify_sec_annual_revenue

MAX_RESPONSE_BYTES = 8_000_000
SEC_ORIGIN = "https://data.sec.gov"
TIMEOUT_SECONDS = 12
_USER_CONTACT = re.compile(r"[A-Za-z0-9_.+%-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_once(request: urllib.request.Request, *, timeout: int):
    """Disable redirects and environment proxies; one direct HTTPS request only."""
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect()
    )
    return opener.open(request, timeout=timeout)


def _failure(reason: str, *, attempted: bool = False) -> dict[str, Any]:
    return {
        "schema": "proofinvest.sec-concept-http-gate.v1",
        "status": "unavailable",
        "reason_code": reason,
        "source_kind": "SEC_API_NETWORK_ATTEMPT_NOT_FACT_CERTIFICATION",
        "live_api_called": attempted,
        "http_request_attempted": attempted,
        "authenticated_external_source": False,
        "source_rights_verified": False,
        "ai_agent_executed": False,
        "official_contest_submission": False,
        "growth_pct": None,
        "current_usd": None,
        "prior_usd": None,
    }


def _valid_contact(raw: Any) -> bool:
    if not isinstance(raw, str) or not 12 <= len(raw) <= 160:
        return False
    if not raw.isascii() or any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        return False
    found = _USER_CONTACT.search(raw)
    if found is None:
        return False
    email = found.group().lower()
    domain = email.rsplit("@", 1)[-1]
    if domain in {"example.com", "example.org", "example.net", "test.com"}:
        return False
    if domain.endswith((".example", ".invalid", ".local", ".test")):
        return False
    return True


def get_sec_concept(
    *, cik: str, user_agent: str, allow_network: bool = False,
) -> tuple[Mapping[str, Any] | None, str | None, bool]:
    """Return (untrusted SEC-shaped JSON payload, error_code, attempted).

    No network unless explicitly opted in with a real identifying contact.
    HTTP errors, malformed JSON, non-SEC URLs and oversized bodies fail closed.
    """
    if not allow_network:
        return None, "NETWORK_OPT_IN_REQUIRED", False
    if not isinstance(cik, str) or not re.fullmatch(r"[0-9]{10}", cik) or int(cik) == 0:
        return None, "INVALID_CIK", False
    if not _valid_contact(user_agent):
        return None, "VALID_SEC_USER_AGENT_REQUIRED", False
    url = f"{SEC_ORIGIN}/api/xbrl/companyconcept/CIK{cik}/us-gaap/{TAG}.json"
    req = urllib.request.Request(
        url, headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        }, method="GET",
    )
    attempted = True
    try:
        with _open_once(req, timeout=TIMEOUT_SECONDS) as resp:
            if resp.geturl() != url:
                return None, "UNEXPECTED_RESPONSE_URL", attempted
            if resp.status != 200:
                return None, "SEC_HTTP_NON_200", attempted
            kind = resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if kind != "application/json":
                return None, "SEC_INVALID_MEDIA_TYPE", attempted
            header_size = resp.headers.get("Content-Length")
            if header_size is not None:
                if not header_size.isdecimal() or int(header_size) > MAX_RESPONSE_BYTES:
                    return None, "SEC_RESPONSE_SIZE_LIMIT", attempted
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None, "SEC_NETWORK_OR_HTTP_ERROR", attempted
    if len(raw) > MAX_RESPONSE_BYTES:
        return None, "SEC_RESPONSE_SIZE_LIMIT", attempted
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        return None, "SEC_INVALID_JSON", attempted
    if not isinstance(result, Mapping):
        return None, "SEC_INVALID_RESPONSE", attempted
    entity_cik = result.get("cik")
    if (type(entity_cik) not in (int, str)
            or not str(entity_cik).isascii() or not str(entity_cik).isdecimal()
            or len(str(entity_cik)) > 10
            or str(int(entity_cik)).zfill(10) != cik):
        return None, "SEC_CIK_MISMATCH", attempted
    if result.get("taxonomy") != "us-gaap" or result.get("tag") != TAG:
        return None, "SEC_CONCEPT_MISMATCH", attempted
    units = result.get("units")
    if not isinstance(units, Mapping):
        return None, "SEC_MISSING_UNITS", attempted
    return result, None, attempted


def run_sec_annual_revenue(
    *, cik: str, accession: str, current_end: str, prior_end: str,
    as_of: str, user_agent: str = "", allow_network: bool = False,
    claimed_growth_pct: str | None = None,
) -> dict[str, Any]:
    """Fetch one concept then reuse deterministic local growth verification.

    Source provenance is an attempted HTTPS SEC endpoint, not an attestation
    that the remote data passed any independent external forensic review.
    """
    # Validate user-supplied target before permitting any HTTP request.
    if (not isinstance(cik, str) or not re.fullmatch(r"[0-9]{10}", cik)
            or not isinstance(accession, str)
            or not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession)
            or accession[:10] != cik):
        return _failure("INVALID_TARGET")
    payload, reason, attempted = get_sec_concept(
        cik=cik, user_agent=user_agent, allow_network=allow_network
    )
    if reason is not None or payload is None:
        return _failure(reason or "SEC_INVALID_RESPONSE", attempted=attempted)
    normalized = {
        "cik": payload["cik"],
        "facts": {"us-gaap": {TAG: {"units": payload["units"]}}},
    }
    result = verify_sec_annual_revenue(
        normalized, cik=cik, accession=accession,
        current_end=current_end, prior_end=prior_end,
        as_of=as_of, claimed_growth_pct=claimed_growth_pct,
    )
    return {
        **result,
        "source_kind": "SEC_HTTPS_CONCEPT_RESPONSE_NOT_INDEPENDENTLY_CERTIFIED",
        "live_api_called": attempted,
        "http_request_attempted": attempted,
        "authenticated_external_source": False,
        "source_rights_verified": False,
        "ai_agent_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Opt-in SEC HTTPS single-concept check; no crawler")
    p.add_argument("--allow-network", action="store_true",
                   help="Explicitly authorize one official SEC HTTPS request")
    for arg in ("cik", "accession", "current-end", "prior-end", "as-of"):
        p.add_argument("--" + arg, required=True)
    p.add_argument("--claimed-growth-pct", default=None)
    args = p.parse_args(argv)
    verdict = run_sec_annual_revenue(
        cik=args.cik, accession=args.accession,
        current_end=args.current_end, prior_end=args.prior_end,
        as_of=args.as_of, allow_network=args.allow_network,
        user_agent=os.environ.get("PROOFINVEST_SEC_USER_AGENT", ""),
        claimed_growth_pct=args.claimed_growth_pct,
    )
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["status"] == "calculated_unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
