"""Risk input gate: refuse unverified or incomparable financial facts.

This is a local, offline structural gate, NOT an authenticity checker.
The evidence's 'verified' label is an asserted result of an upstream
Verification step, and is not accepted as proof of a real DART request.
No numeric risk is calculated here; 11/01 risk edge cases are separate.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping
from urllib.parse import urlsplit
import re

from .engine import amount

_REQUIRED = frozenset({"liabilities", "equity"})
_ALLOWED_PROVENANCE = frozenset({"MANUAL_PRIMARY_SOURCE_VERIFICATION", "SYNTHETIC_FIXTURE"})


def _source_url_valid(value: Any) -> bool:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and parsed.hostname is not None
            and "." in parsed.hostname
            and not parsed.username and not parsed.password
            and parsed.port != 0
        )
    except ValueError:
        return False


def gate_verified_risk_inputs(
    facts: Any, *,
    expected_year: int,
    expected_statement: str = "CFS",
    demo: bool = False,
) -> dict[str, Any]:
    """Allow downstream debt/equity checks only from two matching checked facts.

    Contract is INTERNAL to Risk. 'eligible' means structurally safe for
    downstream calculation, not independently authenticated or investment-safe.
    """
    result: dict[str, Any] = {
        "status": "unavailable",
        "rule": "debt_to_equity_pct",
        "input_gate": "VERIFIED_ONLY_OFFLINE",
        "is_demo": demo,
        "authenticated_external_source": False,
        "risk_calculated": False,
        "facts": {},
        "source_url": None,
        "reason": "",
    }

    def stop(reason: str) -> dict[str, Any]:
        result["reason"] = reason
        return result

    if type(expected_year) is not int or not 2015 <= expected_year <= 2100:
        return stop("Invalid fiscal year")
    if expected_statement not in ("CFS", "OFS") or type(demo) is not bool:
        return stop("Invalid statement or demo mode")
    if not isinstance(facts, list) or len(facts) != 2 or any(not isinstance(x, Mapping) for x in facts):
        return stop("Two explicitly checked financial facts required")

    by_metric: dict[str, Mapping[str, Any]] = {}
    for fact in facts:
        metric = fact.get("metric")
        if not isinstance(metric, str) or metric not in _REQUIRED or metric in by_metric:
            return stop("Missing, duplicate or unrelated financial metric")
        by_metric[metric] = fact
    if set(by_metric) != _REQUIRED:
        return stop("Required liabilities and equity facts not supplied")

    normalized: dict[str, Decimal] = {}
    basis: tuple[str, str, str, str] | None = None
    for metric in ("liabilities", "equity"):
        fact = by_metric[metric]
        if fact.get("state") != "verified":
            return stop("Risk fact is not verified")
        if fact.get("year") != expected_year or fact.get("fs_div") != expected_statement:
            return stop("Different fiscal years or financial statement types")
        if fact.get("unit") != "KRW":
            return stop("Missing or incompatible amount unit")
        if fact.get("report_code") != "11011":
            return stop("Not annual financial disclosure")
        period_end = fact.get("period_end")
        if period_end != f"{expected_year}-12-31":
            return stop("Inconsistent period end")
        issuer_id = fact.get("issuer_id")
        if not isinstance(issuer_id, str) or not re.fullmatch(r"\d{8}", issuer_id):
            return stop("Issuer code unavailable")
        evidence_ref = fact.get("evidence_ref")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            return stop("Missing specific evidence reference")
        url = fact.get("source_url")
        if not _source_url_valid(url):
            return stop("No valid HTTPS source link")
        kind = fact.get("source_kind")
        if kind not in _ALLOWED_PROVENANCE or (kind == "SYNTHETIC_FIXTURE" and not demo):
            return stop("Unapproved source provenance for this mode")
        if demo and kind != "SYNTHETIC_FIXTURE":
            return stop("Live and synthetic provenance cannot be mixed")
        value = amount(fact.get("current_amount"))
        if value is None:
            return stop("Financial amount unavailable or malformed")
        normalized[metric] = value
        current_basis = (issuer_id, evidence_ref, url, kind)
        if basis is not None and basis != current_basis:
            return stop("Financial facts refer to different issuers or source reports")
        basis = current_basis

    result["status"] = "eligible"
    result["facts"] = {metric: str(normalized[metric]) for metric in ("liabilities", "equity")}
    result["source_url"] = basis[2] if basis else None
    result["year"] = expected_year
    result["fs_div"] = expected_statement
    result["unit"] = "KRW"
    result["source_kind"] = basis[3] if basis else None
    result["reason"] = (
        "Both input facts have verified labels and matching metadata; "
        "origin authenticity and numeric risk still require separate verification"
    )
    return result
