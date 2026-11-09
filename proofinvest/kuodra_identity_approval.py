"""In-memory one-use owner attestation for LOCAL public/private entity maps.

A source-bound owner assertion is NOT independent issuer authentication, IAM,
OS network isolation, a license to export, or a trade authorization.
"""
from __future__ import annotations

from hashlib import sha256
import re
import secrets
from typing import Any

from .kuodra_alias_hybrid import _prepare_owner_alias_view
from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from .kuodra_review_report import _canonical
from .kuodra_unified_core import _id, _instant

_TOKEN = re.compile(r"[0-9a-f]{48}\Z", re.ASCII)


def _snapshot_digest(vault: OwnerLocalGateway, key: str) -> str:
    return sha256(_canonical(vault._datasets[key])).hexdigest()


def approve_local_identity_mapping(
    vault: OwnerLocalGateway, principal: VerifiedPrincipal, *,
    public_dataset_id: str, private_dataset_id: str,
    public_sha256: str, private_sha256: str,
    aliases: dict[str, str], as_of: str,
    acknowledge_unverified_issuer_identity: bool,
) -> dict[str, Any]:
    """Owner acknowledges exact, ephemeral source IDs and mapping before ML."""
    if type(vault) is not OwnerLocalGateway or type(principal) is not VerifiedPrincipal:
        raise PermissionError("IDENTITY_ACCESS_DENIED")
    vault._check(principal, write=True)
    if acknowledge_unverified_issuer_identity is not True:
        raise ValueError("IDENTITY_OWNER_ACK_REQUIRED")
    if type(as_of) is not str:
        raise ValueError("IDENTITY_SCOPE_INVALID")
    _instant(as_of)
    # The pre-existing alias path ensures owner role, source SHA, zone,
    # unique mapping and existence of every mapped issuer.
    _, digest = _prepare_owner_alias_view(
        vault, principal,
        public_dataset_id=public_dataset_id,
        private_dataset_id=private_dataset_id,
        public_sha256=public_sha256, private_sha256=private_sha256,
        aliases=aliases, as_of=as_of)
    if len(vault._local_identity_approvals) >= 16:
        raise ValueError("IDENTITY_PENDING_LIMIT")
    token = secrets.token_hex(24)
    vault._local_identity_approvals[token] = {
        "owner": principal, "public": public_dataset_id,
        "private": private_dataset_id, "as_of": as_of,
        "public_sha": public_sha256, "private_sha": private_sha256,
        "mapping": dict(aliases), "mapping_sha": digest,
        "public_snapshot": _snapshot_digest(vault, public_dataset_id),
        "private_snapshot": _snapshot_digest(vault, private_dataset_id),
    }
    return {"schema": "kuodra.local-identity-approval.v1",
            "status": "OWNER_ASSERTED_NOT_SOURCE_VERIFIED",
            "one_use_token": token,
            "mapping_sha256": digest, "alias_count": len(aliases),
            "cross_source_identity_verified": False,
            "host_iam_verified": False, "public_export_allowed": False,
            "network_requests": 0}


def consume_local_identity_mapping(
    vault: OwnerLocalGateway, principal: VerifiedPrincipal, *,
    token: str, public_dataset_id: str, private_dataset_id: str,
    as_of: str,
) -> tuple[OwnerLocalGateway, dict[str, Any]]:
    """Only use after other tool inputs are checked; consume before ML fit."""
    if type(vault) is not OwnerLocalGateway or type(principal) is not VerifiedPrincipal:
        raise PermissionError("IDENTITY_ACCESS_DENIED")
    vault._check(principal, dataset_id=public_dataset_id)
    vault._check(principal, dataset_id=private_dataset_id)
    if (type(token) is not str or _TOKEN.fullmatch(token) is None
            or type(as_of) is not str):
        raise PermissionError("IDENTITY_APPROVAL_REQUIRED")
    approval = vault._local_identity_approvals.get(token)
    if (approval is None or approval["public"] != public_dataset_id
            or approval["private"] != private_dataset_id
            or approval["as_of"] != as_of):
        raise PermissionError("IDENTITY_APPROVAL_SCOPE_MISMATCH")
    if (_snapshot_digest(vault, public_dataset_id) != approval["public_snapshot"]
            or _snapshot_digest(vault, private_dataset_id) != approval["private_snapshot"]):
        vault._local_identity_approvals.pop(token, None)
        raise ValueError("IDENTITY_APPROVED_SNAPSHOT_CHANGED")
    # One-use capability; even a subsequent model failure cannot be replayed.
    del vault._local_identity_approvals[token]
    view, digest = _prepare_owner_alias_view(
        vault, approval["owner"], public_dataset_id=public_dataset_id,
        private_dataset_id=private_dataset_id,
        public_sha256=approval["public_sha"],
        private_sha256=approval["private_sha"],
        aliases=approval["mapping"], as_of=as_of)
    if digest != approval["mapping_sha"]:
        raise ValueError("IDENTITY_APPROVED_MAPPING_CHANGED")
    return view, {
        "schema": "kuodra.local-identity-review.v1",
        "mapping_sha256": digest,
        "alias_count": len(approval["mapping"]),
        "attestation": "OWNER_ASSERTED_NOT_SOURCE_VERIFIED",
        "source_hashes": {"public": approval["public_sha"],
                          "private": approval["private_sha"]},
        "single_use_consumed": True,
        "cross_source_identity_verified": False,
        "public_export_allowed": False, "host_iam_verified": False,
        "network_requests": 0,
    }
