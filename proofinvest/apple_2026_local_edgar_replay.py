"""P237 offline check of an operator-held Apple FY2026 EDGAR 10-K HTML file.

A local file can establish bounded byte integrity, printed-form identity,
undimensioned iXBRL periods/units/numbers and a match to the official SEC
public index's published size. A locally supplied filename/bytes/claim or
unkeyed SHA cannot establish SEC TLS transport, *byte-identical original SEC
origin*, any commercial third-party rights, or a valid live GET. No network,
automatic SEC 403 retry, writes, original uploads, AI or trading occurs.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

from .apple_fy2026_public_filing_review import (
    public_2026_values, review_apple_2026_public_financials,
)
from .dell_real_ixbrl_2026_once import _Ix

_SCHEMA = "kuodra.p237-offline-aapl-2026-sec-filing-ixbrl.v1"
_INDEX = ("https://www.sec.gov/Archives/edgar/data/320193/"
          "000032019326000026/0000320193-26-000026-index.htm")
_DOC = ("https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019326000026/aapl-20260926.htm")
_NAME = "aapl-20260926.htm"
_SIZE = 1650003  # Official SEC EDGAR filing index: 2026-11-03 10-K seq 1
_FILING_DATE = "2026-11-03"
_PERIOD = "2026-09-26"
_AUDIT_AS_OF = "2026-11-05"
_CIK = "0000320193"
_ACC = "0000320193-26-000026"
_DURATIONS = {
    "2026": ("2025-09-28", "2026-09-26"),
    "2025": ("2024-09-29", "2025-09-27"),
}
_CONCEPTS = {
    "net_sales": (
        "us-gaap:revenues",
        "us-gaap:salesrevenuenet",
        "us-gaap:revenuefromcontractwithcustomerexcludingassessedtax",
        "us-gaap:revenuefromcontractwithcustomerincludingassessedtax",
    ),
    "net_income": ("us-gaap:netincomeloss",),
    "operating_cash_flow": ("us-gaap:netcashprovidedbyusedinoperatingactivities",),
}


class _AppleIx(_Ix):
    """Reuse the proven duration/ISO4217-unit iXBRL parser, plus dei facts."""
    def __init__(self):
        super().__init__()
        self.dei: dict[str, list[str]] = {}
        self._meta_stack: list[dict[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "ix:nonnumeric":
            d = dict(attrs)
            if len(self._meta_stack) >= 12:
                raise ValueError("DEI_NEST_LIMIT")
            self._meta_stack.append({
                "name": d.get("name", "").lower(), "text": "",
            })
        super().handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._meta_stack:
            top = self._meta_stack[-1]
            if len(top["text"]) + len(data) > 1024:
                raise ValueError("DEI_METADATA_TOO_LONG")
            top["text"] += data
        super().handle_data(data)

    def handle_endtag(self, tag):
        if tag == "ix:nonnumeric" and self._meta_stack:
            top = self._meta_stack.pop()
            if top["name"].startswith("dei:"):
                self.dei.setdefault(top["name"], []).append(
                    top["text"].strip())
        super().handle_endtag(tag)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "official_sec_index_reference": _INDEX,
        "expected_filing_reference": _DOC,
        "official_index_document_size": _SIZE,
        "local_bytes_verified_against_index_size": False,
        "local_ixbrl_issuer_period_fact_consistent": False,
        "transport_tls_sec_origin_authenticated": False,
        "sec_edgar_original_byte_identical_authenticated": False,
        "individual_original_sha256_published_by_sec": False,
        "sec_get_approved_or_executed": False,
        "sec_http_requests": 0, "remote_model_requests": 0,
        "user_original_uploaded_or_saved": False,
        "licensed_stock_ndx_peer_data": False,
        "source_commercial_or_ai_rights_verified": False,
        "full_abc_ready": False, "guard_policy_preview": "HOLD",
        "investment_advice": False, "trades": 0,
    }


def _canonical_period_end(value: Any) -> bool:
    # Public SEC Inline-XBRL can render the underlying DEI date using
    # ixt:datemonthdayyearen rather than ISO-8601 in HTML. Accept ONLY
    # a small enumerated list of English spellings for this ONE filed date;
    # never interpret an ambiguous free-form date or trust a client claim.
    if type(value) is not str or len(value) > 64:
        return False
    return value.strip().replace("\u00a0", " ") in {
        "2026-09-26", "September 26, 2026", "Sep 26, 2026",
        "Sep. 26, 2026", "Sept 26, 2026", "Sept. 26, 2026",
        "9/26/2026", "09/26/2026",
    }


def _money_millions(fact: dict, units: dict[str, list[str]]) -> Decimal | None:
    if units.get(fact.get("unit")) != ["iso4217:usd"]:
        return None
    if fact.get("sign") not in (None, "+"):
        return None
    number, scale = fact.get("text"), fact.get("scale")
    if (type(number) is not str or type(scale) is not str
            or not re.fullmatch(r"\s*(?:[0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\s*", number)
            or not re.fullmatch(r"[0-9]", scale)):
        return None
    try:
        return Decimal(number.strip().replace(",", "")) * (Decimal(10) ** int(scale)) / 1000000
    except (ValueError, InvalidOperation, OverflowError):
        return None


def verify_operator_apple_2026_edgar_html(
    raw: Any, *, filename: Any = _NAME, as_of: Any = _AUDIT_AS_OF,
) -> dict[str, Any]:
    """One bounded offline parse; no origin promotion from user-held bytes."""
    if (type(filename) is not str or filename != _NAME
            or type(as_of) is not str or as_of != _AUDIT_AS_OF):
        return _blocked("OFFICIAL_INDEX_FILENAME_OR_REVIEW_VINTAGE_MISMATCH")
    if type(raw) is not bytes or len(raw) != _SIZE:
        return _blocked("RAW_LOCAL_SOURCE_SIZE_DISAGREES_WITH_SEC_INDEX")
    # Reject known non-HTML response masquerades and UTF8 decoding failure.
    if b"\x00" in raw or not raw.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        return _blocked("LOCAL_FILE_NOT_SEC_10K_HTML_SHAPE")
    try:
        parser = _AppleIx()
        parser.feed(raw.decode("utf-8"))
        parser.close()
        meta = parser.dei
        actual_cik = meta.get("dei:entitycentralindexkey")
        if (type(actual_cik) is not list or len(actual_cik) != 1
                or not actual_cik[0].strip().isdecimal()
                or actual_cik[0].strip().zfill(10) != _CIK
                or meta.get("dei:documenttype") != ["10-K"]
                or meta.get("dei:documentfiscalyearfocus") != ["2026"]
                or type(meta.get("dei:documentperiodenddate")) is not list
                or len(meta["dei:documentperiodenddate"]) != 1
                or not _canonical_period_end(meta["dei:documentperiodenddate"][0])):
            return _blocked("INLINE_DEI_CIK_FORM_FISCAL_IDENTITY_MISMATCH")
        if not parser.contexts or not parser.units or not parser.facts:
            return _blocked("STRUCTURED_INLINE_XBRL_CONTEXTS_OR_FACTS_MISSING")
        expected = public_2026_values()
        counts = {}
        for year, (start, end) in _DURATIONS.items():
            for key, concepts in _CONCEPTS.items():
                amounts = []
                for fact in parser.facts:
                    ctx = parser.contexts.get(fact.get("ctx"))
                    if (ctx is None or ctx.get("segmented") is not False
                            or ctx.get("start") != start or ctx.get("end") != end
                            or fact.get("name") not in concepts):
                        continue
                    value = _money_millions(fact, parser.units)
                    if value is not None:
                        amounts.append(value)
                if not amounts or any(x != Decimal(expected[key][year]) for x in amounts):
                    return _blocked("CONSOLIDATED_DURATION_GAAP_VALUE_DISAGREES")
                counts[key + "_" + year] = len(amounts)
        reviewed = review_apple_2026_public_financials(
            ticker="AAPL", accession=_ACC, as_of=_AUDIT_AS_OF,
            values=expected,
        )
        if (reviewed.get("status") !=
                "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED"
                or reviewed.get("original_bytes_authenticated") is not False
                or reviewed.get("source_rights_verified") is not False
                or reviewed.get("public_filing_url") != _DOC
                or reviewed.get("guard_policy_preview") != "HOLD"
                or reviewed.get("trade_executed") is not False):
            return _blocked("INDEPENDENT_PUBLIC_FILING_NUMBER_REPLAY_FAILED")
        return {
            **_blocked("LOCAL_BYTES_AND_GAAP_FACTS_ONLY_NOT_SEC_TRANSPORT_PROOF"),
            "status": "LOCAL_SEC_2026_HTML_6_GAAP_FACTS_MATCH_UNAUTHENTICATED",
            "local_bytes_verified_against_index_size": True,
            "local_ixbrl_issuer_period_fact_consistent": True,
            "local_html_sha256": sha256(raw).hexdigest(),
            "local_html_size": len(raw),
            "filing_date_from_sec_index": _FILING_DATE,
            "annual_end_verified": _PERIOD,
            "fiscal_periods": {k: {"start": v[0], "end": v[1]}
                               for k, v in _DURATIONS.items()},
            "six_fact_names": sorted(counts),
            "six_undimensioned_fact_counts": counts,
            "operator_file_treated_as_unauthenticated": True,
        }
    except (ValueError, TypeError, KeyError, OverflowError, UnicodeError,
            RecursionError):
        return _blocked("LOCAL_IXBRL_PARSE_OR_REVIEW_FAILED_CLOSED")
