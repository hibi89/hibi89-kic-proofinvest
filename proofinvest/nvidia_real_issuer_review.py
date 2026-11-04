"""P209 genuine second-issuer FY2026 NVIDIA public release human-review receipt.

Real official NVIDIA 2026/2025 GAAP financial table values from one successful
read-only GitHub CI source GET. The immutable facts are an auditable receipt,
not a 10-K EDGAR raw-original, license grant, benchmark or market feed.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .nvidia_issuer_fy2026_once import _URL, _EXPECTED

_ACTUAL_SHA = "d07c1eba1c308b12acce8a559a9313e9f344ae88ffa68800d5f18a1935dbd03a"
_ORIGINAL_BYTES = 480896
_SOURCE_CI = "https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41903352635"
_SOURCE_SHA = "1102f218f58f54c165cbefcc777796b9b86d1df5"


def actual_nvidia_issuer_receipt() -> dict[str, Any]:
    """Frozen record from an actual NVIDIA issuer-origin HTTPS GET; no new HTTP."""
    return {
        "schema": "kuodra.p209-genuine-nvda-primary-release-receipt.v1",
        "source_url": _URL, "source_sha256": _ACTUAL_SHA,
        "source_bytes": _ORIGINAL_BYTES, "source_ci_run": _SOURCE_CI,
        "source_functional_commit_sha": _SOURCE_SHA,
        "ticker": "NVDA", "cik": "0001045810",
        "fiscal_2026_end": "2026-01-25",
        "fiscal_2025_end": "2025-01-26",
        "release_date": "2026-02-25", "unit": "USD_millions",
        "source_unaudited": True,
        "gaap_income_quarterly_and_annual": {
            "revenue": tuple(str(v) for v in _EXPECTED["revenue"]),
            "net_income": tuple(str(v) for v in _EXPECTED["net_income"]),
        },
        "gaap_cashflow_quarterly_and_annual": {
            "net_income": tuple(str(v) for v in _EXPECTED["net_income"]),
            "cash_from_operations": tuple(str(v) for v in _EXPECTED["cash_from_operations"]),
        },
        "balance_sheet_fy2026_fy2025": {
            key: tuple(str(v) for v in _EXPECTED[key])
            for key in ("trade_receivables", "inventories", "current_assets")
        },
        "sec_10k_raw_identical": False,
        "commercial_ai_rights_verified": False,
        "stock_ndx_peer_license_verified": False, "trade_executed": False,
    }


def _blocked(code: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p209-actual-second-issuer-nvda-review.v1",
        "status": "BLOCKED", "reason_code": code, "evidence": None,
        "issuer_original_publisher_seen": False, "sec_original_identical": False,
        "commercial_ai_rights_verified": False,
        "licensed_stock_ndx_peer_available": False,
        "full_engine_b_authenticated": False, "full_abc_ready": False,
        "ai_agent_executed": False, "guard_policy_preview": "HOLD",
        "trade_executed": False, "network_requests": 0,
    }


def _pct(now: Decimal, before: Decimal) -> Decimal:
    if now <= 0 or before <= 0:
        raise ValueError("P209_NONPOSITIVE_FINANCIALS")
    return (now / before - 1) * 100


def review_nvidia_actual_release(*, as_of: str,
                                 receipt: dict[str, Any]) -> dict[str, Any]:
    """Independently recompute observed numbers, not another original GET."""
    if as_of != "2026-11-05":
        return _blocked("ORIGINAL_REVIEW_AS_OF_NOT_CURRENTLY_ATTESTED")
    if type(receipt) is not dict or receipt != actual_nvidia_issuer_receipt():
        return _blocked("ACTUAL_ISSUER_RECEIPT_CHANGED")
    try:
        income = receipt["gaap_income_quarterly_and_annual"]
        cash = receipt["gaap_cashflow_quarterly_and_annual"]
        assets = receipt["balance_sheet_fy2026_fy2025"]
        revenue = [Decimal(x) for x in income["revenue"]]
        ni = [Decimal(x) for x in income["net_income"]]
        cfo = [Decimal(x) for x in cash["cash_from_operations"]]
        if (cash["net_income"] != income["net_income"]
                or revenue[0] == revenue[2] or ni[0] == ni[2]
                or cfo[0] == cfo[2]):
            return _blocked("GAAP_ANNUAL_AND_QUARTER_CONTEXT_CONFLICT")
        r_growth = _pct(revenue[2], revenue[3])
        a_growth = _pct(Decimal(assets["trade_receivables"][0]),
                        Decimal(assets["trade_receivables"][1]))
        i_growth = _pct(Decimal(assets["inventories"][0]),
                        Decimal(assets["inventories"][1]))
        four = Decimal("0.0001")
        two = Decimal("0.01")
        metrics = {
            "revenue_2026_usdm": str(revenue[2]),
            "revenue_2025_usdm": str(revenue[3]),
            "revenue_growth_pct": str(r_growth.quantize(two, rounding=ROUND_HALF_UP)),
            "net_income_2026_usdm": str(ni[2]),
            "cashflow_2026_usdm": str(cfo[2]),
            "cfo_to_net_income_2026": str(
                (cfo[2] / ni[2]).quantize(four, rounding=ROUND_HALF_UP)),
            "trade_receivables_2026_usdm": assets["trade_receivables"][0],
            "trade_receivables_2025_usdm": assets["trade_receivables"][1],
            "ar_growth_pct": str(a_growth.quantize(two, rounding=ROUND_HALF_UP)),
            "ar_growth_minus_revenue_pp": str(
                (a_growth-r_growth).quantize(two, rounding=ROUND_HALF_UP)),
            "inventory_2026_usdm": assets["inventories"][0],
            "inventory_2025_usdm": assets["inventories"][1],
            "inventory_growth_pct": str(i_growth.quantize(two, rounding=ROUND_HALF_UP)),
            "inventory_growth_minus_revenue_pp": str(
                (i_growth-r_growth).quantize(two, rounding=ROUND_HALF_UP)),
            "total_current_assets_2026_usdm": assets["current_assets"][0],
        }
        if (metrics["revenue_growth_pct"] != "65.47"
                or metrics["cfo_to_net_income_2026"] != "0.8555"
                or metrics["ar_growth_pct"] != "66.77"
                or metrics["inventory_growth_pct"] != "112.33"
                or metrics["ar_growth_minus_revenue_pp"] != "1.30"
                or metrics["inventory_growth_minus_revenue_pp"] != "46.86"):
            return _blocked("REAL_NVIDIA_SOURCE_NUMERIC_REPLAY_CONFLICT")
        return {
            **_blocked("ISSUER_REAL_GAAP_NOT_LICENSE_OR_EDGAR_AUTHENTICATION"),
            "status": "REAL_NVDA_FY2026_2025_ISSUER_GAAP_REVIEW_LIMITED",
            "issuer_original_publisher_seen": True,
            "evidence": {
                "ticker": "NVDA", "cik": receipt["cik"],
                "issuer_source_url": receipt["source_url"],
                "issuer_source_sha256": receipt["source_sha256"],
                "source_bytes": receipt["source_bytes"],
                "source_ci_run": receipt["source_ci_run"],
                "fiscal_2026_end": receipt["fiscal_2026_end"],
                "fiscal_2025_end": receipt["fiscal_2025_end"],
                "amount_unit": receipt["unit"], "release_unaudited": True,
                "metrics": metrics,
                "audited_10k_verified": False,
                "financial_misconduct_proven": False,
            },
        }
    except (KeyError, TypeError, ValueError, ArithmeticError, OverflowError):
        return _blocked("ORIGINAL_RECEIPT_NUMERIC_INVALID")


def main() -> int:
    import json
    outcome = review_nvidia_actual_release(
        as_of="2026-11-05", receipt=actual_nvidia_issuer_receipt())
    print(json.dumps(outcome, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if outcome["issuer_original_publisher_seen"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
