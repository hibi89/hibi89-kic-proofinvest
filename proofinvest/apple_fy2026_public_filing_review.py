"""P190: Apple FY2026 public 10-K statement arithmetic, read-only, no original bytes.

Figures manually checked against PUBLIC SEC 10-K text on 2026-11-05.
This is NOT SEC raw-file authentication, data-use clearance, a live source API,
a market/NDX/peer benchmark or investment advice. No HTTP, writes or trades.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from typing import Any

_TICKER = "AAPL"
_CIK = "0000320193"
_ACCESSION = "0000320193-26-000026"
_FILED = date(2026, 11, 3)
_LAST_REVIEWED = date(2026, 11, 5)
_FY_ENDS = {"2026": "2026-09-26", "2025": "2025-09-27"}
_SOURCE = "https://www.sec.gov/Archives/edgar/data/320193/000032019326000026/aapl-20260926.htm"
# Source: FY2026 SEC 10-K Item 8, consolidated USD millions; page, current, prior.
_SECTIONS = {
    "net_sales": ("32", 478834, 416161),
    "net_income": ("32,36", 132175, 112010),
    "operating_cash_flow": ("36", 145097, 111482),
    "accounts_receivable": ("34", 43817, 39777),
    "inventory": ("34", 14541, 5718),
    "capital_expenditure": ("36", 9041, 12715),
}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.apple-fy2026-public-financial-review.v1",
        "status": "BLOCKED", "reason_code": reason,
        "ticker": _TICKER, "cik": _CIK, "accession": _ACCESSION,
        "original_bytes_authenticated": False,
        "publisher_origin_authenticated": False,
        "source_rights_verified": False, "ai_processing_rights_verified": False,
        "market_ndx_peer_ready": False, "ai_agent_executed": False,
        "guard_policy_preview": "HOLD", "trade_executed": False,
        "external_network_requests": 0, "raw_original_downloaded": False,
        "audit_written": False, "derived_metrics": None, "signals": [],
    }


def _decimal(value: Any) -> Decimal:
    if (type(value) is not str or not value.isascii() or not value.isdigit()
            or len(value) > 12):
        raise ValueError("RAW_NUMERIC_VALUE_INVALID")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("RAW_NUMERIC_VALUE_INVALID") from exc


def _pct(numer: Decimal, denom: Decimal) -> str:
    if denom <= 0:
        raise ValueError("ZERO_BASELINE_OR_NONPOSITIVE_DENOMINATOR")
    return str(((numer / denom - Decimal(1)) * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))


def _ratio(numer: Decimal, denom: Decimal) -> str:
    if denom <= 0:
        raise ValueError("ZERO_BASELINE_OR_NONPOSITIVE_DENOMINATOR")
    return str((numer / denom).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def public_2026_values() -> dict[str, dict[str, str]]:
    """Return an untrusted-copy-safe dict of public financial transcriptions."""
    return {name: {"2026": str(row[1]), "2025": str(row[2])}
            for name, row in _SECTIONS.items()}


def review_apple_2026_public_financials(
    *, ticker: str, as_of: str, accession: str,
    values: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Independent Decimal replay; exact known public text, not raw SEC bytes."""
    if (type(ticker) is not str or ticker != _TICKER
            or type(accession) is not str or accession != _ACCESSION
            or type(as_of) is not str or len(as_of) != 10):
        return _blocked("IDENTITY_OR_DATE_INVALID")
    try:
        cutoff = date.fromisoformat(as_of)
        if cutoff.isoformat() != as_of:
            return _blocked("AS_OF_INVALID")
    except (ValueError, TypeError):
        return _blocked("AS_OF_INVALID")
    if not _FILED < cutoff <= _LAST_REVIEWED:
        return _blocked("PUBLIC_FILING_AS_OF_UNAVAILABLE_OR_CATALOG_EXPIRED")
    if type(values) is not dict or set(values) != set(_SECTIONS):
        return _blocked("METRIC_SET_UNAVAILABLE_OR_EXTRA")
    parsed: dict[str, dict[str, Decimal]] = {}
    try:
        for name, (_, official_current, official_prior) in _SECTIONS.items():
            val = values[name]
            if type(val) is not dict or set(val) != {"2026", "2025"}:
                return _blocked("METRIC_PERIOD_SET_INVALID")
            current, prior = _decimal(val["2026"]), _decimal(val["2025"])
            if current != official_current or prior != official_prior:
                return _blocked("PUBLIC_REVIEWED_10K_VALUE_MISMATCH")
            parsed[name] = {"2026": current, "2025": prior}
        revenue, net = parsed["net_sales"], parsed["net_income"]
        cfo, inv = parsed["operating_cash_flow"], parsed["inventory"]
        ar, capex = parsed["accounts_receivable"], parsed["capital_expenditure"]
        revenue_growth = _pct(revenue["2026"], revenue["2025"])
        inventory_growth = _pct(inv["2026"], inv["2025"])
        receivable_growth = _pct(ar["2026"], ar["2025"])
        lines = {name: {
            "2026_usd_millions": str(numbers["2026"]),
            "2025_usd_millions": str(numbers["2025"]),
            "form_10k_page": _SECTIONS[name][0],
        } for name, numbers in parsed.items()}
        metrics = {
            "revenue_growth_pct": revenue_growth,
            "net_income_growth_pct": _pct(net["2026"], net["2025"]),
            "operating_cash_flow_growth_pct": _pct(cfo["2026"], cfo["2025"]),
            "receivables_growth_pct": receivable_growth,
            "inventory_growth_pct": inventory_growth,
            "inventory_growth_minus_revenue_growth_pp": str(
                (Decimal(inventory_growth) - Decimal(revenue_growth)).quantize(Decimal("0.01"))),
            "operating_cash_flow_to_net_income_2026": _ratio(cfo["2026"], net["2026"]),
            "operating_cash_flow_to_net_income_2025": _ratio(cfo["2025"], net["2025"]),
            "free_cash_flow_2026_usd_millions_unverified": str(cfo["2026"] - capex["2026"]),
            "free_cash_flow_2025_usd_millions_unverified": str(cfo["2025"] - capex["2025"]),
        }
        return {
            **_blocked("PUBLIC_BROWSER_REVIEW_NOT_RAW_ORIGIN_PROOF"),
            "status": "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED",
            "fiscal_period_ends": dict(_FY_ENDS),
            "public_filing_url": _SOURCE,
            "filing_date": _FILED.isoformat(),
            "publication_reviewed_through": _LAST_REVIEWED.isoformat(),
            "values_unit": "USD_MILLIONS",
            "transcribed_financial_statement_values": lines,
            "derived_metrics": metrics,
            "signals": (["INVENTORY_GROWTH_OUTPACED_REVENUE_HUMAN_REVIEW"]
                        if Decimal(inventory_growth) > Decimal(revenue_growth) else []),
            "fraud_proven": False, "investment_advice": False,
            "human_review_required": True,
        }
    except (ValueError, TypeError, InvalidOperation, OverflowError):
        return _blocked("FINANCIAL_DECIMAL_RECALCULATION_INVALID")


def main() -> int:
    result = review_apple_2026_public_financials(
        ticker=_TICKER, accession=_ACCESSION, as_of="2026-11-05",
        values=public_2026_values())
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if result["status"].startswith("PUBLIC_FINANCIAL_VALUES_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
