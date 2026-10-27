"""Deterministic offline risk screening of untrusted financial evidence.

No issuer authentication, investment recommendation, external API or trading.
"""
from __future__ import annotations
from typing import Any
import re


def screen_local_evidence(financial: Any, source_span: Any) -> dict[str, Any]:
    flags = ["SOURCE_ORIGIN_UNAUTHENTICATED"]
    result: dict[str, Any] = {
        "schema": "proofinvest.local-risk-screen.v1",
        "status": "unavailable",
        "reason_codes": flags,
        "source_authenticated": False,
        "investment_recommendation": False,
        "trade_authorized": False,
    }
    if not isinstance(financial, dict) or not isinstance(source_span, dict):
        flags.append("INPUT_SECTIONS_MISSING")
        return result
    if financial.get("status") == "conflict":
        flags.append("CLAIMED_GROWTH_CONFLICT")
        return result
    if financial.get("status") != "calculated_unverified":
        flags.append("FINANCIAL_CALCULATION_UNAVAILABLE")
        return result
    if not isinstance(source_span.get("original_sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", source_span["original_sha256"]) is None:
        flags.append("SOURCE_DIGEST_MISSING")
        return result
    if type(source_span.get("start_byte")) is not int or type(source_span.get("end_byte_exclusive")) is not int or source_span["start_byte"] < 0 or source_span["end_byte_exclusive"] <= source_span["start_byte"]:
        flags.append("SOURCE_SPAN_INVALID")
        return result
    flags.append("LOCAL_EVIDENCE_REVIEW_ONLY")
    result["status"] = "reviewed_unverified"
    return result
