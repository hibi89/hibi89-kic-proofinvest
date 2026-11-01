"""Reproducible, read-only Engine B evidence trace for 28 manually checked SEC WEB cells.

A SHA-256 here detects local report changes, NOT publisher authenticity,
licensed rights, historic SEC vintage, accounting fraud, or investment risk.
No external IO, network, model, audit DB or trades.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json

from .sec_primary_web_brief import build_web_only_brief
from .sec_primary_web_replay import EVIDENCE
from .sec_web_accounting_signals import triage_manual_sec_web

_Q = Decimal("0.01")
_PAGES = {"operations": 29, "balance": 31, "cash": 33}
_KEYS = (
    "sales", "net_income", "operating_cashflow", "capex_payments",
    "accounts_receivable_net", "liabilities", "equity",
)
_FALSE = (
    "source_authenticated", "original_sec_bytes_verified", "rights_verified",
    "point_in_time_verified", "real_llm_called", "investment_risk_certified",
    "misconduct_proven", "external_http_called", "audit_written",
    "trade_executed", "officially_submitted",
)


def canonical_json(value: dict) -> bytes:
    """Deterministic JSON only; fail rather than emit nonfinite numbers."""
    if type(value) is not dict:
        raise ValueError("WEB_B_TRACE_INVALID_REPORT")
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _percent(a: Decimal, b: Decimal) -> Decimal:
    if b <= 0:
        raise ValueError("WEB_B_TRACE_INVALID_DENOMINATOR")
    return (a / b * Decimal("100")).quantize(_Q, rounding=ROUND_HALF_UP)


def build_accounting_trace() -> dict:
    """Independently recalculate exact signals and bind source cells/formulas."""
    brief = build_web_only_brief()
    triage = triage_manual_sec_web()
    if (type(brief) is not dict
            or brief.get("schema") != "kuodra.sec-web-manual-brief.v1"
            or brief.get("manual_cells_checked") != 28
            or brief.get("issuer") != "Apple Inc."
            or brief.get("unit") != "USD_MILLIONS"
            or brief.get("source_basis") !=
            "SEC_RENDERED_WEB_TEXT_MANUALLY_CHECKED_NOT_ORIGINAL"
            or type(brief.get("metrics")) is not list
            or len(brief["metrics"]) != 14
            or any(v is not False for v in brief.get("unverified", {}).values())
            or type(triage) is not dict
            or triage.get("schema") != "kuodra.web-manual-accounting-triage.v1"
            or triage.get("review_prompt_count") != 3
            or any(triage.get(k) is not False for k in _FALSE)
            or triage.get("manual_cells") != 28
            or triage.get("basis") != brief["source_basis"]
            or triage.get("source_url") != brief["source_url"]
            or type(triage.get("prompts")) is not list
            or len(triage["prompts"]) != 4):
        raise ValueError("WEB_B_TRACE_UNTRUSTED_INPUT")
    metrics = {m.get("key"): m for m in brief["metrics"]
               if type(m) is dict and type(m.get("key")) is str}
    if len(metrics) != 14 or any(k not in metrics for k in _KEYS):
        raise ValueError("WEB_B_TRACE_METRICS_MISSING")
    cells = []
    pairs = {}
    for key in _KEYS:
        m = metrics[key]
        if (m.get("statement") not in _PAGES
                or type(m.get("name")) is not str):
            raise ValueError("WEB_B_TRACE_BAD_SOURCE_LOCATION")
        numbers = []
        for year in ("fy2024", "fy2025"):
            value = m.get(year)
            if (type(value) is not str or not value.isascii()
                    or not value.isdecimal() or str(int(value)) != value):
                raise ValueError("WEB_B_TRACE_BAD_SOURCE_AMOUNT")
            numbers.append(Decimal(value))
        pairs[key] = tuple(numbers)
        cells.append({
            "key": key, "label": m["name"], "statement": m["statement"],
            "printed_page_claimed": _PAGES[m["statement"]],
            "fy2024_usd_millions": m["fy2024"],
            "fy2025_usd_millions": m["fy2025"],
        })
    prior, current = 0, 1
    def growth(key: str) -> Decimal:
        old, new = pairs[key]
        return _percent(new - old, old)

    sales_growth = growth("sales")
    ar_gap = growth("accounts_receivable_net") - sales_growth
    cfo_prior = _percent(pairs["operating_cashflow"][prior],
                         pairs["net_income"][prior])
    cfo_current = _percent(pairs["operating_cashflow"][current],
                           pairs["net_income"][current])
    cash_delta = cfo_current - cfo_prior
    fcf_prior = pairs["operating_cashflow"][prior] - pairs["capex_payments"][prior]
    fcf_current = pairs["operating_cashflow"][current] - pairs["capex_payments"][current]
    fcf_gap = _percent(fcf_current - fcf_prior, fcf_prior) - sales_growth
    total_liability_ratio = _percent(pairs["liabilities"][current],
                                     pairs["equity"][current])
    computed = (ar_gap, cash_delta, fcf_gap, total_liability_ratio)
    codes = ("AR_VS_SALES", "CFO_TO_INCOME_DROP",
             "FCF_PROXY_VS_SALES", "TOTAL_LIABILITIES_TO_EQUITY")
    value_fields = ("value_pp", "change_pp", "difference_pp", "current_pct")
    uses = (
        ("accounts_receivable_net", "sales"),
        ("operating_cashflow", "net_income"),
        ("operating_cashflow", "capex_payments", "sales"),
        ("liabilities", "equity"),
    )
    formulas = (
        "pct_change(receivables) - pct_change(sales)",
        "pct(CFO_FY2025 / net_income_FY2025) - pct(CFO_FY2024 / net_income_FY2024)",
        "pct_change(CFO - capex_payments) - pct_change(sales)",
        "pct(liabilities_FY2025 / equity_FY2025)",
    )
    expected_review = (True, True, True, False)
    signals = []
    for i, (code, field, number, keys, expr, is_review) in enumerate(zip(
            codes, value_fields, computed, uses, formulas, expected_review)):
        p = triage["prompts"][i]
        if (type(p) is not dict or p.get("code") != code
                or p.get(field) != str(number)
                or p.get("review") is not is_review):
            raise ValueError("WEB_B_TRACE_ARITHMETIC_OR_REVIEW_CONFLICT")
        signals.append({
            "code": code, "value": str(number),
            "unit": "percent" if i == 3 else "percentage_points",
            "formula": expr, "input_keys": list(keys),
            "review_prompt": is_review,
            "heuristic_threshold": p["threshold"],
            "review_action": p["action"],
            "is_interest_bearing_debt": False if i == 3 else None,
        })
    if (triage["prompts"][1].get("prior_pct") != str(cfo_prior)
            or triage["prompts"][1].get("current_pct") != str(cfo_current)
            or triage["prompts"][2].get("prior_usd_millions") != str(fcf_prior)
            or triage["prompts"][2].get("current_usd_millions") != str(fcf_current)):
        raise ValueError("WEB_B_TRACE_INTERMEDIATE_CONFLICT")
    report = {
        "schema": "kuodra.manual-sec-web-accounting-trace.v1",
        "status": "OFFLINE_MANUAL_WEB_REVIEW_NOT_ORIGINAL",
        "issuer": "Apple Inc.", "issuer_cik": "0000320193",
        "accession_operator_recorded": "0000320193-25-000079",
        "annual_periods": {"fy2024": "2024-09-28", "fy2025": "2025-09-27"},
        "currency": "USD", "unit": "millions",
        "source_kind": brief["source_basis"],
        "source_url_operator_recorded": brief["source_url"],
        "local_review_manifest_sha256": sha256(EVIDENCE.read_bytes()).hexdigest(),
        "digest_proves_sec_origin": False,
        "manual_cells_reviewed": 28, "trace_cells": cells,
        "signals": signals, "review_prompt_count": 3,
        "cash_conversion_intermediates": {
            "fy2024_pct": str(cfo_prior), "fy2025_pct": str(cfo_current)},
        "non_gaap_fcf_intermediates_usd_millions": {
            "fy2024": str(fcf_prior), "fy2025": str(fcf_current)},
        "sales_growth_pct": str(sales_growth),
        "method": "Decimal, ROUND_HALF_UP to 2dp at each percent step",
        "thresholds_not_financial_standards": True,
        "source_authenticated": False,
        "original_sec_bytes_verified": False, "rights_verified": False,
        "point_in_time_verified": False, "real_llm_called": False,
        "investment_risk_certified": False, "misconduct_proven": False,
        "external_http_called": False, "audit_written": False,
        "trade_executed": False, "officially_submitted": False,
        "guard_decision_changed": False,
        "triage_output_sha256": sha256(canonical_json(triage)).hexdigest(),
    }
    report["report_sha256"] = sha256(canonical_json(report)).hexdigest()
    return report


def export_accounting_trace(report: dict) -> bytes:
    """Only export the exact independently reconstructed report."""
    if type(report) is not dict or report != build_accounting_trace():
        raise ValueError("WEB_B_TRACE_REPORT_TAMPERED")
    claimed_digest = report.get("report_sha256")
    unsigned = {k: v for k, v in report.items() if k != "report_sha256"}
    if type(claimed_digest) is not str or claimed_digest != sha256(
            canonical_json(unsigned)).hexdigest():
        raise ValueError("WEB_B_TRACE_REPORT_DIGEST_MISMATCH")
    data = canonical_json(report)
    if len(data) > 16_384:
        raise ValueError("WEB_B_TRACE_EXPORT_TOO_LARGE")
    return data


def main() -> int:
    report = build_accounting_trace()
    print(export_accounting_trace(report).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
