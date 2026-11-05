"""One local operator click: publisher-supported NVDA Engine B + untrusted local
market A + first-party historical AMD/Intel peer C. Human-only, not completed
A/B/C, licensed data, provider-origin proof, SEC bytes or investment advice.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .real_issuer_local_market import verify_derived_ab_checksum
from .real_issuer_ticker_review import review_supported_real_ticker
from .intel_amd_peer_cohort import review_two_official_10k_peers

_SCHEMA = "kuodra.p224-partial-source-bound-abc.v1"
_STATUS = "REAL_ISSUER_B_LOCAL_A_PEER_C_PARTIAL_UNVERIFIED"


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _blocked(reason: str) -> dict[str, Any]:
    return {"schema": _SCHEMA, "status": "BLOCKED", "reason": reason,
            "guard_policy_preview": "HOLD", "full_abc_complete": False,
            "market_rights_verified": False, "peer_rights_verified": False,
            "trade_executed": False, "network_requests": 0}


def build_partial_source_bound_abc(
    *, ab_review: dict[str, Any],
    peer_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if type(ab_review) is not dict or not verify_derived_ab_checksum(ab_review):
        return _blocked("INVALID_AB_SOURCE_CHECKSUM")
    if (ab_review.get("ticker") != "NVDA"
            or ab_review.get("as_of") != "2026-11-05"
            or ab_review.get("benchmark") != "NASDAQ_100"
            or ab_review.get("submitted_ndx_symbol") != "NDX"
            or ab_review.get("guard_policy_preview") != "HOLD"
            or ab_review.get("full_abc_complete") is not False
            or ab_review.get("source_authenticated_by_sec") is not False
            or ab_review.get("commercial_reuse_allowed") is not False
            or ab_review.get("market_rights_verified") is not False
            or ab_review.get("stock_provider_authenticated") is not False
            or ab_review.get("ndx_provider_authenticated") is not False
            or ab_review.get("trade_executed") is not False):
        return _blocked("AB_IDENTITY_OR_RIGHTS_MISMATCH")
    issuer=review_supported_real_ticker("NVDA",as_of="2026-11-05")
    b=ab_review.get("engine_b")
    if (issuer.get("status") != "REAL_ISSUER_HUMAN_REVIEW_ONLY"
            or issuer.get("publisher_original_observed") is not True
            or issuer.get("source_rights_verified") is not False
            or issuer.get("source_authenticated_by_sec") is not False
            or issuer.get("guard_policy_preview") != "HOLD"
            or ab_review.get("issuer_source_sha256") != issuer.get("source_sha256")
            or ab_review.get("issuer_source_url") != issuer.get("source_url")
            or ab_review.get("cik") != issuer.get("cik")
            or type(b) is not dict
            or b.get("issuer_financial_source_sha256") != issuer.get("source_sha256")
            or b.get("issuer_source_ci_run") != issuer.get("source_ci_run")
            or b.get("fiscal_latest_end") != issuer.get("fiscal_latest_end")
            or b.get("fiscal_prior_end") != issuer.get("fiscal_prior_end")
            or b.get("revenue_growth_pct") != issuer.get("issuer_revenue_growth_pct")
            or b.get("cashflow_to_net_income_ratio") != issuer.get("cashflow_to_net_income_ratio")
            or b.get("receivables_minus_revenue_growth_pp") != issuer.get("receivables_minus_revenue_growth_pp")
            or b.get("inventory_minus_revenue_growth_pp") != issuer.get("inventory_minus_revenue_growth_pp")):
        return _blocked("PUBLISHER_B_NUMERIC_REPLAY_FAILED")
    authentic_peer=review_two_official_10k_peers(ticker="NVDA",reviewed_as_of="2026-11-05")
    if peer_review is None:
        peer_review=authentic_peer
    if (type(peer_review) is not dict or peer_review != authentic_peer
            or authentic_peer.get("status") != "TWO_DISTINCT_AUDITED_PEER_REFERENCES_LIMITED"
            or authentic_peer.get("target_ticker") != "NVDA"
            or authentic_peer.get("real_nvda_issuer_original_source_sha256") != issuer["source_sha256"]
            or authentic_peer.get("peer_count") != 2
            or authentic_peer.get("fiscal_end_offsets_days") != {"AMD": 29, "INTC": 29}
            or authentic_peer.get("peer_rights_verified") is not False
            or authentic_peer.get("engine_c_complete") is not False
            or authentic_peer.get("full_abc_complete") is not False
            or authentic_peer.get("trade_executed") is not False
            or authentic_peer.get("guard_policy_preview") != "HOLD"):
        return _blocked("PEER_C_SOURCE_REPLAY_FAILED")
    try:
        rows=authentic_peer["revenue_growth_observations_not_sector_rank"]
        if (type(rows) is not list or len(rows) != 3
                or [x["ticker"] for x in rows] != ["NVDA","AMD","INTC"]
                or rows[0]["actual_source_sha256"] != issuer["source_sha256"]
                or rows[1]["actual_source_sha256"] is not None
                or rows[2]["actual_source_sha256"] is not None):
            return _blocked("PEER_LIST_PROVENANCE_MISMATCH")
        ab=json.loads(_canonical(ab_review))
        c={
            "status": authentic_peer["status"], "peer_count": 2,
            "issuer_source_sha256": issuer["source_sha256"],
            "source_revenue_growth_observations_not_sector_rank": rows,
            "intel_filing_accession": authentic_peer["intel_filing_accession"],
            "nvda_minus_amd_growth_pp": authentic_peer["observed_nvda_minus_amd_growth_pp"],
            "nvda_minus_intc_growth_pp": authentic_peer["observed_nvda_minus_intc_growth_pp"],
            "fiscal_end_offsets_days": {"AMD":29, "INTC":29},
            "intel_altera_deconsolidation_unadjusted": True,
            "peers_raw_bytes_verified": False,
            "representative_peer_license_verified": False,
        }
        packet={
            "schema":_SCHEMA, "status":_STATUS,
            "ticker":"NVDA", "as_of":"2026-11-05",
            "source_linked_issuer_sha256":issuer["source_sha256"],
            "stock_uploaded_sha256":ab["local_stock_sha256"],
            "ndx_uploaded_sha256":ab["local_ndx_sha256"],
            "engine_ab_partial":ab, "engine_c_partial":c,
            "guard_policy_preview":"HOLD", "guard_executed":False,
            "full_abc_complete":False,
            "market_rights_verified":False, "peer_rights_verified":False,
            "sec_edgar_original_bytes_verified":False,
            "ai_model_source_processing_authorized":False,
            "source_provider_authenticated":False,
            "investment_recommendation":False,
            "ai_agent_executed":False, "trade_executed":False,
            "network_requests":0,
            "integrity_kind":"UNKEYED_DERIVED_SHA256_NOT_SOURCE_AUTHENTICATION",
        }
        raw=_canonical(packet)
        if len(raw)>65536:
            return _blocked("DERIVED_PACKET_SIZE_EXCEEDED")
        packet["derived_sha256"]=sha256(raw).hexdigest()
        return packet
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
        return _blocked("INVALID_DERIVED_SOURCE_FIELDS")


def replay_partial_source_bound_abc(packet: Any) -> bool:
    """Check output and immutable issuer/peer facts; unkeyed hashes never
    authenticate operator-entered price values or establish legal rights."""
    if (type(packet) is not dict or packet.get("status") != _STATUS
            or type(packet.get("engine_ab_partial")) is not dict
            or type(packet.get("derived_sha256")) is not str
            or len(packet["derived_sha256"]) != 64):
        return False
    try:
        unsigned=dict(packet)
        digest=unsigned.pop("derived_sha256")
        if sha256(_canonical(unsigned)).hexdigest()!=digest:
            return False
        return packet==build_partial_source_bound_abc(
            ab_review=packet["engine_ab_partial"])
    except (TypeError,ValueError,KeyError,OverflowError,RecursionError):
        return False
