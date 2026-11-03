"""P128: strictly local exact-byte comparison against P127 public observation.

The observed SHA/size came from one GitHub Actions issuer-hosted GET.
Matching a local file to that observation does NOT authenticate its origin,
grant license/AI/display rights, validate SEC APIs, or permit trading.
No network, persistence, user-file upload, or external action is performed.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import re
from typing import Any

from .apple_audited_10k_replay import TEN_K
from .apple_local_html_crosscheck import verify_local_apple_10k_html
from .public_primary_baseline import APPLE, CURATED, _read

OBSERVED_SHA256 = "eb08113db1fa3b847936c68ddf7bd9c31b5d708c14794c94355fd38ac3846850"
OBSERVED_SIZE = 1452459
MAX_UPLOAD_SIZE = 5_000_000
ACTION_URL = "https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41595034265"
FILED_AT = date(2025, 10, 31)
SUCCESS = "LOCAL_BYTES_EQUAL_P127_OBSERVATION_24_CELLS_MATCH_ORIGIN_UNVERIFIED"


def prior_public_observation() -> dict[str, Any]:
    """Static historical evidence; this does not re-fetch the filing."""
    return {
        "schema": "kuodra.p128-local-p127-observation.v1",
        "status": "P127_HISTORICAL_OBSERVATION_ONLY",
        "issuer": "Apple Inc.", "ticker": "AAPL",
        "fiscal_end": "2025-09-27", "filed_at": FILED_AT.isoformat(),
        "observed_original_size": OBSERVED_SIZE,
        "observed_original_sha256": OBSERVED_SHA256,
        "observed_numeric_cells": 24,
        "action_url": ACTION_URL,
        "sec_original_authenticated": False,
        "issuer_cryptographic_attestation": False,
        "source_rights_verified": False,
        "ai_processing_allowed": False,
        "live_market_data_verified": False,
        "original_bytes_retained": False,
        "network_requests": 0,
        "trade_executed": False,
    }


def _blocked(reason: str) -> dict[str, Any]:
    return {
        **prior_public_observation(),
        "status": "BLOCKED",
        "reason_code": reason,
        "local_file_matches_p127_observation": False,
        "local_financial_rows_verified": False,
        "matched_numeric_cells": 0,
    }


def review_local_apple_p127_original(
    original_html: bytes, *, ticker: str, as_of: str
) -> dict[str, Any]:
    """Verify a voluntary local HTML byte sequence against fixed P127 SHA.

    This exact-byte gate intentionally rejects a different HTML export even
    if it prints similar numbers. It never treats a hash as a publisher signature.
    """
    if type(ticker) is not str or ticker.strip().upper() != "AAPL":
        return _blocked("APPLE_TICKER_REQUIRED")
    if type(as_of) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of) is None:
        return _blocked("INVALID_AS_OF_DATE")
    try:
        if date.fromisoformat(as_of) < FILED_AT:
            return _blocked("FILING_NOT_YET_AVAILABLE_AS_OF")
    except ValueError:
        return _blocked("INVALID_AS_OF_DATE")
    if type(original_html) is not bytes or not 0 < len(original_html) <= MAX_UPLOAD_SIZE:
        return _blocked("LOCAL_ORIGINAL_HTML_SIZE_OR_TYPE_BLOCKED")
    # Hash first, parse only exact observed bytes. Never print source content.
    if len(original_html) != OBSERVED_SIZE:
        return _blocked("LOCAL_BYTES_DIFFER_FROM_P127_OBSERVATION")
    if sha256(original_html).hexdigest() != OBSERVED_SHA256:
        return _blocked("LOCAL_BYTES_DIFFER_FROM_P127_OBSERVATION")
    try:
        compared = verify_local_apple_10k_html(
            original_html, _read(TEN_K), _read(APPLE), _read(CURATED)
        )
        if (
            compared.get("status")
                != "LOCAL_ORIGINAL_HTML_BYTES_MATCH_MANUAL_FINANCIAL_ROWS_ORIGIN_UNVERIFIED"
            or compared.get("matched_numeric_cells") != 24
            or compared.get("original_local_html_sha256") != OBSERVED_SHA256
            or compared.get("original_local_html_size") != OBSERVED_SIZE
            or compared.get("sec_original_file_authenticated") is not False
            or compared.get("issuer_original_file_authenticated") is not False
            or compared.get("data_rights_verified") is not False
            or compared.get("original_bytes_retained") is not False
            or compared.get("network_requests") != 0
            or compared.get("trade_executed") is not False
        ):
            return _blocked("LOCAL_FINANCIAL_REPLAY_TRUST_CONTRACT_BLOCKED")
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            ArithmeticError, RecursionError, OverflowError):
        return _blocked("LOCAL_FINANCIAL_REPLAY_BLOCKED")
    return {
        **prior_public_observation(),
        "status": SUCCESS,
        "reason_code": "EXACT_P127_BYTES_AND_LOCAL_TABLES_MATCH",
        "local_file_matches_p127_observation": True,
        "local_financial_rows_verified": True,
        "matched_numeric_cells": 24,
    }
