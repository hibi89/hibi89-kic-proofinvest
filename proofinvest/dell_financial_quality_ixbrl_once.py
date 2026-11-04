"""P200 real issuer-only Dell 2026/2025 CFO and GAAP NI Inline XBRL replay.

Exactly one source HTTPS GET, with no SEC.gov fetch, secrets, paid calls,
raw content storage, external AI, security bypass or stock/NDX assumptions.
Publisher TLS is not SEC EDGAR byte identity or redistribution license.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Any, Callable
from urllib.request import Request

from .dell_issuer_2026_10k_once import _URL, _MAX_HTML, _check_report_html, _open
from .dell_real_ixbrl_2026_once import _Ix, _PERIODS

_KNOWN_SHA = "c48524018e82710057f6ef7cb27b665c4c7f4a39b65b02973417de0d68a5a4ac"
_KNOWN_SIZE = 3610307
_CONCEPTS = {
    "net_income": frozenset({"us-gaap:netincomeloss"}),
    "operating_cash_flow": frozenset({
        "us-gaap:netcashprovidedbyusedinoperatingactivities"
    }),
}
_EXPECTED = {
    "FY2026": {"net_income": Decimal("5936"), "operating_cash_flow": Decimal("11185")},
    "FY2025": {"net_income": Decimal("4576"), "operating_cash_flow": Decimal("4521")},
}


def _amount(fact: dict, units: dict[str, list[str]]) -> Decimal | None:
    if units.get(fact.get("unit")) != ["iso4217:usd"] or fact.get("sign") not in (None, "+"):
        return None
    scale, text = fact.get("scale"), fact.get("text")
    if (type(scale) is not str or not re.fullmatch("[0-9]", scale)
            or type(text) is not str
            or not re.fullmatch(r"\d{1,3}(?:,\d{3})*|\d+", text.strip())):
        return None
    try:
        return Decimal(text.strip().replace(",", "")) * (Decimal(10) ** int(scale)) / 1000000
    except (ValueError, TypeError, InvalidOperation, OverflowError):
        return None


def extract_dell_real_cashflow_income_xbrl(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or len(raw) > _MAX_HTML or not _check_report_html(raw):
        raise ValueError("FIRSTPARTY_10K_VISIBLE_SOURCE_INCONSISTENT")
    p = _Ix()
    p.feed(raw.decode("utf-8"))
    if not p.contexts or not p.units or not p.facts:
        raise ValueError("ACTUAL_INLINE_XBRL_STRUCTURE_MISSING")
    output = {}
    for fy, (start, end, _revenue) in _PERIODS.items():
        out = {}
        for concept_kind, names in _CONCEPTS.items():
            candidates = []
            for fact in p.facts:
                if fact["name"] not in names:
                    continue
                ctx = p.contexts.get(fact["ctx"])
                if (ctx is None or ctx["segmented"] is not False
                        or ctx["start"] != start or ctx["end"] != end):
                    continue
                value = _amount(fact, p.units)
                if value is not None:
                    candidates.append((value, fact))
            if not candidates:
                raise ValueError(f"{fy}_{concept_kind.upper()}_USD_IXBRL_NOT_FOUND")
            if any(v != _EXPECTED[fy][concept_kind] for v, _ in candidates):
                raise ValueError(f"{fy}_{concept_kind.upper()}_USD_AMOUNT_CONFLICT")
            out[concept_kind] = {
                "amount_usd_millions": str(candidates[0][0]),
                "xbrl_concept": candidates[0][1]["name"],
                "context": candidates[0][1]["ctx"],
                "currency": "USD",
                "start": start, "end": end,
                "unsegmented_matching_facts": len(candidates),
            }
        output[fy] = out
    # Compute a financial-quality screening signal from XBRL facts only.
    for fy in output:
        net = Decimal(output[fy]["net_income"]["amount_usd_millions"])
        cash = Decimal(output[fy]["operating_cash_flow"]["amount_usd_millions"])
        if net <= 0 or cash <= 0:
            raise ValueError("CASH_QUALITY_RATIO_NONPOSITIVE")
        out = output[fy]
        out["cash_conversion_ratio"] = str((cash / net).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP))
        out["cash_minus_income_usd_millions"] = str(cash - net)
        out["human_only_signal"] = (
            "OPERATING_CASH_FLOW_ABOVE_NET_INCOME"
            if cash > net else "OPERATING_CASH_FLOW_NOT_ABOVE_NET_INCOME"
        )
    return output


def verify_dell_financial_quality_xbrl_once(*, opener: Callable | None = None) -> dict:
    out = {
        "schema": "kuodra.p200-real-issuer-financial-quality-ixbrl.v1",
        "status": "BLOCKED", "reason_code": "NO_PUBLISHER_SOURCE_YET",
        "issuer": "DELL", "official_issuer_url": _URL,
        "http_get_attempted": 0, "http_get_budget": 1,
        "sec_http_requests": 0, "redirects_followed": 0,
        "paid_requests": 0, "raw_file_persisted": False,
        "raw_file_uploaded": False,
        "original_sha256": None, "original_size": None,
        "source_publisher_https_verified": False,
        "real_annual_earnings_cashflow_xbrl_verified": False,
        "sec_edgar_original_byte_equivalence": False,
        "source_commercial_ai_rights_verified": False,
        "full_engine_b_authenticated": False,
        "price_ndx_peer_licenses_verified": False,
        "full_abc_agent_ready": False,
        "trade_executed": False, "guard_policy_preview": "HOLD",
        "financial_misconduct_proven": False, "xbrl_facts": None,
    }
    req = Request(_URL, method="GET", headers={
        "User-Agent": "KUODRA-P200-DellPublicOriginalOneShot/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity",
    })
    try:
        out["http_get_attempted"] = 1
        with (opener or _open)(req) as r:
            if r.status != 200 or r.geturl() != _URL:
                raise ValueError("ISSUER_HTTPS_SOURCE_OR_STATUS_CHANGED")
            if r.headers.get("Content-Type", "").split(";")[0].strip().lower() not in (
                "text/html", "application/xhtml+xml"
            ) or r.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("ISSUER_MIME_OR_ENCODING_REJECTED")
            length = r.headers.get("Content-Length")
            if length and (not length.isdigit() or not 0 < int(length) <= _MAX_HTML):
                raise ValueError("ISSUER_DECLARED_LENGTH_INVALID")
            raw = r.read(_MAX_HTML + 1)
            if not 0 < len(raw) <= _MAX_HTML or (length and len(raw) != int(length)):
                raise ValueError("ISSUER_RECEIVED_LENGTH_INVALID")
        out["source_publisher_https_verified"] = True
        out["original_sha256"] = sha256(raw).hexdigest()
        out["original_size"] = len(raw)
        # Exact historical source version required; a different file is not
        # silently recast as validated P195/P198 raw evidence.
        if out["original_sha256"] != _KNOWN_SHA or len(raw) != _KNOWN_SIZE:
            raise ValueError("ISSUER_ORIGINAL_RAW_CONTENT_VERSION_CHANGED")
        out["xbrl_facts"] = extract_dell_real_cashflow_income_xbrl(raw)
        out.update(
            status="DELL_REAL_FY2026_FY2025_XBRL_ENGINE_B_CASH_QUALITY_PROVENANCE",
            reason_code="FIRSTPARTY_CFO_NETINCOME_STRUCTURED_FACTS_HUMAN_ONLY",
            real_annual_earnings_cashflow_xbrl_verified=True,
        )
    except (OSError, ValueError, UnicodeError, TypeError, InvalidOperation,
            OverflowError, RecursionError) as error:
        code = str(error)
        out["reason_code"] = (code if re.fullmatch(r"[A-Z0-9_]{3,100}", code)
                              else "ONE_PUBLISHER_FACT_READ_OR_PARSE_FAILED")
        out["xbrl_facts"] = None
    return out


def main() -> int:
    result = verify_dell_financial_quality_xbrl_once()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return (0 if result["status"] ==
            "DELL_REAL_FY2026_FY2025_XBRL_ENGINE_B_CASH_QUALITY_PROVENANCE"
            else 2)


if __name__ == "__main__":
    raise SystemExit(main())
