"""P55 primary-publisher manual financial replay; no network or source-auth claims.

Apple issuer Q4 statements are an unaudited 2025-10-30 press release.
Apple's curated CompanyFacts JSON is NOT the raw SEC API response.
Samsung values are an earlier manually reviewed audited issuer PDF example.
No FX, cross-issuer ranking, investment advice, source retention or trades.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
APPLE = ROOT / "docs/evidence/apple_fy2025_issuer_manual_metrics.json"
CURATED = ROOT / "fixtures/sec_apple_fy2025_curated_companyfacts.json"
SAMSUNG = ROOT / "docs/evidence/samsung_2024_cfs_revenue.json"
SOURCE_URL = ("https://www.apple.com/newsroom/pdfs/fy2025-q4/"
              "FY25_Q4_Consolidated_Financial_Statements.pdf")
_METRICS = ("net_sales", "products_sales", "services_sales", "cost_of_sales",
            "gross_margin", "operating_income", "net_income", "operating_cash_flow",
            "accounts_receivable_net", "inventories")
_DECIMAL_2 = Decimal("0.01")
_AMOUNT = re.compile(r"(?:0|[1-9][0-9]{0,11})\Z")


def _require(test: bool, code: str) -> None:
    if not test:
        raise ValueError(code)


def _exact(value: Any, keys: set[str], code: str) -> dict:
    _require(type(value) is dict and set(value) == keys, code)
    return value


def _date(raw: Any) -> date:
    _require(type(raw) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw) is not None,
             "INVALID_PUBLIC_DATE")
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("INVALID_PUBLIC_DATE") from exc


def _number(value: Any) -> Decimal:
    _require(type(value) is str and _AMOUNT.fullmatch(value) is not None,
             "INVALID_MANUAL_PUBLIC_AMOUNT")
    return Decimal(value)


def _percent(a: Decimal, b: Decimal) -> str | None:
    if b == 0:
        return None
    try:
        return format(((a - b) / b * 100).quantize(_DECIMAL_2), ".2f")
    except (InvalidOperation, ArithmeticError, OverflowError) as exc:
        raise ValueError("PUBLIC_PERCENT_NOT_REPRESENTABLE") from exc


def _read_period(value: Any) -> tuple[date, date, dict[str, Decimal]]:
    row = _exact(value, {"start", "end", *_METRICS}, "PUBLIC_FINANCIAL_FIELDS")
    start, end = _date(row["start"]), _date(row["end"])
    _require(330 <= (end - start).days <= 380, "PUBLIC_ANNUAL_PERIOD_INVALID")
    values = {key: _number(row[key]) for key in _METRICS}
    _require(values["net_sales"] > 0 and values["net_income"] > 0,
             "PUBLIC_MISSING_REVENUE_OR_NET_INCOME")
    _require(values["products_sales"] + values["services_sales"] == values["net_sales"],
             "PUBLIC_SALES_COMPONENTS_CONFLICT")
    _require(values["net_sales"] - values["cost_of_sales"] == values["gross_margin"],
             "PUBLIC_GROSS_MARGIN_CONFLICT")
    return start, end, values


def analyze_apple_manual_pair(evidence: Any, curated_companyfacts: Any) -> dict:
    """Compute real reported values, not independent authentication of issuer PDF."""
    data = _exact(evidence, {"schema", "issuer", "cik", "as_of", "currency", "unit",
                             "accounting_basis", "statement_status", "source",
                             "filing_context", "prior", "current"},
                  "PUBLIC_APPLE_SCHEMA_INVALID")
    _require(data["schema"] == "kuodra.apple-fy2025-public-manual.v1"
             and data["issuer"] == "Apple Inc." and data["cik"] == "0000320193"
             and data["currency"] == "USD" and data["unit"] == "MILLIONS"
             and data["accounting_basis"] == "US_GAAP_CONSOLIDATED"
             and data["statement_status"] == "UNAUDITED_ISSUER_PRESS_RELEASE",
             "PUBLIC_APPLE_IDENTITY_OR_UNITS_MISMATCH")
    context = _exact(data["filing_context"], {"kind", "accession", "filed_at"},
                     "PUBLIC_APPLE_FILING_CONTEXT_INVALID")
    _require(context == {
        "kind": "MANUALLY_CURATED_10K_COMPANYFACTS_NOT_RAW_API",
        "accession": "0000320193-25-000079", "filed_at": "2025-10-31"},
        "PUBLIC_APPLE_FILING_CONTEXT_MISMATCH")
    source = _exact(data["source"], {
        "publisher", "document", "url", "release_date", "pdf_pages_one_based",
        "transcription_method", "pdf_original_sha256_authenticated",
        "distribution_rights_verified"}, "PUBLIC_APPLE_SOURCE_SCHEMA_INVALID")
    _require(source == {
        "publisher": "Apple Inc.",
        "document": "FY2025 Q4 Condensed Consolidated Financial Statements",
        "url": SOURCE_URL, "release_date": "2025-10-30",
        "pdf_pages_one_based": [1, 2, 3],
        "transcription_method": "MANUAL_FIRST_PARTY_PDF_TABLE_REVIEW",
        "pdf_original_sha256_authenticated": False,
        "distribution_rights_verified": False}, "PUBLIC_APPLE_SOURCE_NOT_PINNED")
    prior_start, prior_end, prior = _read_period(data["prior"])
    current_start, current_end, current = _read_period(data["current"])
    _require((prior_start.isoformat(), prior_end.isoformat(),
              current_start.isoformat(), current_end.isoformat()) ==
             ("2023-10-01", "2024-09-28", "2024-09-29", "2025-09-27"),
             "PUBLIC_APPLE_FISCAL_PERIOD_MISMATCH")
    _require(current_start.toordinal() == prior_end.toordinal() + 1
             and _date(source["release_date"]) > current_end
             and _date(data["as_of"]) >= _date(context["filed_at"]),
             "PUBLIC_APPLE_LOOKAHEAD_OR_GAP")
    curated = _exact(curated_companyfacts, {"cik", "entityName", "_provenance_notice", "facts"},
                     "PUBLIC_CURATED_FACTS_SCHEMA_INVALID")
    _require(type(curated["cik"]) is int and curated["cik"] == 320193
             and curated["entityName"] == data["issuer"]
             and type(curated["_provenance_notice"]) is str
             and "MANUALLY_CURATED" in curated["_provenance_notice"],
             "PUBLIC_CURATED_SOURCE_NOT_RAW_OR_MISMATCH")
    try:
        usd_rows = curated["facts"]["us-gaap"][
            "RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    except (KeyError, TypeError):
        raise ValueError("PUBLIC_CURATED_REVENUE_MISSING") from None
    _require(type(usd_rows) is list and len(usd_rows) == 2,
             "PUBLIC_CURATED_EXACT_PAIR_REQUIRED")
    mapping: dict[str, Decimal] = {}
    for row in usd_rows:
        _exact(row, {"start", "end", "val", "accn", "fy", "fp", "form", "filed"},
               "PUBLIC_CURATED_ROW_SCHEMA_INVALID")
        _require(row["accn"] == context["accession"] and row["filed"] == context["filed_at"]
                 and row["form"] == "10-K" and row["fp"] == "FY"
                 and type(row["fy"]) is int and row["fy"] == 2025
                 and type(row["val"]) is int and row["val"] >= 0,
                 "PUBLIC_CURATED_ROW_NOT_10K")
        _require(row["end"] in (prior_end.isoformat(), current_end.isoformat())
                 and row["end"] not in mapping,
                 "PUBLIC_CURATED_PERIOD_DUPLICATE_OR_UNKNOWN")
        expected_start = (prior_start if row["end"] == prior_end.isoformat()
                          else current_start).isoformat()
        _require(row["start"] == expected_start, "PUBLIC_CURATED_PERIOD_MISMATCH")
        mapping[row["end"]] = Decimal(row["val"])
    _require(mapping.get(prior_end.isoformat()) == prior["net_sales"] * 1000000
             and mapping.get(current_end.isoformat()) == current["net_sales"] * 1000000,
             "PUBLIC_ISSUER_PDF_VS_CURATED_SEC_REVENUE_CONFLICT")
    sales_growth = _percent(current["net_sales"], prior["net_sales"])
    ar_growth = _percent(current["accounts_receivable_net"], prior["accounts_receivable_net"])
    ar_gap = (Decimal(ar_growth) - Decimal(sales_growth)).quantize(_DECIMAL_2)
    return {
        "schema": "kuodra.apple-public-manual-baseline.v1",
        "status": "MANUALLY_RECORDED_PUBLISHER_VALUES_AND_CURATED_SEC_NUMBERS_MATCH",
        "issuer": data["issuer"], "cik": data["cik"], "as_of": data["as_of"],
        "source_url": source["url"],
        "source_release_date": source["release_date"],
        "statement_status": data["statement_status"],
        "fiscal_prior_end": prior_end.isoformat(),
        "fiscal_current_end": current_end.isoformat(),
        "unit": "USD_MILLIONS",
        "sales_prior": str(prior["net_sales"]),
        "sales_current": str(current["net_sales"]),
        "sales_growth_pct": sales_growth,
        "net_income_growth_pct": _percent(current["net_income"], prior["net_income"]),
        "operating_cashflow_growth_pct": _percent(current["operating_cash_flow"],
                                                   prior["operating_cash_flow"]),
        "cash_to_net_income_pct": format(
            (current["operating_cash_flow"] / current["net_income"] * 100)
            .quantize(_DECIMAL_2), ".2f"),
        "accounts_receivable_growth_pct": ar_growth,
        "accounts_receivable_minus_sales_growth_pp": format(ar_gap, ".2f"),
        "inventory_growth_pct": _percent(current["inventories"], prior["inventories"]),
        "exploratory_review_signal": ("REVIEW_RECEIVABLE_GROWTH_GAP_GT_10PP"
                                      if ar_gap > Decimal("10") else "NO_THRESHOLD_TRIGGER"),
        "issuer_pdf_original_authenticated_by_software": False,
        "raw_sec_companyfacts_authenticated": False,
        "sec_live_requests": 0,
        "publisher_rights_verified": False,
        "point_in_time_market_price_verified": False,
        "future_outlook_verified": False,
        "fraud_proven": False,
        "investment_recommendation": False,
        "trade_executed": False,
        "limitations": [
            "Apple publisher Q4 financial statements are unaudited; figures were transcribed by an analyst.",
            "The compared 10-K CompanyFacts file is manually curated, not an authenticated SEC API response.",
            "Receivables growth exceeding revenue growth by 10pp is a screening flag, not fraud evidence.",
            "No current issuer SEC filings, stock-market data rights, AI forecasts or industry comparisons authenticated.",
        ],
    }


def run_public_primary_baseline(apple: Any, curated: Any, samsung: Any) -> dict:
    """Two independent primary issuer examples, NEVER a cross-currency comparison."""
    from .evidence_scenarios import verify_growth_claim
    a = analyze_apple_manual_pair(apple, curated)
    s = verify_growth_claim(samsung, "16.20")
    _require(s["state"] == "verified" and s["dart_viewer_verified"] is False
             and s["source_kind"] == "MANUAL_PRIMARY_SOURCE_VERIFICATION",
             "SAMSUNG_MANUAL_PUBLIC_RECEIPT_NOT_REPRODUCED")
    return {
        "schema": "kuodra.two-publisher-offline-financial-baseline.v1",
        "status": "TWO_MANUAL_PUBLIC_ISSUER_ARITHMETIC_CASES_REPRODUCED",
        "apple": a,
        "samsung": {
            "issuer": "Samsung Electronics Co., Ltd. and its subsidiaries",
            "period": "FY2023_TO_FY2024", "unit": "KRW_MILLIONS",
            "reported_growth_pct": s["computed_pct"],
            "source_url": s["source_url"],
            "statement": s["statement"],
            "status": "MANUAL_PUBLISHER_PDF_ARITHMETIC_MATCH",
            "dart_viewer_verified": False,
        },
        "cross_issuer_absolute_comparison": None,
        "cross_issuer_growth_ranking": None,
        "source_authenticated": False,
        "real_world_a_b_c_end_to_end_verified": False,
        "live_api_called": False,
        "ai_generated": False,
        "guard_policy_modified": False,
        "trade_executed": False,
    }


def _read(path: Path) -> dict:
    _require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536,
             "PUBLIC_MANIFEST_INVALID_PATH_OR_SIZE")
    with path.open("rb") as inp:
        raw = inp.read(65537)
    _require(0 < len(raw) <= 65536, "PUBLIC_MANIFEST_TOO_LARGE")
    def no_dups(pairs):
        obj = {}
        for k, v in pairs:
            _require(k not in obj, "PUBLIC_MANIFEST_DUPLICATE_JSON_KEY")
            obj[k] = v
        return obj
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=no_dups,
                          parse_constant=lambda _: (_require(False, "PUBLIC_JSON_NONFINITE")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("PUBLIC_MANIFEST_INVALID_JSON") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline Apple/Samsung manually sourced financial check")
    parser.add_argument("--apple", type=Path, default=APPLE)
    parser.add_argument("--curated", type=Path, default=CURATED)
    parser.add_argument("--samsung", type=Path, default=SAMSUNG)
    args = parser.parse_args(argv)
    report = run_public_primary_baseline(_read(args.apple), _read(args.curated),
                                         _read(args.samsung))
    print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
