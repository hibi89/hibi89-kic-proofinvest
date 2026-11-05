"""Fact-check human-supplied local model drafts against a pinned real NVIDIA issuer receipt.

No LLM invocation, external HTTP, source-file export, permission inference,
investment advice or automatic trading. Exact financial claims only.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .nvidia_real_issuer_review import actual_nvidia_issuer_receipt, review_nvidia_actual_release

_SCHEMA = "kuodra.nvda-issuer-factual-draft.v1"
_ALLOWED = {
    "revenue_growth_pct": "pct",
    "cfo_to_net_income_2026": "ratio",
    "ar_growth_minus_revenue_pp": "pp",
    "inventory_growth_minus_revenue_pp": "pp",
}
_MAX = 4096


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.nvda-issuer-draft-fact-check.v1",
        "status": "BLOCKED", "reason_code": reason,
        "source_authenticated_by_sec": False,
        "source_commercial_ai_rights_verified": False,
        "llm_invoked": False, "external_network_requests": 0,
        "decision": "HOLD", "investment_recommendation": False,
        "trade_executed": False,
    }


def _pairs(items: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("DUPLICATE_KEY")
        result[key] = value
    return result


def verify_nvidia_factual_draft(proposal_json: bytes) -> dict[str, Any]:
    """Independently re-evaluate 2-4 annual financial claims from a local draft.

    Exact strings are required: a draft cannot round away a mismatched fact.
    An accepted outcome is a local fact-match, not a license or AI correctness
    attestation. Unsupported forecasts/free text are rejected, not sanitized.
    """
    if type(proposal_json) is not bytes or not 0 < len(proposal_json) <= _MAX:
        return _blocked("DRAFT_MISSING_OR_TOO_LARGE")
    try:
        proposal = json.loads(
            proposal_json.decode("utf-8"), object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE")),
        )
        receipt = actual_nvidia_issuer_receipt()
        checked = review_nvidia_actual_release(
            as_of="2026-11-05", receipt=receipt,
        )
        if (
            checked.get("status") != "REAL_NVDA_FY2026_2025_ISSUER_GAAP_REVIEW_LIMITED"
            or checked.get("issuer_original_publisher_seen") is not True
            or checked.get("sec_original_identical") is not False
            or checked.get("commercial_ai_rights_verified") is not False
            or checked.get("guard_policy_preview") != "HOLD"
            or checked.get("trade_executed") is not False
        ):
            return _blocked("ISSUER_REPLAY_OR_RIGHTS_CONTRACT_INVALID")
        if (
            type(proposal) is not dict
            or set(proposal) != {
                "schema", "ticker", "source_sha256", "decision", "claims"
            }
            or proposal.get("schema") != _SCHEMA
            or proposal.get("ticker") != "NVDA"
            or proposal.get("source_sha256") != receipt["source_sha256"]
            or proposal.get("decision") != "HUMAN_REVIEW_ONLY"
        ):
            return _blocked("DRAFT_SCHEMA_ISSUER_OR_SOURCE_MISMATCH")
        claims = proposal["claims"]
        if type(claims) is not list or not 2 <= len(claims) <= len(_ALLOWED):
            return _blocked("TWO_TO_FOUR_DISTINCT_FACTS_REQUIRED")
        actual = checked["evidence"]["metrics"]
        seen: set[str] = set()
        validated = []
        for claim in claims:
            if type(claim) is not dict or set(claim) != {"metric", "value"}:
                return _blocked("FREE_TEXT_OR_UNSUPPORTED_CLAIM")
            metric, value = claim["metric"], claim["value"]
            if (type(metric) is not str or metric not in _ALLOWED or metric in seen
                    or type(value) is not str or value != actual[metric]):
                return _blocked("CLAIM_NOT_SUPPORTED_BY_PINNED_ISSUER_FACTS")
            seen.add(metric)
            validated.append({"metric": metric, "value": value,
                              "unit": _ALLOWED[metric]})
        return {
            **_blocked("LOCAL_PINNED_FINANCIAL_FACT_MATCH_ONLY"),
            "status": "REAL_ISSUER_NUMERIC_FACTS_MATCH_FOR_HUMAN_REVIEW",
            "issuer": "NVDA",
            "annual_period": "FY2026_vs_FY2025",
            "pinned_source_sha256": receipt["source_sha256"],
            "publisher_source_url": receipt["source_url"],
            "pinned_source_ci_run": receipt["source_ci_run"],
            "source_unaudited": True,
            "claim_count": len(validated),
            "claims": validated,
            "draft_sha256": sha256(proposal_json).hexdigest(),
        }
    except (UnicodeError, json.JSONDecodeError, ValueError, KeyError, TypeError,
            AttributeError, RecursionError, OverflowError):
        return _blocked("DRAFT_OR_ISSUER_EVIDENCE_INVALID")
