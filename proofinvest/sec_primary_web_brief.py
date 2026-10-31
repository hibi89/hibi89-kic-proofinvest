"""Read-only KUODRA brief of 28 SEC rendered-web manually reviewed cells.

NOT source-byte authentication, Guard execution, actual A/B/C data, a live
SEC response, misconduct proof or investment advice. No network or filesystem writes; reads committed public evidence.
"""
from __future__ import annotations
import argparse
from html import escape
import json
from .apple_audited_10k_replay import TEN_K
from .public_primary_baseline import APPLE, CURATED, _read
from .sec_primary_web_replay import EVIDENCE, review_sec_apple_web_cells

_METRICS = (
    ("sales", "Net sales"), ("products", "Products revenue"),
    ("services", "Services revenue"), ("cost_of_sales", "Cost of sales"),
    ("gross_margin", "Gross margin"), ("operating_income", "Operating income"),
    ("net_income", "Net income"), ("operating_cashflow", "Operating cash flow"),
    ("capex_payments", "Capital expenditure payments"),
    ("accounts_receivable_net", "Accounts receivable, net"),
    ("inventory_net", "Inventory, net"), ("assets", "Total assets"),
    ("liabilities", "Total liabilities"), ("equity", "Shareholders' equity"),
)
_LIMITS = (
    "source_authenticated", "original_sec_bytes_verified", "rights_verified",
    "point_in_time_verified", "real_sec_three_engine_e2e_verified",
    "guard_executed", "ai_agent_executed", "audit_written", "trade_executed",
    "financial_misconduct_proven", "external_http_called",
)

def build_web_only_brief():
    source = _read(EVIDENCE)
    result = review_sec_apple_web_cells(source, _read(TEN_K),
                                        _read(APPLE), _read(CURATED))
    if (result.get("verified_cell_count") != 28
            or any(result.get(k) is not False for k in (
                "source_authenticated", "original_sec_bytes_verified",
                "data_rights_verified", "real_sec_three_source_e2e_verified",
                "external_http_called", "audit_written", "trade_executed",
                "financial_misconduct_proven"))):
        raise ValueError("WEB_BRIEF_UNTRUSTED_ENGINE_B")
    return {
        "schema": "kuodra.sec-web-manual-brief.v1",
        "issuer": "Apple Inc.", "unit": "USD_MILLIONS",
        "source_url": source["official_url"],
        "source_basis": "SEC_RENDERED_WEB_TEXT_MANUALLY_CHECKED_NOT_ORIGINAL",
        "manual_cells_checked": 28,
        "metrics": [
            {"key": key, "name": name, "statement": source["metric_page"][key],
             "fy2025": source["current"][key], "fy2024": source["prior"][key]}
            for key, name in _METRICS
        ],
        "analysis": {
            k: result[k] for k in (
                "revenue_growth_pct", "receivables_growth_pct",
                "receivables_minus_revenue_growth_pp",
                "operating_cashflow_growth_pct", "fcf_proxy_yoy_pct",
                "free_cashflow_proxy_current_millions",
                "engine_b_balance_status", "engine_b_cashflow_status"
            )
        },
        "workflow_state": "ORIGINAL_SEC_BYTES_REQUIRED_GUARD_NOT_RUN",
        "unverified": {k: False for k in _LIMITS},
    }

def render_web_only_brief_html(brief):
    # Refuse injected fields/values/trust upgrades, including forged negatives.
    if type(brief) is not dict or brief != build_web_only_brief():
        raise ValueError("WEB_BRIEF_UNTRUSTED_OR_TAMPERED_REPORT")
    rows = "".join(
        "<tr><th>" + escape(m["name"]) + "</th><td>"
        + escape(m["statement"]) + "</td><td>" + escape(m["fy2025"])
        + "</td><td>" + escape(m["fy2024"]) + "</td></tr>"
        for m in brief["metrics"]
    )
    details = "".join(
        "<li>" + escape(k.replace("_", " ")) + ": "
        + escape(str(v)) + "</li>" for k,v in brief["analysis"].items()
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>KUODRA | Reviewed SEC web numbers</title>"
        "<style>body{font:16px system-ui;max-width:960px;margin:auto;padding:24px}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #999;"
        "padding:8px;text-align:left}aside{border-left:5px solid #b44;"
        "padding:12px;background:#fff2ed;color:#6b211c}</style></head><body>"
        "<h1>KUODRA — Apple FY2025 SEC web-only review</h1>"
        "<aside><strong>ORIGINAL UNVERIFIED · GUARD NOT RUN · "
        "NO INVESTMENT RECOMMENDATION</strong><p>28 manually matched SEC "
        "rendered-web cells, not downloaded original HTML, Submissions or "
        "CompanyFacts. Source origin, rights and historical vintage remain "
        "unauthenticated. These signals do not establish misconduct.</p></aside>"
        "<table><thead><tr><th>Metric</th><th>Statement</th><th>FY2025</th>"
        "<th>FY2024</th></tr></thead><tbody>" + rows + "</tbody></table>"
        "<h2>Existing deterministic Engine B checks</h2><ul>" + details
        + "</ul><p><strong>" + escape(brief["workflow_state"])
        + "</strong></p><p>Source: " + escape(brief["source_url"])
        + "</p></body></html>"
    )

def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline, source-unverified SEC web evidence")
    parser.add_argument("--format", choices=("json", "html"), default="json")
    args = parser.parse_args(argv)
    brief = build_web_only_brief()
    print(render_web_only_brief_html(brief) if args.format == "html"
          else json.dumps(brief, ensure_ascii=False, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
