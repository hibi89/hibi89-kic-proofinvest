"""P117: bounded offline evidence report for caller-supplied SEC-shaped bytes.

A digest binds this report to declared local SHA values, not to SEC publisher
authenticity or source redistribution rights. Never persist or include originals.
"""
from __future__ import annotations

from hashlib import sha256
import json


def make_local_report(receipt: dict, revenue: dict, original: dict,
                      supplementary: dict) -> dict:
    if (type(receipt) is not dict or type(revenue) is not dict
            or type(original) is not dict or type(supplementary) is not dict):
        raise ValueError("LOCAL_REPORT_INPUT_INVALID")
    if (receipt.get("schema") != "kuodra.local-sec-source-receipt.v1"
            or receipt.get("status") != "local_four_sources_unverified"
            or receipt.get("source_kind") != "CALLER_SUPPLIED_LOCAL_UNAUTHENTICATED"
            or receipt.get("network_requests") != 0
            or receipt.get("http_requests_attempted") != 0
            or receipt.get("live_sec_http_called") is not False
            or receipt.get("source_authenticated") is not False
            or receipt.get("source_rights_verified") is not False
            or receipt.get("trade_executed") is not False
            or type(receipt.get("source_sha256")) is not dict
            or set(receipt["source_sha256"]) != {
                "ticker_map", "submissions", "companyfacts", "original_10k"
            }
            or any(type(d) is not str or len(d) != 64
                   or any(c not in "0123456789abcdef" for c in d)
                   for d in receipt["source_sha256"].values())):
        raise ValueError("LOCAL_RECEIPT_TRUST_INVALID")
    if (revenue.get("status") != "REVENUE_CALCULATED_UNVERIFIED"
            or revenue.get("input_mode") != "LOCAL_UPLOAD_UNAUTHENTICATED"
            or revenue.get("issuer_cik") != receipt.get("cik")
            or revenue.get("ticker") != receipt.get("ticker")
            or revenue.get("accession") != receipt.get("selected_10k_accession")
            or revenue.get("companyfacts_sha256") != receipt["source_sha256"]["companyfacts"]
            or revenue.get("original_10k_sha256") != receipt["source_sha256"]["original_10k"]
            or revenue.get("source_authenticated") is not False
            or revenue.get("source_rights_verified") is not False
            or revenue.get("guard_executed") is not False):
        raise ValueError("LOCAL_REVENUE_TRUST_INVALID")
    policy = original.get("guard_preview")
    if (type(policy) is not dict or policy.get("decision") not in ("HOLD", "REJECT")
            or policy.get("source_authenticated") is not False
            or policy.get("human_approved") is not False
            or policy.get("trade_executed") is not False
            or original.get("cik") != receipt.get("cik")
            or original.get("accession") != receipt.get("selected_10k_accession")
            or original.get("companyfacts_sha256") != receipt["source_sha256"]["companyfacts"]
            or original.get("original_10k_sha256") != receipt["source_sha256"]["original_10k"]
            or original.get("source_authenticated") is not False
            or original.get("guard_executed") is not False
            or original.get("audit_written") is not False):
        raise ValueError("LOCAL_ORIGINAL_GUARD_TRUST_INVALID")
    if (supplementary.get("source_authenticated") is not False
            or supplementary.get("source_rights_verified") is not False
            or supplementary.get("guard_executed") is not False
            or supplementary.get("trade_executed") is not False
            or type(supplementary.get("engine_a")) is not dict
            or type(supplementary.get("engine_c")) is not dict):
        raise ValueError("LOCAL_A_C_TRUST_INVALID")
    report = {
        "schema": "kuodra.local-four-source-review-report.v1",
        "status": "STRUCTURAL_ARITHMETIC_ONLY_UNVERIFIED",
        "source_kind": "CALLER_SUPPLIED_LOCAL_UNAUTHENTICATED",
        "issuer": {
            "ticker": receipt["ticker"], "cik": receipt["cik"],
            "accession": receipt["selected_10k_accession"],
            "filing_date": receipt["selected_10k_filing_date"],
            "as_of": receipt["requested_as_of"],
        },
        "source_sha256": dict(receipt["source_sha256"]),
        "verification": {
            "status": revenue["status"],
            "current_end": revenue["current_end"],
            "prior_end": revenue["prior_end"],
            "current_usd": revenue["current_usd"],
            "prior_usd": revenue["prior_usd"],
            "growth_pct": revenue["growth_pct"],
        },
        "original_context": original["status"],
        "guard_policy_preview": policy["decision"],
        "engine_a_status": supplementary["engine_a"]["status"],
        "engine_c_status": supplementary["engine_c"]["status"],
        "limits": {
            "source_authenticated": False, "source_rights_verified": False,
            "independent_original_authenticated": False,
            "live_sec_http_called": False, "external_http_requests": 0,
            "ai_agent_executed": False, "guard_executed": False,
            "audit_written": False, "human_approved": False,
            "trade_executed": False, "official_contest_submission": False,
        },
    }
    canonical = (json.dumps(report, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    report["report_sha256"] = sha256(canonical).hexdigest()
    return report


def report_json_bytes(report: dict) -> bytes:
    """Serialize for an explicit local browser download, no server write."""
    return (json.dumps(report, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
