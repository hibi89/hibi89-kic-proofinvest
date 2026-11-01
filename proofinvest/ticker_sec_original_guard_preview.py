"""P102 same-source SEC original iXBRL crosscheck and read-only Guard preview.

Reuses the exact P101 receipt/fact verification, existing iXBRL context checks
and existing Guard rules. It does not authenticate the SEC server or original
filing, assert fraud, persist an audit, execute trades or call a remote API.
"""
from __future__ import annotations

from typing import Any

from .dei_identity_review import review_embedded_dei_identity
from .guard_sec_adapter import evaluate_sec_guard
from .ixbrl_revenue_review import review_inline_annual_revenue
from .sec_companyfacts import verify_sec_annual_revenue
from .ticker_research_intake import _json
from .ticker_sec_financial_bridge import inspect_collected_annual_revenue
from .local_sec_packet import _MAX_FILE_BYTES


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.single-ticker-original-guard-preview.v1",
        "status": "UNAVAILABLE",
        "reason_code": reason,
        "ixbrl_status": "unavailable", "ixbrl_reason": None,
        "dei_status": "unavailable", "dei_reason": None,
        "guard_preview": None,
        "source_authenticated": False, "financial_facts_authenticated": False,
        "source_rights_verified": False, "xbrl_taxonomy_validated": False,
        "original_to_accession_authenticated": False,
        "engine_a_ready": False, "engine_b_full_ready": False,
        "engine_c_ready": False, "guard_executed": False,
        "audit_written": False, "ai_interpretation_ready": False,
        "trade_executed": False,
    }


def inspect_original_guard_preview(
    receipt: dict, raw_sources: dict[str, bytes] | None,
    *, expected_revenue: dict | None = None,
) -> dict[str, Any]:
    """Read-only one-source inspection: exact issuer/fiscal checks precede UI.

    Source proof here is strictly within untrusted source bytes, not a SEC
    attribution; the Guard result is a simulated policy preview, NOT audit.
    """
    revenue = inspect_collected_annual_revenue(receipt, raw_sources)
    if revenue.get("status") != "REVENUE_CALCULATED_UNVERIFIED":
        return _blocked("REVENUE_BRIDGE_NOT_ELIGIBLE")
    keys = ("ticker", "issuer_cik", "accession", "filing_date",
            "as_of", "current_end", "prior_end", "current_usd",
            "prior_usd", "growth_pct", "revenue_concept",
            "companyfacts_sha256", "original_10k_sha256", "original_10k_url")
    if expected_revenue is not None and (
        type(expected_revenue) is not dict
        or expected_revenue.get("status") != revenue["status"]
        or any(expected_revenue.get(k) != revenue.get(k) for k in keys)
        or expected_revenue.get("source_authenticated") is not False
        or expected_revenue.get("guard_executed") is not False
    ):
        return _blocked("REVENUE_PREVIEW_CHANGED")
    # The bridge above has already checked all four SHA/byte/CIK/as-of
    # pins, so no standalone forged raw HTML or issuer can reach here.
    try:
        raw = raw_sources["original_10k"]
        facts = _json(raw_sources["companyfacts"], _MAX_FILE_BYTES, "COMPANYFACTS")
        verdict = verify_sec_annual_revenue(
            facts, cik=revenue["issuer_cik"], accession=revenue["accession"],
            current_end=revenue["current_end"], prior_end=revenue["prior_end"],
            as_of=revenue["as_of"],
        )
        if (verdict.get("status") != "calculated_unverified"
                or verdict.get("filing_date") != revenue["filing_date"]
                or any(str(verdict.get(k)) != str(revenue.get(k)) for k in
                       ("current_usd", "prior_usd", "growth_pct", "revenue_concept"))):
            return _blocked("REVENUE_VERDICT_CHANGED")
        dei = review_embedded_dei_identity(raw, cik=revenue["issuer_cik"])
        ixbrl = review_inline_annual_revenue(
            raw, companyfacts=facts, verdict=verdict,
            cik=revenue["issuer_cik"],
        )
        if (dei.get("source_authenticated") is not False
                or ixbrl.get("source_authenticated") is not False
                or ixbrl.get("financial_facts_authenticated") is not False
                or ixbrl.get("xbrl_taxonomy_validated") is not False):
            return _blocked("ORIGINAL_TRUST_CONTRACT_INVALID")
        conflict = dei["status"] in ("conflict", "ambiguous")
        matched = (ixbrl.get("status") ==
                   "local_ixbrl_revenue_context_match_unverified")
        if not conflict and matched:
            preview_verdict = {"status": "calculated_unverified"}
            status, reason = "ORIGINAL_CONTEXT_MATCH_UNVERIFIED", (
                "LOCAL_IXBRL_CONTEXT_AND_COMPANYFACTS_MATCH_NOT_AUTHENTICATION"
            )
        elif conflict:
            preview_verdict = {"status": "conflict"}
            status, reason = "ORIGINAL_SELF_CLAIM_CONFLICT", dei["reason_code"]
        else:
            preview_verdict = {"status": "unavailable"}
            status, reason = "ORIGINAL_EVIDENCE_UNAVAILABLE", ixbrl["reason_code"]
        policy = evaluate_sec_guard(preview_verdict, risk=None)
        guard = policy.get("guard") if type(policy) is dict else None
        if (type(guard) is not dict
                or guard.get("decision") not in ("HOLD", "REJECT")
                or guard.get("source_authenticated") is not False
                or guard.get("trade_executed") is not False
                or guard.get("human_approved") is not False):
            return _blocked("GUARD_PREVIEW_UNSAFE")
        return {
            **_blocked(reason),
            "status": status, "reason_code": reason,
            "ticker": revenue["ticker"], "cik": revenue["issuer_cik"],
            "accession": revenue["accession"],
            "companyfacts_sha256": revenue["companyfacts_sha256"],
            "original_10k_sha256": revenue["original_10k_sha256"],
            "ixbrl_status": ixbrl["status"],
            "ixbrl_reason": ixbrl["reason_code"],
            "dei_status": dei["status"],
            "dei_reason": dei["reason_code"],
            "guard_preview": {
                "decision": guard["decision"],
                "reason_codes": list(guard["reason_codes"]),
                "policy_version": guard["policy_version"],
                "meaning": "RULE_ONLY_NO_AUDIT_OR_AUTHORIZATION",
                "source_authenticated": False,
                "audit_written": False, "human_approved": False,
                "trade_executed": False,
            },
        }
    except (ValueError, TypeError, KeyError, IndexError, OverflowError,
            RecursionError, AttributeError):
        return _blocked("ORIGINAL_REVIEW_UNAVAILABLE")
