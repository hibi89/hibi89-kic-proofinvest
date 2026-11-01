"""Read-only Engine B triage from 28 pre-reviewed SEC rendered-web cells.

No raw SEC issuer authentication, misconduct proof, model, Guard override,
investment recommendation, source rights, network, persistence or trade.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import json
from .sec_primary_web_brief import build_web_only_brief

_Q = Decimal("0.01")
_FIELDS = ("sales", "net_income", "operating_cashflow", "capex_payments",
           "accounts_receivable_net", "liabilities", "equity")


def _pct(a: Decimal, b: Decimal) -> Decimal:
    if b <= 0:
        raise ValueError("WEB_B_INVALID_DENOMINATOR")
    return (Decimal("100") * a / b).quantize(_Q, rounding=ROUND_HALF_UP)


def triage_manual_sec_web() -> dict:
    """Compare AR, profit-to-cash, non-GAAP FCF proxy and total liabilities."""
    brief = build_web_only_brief()  # existing 28-cell source cross-check
    if (brief.get("schema") != "kuodra.sec-web-manual-brief.v1"
            or brief.get("manual_cells_checked") != 28
            or brief.get("issuer") != "Apple Inc."
            or brief.get("unit") != "USD_MILLIONS"
            or brief.get("source_basis") !=
            "SEC_RENDERED_WEB_TEXT_MANUALLY_CHECKED_NOT_ORIGINAL"
            or type(brief.get("unverified")) is not dict
            or not brief["unverified"]
            or any(v is not False for v in brief["unverified"].values())
            or type(brief.get("metrics")) is not list
            or len(brief["metrics"]) != 14):
        raise ValueError("WEB_B_SOURCE_NOT_TRUSTED")
    amounts = {}
    for m in brief["metrics"]:
        if type(m) is not dict or type(m.get("key")) is not str:
            raise ValueError("WEB_B_INVALID_METRIC")
        k = m["key"]
        if k in amounts:
            raise ValueError("WEB_B_DUPLICATE_METRIC")
        pair = []
        for y in ("fy2024", "fy2025"):
            v = m.get(y)
            if (type(v) is not str or not v.isascii() or not v.isdecimal()
                    or str(int(v)) != v):
                raise ValueError("WEB_B_INVALID_AMOUNT")
            pair.append(Decimal(v))
        amounts[k] = tuple(pair)
    if any(k not in amounts for k in _FIELDS):
        raise ValueError("WEB_B_REQUIRED_METRIC_MISSING")
    if any(amounts[k][i] <= 0 for k in (
            "sales", "net_income", "operating_cashflow", "accounts_receivable_net",
            "equity") for i in (0, 1)):
        raise ValueError("WEB_B_INVALID_DENOMINATOR")
    g = lambda key: _pct(amounts[key][1] - amounts[key][0], amounts[key][0])
    sales, ar = g("sales"), g("accounts_receivable_net")
    gap_ar = ar - sales
    cash = [_pct(amounts["operating_cashflow"][i], amounts["net_income"][i])
            for i in (0, 1)]
    cash_drop = cash[1] - cash[0]
    fcf = [amounts["operating_cashflow"][i] - amounts["capex_payments"][i]
           for i in (0, 1)]
    if fcf[0] <= 0 or fcf[1] < 0:
        raise ValueError("WEB_B_INVALID_FCF_PROXY")
    fcf_growth = _pct(fcf[1] - fcf[0], fcf[0])
    gap_fcf = fcf_growth - sales
    lev = [_pct(amounts["liabilities"][i], amounts["equity"][i])
           for i in (0, 1)]
    analysis = brief.get("analysis")
    if (type(analysis) is not dict
            or analysis.get("revenue_growth_pct") != str(sales)
            or analysis.get("receivables_growth_pct") != str(ar)
            or analysis.get("receivables_minus_revenue_growth_pp") != str(gap_ar)
            or analysis.get("fcf_proxy_yoy_pct") != str(fcf_growth)
            or analysis.get("free_cashflow_proxy_current_millions") != str(fcf[1])):
        raise ValueError("WEB_B_ARITHMETIC_CROSSCHECK_FAILED")
    prompts = [
        {"code": "AR_VS_SALES", "value_pp": str(gap_ar),
         "review": gap_ar >= 10, "threshold": ">=10pp exploratory",
         "action": "Review collection timing and revenue recognition notes"},
        {"code": "CFO_TO_INCOME_DROP", "prior_pct": str(cash[0]),
         "current_pct": str(cash[1]), "change_pp": str(cash_drop),
         "review": cash_drop <= -20, "threshold": "<=-20pp exploratory",
         "action": "Review working capital and non-cash items"},
        {"code": "FCF_PROXY_VS_SALES", "prior_usd_millions": str(fcf[0]),
         "current_usd_millions": str(fcf[1]), "growth_pct": str(fcf_growth),
         "difference_pp": str(gap_fcf), "review": gap_fcf <= -10,
         "threshold": "<=-10pp exploratory",
         "action": "Review capex and cash flow notes (non-GAAP proxy)"},
        {"code": "TOTAL_LIABILITIES_TO_EQUITY", "prior_pct": str(lev[0]),
         "current_pct": str(lev[1]), "review": False,
         "threshold": "context_only_not_interest_bearing_debt",
         "action": "Review debt composition and share repurchases"},
    ]
    return {
        "schema": "kuodra.web-manual-accounting-triage.v1",
        "issuer": "Apple Inc.", "source_url": brief["source_url"],
        "basis": "SEC_RENDERED_WEB_TEXT_MANUALLY_CHECKED_NOT_ORIGINAL",
        "manual_cells": 28, "years": ["FY2024", "FY2025"],
        "currency": "USD", "amount_unit": "millions",
        "prompts": prompts,
        "review_prompt_count": sum(p["review"] for p in prompts),
        "thresholds_heuristic_not_standards": True,
        "fcf_proxy_non_gaap": True, "guard_unchanged": True,
        "misconduct_proven": False, "source_authenticated": False,
        "original_sec_bytes_verified": False, "rights_verified": False,
        "point_in_time_verified": False, "real_llm_called": False,
        "investment_risk_certified": False, "external_http_called": False,
        "audit_written": False, "trade_executed": False,
        "officially_submitted": False,
    }


def main() -> int:
    print(json.dumps(triage_manual_sec_web(), ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
