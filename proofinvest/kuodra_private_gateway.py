"""Local-only KUODRA owner-scoped ingest/analysis boundary (synthetic validation).

Only accepts bytes supplied by a trusted operator host. No disk, HTTP, subprocess,
logging or external export is implemented here. This is NOT an authentication
provider or OS/firewall-level deny-egress guarantee: the caller must supply a
verified principal, isolate the worker and deny outbound traffic at host level
before processing real confidential data. PUBLIC review is always withheld if
source rights have not been independently established.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .kuodra_unified_core import _id, normalize_local_csv, normalize_local_sqlite
from .kuodra_unified_core import observed_relationships
from .kuodra_time_ml import evaluate_lagged_regression
from .kuodra_stats import cross_section_fdr


@dataclass(frozen=True)
class VerifiedPrincipal:
    """Trusted-host-authenticated identity. Do not construct from UI input."""
    subject: str
    owner_id: str
    roles: tuple[str, ...]
    authenticated_by_host: bool

    def __post_init__(self) -> None:
        if (not _id(self.subject) or not _id(self.owner_id)
                or type(self.authenticated_by_host) is not bool
                or type(self.roles) is not tuple or not self.roles
                or len(self.roles) > 8 or len(set(self.roles)) != len(self.roles)
                or any(not _id(r) for r in self.roles)):
            raise ValueError("GATEWAY_PRINCIPAL_INVALID")


class OwnerLocalGateway:
    """Ephemeral dataset vault; NEVER register it as a public web endpoint.

    Owner-scoped dataset namespace and allowlisted roles; only verified local
    host principals can invoke this interface. Per-request authorization occurs
    before any lookup, and all successful analysis calls return deep copies.
    """

    def __init__(self, owner_id: str) -> None:
        if not _id(owner_id):
            raise ValueError("GATEWAY_OWNER_INVALID")
        self._owner = owner_id
        self._datasets: dict[str, dict[str, Any]] = {}
        self._allowed_roles: dict[str, frozenset[str]] = {}
        self._local_identity_approvals: dict[str, dict[str, Any]] = {}
        # Set only on the fresh, owner-reconciled ephemeral alias view.
        self._approved_hybrid_scope: tuple[str, str, str, str, str] | None = None

    def _check(self, principal: VerifiedPrincipal, *, write: bool = False,
               dataset_id: str | None = None) -> None:
        if (type(principal) is not VerifiedPrincipal
                or principal.authenticated_by_host is not True
                or principal.owner_id != self._owner):
            raise PermissionError("GATEWAY_ACCESS_DENIED")
        if write and "owner" not in principal.roles:
            raise PermissionError("GATEWAY_ACCESS_DENIED")
        if dataset_id is not None:
            if not _id(dataset_id) or dataset_id not in self._datasets:
                raise PermissionError("GATEWAY_ACCESS_DENIED")
            if ("owner" not in principal.roles
                    and not self._allowed_roles[dataset_id].intersection(principal.roles)):
                raise PermissionError("GATEWAY_ACCESS_DENIED")

    def ingest_csv(self, principal: VerifiedPrincipal, *, raw: bytes,
                   dataset_id: str, source_id: str, access_level: str,
                   allowed_roles: tuple[str, ...] = ("analyst",)) -> dict[str, Any]:
        self._check(principal, write=True)
        self._check_roles(allowed_roles)
        if dataset_id in self._datasets:
            raise ValueError("GATEWAY_DATASET_ALREADY_REGISTERED")
        data = normalize_local_csv(raw, dataset_id=dataset_id,
            source_id=source_id, access_level=access_level,
            consent=access_level == "PRIVATE")
        self._register(dataset_id, data, allowed_roles)
        return self._receipt(data)

    def ingest_mapped_wide_csv(
            self, principal: VerifiedPrincipal, *, raw: bytes,
            dataset_id: str, source_id: str, access_level: str,
            metric_columns: dict[str, tuple[str, str]],
            allowed_roles: tuple[str, ...] = ("analyst",)) -> dict[str, Any]:
        """Owner-approved wide columns; retain original and mapping digests."""
        self._check(principal, write=True)
        self._check_roles(allowed_roles)
        if dataset_id in self._datasets:
            raise ValueError("GATEWAY_DATASET_ALREADY_REGISTERED")
        from .kuodra_wide_adapter import normalize_mapped_wide_csv
        data = normalize_mapped_wide_csv(
            raw, dataset_id=dataset_id, source_id=source_id,
            access_level=access_level, metric_columns=metric_columns,
            consent=access_level == "PRIVATE")
        self._register(dataset_id, data, allowed_roles)
        return self._receipt(data)

    def ingest_sqlite(self, principal: VerifiedPrincipal, *, raw_db: bytes,
                      table: str, dataset_id: str, source_id: str,
                      access_level: str,
                      allowed_roles: tuple[str, ...] = ("analyst",)) -> dict[str, Any]:
        self._check(principal, write=True)
        self._check_roles(allowed_roles)
        if dataset_id in self._datasets:
            raise ValueError("GATEWAY_DATASET_ALREADY_REGISTERED")
        data = normalize_local_sqlite(raw_db, table=table,
            dataset_id=dataset_id, source_id=source_id,
            access_level=access_level, consent=access_level == "PRIVATE")
        self._register(dataset_id, data, allowed_roles)
        return self._receipt(data)

    def ingest_mapped_wide_sqlite(
            self, principal: VerifiedPrincipal, *, raw_db: bytes, table: str,
            dataset_id: str, source_id: str, access_level: str,
            metric_columns: dict[str, tuple[str, str]],
            allowed_roles: tuple[str, ...] = ("analyst",)) -> dict[str, Any]:
        """Read approved local SQLite wide columns, with owner/role gate."""
        self._check(principal, write=True)
        self._check_roles(allowed_roles)
        if dataset_id in self._datasets:
            raise ValueError("GATEWAY_DATASET_ALREADY_REGISTERED")
        from .kuodra_wide_sqlite_adapter import normalize_mapped_wide_sqlite
        data = normalize_mapped_wide_sqlite(
            raw_db, table=table, dataset_id=dataset_id,
            source_id=source_id, access_level=access_level,
            metric_columns=metric_columns, consent=access_level == "PRIVATE")
        self._register(dataset_id, data, allowed_roles)
        return self._receipt(data)

    @staticmethod
    def _check_roles(roles: tuple[str, ...]) -> None:
        if (type(roles) is not tuple or not roles or len(roles) > 8
                or len(set(roles)) != len(roles)
                or "owner" in roles or any(not _id(r) for r in roles)):
            raise ValueError("GATEWAY_ROLES_INVALID")

    def _register(self, dataset_id: str, data: dict, roles: tuple[str, ...]) -> None:
        self._datasets[dataset_id] = deepcopy(data)
        self._allowed_roles[dataset_id] = frozenset(roles)

    @staticmethod
    def _receipt(data: dict) -> dict[str, Any]:
        return {"schema": "kuodra.local-gateway-receipt.v1",
                "status": "LOCAL_BYTES_NORMALIZED_ORIGIN_UNVERIFIED",
                "rows": data["rows"], "access_level": data["access_level"],
                "host_egress_policy_verified": False, "network_requests": 0}

    def descriptive(self, principal: VerifiedPrincipal, *, dataset_id: str,
                    metrics: tuple[str, ...], as_of: str) -> dict[str, Any]:
        self._check(principal, dataset_id=dataset_id)
        result = observed_relationships(deepcopy(self._datasets[dataset_id]),
                                        metrics=metrics, as_of=as_of)
        return deepcopy(result)

    def statistical(self, principal: VerifiedPrincipal, *, dataset_id: str,
                    metrics: tuple[str, ...], observation_at: str,
                    as_of: str) -> dict[str, Any]:
        self._check(principal, dataset_id=dataset_id)
        result = cross_section_fdr(deepcopy(self._datasets[dataset_id]),
            metrics=metrics, observation_at=observation_at, as_of=as_of)
        return deepcopy(result)

    def predictive(self, principal: VerifiedPrincipal, *, dataset_id: str,
                   target_metric: str, feature_metrics: tuple[str, ...],
                   as_of: str) -> dict[str, Any]:
        self._check(principal, dataset_id=dataset_id)
        result = evaluate_lagged_regression(deepcopy(self._datasets[dataset_id]),
            target_metric=target_metric, feature_metrics=feature_metrics,
            as_of=as_of)
        return deepcopy(result)

    def export_to_public(self, principal: VerifiedPrincipal, *, dataset_id: str) -> dict:
        """Deny by default: unknown rights OR private source bars public export.

        No override exists on this synthetic boundary. Future licensed public
        export must be implemented in a separately approved source gateway.
        """
        self._check(principal, dataset_id=dataset_id)
        return {"status": "PUBLIC_EXPORT_DENIED_UNVERIFIED_RIGHTS_OR_PRIVATE",
                "guard": "HOLD", "data_disclosed": False,
                "network_requests": 0}

    def release(self, principal: VerifiedPrincipal, *, dataset_id: str) -> None:
        """Delete a source and revoke every pending identity grant that references it."""
        self._check(principal, write=True, dataset_id=dataset_id)
        # Source lifecycle is part of approval scope. A byte-identical later
        # re-import must never revive authorization issued to the old dataset.
        for token, approval in tuple(self._local_identity_approvals.items()):
            if dataset_id in (approval["public"], approval["private"]):
                del self._local_identity_approvals[token]
        if (self._approved_hybrid_scope is not None
                and dataset_id in self._approved_hybrid_scope[:2]):
            self._approved_hybrid_scope = None
        del self._datasets[dataset_id]
        del self._allowed_roles[dataset_id]
