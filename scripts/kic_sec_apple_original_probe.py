"""One-time SEC issuer-original live probe from an ephemeral CI runner.

Explicitly approved for the KIC project on 2026-11-01. Exactly 3 URLs at
most, sequential, no retries/credentials/third parties and NO persistence
of SEC original bytes, even as GitHub Actions artifacts. Never runs on regular
CI pushes (separate path-limited one-off workflow is required).
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from proofinvest.sec_companyfacts import verify_sec_annual_revenue
from proofinvest.local_sec_packet import _json_object

CIK = "0000320193"
ACCESSION = "0000320193-25-000079"
AS_OF = "2025-10-31"
PRIOR_END = "2024-09-28"
CURRENT_END = "2025-09-27"
USER_AGENT = (
    "KUODRA-Research/1.0 "
    "(public contact: https://github.com/hibi89/hibi89-kic-proofinvest)"
)
SOURCES = (
    ("submissions", "https://data.sec.gov/submissions/CIK0000320193.json", 5_000_000),
    ("companyfacts", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json", 24_000_000),
    ("filing", "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm", 12_000_000),
)
ALLOWED_HOSTS = {"data.sec.gov", "www.sec.gov"}


def bounded_get(url: str, limit: int, *, opener=urlopen) -> bytes:
    uri = urlsplit(url)
    if (uri.scheme != "https" or uri.hostname not in ALLOWED_HOSTS
            or uri.username or uri.password or uri.port not in (None, 443)
            or uri.query or uri.fragment):
        raise ValueError("NON_SEC_URL_BLOCKED")
    req = Request(url, method="GET", headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/html;q=0.8",
        "Accept-Encoding": "identity",
    })
    # SEC fair-access: one request at a time, no retry, 1.3s spacing.
    with opener(req, timeout=20) as response:
        status = getattr(response, "status", 200)
        actual = urlsplit(response.geturl())
        if status != 200 or actual.scheme != "https" or actual.hostname not in ALLOWED_HOSTS:
            raise ValueError("SEC_HTTP_OR_REDIRECT_BLOCKED")
        raw = response.read(limit + 1)
        if type(raw) is not bytes or not 0 < len(raw) <= limit:
            raise ValueError("SEC_ORIGINAL_BYTES_SIZE_BLOCKED")
        return raw


def check_originals(raws: dict[str, bytes]) -> dict:
    subs = _json_object(raws["submissions"], limit=5_000_000)
    facts = _json_object(raws["companyfacts"], limit=24_000_000)
    filing = raws["filing"]
    if not (str(subs.get("cik")) == "320193"
            and subs.get("name") == "Apple Inc."
            and str(facts.get("cik")) == "320193"
            and filing[:2000].lower().find(b"<html") >= 0
            and b"Apple Inc." in filing):
        raise ValueError("ISSUER_OR_DOCUMENT_IDENTITY_BLOCKED")
    recent = subs.get("filings", {}).get("recent", {})
    accession_rows = recent.get("accessionNumber", [])
    if type(accession_rows) is not list:
        raise ValueError("RECENT_ACCESSION_FORMAT_BLOCKED")
    # This list is a rolling window: absence does not establish nonfiling.
    filing_in_recent = ACCESSION in accession_rows
    if filing_in_recent:
        i = accession_rows.index(ACCESSION)
        if (recent.get("form", [])[i] != "10-K"
                or recent.get("filingDate", [])[i] != AS_OF):
            raise ValueError("APPLE_10K_SUBMISSIONS_METADATA_CONFLICT")
    rev = verify_sec_annual_revenue(
        facts, cik=CIK, accession=ACCESSION,
        as_of=AS_OF, prior_end=PRIOR_END, current_end=CURRENT_END,
    )
    return {
        "schema": "kuodra.sec-apple-original-probe.v1",
        "issuer_cik": CIK,
        "filing_accession": ACCESSION,
        "filing_date": AS_OF,
        "period_end": CURRENT_END,
        "target_accession_in_current_submissions_window": filing_in_recent,
        "companyfacts_revenue_status": rev.get("status"),
        "companyfacts_revenue_reason": rev.get("reason_code"),
        "companyfacts_current_usd": rev.get("current_usd"),
        "companyfacts_prior_usd": rev.get("prior_usd"),
        "companyfacts_growth_pct": rev.get("growth_pct"),
        "source_authenticated": False,
        "rights_verified": False,
        "historical_snapshot_authenticated": False,
        "live_sec_requested": True,
        "original_bytes_uploaded_or_persisted": False,
    }


def main() -> int:
    receipt = {
        "schema": "kuodra.sec-apple-original-probe.v1",
        "status": "BLOCKED",
        "request_limit": 3,
        "requests_attempted": 0,
        "source_authenticated": False,
        "original_bytes_uploaded_or_persisted": False,
    }
    raws: dict[str, bytes] = {}
    try:
        for i, (kind, url, limit) in enumerate(SOURCES):
            if i:
                time.sleep(1.3)
            receipt["requests_attempted"] += 1
            raw = bounded_get(url, limit)
            raws[kind] = raw
            receipt[kind] = {
                "canonical_url": url,
                "sha256": sha256(raw).hexdigest(),
                "byte_length": len(raw),
            }
        receipt.update(check_originals(raws))
        receipt["status"] = (
            "THREE_OFFICIAL_RESPONSE_BYTES_IN_MEMORY_REVENUE_PARSED"
            if receipt["companyfacts_revenue_status"] == "calculated_unverified"
            else "REVENUE_PARSER_BLOCKED_WITH_REAL_SOURCE"
        )
    except HTTPError as exc:
        receipt["reason_code"] = "SEC_HTTP_" + str(exc.code)
    except (URLError, TimeoutError) as exc:
        receipt["reason_code"] = "SEC_NETWORK_UNAVAILABLE_" + type(exc).__name__
    except (ValueError, TypeError, KeyError, UnicodeError, OSError) as exc:
        receipt["reason_code"] = str(exc)[:95] if type(exc) is ValueError else type(exc).__name__
    finally:
        print(json.dumps(receipt, sort_keys=True, ensure_ascii=True))
        raws.clear()
    return 0 if receipt["status"] == "THREE_OFFICIAL_RESPONSE_BYTES_IN_MEMORY_REVENUE_PARSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
