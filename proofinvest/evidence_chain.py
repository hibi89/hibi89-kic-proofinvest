"""Offline, evidence-linked Research -> Verification -> Risk preview.

All records are caller-supplied and potentially untrusted. This module does
not fetch filings, certify ownership, authorize redistribution, run an LLM,
or make investment recommendations. It never upgrades caller assertions to
external source authentication.
"""
from __future__ import annotations

from typing import Any, Mapping

from .evidence_scenarios import verify_growth_claim
from .research import normalize_research
from .risk import calculate_verified_debt_to_equity


def _withheld(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "risk_calculated": False,
        "authenticated_external_source": False,
        "ratio_pct": None,
        "triggered": None,
        "reason": reason,
        "withheld_reason_code": "UPSTREAM_EVIDENCE_NOT_LINKED",
    }


def _linked(research: Mapping[str, Any], verification: Mapping[str, Any],
            evidence: Any) -> bool:
    """Require one surviving cited finding to reference the SAME source URL.

    This only proves that the submitted metadata connect; it does NOT prove
    that the publisher, claimed fact or download is genuine.
    """
    if not isinstance(evidence, Mapping):
        return False
    identity = evidence.get("corp_code")
    expected_year = evidence.get("report_year")
    if (not isinstance(identity, str) or len(identity) != 8
            or not identity.isascii() or not identity.isdecimal()
            or type(expected_year) is not int
            or research.get("target", {}).get("id") != identity
            or verification.get("fiscal_year") != expected_year
            or verification.get("source_kind") != "MANUAL_PRIMARY_SOURCE_VERIFICATION"):
        return False
    url = verification.get("source_url")
    sources = research.get("sources", [])
    findings = research.get("findings", [])
    if not isinstance(url, str) or not isinstance(sources, list) or not isinstance(findings, list):
        return False
    ids = {
        s.get("id") for s in sources
        if isinstance(s, Mapping) and s.get("url") == url
        and isinstance(s.get("id"), str)
    }
    return any(
        isinstance(f, Mapping)
        and isinstance(f.get("source_ids"), list)
        and any(sid in ids for sid in f["source_ids"])
        for f in findings
    )


def evaluate_offline_chain(
    *,
    research_request: Any,
    financial_evidence: Any,
    claimed_growth_pct: Any,
    risk_facts: Any = None,
) -> dict[str, Any]:
    """Evaluate 3 bounded modules with provenance gates, never network I/O.

    Upstream risk facts are asserted-by-caller, not actually authenticated.
    Risk calculation (if any) is exploratory and remains clearly unverified.
    """
    out = {
        "mode": "OFFLINE_SUPPLIED_EVIDENCE_CHAIN",
        "ai_agent_executed": False,
        "live_api_called": False,
        "authenticated_external_source": False,
        "source_rights_verified": False,
        "status": "unavailable",
        "research": None,
        "verification": None,
        "trace_linked": False,
        "risk": _withheld("Workflow has not verified its upstream evidence"),
    }
    if not isinstance(research_request, Mapping):
        out["risk"] = _withheld("Research input must be a mapping")
        return out
    research = normalize_research(research_request)
    verification = verify_growth_claim(financial_evidence, claimed_growth_pct)
    out["research"], out["verification"] = research, verification

    linked = _linked(research, verification, financial_evidence)
    out["trace_linked"] = linked
    if research["status"] not in ("success", "partial") or not linked:
        out["risk"] = _withheld("No valid same-issuer finding links to the financial statement source")
        return out
    if verification.get("state") != "verified":
        out["risk"] = _withheld("Growth claim is conflict/unavailable; risk calculation withheld")
        out["status"] = "partial"
        return out

    out["status"] = "partial"
    if not isinstance(risk_facts, list) or len(risk_facts) != 2:
        out["risk"] = _withheld("Liabilities and equity facts not provided")
        return out
    source_url = verification["source_url"]
    year = verification["fiscal_year"]
    issuer = financial_evidence["corp_code"]
    if any(
        not isinstance(f, Mapping)
        or f.get("issuer_id") != issuer
        or f.get("source_url") != source_url
        or f.get("source_kind") != "MANUAL_PRIMARY_SOURCE_VERIFICATION"
        for f in risk_facts
    ):
        out["risk"] = _withheld("Risk facts do not share issuer and source provenance")
        return out
    risk = calculate_verified_debt_to_equity(
        risk_facts, expected_year=year, expected_statement="CFS", demo=False,
    )
    out["risk"] = risk
    if risk["status"] == "calculated":
        out["status"] = "structurally_calculated_unverified"
    return out
