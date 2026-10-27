"""Offline, fail-closed peer screening with explicit rationale.

Peer metadata are supplied by the caller, not verified real-world facts.
A matching profile is only a candidate FOR REVIEW, never a certified peer.
No API, valuation, issuer identity lookup, or legal rights verification.
"""
from __future__ import annotations

from typing import Any, Mapping

_CRITERIA = ("industry_code", "product_group", "business_model", "market_region",
             "size_band", "fiscal_year", "fs_div", "currency")


def _valid_profile(item: Any) -> bool:
    if not isinstance(item, Mapping):
        return False
    if not isinstance(item.get("issuer_id"), str) or not item["issuer_id"].strip():
        return False
    for field in _CRITERIA:
        value = item.get(field)
        if field == "fiscal_year":
            if type(value) is not int or not 2015 <= value <= 2100:
                return False
        elif not isinstance(value, str) or not value.strip():
            return False
    return item["fs_div"] in ("CFS", "OFS")


def _source_ids(item: Mapping[str, Any], accepted: set[str]) -> bool:
    ids = item.get("source_ids")
    return (isinstance(ids, list) and bool(ids)
            and all(isinstance(s, str) and s.strip() and s in accepted for s in ids))


def screen_peer_candidates(
    target: Any, peers: Any, research_result: Any,
) -> dict[str, Any]:
    """Screen supplied peer profiles by comparable attributes and cited IDs.

    A matching candidate remains provisional because even a Research
    'success' means only that supplied citation metadata is structurally
    well-formed. It does not authenticate industry classification, source
    truth, scale, or permission to reuse third-party data.
    """
    out = {
        "status": "unavailable",
        "scope": "OFFLINE_PROVISIONAL_PEER_SCREEN",
        "verified_real_company_peers": False,
        "criteria": list(_CRITERIA),
        "candidates": [],
        "warnings": [],
    }
    if not _valid_profile(target) or not isinstance(peers, list):
        out["warnings"].append("invalid_target_or_candidate_collection")
        return out
    if not isinstance(research_result, Mapping) or research_result.get("status") not in ("success", "partial"):
        out["warnings"].append("no_usable_research_evidence")
        return out
    sources = research_result.get("sources")
    if not isinstance(sources, list) or not all(isinstance(s, Mapping) for s in sources):
        out["warnings"].append("malformed_research_sources")
        return out
    ids = [s.get("id") for s in sources]
    if any(not isinstance(s, str) or not s.strip() for s in ids) or len(set(ids)) != len(ids):
        out["warnings"].append("invalid_research_source_ids")
        return out
    accepted = set(ids)
    # A registered source is not by itself support for a peer profile.
    # Only IDs actually cited by surviving Research findings are eligible.
    # Research output is also caller-supplied: a forged "success" status
    # must not turn uncited or malformed records into peer evidence.
    findings = research_result.get("findings")
    if (not isinstance(findings, list) or not findings or any(
        not isinstance(finding, Mapping)
        or not isinstance(finding.get("claim"), str)
        or not finding["claim"].strip()
        or not isinstance(finding.get("source_ids"), list)
        or not finding["source_ids"]
        or any(not isinstance(sid, str) or sid not in accepted
               for sid in finding["source_ids"])
        for finding in findings
    )):
        out["warnings"].append("malformed_or_uncited_research_findings")
        return out
    cited = {sid for finding in findings for sid in finding["source_ids"]}
    if not _source_ids(target, cited):
        out["warnings"].append("target_evidence_missing")
        return out

    # A duplicated issuer cannot be resurrected by changing the ordering.
    counts: dict[str, int] = {}
    for candidate in peers:
        if isinstance(candidate, Mapping) and isinstance(candidate.get("issuer_id"), str):
            issuer_id = candidate["issuer_id"]
            counts[issuer_id] = counts.get(issuer_id, 0) + 1
    seen: set[str] = set()
    for index, candidate in enumerate(peers):
        if not isinstance(candidate, Mapping) or not isinstance(candidate.get("issuer_id"), str):
            out["warnings"].append(f"invalid_candidate[{index}]")
            continue
        cid = candidate["issuer_id"]
        if cid in seen:
            continue
        seen.add(cid)
        mismatches = []
        if counts[cid] != 1:
            mismatches.append("duplicate_issuer_id")
        if not _valid_profile(candidate):
            mismatches.append("missing_comparison_metadata")
        if cid == target["issuer_id"]:
            mismatches.append("same_issuer_as_target")
        if not _source_ids(candidate, cited):
            mismatches.append("candidate_evidence_missing")
        if _valid_profile(candidate):
            mismatches.extend(field for field in _CRITERIA if candidate[field] != target[field])
        out["candidates"].append({
            "issuer_id": cid,
            "state": "excluded" if mismatches else "candidate_for_review",
            "reasons": mismatches or ["profile_match_with_traceable_but_unverified_sources"],
            "source_ids": list(candidate.get("source_ids", []))
                if isinstance(candidate.get("source_ids"), list)
                and all(isinstance(s, str) for s in candidate["source_ids"]) else [],
            "authenticated_external_source": False,
        })
    if any(c["state"] == "candidate_for_review" for c in out["candidates"]):
        out["status"] = "candidates_for_review"
    return out
