"""P201 actual Dell publisher 2026 iXBRL DEI identity -> official SEC index meta.

ONE bounded Dell firstparty GET, no SEC HTTP/API/retries/paid/proprietary
market sources and no body saved. This validates document/ticker identity
metadata, NOT SEC EDGAR byte equivalence, SEC-source copyright or AI rights.
"""
from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
from datetime import datetime
import json
import re
from typing import Any, Callable
from urllib.request import Request

from .dell_issuer_2026_10k_once import _URL, _MAX_HTML, _check_report_html, _open

_KNOWN_SHA = "c48524018e82710057f6ef7cb27b665c4c7f4a39b65b02973417de0d68a5a4ac"
_KNOWN_BYTES = 3610307
# SEC official public EDGAR filing index metadata (public search/document index):
# https://www.sec.gov/Archives/edgar/data/1571996/
# 000157199626000008/0001571996-26-000008-index.htm
_SEC_META = {
    "cik": "0001571996", "accession": "0001571996-26-000008",
    "fiscal_end": "2026-01-30", "form": "10-K",
    "issuer": "Dell Technologies Inc.", "filed": "2026-03-16",
}
_REQUIRED_DEI = {
    "dei:entitycentralindexkey", "dei:entityregistrantname",
    "dei:documenttype", "dei:documentperiodenddate",
    "dei:documentfiscalyearfocus", "dei:documentfiscalperiodfocus",
}


class _DeiParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, str]] = []
        self.facts: dict[str, list[str]] = {}

    def handle_starttag(self, tag, attrs):
        if tag != "ix:nonnumeric":
            return
        d = dict(attrs)
        if len(self.stack) >= 12:
            raise ValueError("DOCUMENT_IDENTITY_DEI_DEPTH_BLOCKED")
        name = d.get("name", "").lower()
        self.stack.append({"name": name, "text": ""})

    def handle_data(self, data):
        if self.stack:
            fact = self.stack[-1]
            if len(fact["text"]) + len(data) > 400:
                raise ValueError("DOCUMENT_IDENTITY_DEI_TEXT_TOO_LONG")
            fact["text"] += data

    def handle_endtag(self, tag):
        if tag != "ix:nonnumeric":
            return
        if not self.stack:
            raise ValueError("DEI_TAG_UNEXPECTED_CLOSE")
        fact = self.stack.pop()
        if fact["name"] in _REQUIRED_DEI:
            if len(self.facts.get(fact["name"], [])) >= 20:
                raise ValueError("DEI_DUPLICATE_LIMIT")
            self.facts.setdefault(fact["name"], []).append(fact["text"].strip())


def _normal_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _date(value: str) -> str | None:
    value = re.sub(r"\s+", " ", value.strip())
    formats = ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y",
               "%m/%d/%Y", "%m/%d/%y", "%m/%d/%Y")
    for format_ in formats:
        try:
            return datetime.strptime(value, format_).date().isoformat()
        except ValueError:
            pass
    return None


def extract_dell_real_sec_document_identity(raw: bytes) -> dict[str, Any]:
    """Require exact actual source filename/facts; no inferred SEC raw bytes."""
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_HTML or not _check_report_html(raw):
        raise ValueError("FIRSTPARTY_ORIGINAL_FILE_OR_FILING_TEXT_INVALID")
    p = _DeiParser()
    p.feed(raw.decode("utf-8"))
    if set(p.facts) != _REQUIRED_DEI:
        raise ValueError("REQUIRED_DEI_DISCLOSURE_TAGS_MISSING")
    for key, entries in p.facts.items():
        if not entries:
            raise ValueError("EMPTY_DEI_FACT")
        if key == "dei:entitycentralindexkey":
            valid = all(v.isascii() and v.isdigit() and
                        v.zfill(10) == _SEC_META["cik"] for v in entries)
        elif key == "dei:entityregistrantname":
            valid = all(_normal_name(v) == _normal_name(_SEC_META["issuer"])
                        for v in entries)
        elif key == "dei:documenttype":
            valid = all(v.strip().upper() == "10-K" for v in entries)
        elif key == "dei:documentperiodenddate":
            valid = all(_date(v) == _SEC_META["fiscal_end"] for v in entries)
        elif key == "dei:documentfiscalyearfocus":
            valid = all(v.strip() == "2026" for v in entries)
        elif key == "dei:documentfiscalperiodfocus":
            valid = all(v.strip().upper() == "FY" for v in entries)
        else:
            raise ValueError("UNEXPECTED_DEI")
        if not valid:
            raise ValueError("DEI_" + key.split(":")[-1].upper() +
                             "_MISMATCH_WITH_PUBLIC_SEC_FILING_METADATA")
    return {
        "issuer": _SEC_META["issuer"], "cik": _SEC_META["cik"],
        "form": _SEC_META["form"], "accession_from_publisher_path": _SEC_META["accession"],
        "fiscal_end": _SEC_META["fiscal_end"],
        "filing_date_from_independent_sec_index": _SEC_META["filed"],
        "fiscal_year_focus": "2026", "fiscal_period_focus": "FY",
        "verified_dei_tag_types": len(_REQUIRED_DEI),
        "verified_dei_fact_occurrences": sum(len(v) for v in p.facts.values()),
        "sec_index_metadata_verified_in_source": True,
        "publisher_bytes_identical_to_sec_original": False,
    }


def verify_dell_real_source_identity_once(*, opener: Callable | None = None) -> dict:
    out = {
        "schema": "kuodra.p201-publisher-ixbrl-entity-binding.v1",
        "status": "BLOCKED", "reason_code": "PUBLISHER_SOURCE_REQUIRED",
        "source_url": _URL, "source_sha256": None, "source_bytes": None,
        "http_get_budget": 1, "http_get_attempted": 0,
        "sec_http_requests": 0, "paid_requests": 0, "redirects": 0,
        "issuer_identity_bound_to_sec_index_metadata": False,
        "issuer_original_bytes_authenticated_via_sec_edgar": False,
        "source_redistribution_ai_rights": False,
        "stock_ndx_licenses": False, "peer_license": False,
        "guard_policy_preview": "HOLD", "trade_executed": False,
        "raw_body_saved": False, "raw_body_uploaded": False,
        "identity": None,
    }
    request = Request(_URL, method="GET", headers={
        "User-Agent": "KUODRA-P201-PublisherIdentityOnly/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity"
    })
    try:
        out["http_get_attempted"] = 1
        with (opener or _open)(request) as response:
            if response.status != 200 or response.geturl() != _URL:
                raise ValueError("PUBLISHER_URL_OR_STATUS_CHANGED")
            if response.headers.get("Content-Type", "").split(";")[0].lower() not in (
                "text/html", "application/xhtml+xml"
            ) or response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("PUBLISHER_MIME_NOT_HTML")
            length = response.headers.get("Content-Length")
            if length and (not length.isdigit() or not 0 < int(length) <= _MAX_HTML):
                raise ValueError("SOURCE_LENGTH_INVALID")
            raw = response.read(_MAX_HTML + 1)
            if not 0 < len(raw) <= _MAX_HTML or (length and int(length) != len(raw)):
                raise ValueError("SOURCE_BYTES_INVALID")
        out["source_sha256"] = sha256(raw).hexdigest()
        out["source_bytes"] = len(raw)
        if out["source_sha256"] != _KNOWN_SHA or len(raw) != _KNOWN_BYTES:
            raise ValueError("SOURCE_VERSION_NOT_PREVIOUSLY_VERIFIED")
        out["identity"] = extract_dell_real_sec_document_identity(raw)
        out.update(status="REAL_PUBLISHER_DEI_SEC_INDEX_ISSUER_IDENTITY_RECONCILED",
                   reason_code="DEI_CIK_FORM_YEAR_METADATA_ONLY_NOT_SEC_ORIGINAL",
                   issuer_identity_bound_to_sec_index_metadata=True)
    except (OSError, TypeError, ValueError, UnicodeError, RecursionError) as e:
        value = str(e)
        out["reason_code"] = (value if re.fullmatch("[A-Z0-9_]{3,110}",value)
                              else "DEI_PUBLISHER_PARSE_OR_FETCH_FAILED")
        out["identity"] = None
    return out


def main() -> int:
    result = verify_dell_real_source_identity_once()
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if result["status"] == "REAL_PUBLISHER_DEI_SEC_INDEX_ISSUER_IDENTITY_RECONCILED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
