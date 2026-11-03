"""P126: one-click issuer-reported Apple FY2025 historical review.

This is NOT live ticker retrieval, authenticated SEC/Apple original HTML,
a vendor data entitlement, LLM operation, or an investment recommendation.
It reuses existing manual 10-K/press-release cross-source arithmetic and
the real read-only Guard policy preview, without SEC retry or remote access.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Any

from .apple_audited_10k_replay import TEN_K, replay_audited_10k_manual_excerpt
from .public_primary_baseline import APPLE, CURATED, _read
from .guard_sec_adapter import evaluate_sec_guard

_FILED = date(2025, 10, 31)
_TWO = Decimal("0.01")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.apple-fy2025-single-ticker-manual-preview.v1",
        "status": "BLOCKED", "reason_code": reason,
        "source_authenticated": False, "source_rights_verified": False,
        "original_html_authenticated": False, "raw_sec_api_used": False,
        "current_filing_status_verified": False,
        "guard_executed": False, "audit_written": False,
        "human_approved": False, "trade_executed": False,
        "ai_agent_executed": False, "network_requests": 0,
        "official_submission": False,
    }


def review_apple_fy2025_historical(*, ticker: str, as_of: str) -> dict[str, Any]:
    """Explicit local historical issuer case; only when 10-K was available.

    No database, network or original ingestion; historical manually entered
    numbers remain different from publisher-authenticated source bytes.
    """
    out = _blocked("TICKER_OR_DATE_UNAVAILABLE")
    if type(ticker) is not str or ticker.strip().upper() != "AAPL":
        return out
    if type(as_of) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of) is None:
        return out
    try:
        observed = date.fromisoformat(as_of)
    except ValueError:
        return out
    if observed < _FILED:
        out["reason_code"] = "FILING_NOT_YET_AVAILABLE_AS_OF"
        return out
    try:
        doc, manual, curated = _read(TEN_K), _read(APPLE), _read(CURATED)
        replay = replay_audited_10k_manual_excerpt(doc, manual, curated)
        if (
            replay.get("status")
                != "MANUAL_FIRST_PARTY_10K_NUMBERS_CROSSCHECKED_WITH_P55_AND_ENGINE_B"
            or replay.get("issuer_cik") != "0000320193"
            or replay.get("accession") != "0000320193-25-000079"
            or replay.get("source_authenticated") is not False
            or replay.get("data_rights_verified") is not False
            or replay.get("original_raw_10k_bytes_authenticated") is not False
            or replay.get("automatic_sec_3_source_guard_real_data_validated") is not False
            or replay.get("fraud_proven") is not False
            or replay.get("trade_executed") is not False
            or replay.get("network_requests") != 0
        ):
            return _blocked("APPLE_MANUAL_REPLAY_TRUST_CONTRACT_INVALID")
        prior, current = Decimal(doc["prior"]["sales"]), Decimal(doc["current"]["sales"])
        if prior <= 0 or current <= 0:
            return _blocked("APPLE_ANNUAL_SALES_INVALID")
        growth = str(((current / prior - 1) * 100).quantize(
            _TWO, rounding=ROUND_HALF_UP))
        if growth != "6.43" or replay.get("fcf_proxy_2025_usd_millions") != "98767":
            return _blocked("APPLE_MANUAL_NUMERICAL_REPLAY_CHANGED")
        preview = evaluate_sec_guard({"status": "calculated_unverified"}, risk=None)
        guard = preview.get("guard") if type(preview) is dict else None
        if (type(guard) is not dict
                or guard.get("decision") != "HOLD"
                or guard.get("source_authenticated") is not False
                or guard.get("human_approved") is not False
                or guard.get("trade_executed") is not False):
            return _blocked("GUARD_UNVERIFIED_EVIDENCE_POLICY_CHANGED")

        # Digest is an input tracking aid, not authentication or signature.
        return {
            **_blocked(""), "status": "HISTORICAL_MANUAL_NUMBERS_CROSSCHECKED",
            "reason_code": "APPLE_2025_10K_MANUAL_PUBLISHER_NUMBERS_ONLY",
            "ticker": "AAPL", "issuer_cik": replay["issuer_cik"],
            "accession": replay["accession"], "filed_at": replay["filed_at"],
            "requested_as_of": as_of, "fiscal_end": replay["fiscal_end"],
            "source_kind": replay["source_kind"],
            "issuer_hosted_10k_url": replay["source_url"],
            "issuer_press_release_url": manual["source"]["url"],
            "manual_10k_json_sha256": sha256(TEN_K.read_bytes()).hexdigest(),
            "manual_press_json_sha256": sha256(APPLE.read_bytes()).hexdigest(),
            "manual_companyfacts_excerpt_sha256": sha256(CURATED.read_bytes()).hexdigest(),
            "sales_2025_usd_millions": str(current.quantize(Decimal("1"))),
            "sales_2024_usd_millions": str(prior.quantize(Decimal("1"))),
            "sales_growth_pct": growth,
            "cashflow_minus_capex_2025_usd_millions":
                replay["fcf_proxy_2025_usd_millions"],
            "cashflow_minus_capex_2024_usd_millions":
                replay["fcf_proxy_2024_usd_millions"],
            "fcf_proxy_is_non_gaap": True,
            "receivables_minus_sales_growth_pp":
                replay["receivables_minus_sales_growth_pp"],
            "fraud_proven": False,
            "guard_policy_preview": {
                "decision": "HOLD",
                "reason_codes": list(guard["reason_codes"]),
                "policy_version": guard["policy_version"],
                "meaning": "LOCAL_POLICY_PREVIEW_NOT_AUDIT_OR_TRADE",
            },
            "as_of_latest_filing_researched": False,
            "original_html_authenticated": False,
            "source_rights_verified": False,
            "publisher_origin_automatically_verified": False,
            "raw_sec_api_used": False,
        }
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            OverflowError, RecursionError, ArithmeticError):
        return _blocked("APPLE_HISTORICAL_REPLAY_UNAVAILABLE")
