"""P56 offline Engine B replay of manually transcribed *real issuer numbers*.

The derived in-memory SEC-shaped record is NOT a SEC CompanyFacts API response.
This reuses the genuine Engine B numeric algorithm, but cannot establish data
origin, licensing, point-in-time availability, fraud, Guard eligibility or trades.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

from .accounting_integrity import review_accounting_integrity
from .public_primary_baseline import (
    APPLE, CURATED, _read, analyze_apple_manual_pair,
)

_SCALE = 1_000_000
_REVENUE = "RevenueFromContractWithCustomerExcludingAssessedTax"
_FACTS = {
    "NetIncomeLoss": "net_income",
    "OperatingIncomeLoss": "operating_income",
    "NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
}
_INSTANT = {
    "AccountsReceivableNetCurrent": "accounts_receivable_net",
    "InventoryNet": "inventories",
}


def _checked(assertion: bool, code: str) -> None:
    if not assertion:
        raise ValueError(code)


def _dollars(data: dict, key: str) -> int:
    # The P55 validator must run before _dollars. Reject floats, booleans and
    # any unreviewed numeric representation independently here too.
    value = data.get(key)
    _checked(type(value) is str and value.isascii() and value.isdecimal()
             and str(int(value)) == value, "DERIVED_AMOUNT_INVALID")
    return int(value) * _SCALE


def _annual(amount: int, period: dict, accession: str, filed: str) -> dict:
    return {
        "accn": accession, "form": "10-K", "start": period["start"],
        "end": period["end"], "filed": filed, "val": amount,
    }


def _instant(amount: int, period: dict, accession: str, filed: str) -> dict:
    return {
        "accn": accession, "form": "10-K", "end": period["end"],
        "filed": filed, "val": amount,
    }


def replay_manual_apple_through_engine_b(manual: Any, curated: Any) -> dict:
    """Check first-party transcription, then execute actual Engine B offline.

    A derived SEC-shaped *test adapter* is created and destroyed in memory.
    The adapter is never written or exported as an original SEC data file.
    The output contains only source-labeled, non-authoritative observations.
    """
    baseline = analyze_apple_manual_pair(manual, curated)
    accession = manual["filing_context"]["accession"]
    filed = manual["filing_context"]["filed_at"]
    original_revenue = curated["facts"]["us-gaap"][_REVENUE]
    usgaap = {_REVENUE: deepcopy(original_revenue)}
    current, prior = manual["current"], manual["prior"]

    for tag, key in _FACTS.items():
        usgaap[tag] = {"units": {"USD": [
            _annual(_dollars(current, key), current, accession, filed)
        ]}}
    for tag, key in _INSTANT.items():
        usgaap[tag] = {"units": {"USD": [
            _instant(_dollars(current, key), current, accession, filed),
            _instant(_dollars(prior, key), prior, accession, filed),
        ]}}

    # Include the explicitly manually curated revenue rows, not the entirety
    # of any raw SEC blob. No original PDF/SEC file is held or persisted.
    derived = {
        "cik": 320193, "entityName": "Apple Inc.",
        "facts": {"us-gaap": usgaap},
    }
    derived_bytes = json.dumps(derived, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True).encode("ascii")
    core = review_accounting_integrity(
        derived_bytes, cik=manual["cik"], accession=accession,
        current_end=current["end"], prior_end=prior["end"], as_of=manual["as_of"],
    )
    _checked(core.get("schema") == "kuodra.accounting-integrity-offline.v1"
             and core.get("status") == "reviewed_unverified"
             and core.get("working_capital_review_status") == "REVIEWED_UNVERIFIED"
             and core.get("filing_date") == filed
             and core.get("period_end") == current["end"]
             and core.get("source_authenticated") is False
             and core.get("accounting_fraud_proven") is False
             and core.get("guard_policy_modified") is False
             and core.get("ai_generated") is False
             and core.get("trade_executed") is False
             and core.get("live_api_called") is False,
             "DERIVED_ENGINE_B_TRUST_OR_STATUS_MISMATCH")

    expected = {
        "net_income_usd": str(_dollars(current, "net_income")),
        "operating_income_usd": str(_dollars(current, "operating_income")),
        "operating_cashflow_usd": str(_dollars(current, "operating_cash_flow")),
        "earnings_less_cash_usd": str(
            _dollars(current, "net_income") - _dollars(current, "operating_cash_flow")),
        "revenue_growth_pct": baseline["sales_growth_pct"],
        "receivables_growth_pct": baseline["accounts_receivable_growth_pct"],
        "inventory_growth_pct": baseline["inventory_growth_pct"],
        "cash_to_net_income_pct": baseline["cash_to_net_income_pct"],
        "receivables_minus_revenue_growth_pp":
            baseline["accounts_receivable_minus_sales_growth_pp"],
    }
    _checked(all(core.get(k) == v for k, v in expected.items()),
             "DERIVED_ENGINE_B_DISAGREES_WITH_PRIMARY_MANUAL_REPLAY")
    _checked(core.get("working_capital_signals") ==
             (["RECEIVABLES_OUTPACED_REVENUE"]
              if baseline["exploratory_review_signal"] ==
              "REVIEW_RECEIVABLE_GROWTH_GAP_GT_10PP" else []),
             "DERIVED_ENGINE_B_REVIEW_SIGNAL_DISAGREEMENT")
    _checked(core.get("inventory_minus_revenue_growth_pp") is not None,
             "DERIVED_ENGINE_B_INVENTORY_GAP_UNAVAILABLE")
    return {
        "schema": "kuodra.issuer-manual-engine-b-replay.v1",
        "status": "ENGINE_B_CODE_EXECUTED_ON_DERIVED_UNAUTHENTICATED_SEC_SHAPE",
        "issuer": "Apple Inc.", "cik": manual["cik"],
        "as_of": manual["as_of"],
        "manual_source_url": baseline["source_url"],
        "fiscal_current_end": baseline["fiscal_current_end"],
        "unit": "USD", "amounts_based_on_usd_millions": True,
        "manual_issuer_statement": "UNAUDITED_PUBLISHER_RELEASE",
        "reconstructed_sec_shape_not_raw_api": True,
        "curated_10k_revenue_not_raw_sec_response": True,
        "derived_input_sha256_not_original_sec": sha256(derived_bytes).hexdigest(),
        "engine_b_status": core["status"],
        "engine_b_reason_code": core["reason_code"],
        "engine_b_earnings_cash_signal": core["earnings_cash_signal"],
        "engine_b_working_capital_signals": core["working_capital_signals"],
        "engine_b_working_capital_review_status":
            core["working_capital_review_status"],
        "engine_b_observations": {
            **expected,
            "inventory_minus_revenue_growth_pp":
                core["inventory_minus_revenue_growth_pp"],
        },
        "engine_b_core_source_authenticated": False,
        "manual_source_authenticated_by_software": False,
        "actual_sec_raw_companyfacts_used": False,
        "original_filing_html_used": False,
        "automatic_sec_to_guard_end_to_end_verified": False,
        "issuer_pdf_original_sha256_authenticated": False,
        "provider_rights_verified": False,
        "fraud_proven": False,
        "source_authenticated": False,
        "guard_decision_modified": False,
        "future_growth_forecast": None,
        "investment_recommendation": False,
        "trade_executed": False,
        "network_requests": 0,
        "persistent_derived_record_written": False,
        "limitations": [
            "Actual Apple published figures were manually transcribed, not raw SEC API rows.",
            "SEC-shaped values are a temporary test adapter only; its SHA is NOT an original SEC SHA.",
            "Core Engine B numeric execution is real; source authenticity, rights and filing HTML are not verified.",
            "Working-capital threshold is a review heuristic; it cannot prove fraud or predict returns.",
            "This example is not a production SEC/Guard, market or industry A/B/C integration test.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline manual Apple FY25 Engine B numeric replay")
    parser.add_argument("--manual", default=APPLE, type=str)
    parser.add_argument("--curated", default=CURATED, type=str)
    args = parser.parse_args(argv)
    from pathlib import Path
    result = replay_manual_apple_through_engine_b(
        _read(Path(args.manual)), _read(Path(args.curated)),
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
