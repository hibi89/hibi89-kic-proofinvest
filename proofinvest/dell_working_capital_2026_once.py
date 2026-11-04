"""P207 actual Dell first-party FY2026 working-capital Engine B precondition.

Uses the previously P206-verified unaudited issuer release as a STRICT pinned
version; compares inventory and trade receivables with P195 issuer 10-K revenue.
This is a screening divergence, not accounting misconduct, source rights,
SEC-original equivalence, full licensed financial E2E, or trading advice.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Any, Callable
from urllib.request import Request

from .dell_earnings_release_2026_once import (
    _URL, _MAX, _Tables, _norm, _open, parse_dell_public_fy2026_release,
)
from .dell_2026_publisher_evidence import (
    actual_p195_source_receipt, review_verified_dell_first_party_raw_evidence,
)

_P206_SHA = "ac80c82b0ca59f3ed1b6fd44a3bf68accd48bcb9a13484cb8aa60ad0db98b3d7"
_P206_LENGTH = 594207
_P195_SHA = "c48524018e82710057f6ef7cb27b665c4c7f4a39b65b02973417de0d68a5a4ac"
_KNOWN = {
    "trade_receivables": (17585, 10298),
    "inventories": (10437, 6716),
    "current_assets": (57602, 36229),
}
_HEADERS = ("january 30", "2026", "january 31", "2025")


def _pair(cells: list[str]) -> tuple[int, int] | None:
    vals: list[int] = []
    for cell in cells:
        item = _norm(cell).replace("\u200b", "").replace("\xa0", "")
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d+", item):
            vals.append(int(item.replace(",", "")))
        elif item and item not in ("$", "—", "-", "\u2014"):
            return None
    return (vals[0], vals[1]) if len(vals) == 2 else None


def parse_issuer_working_capital_release(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX:
        raise ValueError("WORKING_CAPITAL_RELEASE_SIZE_INVALID")
    source = raw.decode("utf-8")
    if "dell technologies" not in source.lower() or "2026" not in source:
        raise ValueError("WORKING_CAPITAL_ISSUER_OR_YEAR_INVALID")
    p = _Tables()
    p.feed(source)
    candidates = []
    for table in p.tables:
        body = " ".join(" ".join(row) for row in table).casefold()
        if (not all(x in body for x in _HEADERS)
                or "accounts receivable, net of allowance" not in body
                or "inventories" not in body or "total current assets" not in body):
            continue
        if body.index("january 30") >= body.index("january 31"):
            raise ValueError("WORKING_CAPITAL_FISCAL_HEADER_ORDER_CHANGED")
        values: dict[str, tuple[int, int]] = {}
        for row in table:
            if not row:
                continue
            label = _norm(row[0]).casefold()
            key = None
            if label.startswith("accounts receivable, net of allowance"):
                key = "trade_receivables"  # excludes financing receivables
            elif label == "inventories":
                key = "inventories"
            elif label == "total current assets":
                key = "current_assets"
            if key is not None:
                pair = _pair(row[1:])
                if pair is None or key in values:
                    raise ValueError("WORKING_CAPITAL_ROW_AMBIGUOUS")
                values[key] = pair
        if set(values) == set(_KNOWN):
            candidates.append(values)
    if len(candidates) != 1:
        raise ValueError("WORKING_CAPITAL_UNIQUE_BALANCE_SHEET_NOT_FOUND")
    found = candidates[0]
    if found != _KNOWN:
        raise ValueError("WORKING_CAPITAL_ACTUAL_PRIMARY_NUMERIC_CONFLICT")

    p195 = review_verified_dell_first_party_raw_evidence(
        as_of="2026-11-05", receipt=actual_p195_source_receipt()
    )
    e = p195.get("evidence")
    if (p195.get("status") != "DELL_REAL_FIRST_PARTY_ORIGINAL_NUMERIC_REVIEW_READY_LIMITED"
            or type(e) is not dict
            or e.get("raw_original_bytes_sha256") != _P195_SHA
            or e.get("fiscal_year_end") != "2026-01-30"
            or e.get("prior_year_end") != "2025-01-31"
            or e.get("revenue_2026_usd_millions") != "113538"
            or e.get("revenue_2025_usd_millions") != "95567"):
        raise ValueError("WORKING_CAPITAL_P195_REVENUE_SOURCE_UNVERIFIED")

    # The previous actual P206 independently verified that the release's
    # annual cash flow/income are distinct from its fourth-quarter values.
    financial = parse_dell_public_fy2026_release(raw)
    if (financial["release_is_unaudited"] is not True
            or financial["fy2026_end"] != "2026-01-30"
            or financial["fy2025_end"] != "2025-01-31"):
        raise ValueError("WORKING_CAPITAL_SOURCE_PERIOD_MISMATCH")
    revenue_growth = ((Decimal(113538) / Decimal(95567) - 1) * 100)
    result = {}
    for key, (current, prior) in found.items():
        yoy = (Decimal(current) / Decimal(prior) - 1) * 100
        result[key] = {
            "fy2026_usd_millions": str(current),
            "fy2025_usd_millions": str(prior),
            "growth_pct": str(yoy.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "growth_minus_revenue_pp": str(
                (yoy - revenue_growth).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            ),
        }
    return {
        "issuer": "DELL", "fiscal_2026_end": "2026-01-30",
        "fiscal_2025_end": "2025-01-31",
        "unit": "USD_millions", "source_is_unaudited": True,
        "source_10k_2026_sha256": _P195_SHA,
        "revenue_growth_pct": str(revenue_growth.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "working_capital": result,
        "human_only_signal": "AR_AND_INVENTORY_GROWTH_ABOVE_REVENUE_NEEDS_CONTEXT",
        "misconduct_proven": False, "trade_action": None,
    }


def verify_dell_working_capital_once(*, opener: Callable | None = None) -> dict:
    result = {
        "schema": "kuodra.p207-first-party-working-capital.v1",
        "status": "BLOCKED", "reason_code": "NOT_ATTEMPTED",
        "issuer": "DELL", "source_url": _URL,
        "http_get_attempted": 0, "http_get_budget": 1,
        "sec_http_calls": 0, "paid_calls": 0, "redirects_followed": 0,
        "raw_saved": False, "raw_uploaded": False,
        "source_sha256": None, "source_bytes": None, "facts": None,
        "issuer_working_capital_fy_original_verified": False,
        "sec_edgar_original_byte_identity": False,
        "source_commercial_ai_rights_verified": False,
        "licensed_stock_ndx_peers": False,
        "full_engine_b_complete": False, "full_abc_ready": False,
        "guard_policy_preview": "HOLD", "trade_executed": False,
    }
    req = Request(_URL, method="GET", headers={
        "User-Agent": "KUODRA-P207-ReadOnlyPublicIssuer/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity",
    })
    try:
        result["http_get_attempted"] = 1
        with (opener or _open)(req) as r:
            if r.status != 200 or r.geturl() != _URL:
                raise ValueError("WORKING_CAPITAL_ORIGIN_OR_STATUS_CHANGED")
            if r.headers.get("Content-Type", "").split(";")[0].lower() != "text/html":
                raise ValueError("WORKING_CAPITAL_NONHTML_RESPONSE")
            if r.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("WORKING_CAPITAL_CONTENT_ENCODING_REJECTED")
            declared = r.headers.get("Content-Length")
            if declared is not None and (not declared.isdigit() or not 0 < int(declared) <= _MAX):
                raise ValueError("WORKING_CAPITAL_DECLARED_SIZE_REJECTED")
            raw = r.read(_MAX + 1)
            if (not 0 < len(raw) <= _MAX
                    or declared is not None and len(raw) != int(declared)):
                raise ValueError("WORKING_CAPITAL_RECEIVED_SIZE_REJECTED")
        digest = sha256(raw).hexdigest()
        # Publisher HTML chrome can change while original financial tables
        # remain unchanged. Never claim P206 byte-identical unless exact.
        result["p206_prior_raw_byte_identical"] = (
            digest == _P206_SHA and len(raw) == _P206_LENGTH
        )
        facts = parse_issuer_working_capital_release(raw)
        result.update(
            status="REAL_DELL_FY_WORKING_CAPITAL_PUBLIC_ORIGINAL_CONFIRMED_LIMITED",
            reason_code="REAL_UNAUDITED_ASSETS_VS_REVENUE_SCREENING_ONLY",
            source_sha256=digest, source_bytes=len(raw), facts=facts,
            issuer_working_capital_fy_original_verified=True,
        )
    except (ValueError, OSError, UnicodeError, OverflowError, TypeError, RecursionError) as error:
        reason = str(error)
        result["reason_code"] = (reason if re.fullmatch(r"[A-Z0-9_]{3,90}", reason)
                                 else "WORKING_CAPITAL_SOURCE_OR_PARSE_FAILED")
    return result


def main() -> int:
    result = verify_dell_working_capital_once()
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if result["issuer_working_capital_fy_original_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
