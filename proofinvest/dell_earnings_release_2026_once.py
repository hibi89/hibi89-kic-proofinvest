"""P206: separate Dell FY2026 first-party (unaudited) results release vs real P195 10-K.

One bounded HTTPS GET; no SEC.gov, redirects, retries, raw persistence, AI,
market/index data, license inference, Guard approval or trades.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Any, Callable
from urllib.request import HTTPRedirectHandler, Request, build_opener

_URL = ("https://investors.delltechnologies.com/news-events/press-releases/"
        "detail/93/dell-technologies-delivers-fourth-quarter-and-full-year-fiscal-2026-results")
_MAX = 2_000_000
_P195_SHA = "c48524018e82710057f6ef7cb27b665c4c7f4a39b65b02973417de0d68a5a4ac"
_EXPECTED = {
    "net_income": (2259, 1532, 5936, 4576),
    "operating_cash_flow": (4674, 585, 11185, 4521),
}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _open(req):
    return build_opener(_NoRedirect()).open(req, timeout=12)


def _norm(value: str) -> str:
    return " ".join(value.split()).strip()


class _Tables(HTMLParser):
    """Read cash-flow table cell boundaries; avoid arbitrary text-match claims."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.table = []
        elif self.depth == 1 and tag == "tr":
            self.row = []
        elif self.depth == 1 and self.row is not None and tag in ("th", "td"):
            self.cell = []

    def handle_data(self, text):
        if self.depth == 1 and self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self.depth == 1 and self.cell is not None:
            if self.row is not None:
                self.row.append(_norm(" ".join(self.cell)))
            self.cell = None
        elif tag == "tr" and self.depth == 1 and self.row is not None:
            if self.table is not None:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.depth:
            if self.depth == 1 and self.table is not None:
                self.tables.append(self.table)
                self.table = None
            self.depth -= 1


def _amounts(row: list[str]) -> tuple[int, int, int, int] | None:
    values = []
    for cell in row[1:]:
        t = _norm(cell).replace("\u200b", "")
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d+", t):
            values.append(int(t.replace(",", "")))
        elif re.fullmatch(r"\(\s*\d{1,3}(?:,\d{3})+\s*\)", t):
            values.append(-int(re.sub(r"[^0-9]", "", t)))
    return tuple(values) if len(values) == 4 else None


def parse_dell_public_fy2026_release(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX:
        raise ValueError("PUBLIC_RELEASE_BYTES_INVALID")
    text = raw.decode("utf-8")
    if not all(x in text.lower() for x in ("dell technologies", "2026", "2025")):
        raise ValueError("PUBLIC_RELEASE_ISSUER_PERIOD_MISSING")
    parser = _Tables()
    parser.feed(text)
    matched = []
    for table in parser.tables:
        body = " ".join(" ".join(row) for row in table).lower()
        if ("fiscal year ended" not in body or "three months ended" not in body
                or "cash flows from operating activities" not in body
                or "january 30" not in body or "january 31" not in body):
            continue
        rows = {}
        for row in table:
            if not row:
                continue
            label = _norm(row[0]).casefold().strip(":")
            if label in ("net income", "change in cash from operating activities"):
                key = "net_income" if label == "net income" else "operating_cash_flow"
                values = _amounts(row)
                if values is None or key in rows:
                    raise ValueError("PUBLIC_RELEASE_CASHFLOW_ROW_AMBIGUOUS")
                rows[key] = values
        if set(rows) == set(_EXPECTED):
            matched.append(rows)
    if len(matched) != 1:
        raise ValueError("PUBLIC_RELEASE_SINGLE_CASHFLOW_TABLE_NOT_FOUND")
    rows = matched[0]
    if any(rows[k] != v for k, v in _EXPECTED.items()):
        raise ValueError("PUBLIC_RELEASE_FY_VALUES_CONFLICT")
    net, cash = Decimal(rows["net_income"][2]), Decimal(rows["operating_cash_flow"][2])
    last_net, last_cash = Decimal(rows["net_income"][3]), Decimal(rows["operating_cash_flow"][3])
    return {
        "fy2026_end": "2026-01-30", "fy2025_end": "2025-01-31",
        "currency": "USD", "unit": "millions", "release_is_unaudited": True,
        "q4_2026_net_income": str(rows["net_income"][0]),
        "q4_2025_net_income": str(rows["net_income"][1]),
        "fy2026_net_income": str(net), "fy2025_net_income": str(last_net),
        "q4_2026_cash_from_operations": str(rows["operating_cash_flow"][0]),
        "q4_2025_cash_from_operations": str(rows["operating_cash_flow"][1]),
        "fy2026_cash_from_operations": str(cash),
        "fy2025_cash_from_operations": str(last_cash),
        "fy2026_cfo_to_net_income": str((cash / net).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "fy2025_cfo_to_net_income": str((last_cash / last_net).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "fy2026_cash_minus_net_income": str(cash-net),
        "fy2025_cash_minus_net_income": str(last_cash-last_net),
    }


def _match_p195(facts: dict[str, Any]) -> None:
    """Only accept second source if it matches prior independently run real issuer original."""
    from .dell_2026_publisher_evidence import (
        actual_p195_source_receipt, review_verified_dell_first_party_raw_evidence,
    )
    result = review_verified_dell_first_party_raw_evidence(
        as_of="2026-11-05", receipt=actual_p195_source_receipt())
    evidence = result.get("evidence")
    if (result.get("status") != "DELL_REAL_FIRST_PARTY_ORIGINAL_NUMERIC_REVIEW_READY_LIMITED"
            or not isinstance(evidence, dict)
            or evidence.get("raw_original_bytes_sha256") != _P195_SHA
            or evidence.get("ticker") != "DELL"
            or evidence.get("fiscal_year_end") != facts["fy2026_end"]
            or evidence.get("prior_year_end") != facts["fy2025_end"]
            or evidence.get("operating_cash_flow_2026_usd_millions") != facts["fy2026_cash_from_operations"]
            or evidence.get("net_income_2026_usd_millions") != facts["fy2026_net_income"]
            or evidence.get("cash_flow_to_net_income_ratio") != facts["fy2026_cfo_to_net_income"]):
        raise ValueError("INDEPENDENT_RELEASE_AND_REAL_10K_FACTS_CONFLICT")


def verify_dell_release_once(*, opener: Callable | None = None) -> dict:
    result = {
        "schema": "kuodra.p206-second-issuer-earnings-release.v1",
        "status": "BLOCKED", "reason_code": "NOT_ATTEMPTED",
        "source_url": _URL, "issuer": "DELL", "http_get_budget": 1,
        "http_get_attempted": 0, "sec_http_calls": 0, "paid_calls": 0,
        "redirects_followed": 0, "raw_saved": False, "raw_uploaded": False,
        "source_sha256": None, "source_bytes": None, "facts": None,
        "separate_issuer_primary_source_matched": False,
        "publisher_10k_sha256_reference": _P195_SHA,
        "issuer_sec_original_bytes_identical": False,
        "source_license_commercial_ai_verified": False,
        "licensed_stock_ndx_peers": False, "full_engine_b_complete": False,
        "full_abc_ready": False, "guard_policy_preview": "HOLD", "trade_executed": False,
    }
    req = Request(_URL, headers={
        "User-Agent": "KUODRA-P206-PublicIssuerReadOnly/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity",
    }, method="GET")
    try:
        result["http_get_attempted"] = 1
        with (opener or _open)(req) as response:
            if response.status != 200 or response.geturl() != _URL:
                raise ValueError("PUBLIC_RELEASE_ORIGIN_STATUS_CHANGED")
            if response.headers.get("Content-Type", "").split(";")[0].lower() != "text/html":
                raise ValueError("PUBLIC_RELEASE_CONTENT_TYPE_INVALID")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("PUBLIC_RELEASE_ENCODING_INVALID")
            raw = response.read(_MAX + 1)
            stated = response.headers.get("Content-Length")
            if (not 0 < len(raw) <= _MAX or stated and
                    (not stated.isdigit() or int(stated) != len(raw))):
                raise ValueError("PUBLIC_RELEASE_SIZE_INVALID")
        facts = parse_dell_public_fy2026_release(raw)
        _match_p195(facts)
        result.update(
            status="REAL_SECOND_ISSUER_RELEASE_FY_CFO_NI_CROSSCHECKED_LIMITED",
            reason_code="UNAUDITED_RELEASE_COMPARED_TO_PRIOR_REAL_10K_RECEIPT",
            source_sha256=sha256(raw).hexdigest(), source_bytes=len(raw),
            facts=facts, separate_issuer_primary_source_matched=True,
        )
    except (OSError, ValueError, UnicodeError, TypeError, OverflowError, RecursionError) as error:
        reason = str(error)
        result["reason_code"] = reason if re.fullmatch(r"[A-Z0-9_]{3,90}", reason) else "PUBLIC_RELEASE_FETCH_OR_PARSE_FAILED"
    return result


def main() -> int:
    result = verify_dell_release_once()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["separate_issuer_primary_source_matched"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
