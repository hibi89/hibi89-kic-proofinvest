"""P119 offline source/usage-rights ledger for caller-supplied local bytes.

An exact SHA from local input does NOT prove publisher identity, timestamps,
contractual rights or permission to publish an analysis. The ledger can never
grant an entitlement or override SEC P105 HTTP403 HOLD or the Guard decision.
"""
from __future__ import annotations

import re

_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_ROLES = ("ticker_map", "submissions", "companyfacts", "original_10k")
_OPTIONAL = (("market_json", "engine_a"), ("industry_json", "engine_c"))


def build_local_rights_ledger(receipt: dict, supplementary: dict) -> dict:
    """Create a source-specific, zero-network fail-closed disclosure ledger.

    This is a provenance *gap* inventory, not a license-validation tool.
    Local per-source hashes mean that an operator can repeat the arithmetic,
    not that a vendor/publisher supplied these bytes or granted rights.
    """
    if (type(receipt) is not dict or type(supplementary) is not dict
            or receipt.get("schema") != "kuodra.local-sec-source-receipt.v1"
            or receipt.get("status") != "local_four_sources_unverified"
            or receipt.get("source_authenticated") is not False
            or receipt.get("source_rights_verified") is not False
            or receipt.get("network_requests") != 0
            or receipt.get("live_sec_http_called") is not False
            or supplementary.get("source_authenticated") is not False
            or supplementary.get("source_rights_verified") is not False
            or supplementary.get("trade_executed") is not False):
        raise ValueError("LOCAL_RIGHTS_INPUT_TRUST_INVALID")
    hashes = receipt.get("source_sha256")
    if (type(hashes) is not dict or set(hashes) != set(_ROLES)
            or any(type(hashes[k]) is not str or
                   _SHA.fullmatch(hashes[k]) is None for k in _ROLES)):
        raise ValueError("LOCAL_RIGHTS_SOURCE_SET_INVALID")
    assets = []
    for role in _ROLES:
        assets.append({
            "role": role, "raw_sha256": hashes[role],
            "input_status": "CALLER_SUPPLIED_LOCAL_BYTES",
            "claimed_reference_category": "SEC_FORMAT_NOT_PUBLISHER_VERIFIED",
            "publisher_origin_authenticated": False,
            "acquisition_time_verified": False,
            "source_use_rights_verified": False,
            "external_display_rights_verified": False,
            "redistribution_rights_verified": False,
        })
    for role, engine in _OPTIONAL:
        card = supplementary.get(engine)
        if type(card) is not dict:
            raise ValueError("LOCAL_RIGHTS_ENGINE_MISSING")
        digest = card.get("input_sha256")
        if digest is not None and (type(digest) is not str or
                                  _SHA.fullmatch(digest) is None):
            raise ValueError("LOCAL_RIGHTS_ENGINE_SHA_INVALID")
        assets.append({
            "role": role, "raw_sha256": digest,
            "input_status": ("ACCEPTED_FOR_UNVERIFIED_COMPUTATION"
                             if digest is not None else
                             "NO_ELIGIBLE_SOURCE_BOUND"),
            "claimed_reference_category": "OPERATOR_PROVIDED_NOT_PROVIDER_VERIFIED",
            "publisher_origin_authenticated": False,
            "acquisition_time_verified": False,
            "source_use_rights_verified": False,
            "external_display_rights_verified": False,
            "redistribution_rights_verified": False,
        })
    return {
        "schema": "kuodra.local-source-rights-ledger.v1",
        "status": "EXTERNAL_USE_BLOCKED_RIGHTS_NOT_VERIFIED",
        "purpose": "LOCAL_EVIDENCE_REVIEW_NOT_PERMISSION_GRANT",
        "sources": assets,
        "required_external_clearances": [
            "PUBLISHER_ORIGIN", "LICENSE_OR_PUBLIC_USE_BASIS",
            "ACCOUNT_ENTITLEMENT_WHEN_REQUIRED",
            "DERIVED_DATA_PUBLIC_DISPLAY", "REDISTRIBUTION_WHEN_APPLICABLE",
        ],
        "contest_public_submission_allowed": False,
        "external_sharing_allowed": False,
        "commercial_reuse_allowed": False,
        "publisher_origin_authenticated": False,
        "license_or_reuse_permission_verified": False,
        "network_requests": 0, "paid_services_activated": False,
        "guard_executed": False, "trade_executed": False,
    }
