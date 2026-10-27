"""Explicit opt-in, exactly bounded SEC transport-to-local-review pipeline.

NO NETWORK BY DEFAULT. No upload, unattended scheduling, credentials or trades.
A validated SEC HTTPS response is transport evidence, NOT independent issuer,
source-rights, historical data availability, or financial-fact authentication.

The three HTTPS GETs are intentionally independent and never retried. This
module does not persist copies; caller has to separately opt into retention.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import urllib.error
import urllib.request
from typing import Any

from disclosure_lightning.core import (
    MAX_JSON_BYTES, _NoRedirect, _valid_user_agent, cik10,
    fetch_submissions, index_submissions, save_index,
)
from disclosure_lightning.originals import (
    fetch_original, locate_original, persist_original,
)
from proofinvest.dl_bridge import assess_dl_sec_handoff
from proofinvest.sec_companyfacts import _date, verify_sec_annual_revenue
from proofinvest.local_sec_packet import _json_object

_SEC_DOMAIN = "https://data.sec.gov"
_MAX_FACTS = 8_000_000
_REQUEST_PAUSE_SECONDS = 0.25


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _error(reason: str, stage: str, attempted: int) -> dict[str, Any]:
    return {
        "schema": "proofinvest.sec-3source-explicit-transport.v1",
        "status": "unavailable",
        "reason_code": reason,
        "stage": stage,
        "http_requests_attempted": attempted,
        "live_sec_http_called": attempted > 0,
        "source_authenticated": False,
        "financial_facts_authenticated": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }


def _fetch_companyfacts(cik: str, user_agent: str) -> bytes:
    """A single pinned GET. No redirect, proxy, retry, or data persistence."""
    url = f"{_SEC_DOMAIN}/api/xbrl/companyfacts/CIK{cik}.json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "application/json",
                 "Accept-Encoding": "identity"},
        method="GET",
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect(),
    )
    with opener.open(req, timeout=15) as resp:
        if resp.status != 200 or resp.geturl() != url:
            raise ValueError("UNEXPECTED_SEC_RESPONSE_URL_OR_STATUS")
        media = resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if media != "application/json":
            raise ValueError("SEC_NON_JSON_MEDIA_TYPE")
        length = resp.headers.get("Content-Length")
        if length is not None and (not length.isascii() or not length.isdecimal()
                                   or not 0 < int(length) <= _MAX_FACTS):
            raise ValueError("INVALID_SEC_COMPANYFACTS_SIZE")
        raw = resp.read(_MAX_FACTS + 1)
    if not 0 < len(raw) <= _MAX_FACTS:
        raise ValueError("SEC_COMPANYFACTS_SIZE_LIMIT")
    return raw


def run_sec_three_source_review(
    *, cik: str, accession: str, current_end: str, prior_end: str,
    user_agent: str = "", allow_network: bool = False,
    acknowledge_three_requests: bool = False,
    claimed_growth_pct: str | None = None,
) -> dict[str, Any]:
    """Fetch at most one submissions, one CompanyFacts, one original HTTPS GET.

    Caller must *separately* explicitly authorize use of a genuine contact
    UA and three provider requests. This function performs no network unless
    BOTH allow_network and acknowledge_three_requests are literally True.
    The as-of is always the current actual UTC day, never a backdated capture.
    """
    if allow_network is not True or acknowledge_three_requests is not True:
        return _error("EXPLICIT_THREE_REQUEST_APPROVAL_REQUIRED", "preflight", 0)
    try:
        target = cik10(cik)
    except (TypeError, ValueError):
        return _error("INVALID_CIK", "preflight", 0)
    if (not isinstance(accession, str)
            or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession) is None
            or accession[:10] != target):
        return _error("INVALID_ACCESSION", "preflight", 0)
    if not _valid_user_agent(user_agent):
        return _error("GENUINE_CONTACT_USER_AGENT_REQUIRED", "preflight", 0)
    curr, prev = _date(current_end), _date(prior_end)
    if (curr is None or prev is None or not prev < curr
            or not 330 <= (curr - prev).days <= 380):
        return _error("INVALID_FISCAL_PERIODS", "preflight", 0)
    if (claimed_growth_pct is not None and (
            not isinstance(claimed_growth_pct, str)
            or re.fullmatch(r"[+-]?\d{1,5}(?:\.\d{1,4})?", claimed_growth_pct) is None)):
        return _error("INVALID_GROWTH_CLAIM", "preflight", 0)
    attempts = 0
    stage = "submissions"
    try:
        with TemporaryDirectory(prefix="proofinvest-sec-3source-") as directory:
            db = Path(directory) / "evidence.sqlite3"
            as_of = _utcnow().date().isoformat()
            attempts += 1
            raw_submissions = fetch_submissions(
                target, user_agent=user_agent, allow_network=True,
            )
            observed_submissions = _utcnow()
            if observed_submissions.date().isoformat() != as_of:
                raise ValueError("SEC_COLLECTION_CROSSED_UTC_DAY")
            indexed = index_submissions(
                raw_submissions, cik=target, as_of=as_of,
                forms=frozenset({"10-K"}), provenance="SEC_HTTPS_RESPONSE",
                collected_at=observed_submissions.isoformat(timespec="seconds"),
            )
            filings = [f for f in indexed["filings"] if f.get("accession") == accession]
            if len(filings) != 1 or filings[0].get("form") != "10-K":
                raise ValueError("REQUESTED_10K_NOT_AVAILABLE_IN_SEC_RECENT_WINDOW")
            save_index(db, raw_submissions, indexed)
            receipt = locate_original(db, cik=target, accession=accession)
            stage = "companyfacts"
            time.sleep(_REQUEST_PAUSE_SECONDS)
            attempts += 1
            raw_facts = _fetch_companyfacts(target, user_agent)
            observed_facts = _utcnow()
            if observed_facts.date().isoformat() != as_of:
                raise ValueError("SEC_COLLECTION_CROSSED_UTC_DAY")
            facts = _json_object(raw_facts, limit=MAX_JSON_BYTES)
            actual_cik = facts.get("cik")
            if (type(actual_cik) not in (int, str)
                    or not str(actual_cik).isascii()
                    or not str(actual_cik).isdecimal()
                    or len(str(actual_cik)) > 10
                    or str(int(actual_cik)).zfill(10) != target):
                raise ValueError("SEC_COMPANYFACTS_ISSUER_MISMATCH")
            verdict = verify_sec_annual_revenue(
                facts, cik=target, accession=accession,
                current_end=current_end, prior_end=prior_end,
                as_of=as_of, claimed_growth_pct=claimed_growth_pct,
            )
            if verdict.get("status") not in ("calculated_unverified", "conflict"):
                raise ValueError("SEC_COMPANYFACTS_VERDICT_UNAVAILABLE")
            linked = assess_dl_sec_handoff(indexed, verdict)
            if (linked.get("status") != "linked_metadata_only"
                    or linked.get("trace_linked") is not True
                    or linked.get("authenticated_external_source") is not False):
                raise ValueError("SEC_METADATA_FINANCIAL_LINK_UNAVAILABLE")
            stage = "original_filing"
            time.sleep(_REQUEST_PAUSE_SECONDS)
            attempts += 1
            original, kind = fetch_original(
                receipt=receipt, user_agent=user_agent, allow_network=True,
            )
            observed_original = _utcnow()
            if observed_original.date().isoformat() != as_of:
                raise ValueError("SEC_COLLECTION_CROSSED_UTC_DAY")
            stored = persist_original(
                db_path=db, receipt=receipt, raw=original,
                kind=kind, origin="SEC_HTTPS_RESPONSE_UNVERIFIED",
            )
            if (stored.get("authenticated_external_source") is not False
                    or stored.get("original_filing_retrieved") is not True
                    or stored.get("status") != "SAVED"
                    or stored.get("source_uri") != linked.get("filing_source_uri")
                    or stored.get("filing_sha256") != hashlib.sha256(original).hexdigest()):
                raise ValueError("SEC_ORIGINAL_LOCAL_ARCHIVE_INTEGRITY_FAILURE")
            return {
                "schema": "proofinvest.sec-3source-explicit-transport.v1",
                "status": "three_sec_https_responses_captured_unverified",
                "http_requests_attempted": attempts,
                "live_sec_http_called": True,
                "issuer_cik": target,
                "accession": accession,
                "observed_utc_day": as_of,
                "submissions_observed_at_utc": observed_submissions.isoformat(),
                "companyfacts_observed_at_utc": observed_facts.isoformat(),
                "original_observed_at_utc": observed_original.isoformat(),
                "filing_date": linked["filing_date"],
                "source_uris": {
                    "submissions": indexed["source_uri"],
                    "companyfacts": f"{_SEC_DOMAIN}/api/xbrl/companyfacts/CIK{target}.json",
                    "original_filing": receipt["source_uri"],
                },
                "raw_response_sha256": {
                    "submissions": hashlib.sha256(raw_submissions).hexdigest(),
                    "companyfacts": hashlib.sha256(raw_facts).hexdigest(),
                    "original_filing": stored["filing_sha256"],
                },
                "local_original_content_type": kind,
                "numeric_review": {
                    "status": verdict["status"],
                    "reason_code": verdict["reason_code"],
                    "prior_usd": verdict["prior_usd"],
                    "current_usd": verdict["current_usd"],
                    "growth_pct": verdict["growth_pct"],
                    "source_attribution": "SEC_HTTPS_TRANSPORT_NOT_INDEPENDENTLY_CERTIFIED",
                },
                "capture_bytes_persisted": False,
                "source_authenticated": False,
                "financial_facts_authenticated": False,
                "source_rights_verified": False,
                "official_contest_submission": False,
                "note": ("Only SEC HTTPS transport shape, response digests and local arithmetic checked; "
                         "no independent origin, financial truth or redistribution-rights audit."),
            }
    except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError,
            urllib.error.URLError, http.client.HTTPException):
        # Never leak UA/contact, file content or URLs with unexpected payloads.
        return _error("SEC_CAPTURE_STAGE_FAILED", stage, attempts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Explicit opt-in, max THREE SEC HTTPS GETs, no file persistence."
    )
    p.add_argument("--cik", required=True)
    p.add_argument("--accession", required=True)
    p.add_argument("--current-end", required=True)
    p.add_argument("--prior-end", required=True)
    p.add_argument("--claimed-growth-pct", default=None)
    p.add_argument("--allow-network", action="store_true")
    p.add_argument("--acknowledge-three-requests", action="store_true")
    args = p.parse_args(argv)
    response = run_sec_three_source_review(
        cik=args.cik, accession=args.accession,
        current_end=args.current_end, prior_end=args.prior_end,
        claimed_growth_pct=args.claimed_growth_pct,
        user_agent=os.environ.get("PROOFINVEST_SEC_USER_AGENT", ""),
        allow_network=args.allow_network,
        acknowledge_three_requests=args.acknowledge_three_requests,
    )
    print(json.dumps(response, sort_keys=True, ensure_ascii=False, indent=2))
    return 0 if response["status"] == "three_sec_https_responses_captured_unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
