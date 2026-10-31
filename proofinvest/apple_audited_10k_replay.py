"""Issuer-hosted Apple FY2025 10-K manually transcribed subset -> existing B tools.

Original iXBRL HTML bytes were NOT captured; this is neither raw SEC CompanyFacts
nor independent publisher-origin verification. No network, storage, AI or trades.
The statement's independent audit opinion is documented, not validated by code.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from .kuodra_sec_balance import review_sec_balance_sheet
from .kuodra_sec_cashflow import review_sec_annual_cashflow
from .public_manual_engine_b_replay import replay_manual_apple_through_engine_b
from .public_primary_baseline import APPLE, CURATED, ROOT, _read

TEN_K = ROOT / "docs/evidence/apple_fy2025_issuer_10k_manual_excerpt.json"
_HOSTED = ("https://d18rn0p25nwr6d.cloudfront.net/CIK-0000320193/"
           "c636d8a7-8025-47d2-9b13-bcf5465343b3.html")
_SEC_INDEX = ("https://www.sec.gov/Archives/edgar/data/320193/"
              "0000320193-25-000079-index.htm")
_FIELDS = frozenset({
    "sales", "products", "services", "cost_of_sales", "gross_margin",
    "operating_income", "net_income", "operating_cashflow", "capex_payments",
    "accounts_receivable_net", "inventory_net", "assets", "liabilities", "equity",
})
_PRIOR_CURRENT = {
    "sales": "net_sales",
    "products": "products_sales",
    "services": "services_sales",
    "cost_of_sales": "cost_of_sales",
    "gross_margin": "gross_margin",
    "operating_income": "operating_income",
    "net_income": "net_income",
    "operating_cashflow": "operating_cash_flow",
    "accounts_receivable_net": "accounts_receivable_net",
    "inventory_net": "inventories",
}
_Q = Decimal("0.01")
_NUM = re.compile(r"(?:0|[1-9][0-9]{0,11})\Z", re.ASCII)


def _check(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _exact(value: Any, fields: set[str], code: str) -> dict:
    _check(type(value) is dict and set(value) == fields, code)
    return value


def _values(value: Any) -> dict[str, int]:
    row = _exact(value, set(_FIELDS), "TEN_K_MANUAL_ROW_FIELDS_INVALID")
    for key in _FIELDS:
        text = row[key]
        _check(type(text) is str and _NUM.fullmatch(text) is not None,
               "TEN_K_MANUAL_NUMERIC_VALUE_INVALID")
    amounts = {key: int(row[key]) for key in _FIELDS}
    for positive in ("sales", "assets", "equity", "operating_cashflow"):
        _check(amounts[positive] > 0, "TEN_K_MANUAL_FINANCIAL_DENOMINATOR_ZERO")
    _check(amounts["sales"] == amounts["products"] + amounts["services"]
           and amounts["gross_margin"] == amounts["sales"] - amounts["cost_of_sales"],
           "TEN_K_MANUAL_INCOME_RECONCILIATION_FAILED")
    _check(amounts["assets"] == amounts["liabilities"] + amounts["equity"],
           "TEN_K_MANUAL_BALANCE_IDENTITY_FAILED")
    return amounts


def _fmt(value: Decimal) -> str:
    return str(value.quantize(_Q, rounding=ROUND_HALF_UP))


def _source_contract(doc: Any) -> tuple[dict[str, int], dict[str, int]]:
    data = _exact(doc, {"schema", "issuer", "cik", "accession", "filed_at",
                        "as_of", "currency", "unit", "statement_basis", "fiscal",
                        "source", "prior", "current"},
                  "TEN_K_MANUAL_SCHEMA_INVALID")
    _check(data["schema"] == "kuodra.apple-fy2025-issuer-hosted-10k-manual-excerpt.v1"
           and data["issuer"] == "Apple Inc."
           and data["cik"] == "0000320193"
           and data["accession"] == "0000320193-25-000079"
           and data["filed_at"] == data["as_of"] == "2025-10-31"
           and data["unit"] == "MILLIONS" and data["currency"] == "USD"
           and data["statement_basis"] == "US_GAAP_CONSOLIDATED",
           "TEN_K_MANUAL_IDENTITY_OR_FILING_MISMATCH")
    _check(data["fiscal"] == {
        "prior_start": "2023-10-01", "prior_end": "2024-09-28",
        "current_start": "2024-09-29", "current_end": "2025-09-27",
    }, "TEN_K_MANUAL_FISCAL_PERIOD_MISMATCH")
    _check(data["source"] == {
        "kind": "MANUAL_VIEWED_ISSUER_HOSTED_10K_HTML_NOT_ORIGINAL_BYTES",
        "url": _HOSTED, "sec_index_reference": _SEC_INDEX,
        "financial_statement_printed_pages": [29, 31, 33],
        "independent_auditor_opinion_printed_page": 49,
        "published_form": "10-K",
        "source_raw_html_sha256_verified": False,
        "distribution_rights_verified": False,
        "original_sec_api_authenticated": False,
        "issuer_html_viewed_manually": True,
    }, "TEN_K_MANUAL_SOURCE_TRUST_CONTRACT_INVALID")
    return _values(data["prior"]), _values(data["current"])


def _make_derived_facts(doc: dict, current: dict[str, int]) -> bytes:
    """Bounded one-period trial rows; never persist or expose as SEC originals."""
    acc, filed, end = doc["accession"], doc["filed_at"], doc["fiscal"]["current_end"]
    start = doc["fiscal"]["current_start"]

    def instant(tag: str, amount: int) -> tuple[str, dict]:
        return tag, {"units": {"USD": [{"accn": acc, "form": "10-K",
                    "filed": filed, "end": end, "val": amount * 1_000_000}]}}

    def annual(tag: str, amount: int) -> tuple[str, dict]:
        return tag, {"units": {"USD": [{"accn": acc, "form": "10-K",
                    "filed": filed, "start": start, "end": end,
                    "val": amount * 1_000_000}]}}

    gaap = dict((
        instant("Assets", current["assets"]),
        instant("Liabilities", current["liabilities"]),
        instant("StockholdersEquity", current["equity"]),
        annual("NetCashProvidedByUsedInOperatingActivities",
               current["operating_cashflow"]),
        annual("PaymentsToAcquirePropertyPlantAndEquipment",
               current["capex_payments"]),
    ))
    derived = {"cik": 320193, "entityName": "Apple Inc.", "facts": {"us-gaap": gaap}}
    raw = json.dumps(derived, sort_keys=True, separators=(",", ":")).encode("ascii")
    _check(len(raw) <= 8192, "TEN_K_DERIVED_FACTS_EXCEED_MEMORY_BUDGET")
    return raw


def replay_audited_10k_manual_excerpt(doc: Any, manual: Any, curated: Any) -> dict:
    """Cross-check first-party manually viewed 10-K against P55 + actual B core.

    'Audited' describes the report's own independent-auditor section.
    No original bytes, official SEC API origin or audit opinion verification.
    """
    prior, current = _source_contract(doc)
    manual_b = replay_manual_apple_through_engine_b(manual, curated)
    _check(manual_b["source_authenticated"] is False
           and manual_b["actual_sec_raw_companyfacts_used"] is False
           and manual_b["engine_b_status"] == "reviewed_unverified"
           and manual_b["guard_decision_modified"] is False,
           "TEN_K_PRIOR_MANUAL_ENGINE_B_TRUST_FAILED")
    for year, tenk, reported in (("prior", prior, manual["prior"]),
                                 ("current", current, manual["current"])):
        for metric, mapped in _PRIOR_CURRENT.items():
            _check(tenk[metric] == int(reported[mapped]),
                   "TEN_K_ISSUER_10K_VS_PRESS_RELEASE_MISMATCH_" + year.upper())
    _check(manual_b["engine_b_observations"]["cash_to_net_income_pct"] ==
           _fmt(Decimal(current["operating_cashflow"]) /
                Decimal(current["net_income"]) * 100),
           "TEN_K_ENGINE_B_CASH_CONVERSION_MISMATCH")

    raw = _make_derived_facts(doc, current)
    args = {"cik": doc["cik"], "accession": doc["accession"],
            "period_end": doc["fiscal"]["current_end"], "as_of": doc["as_of"]}
    balance = review_sec_balance_sheet(raw, **args)
    cashflow = review_sec_annual_cashflow(raw, **args)
    _check(balance.get("schema") == "kuodra.sec-balance-sheet-offline.v1"
           and balance.get("status") == "reviewed_unverified"
           and balance.get("balance_identity_match") is True
           and balance.get("liabilities_to_equity_pct") ==
           _fmt(Decimal(current["liabilities"]) / Decimal(current["equity"]) * 100)
           and balance.get("filing_date") == doc["filed_at"]
           and balance.get("source_authenticated") is False
           and balance.get("guard_policy_modified") is False
           and balance.get("trade_executed") is False
           and balance.get("live_api_called") is False,
           "TEN_K_ENGINE_B_BALANCE_REVIEW_MISMATCH")
    fcf_current = current["operating_cashflow"] - current["capex_payments"]
    fcf_prior = prior["operating_cashflow"] - prior["capex_payments"]
    _check(cashflow.get("schema") == "kuodra.sec-annual-cashflow-offline.v1"
           and cashflow.get("status") == "reviewed_unverified"
           and cashflow.get("operating_cashflow_usd") ==
           str(current["operating_cashflow"] * 1_000_000)
           and cashflow.get("capex_payments_usd") ==
           str(current["capex_payments"] * 1_000_000)
           and cashflow.get("free_cashflow_proxy_usd") == str(fcf_current * 1_000_000)
           and cashflow.get("free_cashflow_proxy_is_non_gaap") is True
           and cashflow.get("source_authenticated") is False
           and cashflow.get("trade_executed") is False
           and cashflow.get("live_api_called") is False,
           "TEN_K_ENGINE_B_CASHFLOW_REVIEW_MISMATCH")
    return {
        "schema": "kuodra.apple-10k-manual-issuer-crosscheck.v1",
        "status": "MANUAL_FIRST_PARTY_10K_NUMBERS_CROSSCHECKED_WITH_P55_AND_ENGINE_B",
        "issuer_cik": doc["cik"], "accession": doc["accession"],
        "filed_at": doc["filed_at"], "fiscal_end": doc["fiscal"]["current_end"],
        "source_url": doc["source"]["url"],
        "source_kind": doc["source"]["kind"],
        "financial_statement_auditor_opinion_visible_in_document": True,
        "original_auditor_opinion_automatically_verified": False,
        "reporting_unit": "USD_MILLIONS",
        "press_release_10k_manual_numeric_match": True,
        "prior_engine_b_replay_passed": True,
        "engine_b_balance_status": balance["status"],
        "engine_b_cashflow_status": cashflow["status"],
        "balance_2025_liabilities_to_equity_pct":
            balance["liabilities_to_equity_pct"],
        "balance_2024_liabilities_to_equity_pct":
            _fmt(Decimal(prior["liabilities"]) / Decimal(prior["equity"]) * 100),
        "balance_2025_identity_match": balance["balance_identity_match"],
        "balance_2024_identity_match": True,
        "fcf_proxy_2025_usd_millions": str(fcf_current),
        "fcf_proxy_2024_usd_millions": str(fcf_prior),
        "fcf_proxy_yoy_pct": _fmt(
            (Decimal(fcf_current) / Decimal(fcf_prior) - 1) * 100),
        "fcf_proxy_is_non_gaap": True,
        "receivables_minus_sales_growth_pp":
            manual_b["engine_b_observations"][
                "receivables_minus_revenue_growth_pp"],
        "review_signals": manual_b["engine_b_working_capital_signals"],
        "derived_input_sha256_not_original_sec": sha256(raw).hexdigest(),
        "original_raw_10k_bytes_authenticated": False,
        "original_sec_companyfacts_authenticated": False,
        "original_sec_submissions_authenticated": False,
        "data_rights_verified": False,
        "automatic_sec_3_source_guard_real_data_validated": False,
        "real_world_market_and_industry_validated": False,
        "fraud_proven": False, "investment_recommendation": False,
        "source_authenticated": False, "guard_policy_modified": False,
        "network_requests": 0, "ai_requests": 0, "trade_executed": False,
        "original_html_retained": False, "derived_facts_retained": False,
        "limitations": [
            "10-K excerpt is manually transcribed from a public issuer-hosted HTML display.",
            "Source HTML original bytes and SEC API responses were NOT downloaded or authenticated.",
            "The independent auditor opinion exists in the viewed 10-K; software did not authenticate the auditor.",
            "Engine B reviewed real reported numbers through temporary derived SEC-shaped trial rows only.",
            "FCF proxy is CFO less capex, a non-GAAP simplified calculation, not an issuer-defined free cash flow.",
            "Liabilities-to-equity is not interest-bearing debt and does not establish insolvency.",
            "Receivables/revenue growth gap is an exploratory signal, not evidence of fraud.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline public Apple FY2025 10-K manual fact cross-check")
    parser.add_argument("--10k", dest="ten_k", type=Path, default=TEN_K)
    parser.add_argument("--press-release", type=Path, default=APPLE)
    parser.add_argument("--curated", type=Path, default=CURATED)
    args = parser.parse_args(argv)
    output = replay_audited_10k_manual_excerpt(
        _read(args.ten_k), _read(args.press_release), _read(args.curated))
    print(json.dumps(output, indent=2, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
