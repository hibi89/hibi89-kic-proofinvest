"""P209: independent NVIDIA official FY2026 issuer financial statement one-shot.

A second *issuer* distinct from Dell. Read-only one bounded NVIDIA IR HTML GET.
Strictly distinguish three-month figures from twelve-month figures, issuer
GAAP condensed statements vs non-GAAP summary, as-of and balance-sheet year.
Never assert SEC raw byte identity, commercial/AI rights, market index, peers,
autonomous judgment or trading approval.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Any, Callable
from urllib.request import Request, HTTPRedirectHandler, build_opener

_URL = ("https://investor.nvidia.com/news/press-release-details/2026/"
        "NVIDIA-Announces-Financial-Results-for-Fourth-Quarter-and-Fiscal-2026/")
_MAX = 3_000_000
_EXPECTED = {
    "revenue": (68127, 39331, 215938, 130497),
    "net_income": (42960, 22091, 120067, 72880),
    "cash_from_operations": (36190, 16628, 102718, 64089),
    "trade_receivables": (38466, 23065),
    "inventories": (21403, 10080),
    "current_assets": (125605, 80126),
}


def _compact(value: str) -> str:
    return " ".join(value.replace("\u200b", "").split()).strip()


class _Tables(HTMLParser):
    """Only table-cell positions, never uncontrolled global text/number search."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, Any]] = []
        self.tables: list[list[list[str]]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.stack.append({"rows": [], "row": None, "cell": None})
        elif self.stack and tag == "tr":
            self.stack[-1]["row"] = []
        elif self.stack and tag in ("td", "th") and self.stack[-1]["row"] is not None:
            self.stack[-1]["cell"] = []

    def handle_data(self, value):
        if self.stack and self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"].append(value)

    def handle_endtag(self, tag):
        if not self.stack:
            return
        top = self.stack[-1]
        if tag in ("td", "th") and top["cell"] is not None:
            if top["row"] is not None:
                top["row"].append(_compact(" ".join(top["cell"])))
            top["cell"] = None
        elif tag == "tr" and top["row"] is not None:
            top["rows"].append(top["row"])
            top["row"] = None
        elif tag == "table":
            finished = self.stack.pop()["rows"]
            if finished:
                self.tables.append(finished)


def _amounts(cells: list[str], count: int) -> tuple[int, ...] | None:
    """Reject negatives, decimals and fragmented digits instead of guessing."""
    values = []
    for raw in cells:
        v = _compact(raw)
        if re.fullmatch(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)", v):
            values.append(int(v.replace(",", "")))
        elif v in ("", "$", "—", "-"):
            continue
        else:
            return None
    if len(values) != count:
        return None
    return tuple(values)


def _find(table: list[list[str]], label: str, count: int) -> tuple[int, ...] | None:
    seen: list[tuple[int, ...]] = []
    for row in table:
        for idx, cell in enumerate(row):
            if _compact(cell).casefold().strip(":") == label:
                values = _amounts(row[idx + 1:], count)
                if values is None:
                    raise ValueError("NVIDIA_STATEMENT_ROW_OR_COLUMN_LAYOUT_CHANGED")
                seen.append(values)
    if len(seen) != 1:
        return None
    return seen[0]


def _unique(tables: list[list[list[str]]], *, required: tuple[str, ...],
            labels: dict[str, tuple[str, int]]) -> dict[str, tuple[int, ...]]:
    matches = []
    for table in tables:
        joined = " ".join(" ".join(row) for row in table).casefold()
        if not all(token in joined for token in required):
            continue
        rows = {}
        for key, (label, count) in labels.items():
            found = _find(table, label, count)
            if found is None:
                break
            rows[key] = found
        if len(rows) == len(labels):
            matches.append(rows)
    if len(matches) != 1:
        raise ValueError("NVIDIA_GAAP_STATEMENT_TABLE_NOT_UNIQUE")
    return matches[0]


def _pct(a: int, b: int) -> str:
    if b <= 0:
        raise ValueError("NVIDIA_ZERO_BASELINE")
    return str(((Decimal(a) / Decimal(b) - 1) * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_nvidia_official_fy2026(raw: bytes) -> dict[str, Any]:
    """Parse strict issuer annual vs quarterly values directly from table cells."""
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX:
        raise ValueError("NVIDIA_ORIGINAL_BYTES_INVALID")
    html = raw.decode("utf-8")
    if not all(x in html.casefold() for x in (
        "nvidia", "february 25, 2026", "fiscal 2026", "2025")):
        raise ValueError("NVIDIA_ISSUER_RELEASE_IDENTITY_INVALID")
    parser = _Tables()
    parser.feed(html)
    anchors = ("three months ended", "twelve months ended", "january 25", "january 26", "2026", "2025")
    income = _unique(parser.tables, required=anchors + ("gross profit", "cost of revenue"),
                     labels={"revenue": ("revenue", 4), "net_income": ("net income", 4)})
    cashflow = _unique(parser.tables,
                       required=anchors + ("cash flows from operating activities",
                                           "net cash provided by operating activities"),
                       labels={"net_income": ("net income", 4),
                               "cash_from_operations": ("net cash provided by operating activities", 4)})
    balance = _unique(parser.tables, required=("january 25", "january 26",
                                               "2026", "2025", "total current assets",
                                               "accounts receivable, net"),
                      labels={"trade_receivables": ("accounts receivable, net", 2),
                              "inventories": ("inventories", 2),
                              "current_assets": ("total current assets", 2)})
    combined = {**income, "cash_from_operations": cashflow["cash_from_operations"], **balance}
    if cashflow["net_income"] != income["net_income"]:
        raise ValueError("NVIDIA_INCOME_CASHFLOW_NET_INCOME_CONFLICT")
    if combined != _EXPECTED:
        raise ValueError("NVIDIA_OFFICIAL_GAAP_FY_FIGURES_CONFLICT")
    revenue_growth = _pct(income["revenue"][2], income["revenue"][3])
    ar_growth = _pct(balance["trade_receivables"][0], balance["trade_receivables"][1])
    inv_growth = _pct(balance["inventories"][0], balance["inventories"][1])
    cfo_now = cashflow["cash_from_operations"][2]
    net_now = income["net_income"][2]
    return {
        "issuer": "NVIDIA CORPORATION", "ticker": "NVDA", "cik": "0001045810",
        "fy2026_end": "2026-01-25", "fy2025_end": "2025-01-26",
        "release_date": "2026-02-25", "unit": "USD_millions",
        "release_is_unaudited": True,
        "income": {
            "q4_2026_revenue": str(income["revenue"][0]),
            "q4_2025_revenue": str(income["revenue"][1]),
            "fy2026_revenue": str(income["revenue"][2]),
            "fy2025_revenue": str(income["revenue"][3]),
            "fy2026_net_income": str(net_now),
            "fy2025_net_income": str(income["net_income"][3]),
        },
        "cash": {
            "fy2026_cash_from_operations": str(cfo_now),
            "fy2025_cash_from_operations": str(cashflow["cash_from_operations"][3]),
            "fy2026_cash_to_net_income": str(
                (Decimal(cfo_now) / Decimal(net_now)).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        },
        "balance_sheet": {
            key: {"fy2026": str(balance[key][0]), "fy2025": str(balance[key][1]),
                  "yoy_growth_pct": _pct(*balance[key])}
            for key in ("trade_receivables", "inventories", "current_assets")
        },
        "revenue_growth_pct": revenue_growth,
        "ar_minus_revenue_pp": str(
            (Decimal(ar_growth) - Decimal(revenue_growth)).quantize(Decimal("0.01"))),
        "inventory_minus_revenue_pp": str(
            (Decimal(inv_growth) - Decimal(revenue_growth)).quantize(Decimal("0.01"))),
        "signal": "HUMAN_ONLY_INDUSTRY_SOURCE_SCREEN",
        "misconduct_proven": False, "trading_action": None,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _open(req):
    return build_opener(_NoRedirect()).open(req, timeout=15)


def nvidia_issuer_one_shot(*, open_once: Callable | None = None) -> dict[str, Any]:
    out = {
        "schema": "kuodra.p209-nvda-official-issuer-financial-facts.v1",
        "status": "BLOCKED", "reason_code": "NOT_ATTEMPTED",
        "issuer": "NVDA", "source_url": _URL,
        "source_sha256": None, "source_bytes": None,
        "facts": None, "issuer_real_original_fy_facts_verified": False,
        "http_get_attempted": 0, "http_get_budget": 1,
        "sec_http_calls": 0, "provider_market_calls": 0,
        "redirects_followed": 0, "raw_saved": False, "raw_uploaded": False,
        "sec_original_byte_identical": False,
        "data_commercial_llm_rights_verified": False,
        "real_stock_ndx_peer_licensed": False,
        "full_abc_ready": False, "guard_policy_preview": "HOLD",
        "trade_executed": False,
    }
    req = Request(_URL, method="GET", headers={
        "User-Agent": "KUODRA-P209-PublicNVDAReadOnly/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity",
    })
    try:
        out["http_get_attempted"] = 1
        with (open_once or _open)(req) as response:
            if response.status != 200 or response.geturl() != _URL:
                raise ValueError("NVIDIA_ISSUER_ORIGIN_STATUS_CHANGED")
            if response.headers.get("Content-Type", "").lower().split(";")[0].strip() != "text/html":
                raise ValueError("NVIDIA_ISSUER_CONTENT_TYPE_INVALID")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("NVIDIA_ISSUER_ENCODING_INVALID")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdigit() or not 0 < int(length) <= _MAX):
                raise ValueError("NVIDIA_ISSUER_DECLARED_SIZE_INVALID")
            raw = response.read(_MAX + 1)
            if not 0 < len(raw) <= _MAX or length is not None and len(raw) != int(length):
                raise ValueError("NVIDIA_ISSUER_ORIGINAL_SIZE_INVALID")
        facts = parse_nvidia_official_fy2026(raw)
        out.update(
            status="NVDA_REAL_ISSUER_FY2026_2025_GAAP_FINANCIALS_CONFIRMED_LIMITED",
            reason_code="SOURCE_ISSUER_UNAUDITED_GAAP_NOT_SEC_EDGAR_OR_RIGHTS",
            source_sha256=sha256(raw).hexdigest(), source_bytes=len(raw),
            facts=facts, issuer_real_original_fy_facts_verified=True,
        )
    except (UnicodeError, ValueError, OSError, TypeError, RecursionError, OverflowError) as exc:
        reason = str(exc)
        out["reason_code"] = (
            reason if re.fullmatch(r"[A-Z0-9_]{3,90}", reason)
            else "NVIDIA_ISSUER_FETCH_OR_PARSE_FAILED")
    return out


def main() -> int:
    result = nvidia_issuer_one_shot()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["issuer_real_original_fy_facts_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
