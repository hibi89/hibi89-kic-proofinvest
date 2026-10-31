"""SEC official web-text manual 28-cell review against KUODRA Engine B.

First-party SEC site was viewed through web-rendered output, NOT captured as
original SEC HTML/API raw bytes. This validates selected published numbers,
not data origin, rights, complete facts, or historical as-of availability.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path

from .apple_audited_10k_replay import (
    TEN_K, replay_audited_10k_manual_excerpt,
)
from .public_primary_baseline import APPLE, CURATED, ROOT, _read

EVIDENCE = ROOT / "docs/evidence/apple_fy2025_sec_official_web_view_20261101.json"
_METRICS = frozenset(("sales","products","services","cost_of_sales",
                     "gross_margin","operating_income","net_income",
                     "operating_cashflow","capex_payments",
                     "accounts_receivable_net","inventory_net",
                     "assets","liabilities","equity"))
_Q = Decimal("0.01")


def review_sec_apple_web_cells(source: dict, issuer_manual: dict,
                               apple_manual: dict, curated: dict) -> dict:
    if (type(source) is not dict
            or source.get("schema") !=
                "kuodra.apple-fy2025-official-sec-web-manual-crosscheck.v1"
            or source.get("source_kind") !=
                "OFFICIAL_SEC_RENDERED_WEB_TEXT_MANUALLY_REVIEWED_NOT_RAW_HTML_OR_API"
            or source.get("official_url") !=
                "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
            or source.get("official_filing_index") !=
                "https://www.sec.gov/Archives/edgar/data/320193/0000320193-25-000079-index.htm"
            or source.get("issuer") != "Apple Inc."
            or source.get("issuer_cik") != "0000320193"
            or source.get("accession") != "0000320193-25-000079"
            or source.get("filing_date") != "2025-10-31"
            or source.get("prior_end") != "2024-09-28"
            or source.get("current_end") != "2025-09-27"
            or source.get("unit") != "MILLIONS"
            or source.get("currency") != "USD"
            or source.get("statement_printed_pages") != {
                "operations":29,"balance":31,"cash":33}
            or source.get("source_http_403_observed_in_automated_get") is not True
            or any(source.get(k) is not False for k in (
                "sec_original_html_byte_sha256_verified",
                "sec_api_companyfacts_original_verified",
                "source_authenticated",
                "distribution_rights_verified",
                "historic_sec_api_vintage_authenticated",
                "ai_or_trade_execution"
            ))):
        raise ValueError("SEC_WEB_EVIDENCE_PROVENANCE_OR_SCOPE_INVALID")
    pages = source.get("metric_page")
    if (type(pages) is not dict or set(pages) != _METRICS
            or any(page not in ("operations","balance","cash")
                   for page in pages.values())):
        raise ValueError("SEC_WEB_EVIDENCE_STATEMENT_MAP_INVALID")
    matched = 0
    for period in ("prior","current"):
        values = source.get(period)
        expected = issuer_manual.get(period)
        if type(values) is not dict or set(values) != _METRICS:
            raise ValueError("SEC_WEB_EVIDENCE_NUMERIC_FIELDS_INVALID")
        if type(expected) is not dict or set(expected) != _METRICS:
            raise ValueError("SEC_WEB_ISSUER_MANUAL_FIELDS_INVALID")
        for metric in _METRICS:
            value = values[metric]
            if (type(value) is not str
                    or not value.isascii() or not value.isdecimal()
                    or str(int(value)) != value
                    or expected[metric] != value):
                raise ValueError("SEC_WEB_10K_VS_PRIOR_REVIEW_CONFLICT")
            matched += 1
        ints = {k:int(v) for k,v in values.items()}
        if not (
            ints["sales"] == ints["products"]+ints["services"]
            and ints["gross_margin"] == ints["sales"]-ints["cost_of_sales"]
            and ints["assets"] == ints["liabilities"]+ints["equity"]
        ):
            raise ValueError("SEC_WEB_FINANCIAL_ARITHMETIC_CONFLICT")
    replay = replay_audited_10k_manual_excerpt(
        issuer_manual, apple_manual, curated
    )
    if not (replay["press_release_10k_manual_numeric_match"]
            and replay["prior_engine_b_replay_passed"]
            and replay["source_authenticated"] is False
            and replay["original_raw_10k_bytes_authenticated"] is False
            and replay["original_sec_companyfacts_authenticated"] is False
            and replay["guard_policy_modified"] is False
            and replay["trade_executed"] is False):
        raise ValueError("SEC_WEB_ENGINE_B_UNVERIFIED_GATE")
    prior, current = source["prior"], source["current"]
    def growth(field):
        a,b = Decimal(current[field]),Decimal(prior[field])
        return str(((a/b-1)*100).quantize(_Q,rounding=ROUND_HALF_UP))
    output = {
        "status":"OFFICIAL_SEC_WEB_DISPLAY_28_MANUAL_CELLS_MATCH_EXISTING_ENGINE_B",
        "verified_cell_count":matched,
        "sec_web_source_url":source["official_url"],
        "revenue_growth_pct":growth("sales"),
        "receivables_growth_pct":growth("accounts_receivable_net"),
        "operating_cashflow_growth_pct":growth("operating_cashflow"),
        "free_cashflow_proxy_current_millions":
            str(int(current["operating_cashflow"])-int(current["capex_payments"])),
        "free_cashflow_proxy_prior_millions":
            str(int(prior["operating_cashflow"])-int(prior["capex_payments"])),
        "receivables_minus_revenue_growth_pp":
            replay["receivables_minus_sales_growth_pp"],
        "fcf_proxy_yoy_pct":replay["fcf_proxy_yoy_pct"],
        "engine_b_balance_status":replay["engine_b_balance_status"],
        "engine_b_cashflow_status":replay["engine_b_cashflow_status"],
        "financial_misconduct_proven":False,
        "original_sec_bytes_verified":False,
        "data_rights_verified":False,
        "source_authenticated":False,
        "real_sec_three_source_e2e_verified":False,
        "external_http_called":False,
        "audit_written":False,
        "trade_executed":False,
    }
    if (output["free_cashflow_proxy_current_millions"] !=
            replay["fcf_proxy_2025_usd_millions"]
            or output["free_cashflow_proxy_prior_millions"] !=
               replay["fcf_proxy_2024_usd_millions"]):
        raise ValueError("SEC_WEB_ENGINE_B_FCF_CONFLICT")
    return output


def main() -> int:
    result = review_sec_apple_web_cells(
        _read(EVIDENCE), _read(TEN_K), _read(APPLE), _read(CURATED)
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
