"""Single-ticker SEC CIK + 10-K source planner. No network, upload or trading.

Reads only explicitly supplied ticker-map and submissions bytes. The source
SHA is local integrity, NOT SEC authentication, provider rights or PIT proof.
This module never requests remote data, adds background jobs or persists it.
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_API = "https://data.sec.gov"
SEC_ARCHIVE = "https://www.sec.gov/Archives/edgar/data"
MAX_MAP_BYTES = 3_000_000
MAX_SUBMISSIONS_BYTES = 8_000_000
MAX_ROWS = 35_000
MAX_FILINGS = 20_000
_TICKER = re.compile(r"[A-Z0-9]{1,8}(?:[.-][A-Z0-9]{1,3})?\Z", re.ASCII)
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
_DOCUMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z", re.ASCII)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z", re.ASCII)


def _bad(reason: str):
    raise ValueError(reason)


def _pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            _bad("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _json(raw: bytes, maximum: int, source: str):
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        _bad(source + "_SIZE_INVALID")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                         parse_constant=lambda _: _bad("NONFINITE_NUMBER"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _bad(source + "_INVALID_JSON")
    if type(doc) is not dict:
        _bad(source + "_INVALID_ROOT")
    return doc


def _cik(value: Any) -> str:
    if type(value) is int and 0 < value <= 9999999999:
        return f"{value:010d}"
    if (type(value) is str and 1 <= len(value) <= 10 and value.isascii()
            and value.isdecimal() and int(value) > 0):
        return value.zfill(10)
    _bad("INVALID_CIK")


def _date(value):
    if type(value) is not str or not _DATE.fullmatch(value):
        _bad("INVALID_DATE")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _bad("INVALID_DATE")


def resolve_sec_ticker(raw: bytes, ticker: str) -> dict:
    if type(ticker) is not str:
        _bad("INVALID_TICKER")
    key = ticker.strip().upper()
    if not _TICKER.fullmatch(key):
        _bad("INVALID_TICKER")
    doc = _json(raw, MAX_MAP_BYTES, "TICKER_MAP")
    if not 0 < len(doc) <= MAX_ROWS:
        _bad("TICKER_MAP_ROW_COUNT_INVALID")
    match = None
    for index, item in doc.items():
        if (type(index) is not str or not index.isascii()
                or not index.isdecimal() or type(item) is not dict
                or not {"cik_str", "ticker", "title"}.issubset(item)):
            _bad("TICKER_MAP_ROW_INVALID")
        symbol = item["ticker"]
        # Unrelated special-class identifiers need not fit KUODRA's input
        # grammar; they must not block a valid exact-ticker match.
        if type(symbol) is not str or not symbol.isascii():
            _bad("TICKER_MAP_ROW_INVALID")
        if symbol.upper() == key:
            cik = _cik(item["cik_str"])
            name = item["title"]
            if (type(name) is not str or not 0 < len(name) <= 250
                    or any(ord(c) < 32 or ord(c) == 127 for c in name)):
                _bad("TICKER_MAP_NAME_INVALID")
            if match is not None:
                _bad("TICKER_AMBIGUOUS")
            match = {"ticker": key, "cik": cik, "sec_company_name": name}
    if match is None:
        _bad("TICKER_NOT_IN_MAP")
    return {**match, "ticker_map_url": MAP_URL,
            "ticker_map_sha256": sha256(raw).hexdigest(),
            "map_origin_authenticated": False, "map_freshness_verified": False}


def select_sec_10k(raw: bytes, *, cik: str, as_of: str) -> dict:
    issuer = _cik(cik)
    cutoff = _date(as_of)
    doc = _json(raw, MAX_SUBMISSIONS_BYTES, "SUBMISSIONS")
    if _cik(doc.get("cik")) != issuer:
        _bad("SUBMISSIONS_CIK_MISMATCH")
    filings = doc.get("filings")
    recent = filings.get("recent") if type(filings) is dict else None
    names = ("form", "accessionNumber", "filingDate", "reportDate", "primaryDocument")
    if type(recent) is not dict or any(type(recent.get(k)) is not list for k in names):
        _bad("SUBMISSIONS_RECENT_INVALID")
    sizes = [len(recent[k]) for k in names]
    if len(set(sizes)) != 1 or sizes[0] > MAX_FILINGS:
        _bad("SUBMISSIONS_ARRAY_LENGTH_MISMATCH")
    eligible = []
    amendments = []
    for i in range(sizes[0]):
        form = recent["form"][i]
        if form not in ("10-K", "10-K/A"):
            continue
        filing = _date(recent["filingDate"][i])
        if filing > cutoff:
            continue
        accession = recent["accessionNumber"][i]
        filename = recent["primaryDocument"][i]
        if (type(accession) is not str or not _ACCESSION.fullmatch(accession)
                # The accession prefix is the CIK of the submitting
                # account, which may be a third-party EDGAR filing agent.
                # Issuer identity is bound to THIS issuer's Submissions JSON
                # and later checked against CompanyFacts and original iXBRL.
                or type(filename) is not str or not _DOCUMENT.fullmatch(filename)
                or ".." in filename):
            _bad("UNSAFE_FILING_IDENTIFIER")
        report = recent["reportDate"][i]
        if report and _date(report) > filing:
            _bad("REPORT_DATE_AFTER_FILING")
        if form == "10-K/A":
            amendments.append((filing, report or None))
            continue
        eligible.append((filing, accession, filename, report or None))
    if not eligible:
        _bad("NO_10K_BEFORE_AS_OF_IN_RECENT_WINDOW")
    eligible.sort(key=lambda row: (row[0], row[1]), reverse=True)
    if len(eligible) > 1 and eligible[0][:2] == eligible[1][:2]:
        _bad("DUPLICATE_10K_IDENTITY")
    filing, accession, filename, report = eligible[0]
    # A subsequently filed same-year amendment may change the financial
    # facts or evidence. This four-source workflow holds the original rather
    # than silently treating an earlier 10-K as the newest reviewed evidence.
    # Unknown report dates are ambiguous and also require human review.
    if any(amended_date >= filing and (
            amendment_report is None or report is None
            or amendment_report == report)
            for amended_date, amendment_report in amendments):
        _bad("10K_AMENDMENT_REVIEW_REQUIRED")
    original = (f"{SEC_ARCHIVE}/{int(issuer)}/"
                f"{accession.replace('-', '')}/{filename}")
    return {"form": "10-K", "accession": accession, "filing_date": filing.isoformat(),
            "report_date": report, "original_filing_url": original,
            "issuer_cik": issuer,
            # This prefix is NOT an issuer validation or independent agent
            # identity proof. Keep the two identities explicit for reviewers.
            "accession_submitter_cik_from_identifier": accession[:10],
            "accession_prefix_matches_issuer": accession[:10] == issuer,
            "submissions_sha256": sha256(raw).hexdigest(),
            "point_in_time_verified": False, "original_authenticated": False}


def build_ticker_source_plan(*, ticker: str, ticker_map: bytes,
                             submissions: bytes | None = None,
                             as_of: str | None = None) -> dict:
    """Read-only preflight. Never upgrades a source plan to live financial facts."""
    result = {"schema": "kuodra.single-ticker-source-plan.v1",
              "status": "unavailable", "reason_code": None,
              "network_requests": 0, "live_data_retrieved": False,
              "source_authenticated": False, "source_rights_verified": False,
              "point_in_time_verified": False, "full_a_b_c_ready": False,
              "ai_interpretation_ready": False, "trade_executed": False}
    try:
        company = resolve_sec_ticker(ticker_map, ticker)
        if submissions is not None and as_of is None:
            _bad("AS_OF_REQUIRED")
        if as_of is not None:
            _date(as_of)
        cik = company["cik"]
        result.update(company)
        result.update({"status": "source_plan_only_unverified",
                       "as_of_requested": as_of,
                       "sec_submissions_url": f"{SEC_API}/submissions/CIK{cik}.json",
                       "sec_companyfacts_url":
                       f"{SEC_API}/api/xbrl/companyfacts/CIK{cik}.json",
                       "latest_10k": None,
                       "reason_code": "SUBMISSIONS_NOT_SUPPLIED"
                       if submissions is None else None})
        if submissions is not None:
            result["latest_10k"] = select_sec_10k(submissions, cik=cik, as_of=as_of)
            result["status"] = "10k_source_plan_unverified"
        return result
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        # Never return a partial successful CIK or unverified source URL on
        # integrity failure; callers must fail closed and reselect the file.
        return {k: v for k, v in result.items()
                if k in {"schema", "network_requests", "live_data_retrieved",
                         "source_authenticated", "source_rights_verified",
                         "point_in_time_verified", "full_a_b_c_ready",
                         "ai_interpretation_ready", "trade_executed"}} | {
                         "status": "unavailable", "reason_code": str(error)[:90]}


def _read_bounded(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        return handle.read(maximum + 1)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="KUODRA offline ticker/SEC source plan; NO HTTP")
    p.add_argument("--ticker", required=True)
    p.add_argument("--ticker-map", type=Path, required=True)
    p.add_argument("--submissions", type=Path)
    p.add_argument("--as-of")
    args = p.parse_args(argv)
    try:
        result = build_ticker_source_plan(
            ticker=args.ticker,
            ticker_map=_read_bounded(args.ticker_map, MAX_MAP_BYTES),
            submissions=_read_bounded(args.submissions, MAX_SUBMISSIONS_BYTES)
            if args.submissions else None,
            as_of=args.as_of,
        )
    except (OSError, ValueError, TypeError):
        result = {"schema": "kuodra.single-ticker-source-plan.v1",
                  "status": "unavailable", "reason_code": "LOCAL_INPUT_UNAVAILABLE",
                  "network_requests": 0, "live_data_retrieved": False,
                  "source_authenticated": False}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["status"] != "unavailable" else 2


if __name__ == "__main__":
    raise SystemExit(main())
