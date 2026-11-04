"""P187: read-only Apple 10-K public-filing vintage selector, no HTTP.

Metadata transcribed from PUBLIC SEC index listings (2025 and 2026) and
Apple investor-relations catalog as checked on 2026-11-05 KST. This does not
download, authenticate or grant rights to original SEC/iXBRL bytes.
Date-only as_of conservatively delays a filing until the next calendar day.
Future as_of beyond the last catalog review must fail closed.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any

_TICKER = "AAPL"
_CIK = "0000320193"
_CHECKED_THROUGH = date(2026, 11, 5)
_CATALOG = (
    ("0000320193-25-000079", date(2025, 10, 31), date(2025, 9, 27),
     "https://www.sec.gov/Archives/edgar/data/320193/"
     "000032019325000079/0000320193-25-000079-index.htm"),
    ("0000320193-26-000026", date(2026, 11, 3), date(2026, 9, 26),
     "https://www.sec.gov/Archives/edgar/data/320193/"
     "000032019326000026/0000320193-26-000026-index.htm"),
)
_STRICT_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z", re.ASCII)


def _blocked(code: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.apple-public-10k-vintage.v1",
        "status": "BLOCKED",
        "reason_code": code,
        "fiscal_filing_original_bytes_verified": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "ai_agent_executed": False,
        "guard_policy_preview": "HOLD",
        "trade_executed": False,
        "external_network_requests": 0,
        "data_downloaded": False,
    }


def check_apple_public_filing_vintage(
    *, ticker: str, as_of: str, accession: str, fiscal_period_end: str,
) -> dict[str, Any]:
    """Reject a public filing accession that was not yet safely available.

    Only the literal public metadata catalog is checked. No actual source
    original bytes or legal entitlements are checked, even on MATCHED.
    """
    if (type(ticker) is not str or ticker != _TICKER
            or type(as_of) is not str or _STRICT_DATE.fullmatch(as_of) is None
            or type(accession) is not str
            or type(fiscal_period_end) is not str
            or _STRICT_DATE.fullmatch(fiscal_period_end) is None):
        return _blocked("APPLE_PUBLIC_FILING_METADATA_INVALID")
    try:
        observed = date.fromisoformat(as_of)
        period = date.fromisoformat(fiscal_period_end)
    except ValueError:
        return _blocked("APPLE_PUBLIC_FILING_DATE_INVALID")
    if observed > _CHECKED_THROUGH:
        return _blocked("PUBLIC_CATALOG_RECHECK_REQUIRED_FOR_LATER_AS_OF")
    available = [row for row in _CATALOG if observed > row[1]]
    if not available:
        return _blocked("PUBLIC_FILING_NOT_YET_AVAILABLE_FOR_DATE_ONLY_AS_OF")
    current = available[-1]
    if accession != current[0] or period != current[2]:
        return _blocked("FILING_SUPERSEDED_OR_WRONG_FISCAL_PERIOD")
    return {
        **_blocked(""),
        "status": "PUBLIC_FILING_VINTAGE_METADATA_MATCHED_ORIGINAL_UNVERIFIED",
        "reason_code": "SEC_INDEX_CATALOG_NOT_RAW_SOURCE_AUTHENTICATION",
        "ticker": _TICKER,
        "cik": _CIK,
        "accession": current[0],
        "fiscal_period_end": current[2].isoformat(),
        "filing_date": current[1].isoformat(),
        "public_index_reference_url": current[3],
        "public_issuer_catalog_url": "https://investor.apple.com/sec-filings/default.aspx",
        "catalog_checked_through": _CHECKED_THROUGH.isoformat(),
        "date_only_as_of": observed.isoformat(),
        "date_only_availability_rule": "AVAILABLE_ONLY_DAY_AFTER_FILING",
    }
