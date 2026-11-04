"""P199: immutable LIVE CI issuer inline-XBRL proof -> human-only factual review.

Source P198 one GET real official Dell IR FY2026 10-K 2026-11-05, CI #41886620639.
Neither original raw HTML nor original signed SEC hash is represented here.
No network, storage, AI, trades or financial/industry peer rights.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from .dell_2026_publisher_evidence import (
    actual_p195_source_receipt, review_verified_dell_first_party_raw_evidence,
)
from .dell_issuer_2026_10k_once import _URL

_CI = "https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41886620639"
_SHA = "c48524018e82710057f6ef7cb27b665c4c7f4a39b65b02973417de0d68a5a4ac"
_BYTES = 3610307


def observed_ixbrl_receipt() -> dict[str, Any]:
    """Observed real publisher HTML XBRL facts in exact P198 successful CI."""
    return {
        "result": "REAL_ISSUER_2026_IXBRL_REVENUES_RECOMPUTED",
        "source_url": _URL,
        "source_sha256": _SHA,
        "source_bytes": _BYTES,
        "ci_run": _CI,
        "http_get_attempted": 1,
        "sec_http_calls": 0,
        "raw_html_uploaded": False,
        "origin_sec_edgar_byte_identical": False,
        "source_rights_verified": False,
        "full_abc_ready": False,
        "xbrl_concept": "us-gaap:revenues",
        "xbrl_facts": {
            "FY2026": {
                "context": "c-1", "period_start": "2025-02-01",
                "period_end": "2026-01-30", "amount_usd_millions": "113538",
                "verified_undimensioned_repetitions": 3,
            },
            "FY2025": {
                "context": "c-14", "period_start": "2024-02-03",
                "period_end": "2025-01-31", "amount_usd_millions": "95567",
                "verified_undimensioned_repetitions": 3,
            },
        },
    }


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p199-real-issuer-xbrl-review.v1",
        "status": "BLOCKED", "reason_code": reason,
        "evidence": None,
        "issuer_https_original_seen": False,
        "publisher_xbrl_fact_correctly_replayed": False,
        "sec_edgar_original_authenticated": False,
        "source_commercial_rights_verified": False,
        "price_true_ndx_available": False,
        "sector_peer_period_aligned": False,
        "model_grounded_issuer_numeric_accurate": False,
        "full_abc_ready": False, "guard_policy_preview": "HOLD",
        "trade_executed": False, "network_requests": 0,
    }


def review_observed_real_dell_ixbrl(
    *, as_of: str, receipt: dict[str, Any],
) -> dict[str, Any]:
    """Validate exact publicly logged source and independently re-do Decimal."""
    if type(as_of) is not str or as_of != "2026-11-05":
        return _blocked("REVIEW_VINTAGE_INVALID")
    if type(receipt) is not dict or receipt != observed_ixbrl_receipt():
        return _blocked("LIVE_VERIFIED_SOURCE_RECEIPT_MISMATCH")
    p195 = review_verified_dell_first_party_raw_evidence(
        as_of=as_of, receipt=actual_p195_source_receipt())
    if (p195.get("status") != "DELL_REAL_FIRST_PARTY_ORIGINAL_NUMERIC_REVIEW_READY_LIMITED"
            or p195.get("publisher_https_original_seen") is not True
            or p195.get("sec_edgar_original_byte_equivalence_verified") is not False
            or p195.get("trade_executed") is not False):
        return _blocked("PRIOR_RAW_SOURCE_EVIDENCE_NOT_READY")
    original = p195["evidence"]
    if (original["raw_original_bytes_sha256"] != receipt["source_sha256"]
            or original["raw_original_byte_count"] != receipt["source_bytes"]
            or original["source_url"] != receipt["source_url"]):
        return _blocked("REAL_P195_AND_P198_SOURCE_BYTES_DIVERGED")
    rows = receipt["xbrl_facts"]
    current, prior = Decimal(rows["FY2026"]["amount_usd_millions"]), Decimal(
        rows["FY2025"]["amount_usd_millions"])
    if (current != Decimal(original["revenue_2026_usd_millions"])
            or prior != Decimal(original["revenue_2025_usd_millions"])
            or current <= prior or prior <= 0):
        return _blocked("REAL_XBRL_AND_INDEPENDENT_REVENUE_DISAGREE")
    growth = ((current / prior - 1) * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    if growth != Decimal(original["revenue_yoy_pct"]):
        return _blocked("REAL_SOURCE_GROWTH_ARITHMETIC_DISAGREEMENT")
    return {
        **_blocked("ISSUER_TLS_XBRL_NOT_SEC_IDENTITY_OR_RIGHTS_PROOF"),
        "status": "PUBLISHER_IXBRL_REAL_ANNUAL_REVENUE_CONFIRMED_LIMITED",
        "issuer_https_original_seen": True,
        "publisher_xbrl_fact_correctly_replayed": True,
        "evidence": {
            "issuer": "Dell Technologies Inc.",
            "ticker": "DELL", "source_url": receipt["source_url"],
            "source_sha256": receipt["source_sha256"],
            "source_bytes": receipt["source_bytes"], "ci_run": receipt["ci_run"],
            "xbrl_concept": receipt["xbrl_concept"],
            "xbrl_facts": {k: dict(v) for k, v in rows.items()},
            "annual_revenue_growth_pct": str(growth),
            "rights_warning": "RAW_SEC_EDGAR_IDENTICAL_AND_REUSE_RIGHTS_UNVERIFIED",
        },
    }
