"""Post-Guard Engine C binding to the *same* selected SEC filing.

Only user-provided, locally reviewed records; no independent authentication.
This never alters Guard evidence, trading policy, SQLite or the original source.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping
import re

from .industry_vision import analyze_industry_vision, parse_industry_vision_json

_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _deny(code: str) -> None:
    raise ValueError(code)


def bind_industry_to_sec(report: Mapping[str, Any], raw: bytes) -> dict:
    """Bind target numeric facts, period, issuer, as-of and claimed source hash.

    CompanyFacts SHA is a local byte pin, NOT a SEC issuer authentication.
    The selected industry indicator is independent and is never a market share.
    """
    if type(report) is not dict or type(raw) is not bytes:
        _deny("INVALID_INDUSTRY_BIND_INPUT")
    issuer = report.get("issuer")
    financial = report.get("verification")
    source = report.get("source")
    guard = report.get("guard")
    if (report.get("schema") != "proofinvest.local-sec-guard-report.v1"
            or not all(type(x) is dict for x in (issuer, financial, source, guard))
            or financial.get("status") != "calculated_unverified"
            or issuer.get("cik") is None or issuer.get("as_of") is None
            or guard.get("decision") not in ("HOLD", "REJECT")
            or guard.get("source_authenticated") is not False):
        _deny("INDUSTRY_REQUIRES_EXISTING_UNAUTHENTICATED_GUARD_REVIEW")
    sec_hash = source.get("companyfacts_sha256")
    if type(sec_hash) is not str or _SHA.fullmatch(sec_hash) is None:
        _deny("INDUSTRY_SEC_SHA_MISSING")
    industry = analyze_industry_vision(
        parse_industry_vision_json(raw),
        expected_issuer_cik=issuer["cik"],
        analysis_as_of=issuer["as_of"],
    )
    periods = industry["periods"]
    if (periods["prior_end"] != financial.get("prior_period_end")
            or periods["current_end"] != financial.get("current_period_end")):
        _deny("INDUSTRY_SEC_FISCAL_PERIOD_MISMATCH")
    try:
        target = industry["target"]
        prior = Decimal(str(financial["prior_amount"]))
        current = Decimal(str(financial["current_amount"]))
        target_prior = Decimal(target["prior_revenue_usd"])
        target_current = Decimal(target["current_revenue_usd"])
        recorded_growth = Decimal(str(financial["growth_pct"]))
    except (KeyError, InvalidOperation, ValueError, TypeError):
        _deny("INDUSTRY_SEC_REVENUE_INVALID")
    if (not all(n.is_finite() for n in (prior, current, target_prior,
                                        target_current, recorded_growth))
            or target_prior != prior or target_current != current):
        _deny("INDUSTRY_SEC_REVENUE_MISMATCH")
    if target_prior <= 0 or recorded_growth != (
            (target_current - target_prior) / target_prior * 100
    ).quantize(Decimal("0.01")):
        _deny("INDUSTRY_SEC_GROWTH_INCONSISTENT")

    # Both prior and current annual CompanyFacts values are selected from the
    # same locally reviewed snapshot. Do not join a different unreviewed issuer
    # source simply because its reported amount happens to match.
    sources = {s["id"]: s for s in industry["sources"]}
    refs = target["source_ids"]
    filing_date = issuer.get("filing_date")
    if (type(filing_date) is not str
            or any(ref not in sources
                   or sources[ref]["sha256"] != sec_hash
                   or sources[ref]["published_at"] < filing_date
                   for ref in refs)):
        _deny("INDUSTRY_TARGET_SOURCE_NOT_PINNED_TO_SEC")
    if (industry["source_authenticated"] is not False
            or industry["industry_outlook_verified"] is not False
            or industry["guard_decision_changed"] is not False
            or industry["trade_signal"] is not False):
        _deny("INDUSTRY_UNVERIFIED_TRUST_CONTRACT")
    industry["input_sha256"] = sha256(raw).hexdigest()
    industry["audit_included"] = False
    industry["sec_revenue_link"] = {
        "status": "LOCALLY_MATCHED_NUMERIC_INPUT_UNAUTHENTICATED",
        "companyfacts_sha256": sec_hash,
        "prior_amount": str(prior), "current_amount": str(current),
        "growth_pct": str(recorded_growth),
        "prior_end": periods["prior_end"], "current_end": periods["current_end"],
        "filing_date": filing_date, "source_authenticated": False,
        "original_sec_bytes_authenticated": False,
    }
    return industry


def summarize_three_engines(report: Mapping[str, Any]) -> dict:
    """A descriptive evidence ledger: NO score and NO merged Guard decision."""
    if type(report) is not dict or report.get("schema") != "proofinvest.local-sec-guard-report.v1":
        _deny("INVALID_THREE_ENGINE_REPORT")
    issuer, guard = report.get("issuer"), report.get("guard")
    if (type(issuer) is not dict or type(guard) is not dict
            or guard.get("decision") not in ("HOLD", "REJECT")
            or guard.get("source_authenticated") is not False):
        _deny("UNSAFE_THREE_ENGINE_GUARD")
    a = report.get("market_reality")
    b = report.get("accounting_integrity")
    c = report.get("industry_vision")
    if type(b) is not dict or b.get("source_authenticated") is not False:
        _deny("ENGINE_B_EVIDENCE_REQUIRED")
    for module, valid in ((a, {"REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE"}),
                          (c, {"OBSERVED_COMPARISON_UNVERIFIED", "INSUFFICIENT_EVIDENCE"})):
        if module is not None and (
                type(module) is not dict or module.get("status") not in valid
                or module.get("source_authenticated") is not False
                or module.get("issuer_cik") != issuer.get("cik")
                or module.get("as_of") != issuer.get("as_of")
                or module.get("audit_included") is not False):
            _deny("THREE_ENGINE_INCOMPATIBLE_CONTEXT")
    return {
        "schema": "kuodra.three-engine-evidence-ledger.v1",
        "issuer_cik": issuer["cik"], "as_of": issuer["as_of"],
        "A_market_reality": a["status"] if a else "NO_INPUT",
        "B_financial_integrity": b["status"],
        "C_industry_vision": c["status"] if c else "NO_INPUT",
        "guard_decision_unchanged": guard["decision"],
        "all_three_inputs_present": a is not None and c is not None,
        "source_authenticated": False,
        "combined_risk_score_available": False,
        "market_outlook_verified": False,
        "market_bubble_or_fraud_proven": False,
        "ai_generated": False, "trade_signal": False,
        "audit_included": False,
        "description": (
            "Independent statistical, accounting and industry observations; "
            "absence of an engine is NO_INPUT, never a safe verdict. "
            "No calibrated combined risk score or future market forecast."
        ),
    }
