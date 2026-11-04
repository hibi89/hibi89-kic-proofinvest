"""P207 real first-party Dell issuer working-capital CI evidence -> human-only review.

This is an immutable summary of a genuine bounded issuer HTTPS P207 CI run.
Replaying published source SHA and numeric values does NOT authenticate SEC
EDGAR bytes, copyright/commercial/LLM rights, real prices or peer coverage.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .dell_2026_publisher_evidence import (
    actual_p195_source_receipt, review_verified_dell_first_party_raw_evidence,
)
from .dell_earnings_release_2026_once import _URL

_P207_SHA = "f81e42b0eb2c1b02379510486cd57b8201445ddfbfcfcf042520f106baeb9b06"
_P195_SHA = "c48524018e82710057f6ef7cb27b665c4c7f4a39b65b02973417de0d68a5a4ac"
_RUN = "https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41896986379"
_SOURCE_COMMIT = "b1d493d81c483fc8de9704d12b26a36473c72d44"


def actual_working_capital_receipt() -> dict[str, Any]:
    """Recorded from P207 actual official issuer GET; NOT a new live fetch."""
    return {
        "run": _RUN, "source_commit": _SOURCE_COMMIT,
        "source_url": _URL, "source_sha256": _P207_SHA,
        "source_bytes": 594207,
        "issuer": "DELL",
        "fiscal_2026_end": "2026-01-30",
        "fiscal_2025_end": "2025-01-31",
        "source_is_unaudited": True,
        "p206_prior_byte_identical": False,
        "rights_verified": False, "sec_original_identical": False,
        "annual_revenue_usd_millions": ("113538", "95567"),
        "receivables_usd_millions": ("17585", "10298"),
        "inventory_usd_millions": ("10437", "6716"),
        "current_assets_usd_millions": ("57602", "36229"),
        "trades": 0,
    }


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p207-real-working-capital-review.v1",
        "status": "BLOCKED", "reason_code": reason,
        "evidence": None, "real_issuer_working_capital_source_seen": False,
        "sec_original_identical": False, "rights_verified": False,
        "licensed_market_peer_available": False,
        "ai_grounded_real_financials": False,
        "full_engine_b_complete": False, "full_abc_ready": False,
        "guard_policy_preview": "HOLD",
        "trade_executed": False, "network_requests": 0,
    }


def review_real_working_capital(*, reviewed_as_of: str, receipt: dict[str, Any]) -> dict[str, Any]:
    """Recompute three FY working-capital screening deltas from pinned real receipts."""
    if reviewed_as_of != "2026-11-05":
        return _blocked("REVIEW_VINTAGE_INVALID")
    if type(receipt) is not dict or receipt != actual_working_capital_receipt():
        return _blocked("GENUINE_P207_ISSUER_RECEIPT_CHANGED")
    old = review_verified_dell_first_party_raw_evidence(
        as_of=reviewed_as_of, receipt=actual_p195_source_receipt()
    )
    e = old.get("evidence")
    if (old.get("status") != "DELL_REAL_FIRST_PARTY_ORIGINAL_NUMERIC_REVIEW_READY_LIMITED"
            or type(e) is not dict
            or e.get("raw_original_bytes_sha256") != _P195_SHA
            or e.get("revenue_2026_usd_millions") != receipt["annual_revenue_usd_millions"][0]
            or e.get("revenue_2025_usd_millions") != receipt["annual_revenue_usd_millions"][1]
            or e.get("fiscal_year_end") != receipt["fiscal_2026_end"]
            or e.get("prior_year_end") != receipt["fiscal_2025_end"]):
        return _blocked("P195_FIRST_PARTY_REVENUE_NOT_VERIFIED")
    try:
        revenue_now, revenue_before = (
            Decimal(x) for x in receipt["annual_revenue_usd_millions"]
        )
        revenue_growth = (revenue_now / revenue_before - 1) * 100
        if revenue_before <= 0 or revenue_growth <= 0:
            return _blocked("REVENUE_DENOMINATOR_INVALID")
        values = {}
        for label, key in (
            ("trade_receivables", "receivables_usd_millions"),
            ("inventories", "inventory_usd_millions"),
            ("current_assets", "current_assets_usd_millions"),
        ):
            now, before = (Decimal(x) for x in receipt[key])
            if now <= 0 or before <= 0:
                return _blocked("ASSET_DENOMINATOR_INVALID")
            growth = (now / before - 1) * 100
            values[label] = {
                "fy2026_usd_millions": str(now),
                "fy2025_usd_millions": str(before),
                "growth_pct": str(growth.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "growth_minus_revenue_pp": str((growth-revenue_growth).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)),
            }
        if (values["trade_receivables"]["growth_pct"] != "70.76"
                or values["trade_receivables"]["growth_minus_revenue_pp"] != "51.96"
                or values["inventories"]["growth_pct"] != "55.41"
                or values["inventories"]["growth_minus_revenue_pp"] != "36.60"):
            return _blocked("P207_ACTUAL_PRIMARY_SOURCE_NUMERIC_REPLAY_CONFLICT")
        return {
            **_blocked("ACTUAL_SOURCE_DATA_NOT_COMMERCIAL_RIGHTS_OR_FRAUD_PROOF"),
            "status": "P207_ACTUAL_ISSUER_WORKING_CAPITAL_REVIEW_LIMITED",
            "real_issuer_working_capital_source_seen": True,
            "evidence": {
                "source_url": _URL, "source_sha256": _P207_SHA,
                "source_bytes": receipt["source_bytes"],
                "actual_one_shot_ci": _RUN,
                "revenue_growth_pct": str(revenue_growth.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "asset_rows": values,
                "source_is_unaudited": True,
                "source_wrapped_html_changed_vs_p206": True,
                "signal": "FUNDAMENTALS_WORKING_CAPITAL_GROWTH_DIVERGENCE_REVIEW",
                "misconduct_proven": False, "trade_executed": False,
            },
        }
    except (ValueError, TypeError, OverflowError, ArithmeticError, KeyError):
        return _blocked("P207_REVIEW_RECEIPT_MALFORMED")
