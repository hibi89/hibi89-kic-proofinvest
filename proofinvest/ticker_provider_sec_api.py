"""P145 opt-in one-ticker licensed third-party SEC filing source adapter.

SOURCE BOUNDARY: sec-api.io Mapping -> Filing Search -> XBRL Converter ->
independently hosted EDGAR mirror ORIGINAL. Exactly four vendor requests, no
SEC.gov HTTP at any point. The converter is NOT SEC CompanyFacts; we create a
clearly labeled derived SEC-shaped in-memory representation and only then
feed the unchanged seven-tool local replay. No provider license, signature,
historical publication time or truth is inferred from metadata/digests.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from typing import Any, Callable
from urllib.parse import urlsplit, quote
from urllib.request import (
    Request, build_opener, HTTPRedirectHandler,
)
from .ticker_research_intake import _TICKER
from .ticker_local_workflow import run_local_ticker_workflow
from .ticker_local_dashboard import summarize_local_ticker_dashboard
from .ticker_sec_financial_bridge import _LIMITS

_MAP_HOST = "https://api.sec-api.io"
_MIRROR_HOST = "https://edgar-mirror.sec-api.io"
_GETS_MAX = 4
_MAX_MAP = 200_000
_MAX_QUERY = 400_000
_MAX_XBRL = 8_000_000
_MAX_ORIGINAL = 24_000_000
_REVENUE = ("RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax")
_EXTRA = {
    "StatementsOfIncome": ("NetIncomeLoss", "OperatingIncomeLoss"),
    "StatementsOfCashFlows": ("NetCashProvidedByUsedInOperatingActivities",
                              "PaymentsToAcquirePropertyPlantAndEquipment"),
    "BalanceSheets": ("Assets", "Liabilities", "AccountsReceivableNetCurrent",
                      "InventoryNet"),
}


def _blocked(reason: str, requests: int = 0) -> dict[str, Any]:
    return {
        "schema": "kuodra.sec-api-one-ticker-readonly.v1",
        "status": "BLOCKED", "reason_code": reason,
        "vendor": "SEC_API_IO", "provider_http_requests_attempted": requests,
        "official_sec_http_requests": 0, "source_authenticated": False,
        "source_rights_verified": False,
        "redistribution_allowed": False, "true_historical_vintage_verified": False,
        "original_edgar_bytes_authenticated": False, "trade_executed": False,
        "guard_executed": False, "full_a_b_c_ready": False, "report": None,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _vendor_http(method: str, url: str, payload: bytes | None,
                 key: str, maximum: int) -> bytes:
    """Synchronous, no redirect/retry, fixed-domain, content-bounded HTTP."""
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc not in (
            "api.sec-api.io", "edgar-mirror.sec-api.io")
            or parts.username or parts.password or parts.fragment):
        raise ValueError("INVALID_VENDOR_HOST")
    request = Request(
        url=url, data=payload, method=method,
        headers={"Authorization": key, "Accept-Encoding": "identity",
                 "Accept": "application/json" if parts.netloc == "api.sec-api.io"
                 else "text/html,application/xhtml+xml"},
    )
    # This isolated opener refuses 301/302/307/308 incl. credential leakage.
    with build_opener(_NoRedirect).open(request, timeout=8) as response:
        if response.geturl() != url or response.status != 200:
            raise ValueError("VENDOR_RESPONSE_UNAVAILABLE")
        raw = response.read(maximum + 1)
        if not 0 < len(raw) <= maximum:
            raise ValueError("VENDOR_RESPONSE_SIZE_INVALID")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("COMPRESSED_VENDOR_RESPONSE_UNSUPPORTED")
        return raw


def _object(raw: bytes, maximum: int) -> Any:
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        raise ValueError("VENDOR_JSON_SIZE")
    def duplicate(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("VENDOR_JSON_DUPLICATE")
            out[key] = value
        return out
    def nonfinite(_value):
        raise ValueError("VENDOR_NONFINITE")
    return json.loads(raw.decode("utf-8-sig"),
                      object_pairs_hook=duplicate, parse_constant=nonfinite)


def _cik(value: Any) -> str:
    if (type(value) not in (int, str)
            or type(value) is str and
            (not value.isascii() or not value.isdecimal())
            or not 0 < int(value) < 10**10):
        raise ValueError("VENDOR_CIK_INVALID")
    return str(int(value)).zfill(10)


def _day(value: Any) -> date:
    if type(value) is not str:
        raise ValueError("VENDOR_DATE_INVALID")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("VENDOR_DATE_INVALID")
    return parsed


def _mapping(raw: bytes, ticker: str) -> tuple[str, str, bytes]:
    rows = _object(raw, _MAX_MAP)
    if type(rows) is not list or not 0 < len(rows) <= 300:
        raise ValueError("VENDOR_TICKER_MAP_UNAVAILABLE")
    exact = [entry for entry in rows if type(entry) is dict
             and entry.get("ticker") == ticker and entry.get("isDelisted") is not True]
    if len(exact) != 1:
        raise ValueError("VENDOR_TICKER_AMBIGUOUS")
    row = exact[0]
    cik = _cik(row.get("cik"))
    title = row.get("name")
    if (type(title) is not str or not 0 < len(title) <= 250
            or any(ord(char) < 32 or ord(char) == 127 for char in title)):
        raise ValueError("VENDOR_NAME_INVALID")
    mapping = json.dumps({"0": {"cik_str": int(cik), "ticker": ticker,
                                  "title": title}}, sort_keys=True,
                         separators=(",", ":")).encode()
    return cik, title, mapping


def _filing(raw: bytes, *, ticker: str, cik: str,
            cutoff: date) -> tuple[str, str, str, str]:
    obj = _object(raw, _MAX_QUERY)
    rows = obj.get("filings") if type(obj) is dict else None
    if type(rows) is not list or not 0 < len(rows) <= 10:
        raise ValueError("VENDOR_FILING_LIST_UNAVAILABLE")
    eligible = []
    for row in rows:
        if type(row) is not dict or row.get("formType") != "10-K":
            continue
        if _cik(row.get("cik")) != cik or row.get("ticker") != ticker:
            raise ValueError("VENDOR_FILING_ISSUER_CONFLICT")
        filed = row.get("filedAt")
        if type(filed) is not str or len(filed) < 10:
            raise ValueError("VENDOR_FILED_AT_INVALID")
        filing_day = _day(filed[:10])
        if filing_day > cutoff:
            continue
        acc = row.get("accessionNo")
        if (type(acc) is not str or
                not __import__("re").fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", acc)):
            raise ValueError("VENDOR_ACCESSION_UNSAFE")
        report_date = row.get("periodOfReport")
        if _day(report_date) > filing_day:
            raise ValueError("VENDOR_FISCAL_DATE_FUTURE")
        source_url = row.get("linkToFilingDetails")
        if type(source_url) is not str:
            raise ValueError("VENDOR_ORIGINAL_URI_INVALID")
        p = urlsplit(source_url)
        expected_path = f"/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/"
        if (p.scheme != "https" or p.netloc != "www.sec.gov"
                or p.query or p.fragment or p.username or p.password
                or not p.path.startswith(expected_path)
                or not __import__("re").fullmatch(
                    r"[A-Za-z0-9_.-]+\\.(?:htm|html|xhtml)", p.path[len(expected_path):])):
            raise ValueError("VENDOR_ORIGINAL_URI_INVALID")
        eligible.append((filing_day, acc, report_date,
                         p.path[len(expected_path):]))
    if not eligible:
        raise ValueError("VENDOR_10K_BEFORE_AS_OF_MISSING")
    eligible.sort(key=lambda e: (e[0], e[1]), reverse=True)
    if len(eligible) > 1 and eligible[0][:2] == eligible[1][:2]:
        raise ValueError("VENDOR_DUPLICATE_FILING")
    day, acc, report_date, filename = eligible[0]
    return day.isoformat(), acc, report_date, filename


def _facts_from_xbrl(raw: bytes, *, cik: str, accession: str,
                     filed: str, fiscal_end: str) -> bytes:
    xbrl = _object(raw, _MAX_XBRL)
    cover = xbrl.get("CoverPage") if type(xbrl) is dict else None
    if (type(cover) is not dict or cover.get("DocumentType") != "10-K"
            or _cik(cover.get("EntityCentralIndexKey")) != cik
            or cover.get("DocumentPeriodEndDate") != fiscal_end):
        raise ValueError("VENDOR_XBRL_COVER_IDENTITY")
    statement = xbrl.get("StatementsOfIncome")
    if type(statement) is not dict:
        raise ValueError("VENDOR_XBRL_NO_INCOME")
    facts = {}
    def parse_tag(name: str, body: Any) -> list[dict]:
        entries = body if type(body) is list else [body]
        if len(entries) > 1000:
            raise ValueError("VENDOR_XBRL_TOO_MANY_FACTS")
        found = []
        for row in entries:
            if type(row) is not dict or "segment" in row:
                continue
            period = row.get("period")
            if type(period) is not dict or row.get("unitRef", "").lower() != "usd":
                continue
            value = row.get("value")
            if (type(value) is not str
                    or not __import__("re").fullmatch(r"-?[0-9]{1,20}", value)):
                continue
            if "startDate" not in period or "endDate" not in period:
                continue
            begin, end = _day(period["startDate"]), _day(period["endDate"])
            if (end < begin or end > _day(fiscal_end)
                    or not 330 <= (end - begin).days <= 390):
                continue
            found.append({"accn": accession, "form": "10-K",
                          "start": begin.isoformat(), "end": end.isoformat(),
                          "filed": filed, "val": int(value)})
        # A consistent consolidated fact is required per period, no silent
        # arbitrary order-based choice from competing XBRL contexts.
        by_period = {}
        for row in found:
            key = (row["start"], row["end"])
            if key in by_period and by_period[key] != row["val"]:
                raise ValueError("VENDOR_XBRL_CONFLICTING_CONTEXTS")
            by_period[key] = row["val"]
        return list(found)
    revenue_tag = next((name for name in _REVENUE if name in statement), None)
    if revenue_tag is None:
        raise ValueError("VENDOR_XBRL_REVENUE_MISSING")
    revenues = parse_tag(revenue_tag, statement[revenue_tag])
    if len(set(row["end"] for row in revenues)) < 2:
        raise ValueError("VENDOR_XBRL_TWO_ANNUAL_PERIODS_REQUIRED")
    facts[revenue_tag] = {"units": {"USD": revenues}}
    for section, names in _EXTRA.items():
        block = xbrl.get(section)
        if type(block) is not dict:
            continue
        for name in names:
            if name in block:
                observations = parse_tag(name, block[name])
                if observations:
                    facts[name] = {"units": {"USD": observations}}
    company = {"cik": int(cik), "facts": {"us-gaap": facts}}
    encoded = json.dumps(company, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode()
    if len(encoded) > _LIMITS["companyfacts"]:
        raise ValueError("VENDOR_TRANSLATED_FACTS_TOO_LARGE")
    return encoded


def _submissions(*, cik: str, accession: str, filed: str,
                 report_date: str, filename: str, title: str,
                 ticker: str) -> bytes:
    return json.dumps({
        "cik": int(cik), "name": title, "tickers": [ticker],
        "filings": {"recent": {
            "form": ["10-K"], "accessionNumber": [accession],
            "filingDate": [filed], "reportDate": [report_date],
            "primaryDocument": [filename],
        }},
    }, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def run_sec_api_on_demand(
    *, ticker: str, as_of: str, api_key: str | None,
    explicit_click: bool = False, operator_retrieval_approved: bool = False,
    operator_rights_approved: bool = False,
    market_json: bytes | None = None, industry_json: bytes | None = None,
    transport: Callable[[str, str, bytes | None, str, int], bytes] | None = None,
) -> dict[str, Any]:
    """Bounded licensed alternative to *direct* SEC GET, NEVER 403 bypass.

    This requires separate vendor entitlement and an explicitly authorised
    disclosure of ticker + day to this provider. All defaults fail closed.
    """
    request_count = 0
    if not (explicit_click is True and operator_retrieval_approved is True
            and operator_rights_approved is True
            and os.environ.get("KUODRA_ENABLE_SEC_API_VENDOR") == "1"
            and os.environ.get("KUODRA_SEC_API_VENDOR_RETRIEVAL_APPROVED") == "1"
            and os.environ.get("KUODRA_SEC_API_VENDOR_RIGHTS_APPROVED") == "1"):
        return _blocked("VENDOR_OPERATOR_APPROVAL_REQUIRED")
    if (type(api_key) is not str or not 16 <= len(api_key) <= 256
            or any(ch.isspace() or ord(ch) < 33 or ord(ch) > 126 for ch in api_key)):
        return _blocked("VENDOR_KEY_NOT_CONFIGURED")
    if type(ticker) is not str or not _TICKER.fullmatch(ticker):
        return _blocked("VENDOR_TICKER_INVALID")
    try:
        cutoff = _day(as_of)
        if cutoff > datetime.now(timezone.utc).date():
            return _blocked("VENDOR_DATE_FUTURE")
        if market_json is not None and (type(market_json) is not bytes or len(market_json) > 131072):
            return _blocked("VENDOR_MARKET_INPUT_TOO_LARGE")
        if industry_json is not None and (type(industry_json) is not bytes or len(industry_json) > 65536):
            return _blocked("VENDOR_PEER_INPUT_TOO_LARGE")
        reader = transport if transport is not None else _vendor_http
        def read(method: str, url: str, payload: bytes | None, limit: int) -> bytes:
            nonlocal request_count
            # Every invocation counts as a request attempt even if it throws.
            request_count += 1
            if request_count > _GETS_MAX:
                raise ValueError("VENDOR_NETWORK_BUDGET_EXCEEDED")
            return reader(method, url, payload, api_key, limit)
        mapping_bytes = read("GET", _MAP_HOST + "/mapping/ticker/" + ticker,
                             None, _MAX_MAP)
        cik, company, ticker_map = _mapping(mapping_bytes, ticker)
        query = {
            "query": f'cik:{int(cik)} AND formType:"10-K" AND filedAt:[1993-01-01 TO {as_of}]',
            "from": "0", "size": "10",
            "sort": [{"filedAt": {"order": "desc"}}],
        }
        query_bytes = read("POST", _MAP_HOST,
                           json.dumps(query, separators=(",", ":")).encode(), _MAX_QUERY)
        filing_date, accession, period_end, filename = _filing(
            query_bytes, ticker=ticker, cik=cik, cutoff=cutoff)
        xbrl_bytes = read("GET", _MAP_HOST + "/xbrl-to-json?accession-no=" + accession,
                          None, _MAX_XBRL)
        companyfacts = _facts_from_xbrl(
            xbrl_bytes, cik=cik, accession=accession, filed=filing_date,
            fiscal_end=period_end)
        original_uri = (
            f"{_MIRROR_HOST}/{int(cik)}/{accession.replace('-', '')}/{filename}")
        original = read("GET", original_uri, None, _MAX_ORIGINAL)
        if not (original.lstrip().lower().startswith((b"<!doctype html", b"<html", b"<?xml"))
                or b"<ix:" in original[:4096]):
            raise ValueError("VENDOR_ORIGINAL_FORMAT_INVALID")
        sources = {
            "ticker_map": ticker_map,
            "submissions": _submissions(
                cik=cik, accession=accession, filed=filing_date,
                report_date=period_end, filename=filename,
                title=company, ticker=ticker),
            "companyfacts": companyfacts,
            "original_10k": original,
        }
        if any(not 0 < len(raw) <= _LIMITS[k] for k, raw in sources.items()):
            raise ValueError("VENDOR_SOURCE_LIMIT_MISMATCH")
        workflow = run_local_ticker_workflow(
            ticker=ticker, as_of=as_of, sources=sources,
            market_json=market_json, industry_json=industry_json)
        if workflow.get("status") != "READY_FOR_HUMAN_REVIEW_UNVERIFIED":
            return _blocked("VENDOR_SEVEN_STAGE_REPLAY_BLOCKED", request_count)
        dashboard = summarize_local_ticker_dashboard(workflow)
        if (dashboard.get("status") != "LOCAL_SOURCE_REPLAYED_UNVERIFIED"
                or dashboard.get("guard_policy") != "HOLD"):
            return _blocked("VENDOR_GUARD_OR_REPLAY_NOT_ELIGIBLE", request_count)
        return {
            **_blocked("UNVERIFIED_THIRD_PARTY_TRANSFORMED_DATA", request_count),
            "status": "SOURCE_REPLAYED_UNVERIFIED",
            "ticker": ticker, "issuer_cik": cik, "as_of": as_of,
            "accession": accession, "filing_date": filing_date,
            "fiscal_end": period_end,
            "source_kind": "THIRD_PARTY_XBRL_TO_SEC_SHAPED_UNAUTHENTICATED",
            "provider_documentation": "https://sec-api.io/api-reference",
            "source_sha256": {k: sha256(raw).hexdigest() for k, raw in sources.items()},
            "raw_vendor_response_sha256": {
                "mapping": sha256(mapping_bytes).hexdigest(),
                "filing_query": sha256(query_bytes).hexdigest(),
                "xbrl": sha256(xbrl_bytes).hexdigest(),
                "mirror_original": sha256(original).hexdigest(),
            },
            "source_authenticated": False, "source_rights_verified": False,
            "redistribution_allowed": False, "original_edgar_bytes_authenticated": False,
            "full_a_b_c_ready": False, "guard_policy_preview": "HOLD",
            "report": workflow["report"], "dashboard": dashboard,
        }
    except (ValueError, KeyError, TypeError, OverflowError, UnicodeError,
            OSError, RecursionError, json.JSONDecodeError):
        return _blocked("VENDOR_RESPONSE_OR_REPLAY_INVALID", request_count)
