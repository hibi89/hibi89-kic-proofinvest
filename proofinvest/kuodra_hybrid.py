"""KUODRA synthetic owner-local public/private point-in-time join and analysis.

This module is not a production security boundary. Only a trusted host may
construct VerifiedPrincipal; network isolation/auth must be independently
verified before real confidential data. No network, filesystem or persistence.
Never expose this module as a public API or call a remote model with its output.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any

from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from .kuodra_unified_core import _id, _instant
from .kuodra_stats import cross_section_fdr
from .kuodra_time_ml import evaluate_lagged_regression

_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_LIMIT = 5000


def _approved_snapshot_digest(dataset: dict[str, Any]) -> str:
    """Pin the full owner-reconciled local view; not publisher authentication."""
    return sha256(json.dumps(dataset, ensure_ascii=True, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _validated_local_rows(dataset: dict[str, Any], *, kind: str,
                          as_of: str) -> list[dict[str, Any]]:
    """Revalidate stored records, do not rely on mutable dictionary labels."""
    if (type(dataset) is not dict
            or dataset.get("schema") != "kuodra.canonical.long.v1"
            or dataset.get("access_level") != kind
            or not _id(dataset.get("dataset_id"))
            or not _id(dataset.get("source_id"))
            or type(dataset.get("source_sha256")) is not str
            or _SHA.fullmatch(dataset["source_sha256"]) is None
            or type(dataset.get("records")) is not list
            or not 1 <= len(dataset["records"]) <= _LIMIT
            or len(dataset["records"]) != dataset.get("rows")
            or dataset.get("source_authenticated") is not False
            or dataset.get("source_rights_verified") is not False
            or dataset.get("host_egress_policy_verified") is not False):
        raise ValueError("HYBRID_INPUT_LINEAGE_INVALID")
    seen: set[tuple[str, str, str]] = set()
    units: dict[str, str] = {}
    filtered: list[dict[str, Any]] = []
    cutoff = _instant(as_of)
    for row in dataset["records"]:
        if (type(row) is not dict
                or row.get("dataset_id") != dataset["dataset_id"]
                or row.get("source_id") != dataset["source_id"]
                or row.get("access_level") != kind
                or row.get("evidence_sha256") != dataset["source_sha256"]
                or not all(_id(row.get(k)) for k in ("entity_id", "metric_id", "unit"))
                or type(row.get("value")) is not str):
            raise ValueError("HYBRID_INPUT_ROW_INVALID")
        observed = _instant(row.get("observation_at"))
        ready = _instant(row.get("available_at"))
        if ready < observed:
            raise ValueError("HYBRID_RELEASE_ORDER_INVALID")
        try:
            number = Decimal(row["value"])
        except (ValueError, InvalidOperation) as exc:
            raise ValueError("HYBRID_VALUE_INVALID") from exc
        if not number.is_finite() or len(row["value"]) > 64:
            raise ValueError("HYBRID_VALUE_INVALID")
        k = row["entity_id"], row["metric_id"], row["observation_at"]
        if k in seen:
            raise ValueError("HYBRID_DUPLICATE_ROW")
        seen.add(k)
        metric, unit = row["metric_id"], row["unit"]
        if metric in units and units[metric] != unit:
            raise ValueError("HYBRID_UNIT_CONFLICT")
        units[metric] = unit
        # Historical point-in-time: never include observations or revisions
        # unavailable at the operator's requested decision cut-off.
        if observed <= cutoff and ready <= cutoff:
            filtered.append(row)
    return filtered


def _build_joined(vault: OwnerLocalGateway, principal: VerifiedPrincipal, *,
                  public_dataset_id: str, private_dataset_id: str,
                  as_of: str) -> dict[str, Any]:
    if (type(vault) is not OwnerLocalGateway
            or type(principal) is not VerifiedPrincipal
            or not _id(public_dataset_id) or not _id(private_dataset_id)
            or public_dataset_id == private_dataset_id):
        raise ValueError("HYBRID_REQUEST_INVALID")
    _instant(as_of)
    # Check BOTH datasets before copying any bytes. Generic denial avoids
    # leaking which id exists or which access right is missing.
    vault._check(principal, dataset_id=public_dataset_id)
    vault._check(principal, dataset_id=private_dataset_id)
    # A matching entity_id across two independent source systems is NOT an
    # issuer identity proof. Only the exact owner-mapped, source-pinned,
    # as-of-bound ephemeral view may be joined, even by legacy direct APIs.
    scope = vault._approved_hybrid_scope
    if (type(scope) is not tuple or len(scope) != 5
            or scope[:3] != (public_dataset_id, private_dataset_id, as_of)):
        raise PermissionError("HYBRID_OWNER_MAPPING_REQUIRED")
    if (scope[3] != _approved_snapshot_digest(vault._datasets[public_dataset_id])
            or scope[4] != _approved_snapshot_digest(vault._datasets[private_dataset_id])):
        raise ValueError("HYBRID_APPROVED_SNAPSHOT_CHANGED")
    public = deepcopy(vault._datasets[public_dataset_id])
    private = deepcopy(vault._datasets[private_dataset_id])
    pub_rows = _validated_local_rows(public, kind="PUBLIC", as_of=as_of)
    priv_rows = _validated_local_rows(private, kind="PRIVATE", as_of=as_of)
    pub_keys = {(r["entity_id"], r["observation_at"]) for r in pub_rows}
    priv_keys = {(r["entity_id"], r["observation_at"]) for r in priv_rows}
    common = pub_keys & priv_keys
    if not common:
        return {"status": "INSUFFICIENT_OVERLAPPING_OBSERVATIONS",
                "dataset": None, "joined_keys": 0}
    selected = []
    for prefix, rows in (("public", pub_rows), ("private", priv_rows)):
        for row in rows:
            if (row["entity_id"], row["observation_at"]) in common:
                selected.append((prefix, row))
    if len(selected) > _LIMIT:
        raise ValueError("HYBRID_JOIN_ROW_LIMIT")
    # Hash is evidence of the local *derived* snapshot, never issuer origin
    # authentication or public redistribution rights.
    canonical = [{"zone": zone, "entity": r["entity_id"],
                  "metric": r["metric_id"], "observed": r["observation_at"],
                  "available": r["available_at"], "value": r["value"],
                  "unit": r["unit"], "source_hash": r["evidence_sha256"]}
                 for zone, r in selected]
    digest = sha256(json.dumps({"as_of": as_of, "rows": canonical},
          sort_keys=True, ensure_ascii=True, separators=(",", ":"),
          allow_nan=False).encode("utf-8")).hexdigest()
    records = []
    for zone, row in selected:
        derived = {k: row[k] for k in (
            "entity_id", "observation_at", "available_at", "value", "unit")}
        derived.update({"dataset_id": "hybridLocal", "source_id": "localDerived",
                        "metric_id": zone + "." + row["metric_id"],
                        "access_level": "PRIVATE", "evidence_sha256": digest})
        records.append(derived)
    return {"status": "LOCAL_JOIN_READY", "joined_keys": len(common),
            "dataset": {
                "schema": "kuodra.canonical.long.v1",
                "dataset_id": "hybridLocal", "source_id": "localDerived",
                "source_sha256": digest, "source_authenticated": False,
                "source_rights_verified": False,
                "publisher_vintage_verified": False,
                "host_egress_policy_verified": False,
                "access_level": "PRIVATE", "rows": len(records),
                "records": records, "network_requests": 0,
                "raw_persisted": False,
                "derivation": "POINT_IN_TIME_IN_MEMORY_JOIN_NOT_PUBLISHER_PROOF"
            }}


def analyze_local_hybrid(vault: OwnerLocalGateway, principal: VerifiedPrincipal, *,
                         public_dataset_id: str, private_dataset_id: str,
                         as_of: str, mode: str, metrics: tuple[str, ...] = (),
                         observation_at: str | None = None,
                         target_metric: str | None = None,
                         feature_metrics: tuple[str, ...] = ()) -> dict[str, Any]:
    """Return scoped derived insights, never original rows or CSV/SQL bytes.

    Valid metric names are public.foo/private.foo. Joined at *exact* entity
    and observation timestamp, never silently forward-filled. For forecasting,
    the existing model adapter independently requires features available at
    their observation timestamp and embargoes late training labels.
    """
    if mode not in ("cross_section", "predictive"):
        raise ValueError("HYBRID_MODE_INVALID")
    if mode == "cross_section":
        if (type(metrics) is not tuple or not 2 <= len(metrics) <= 12
                or observation_at is None or target_metric is not None
                or feature_metrics):
            raise ValueError("HYBRID_SELECTION_INVALID")
        _instant(observation_at)
        chosen = metrics
    else:
        if (metrics or observation_at is not None
                or type(target_metric) is not str
                or type(feature_metrics) is not tuple
                or not 1 <= len(feature_metrics) <= 10):
            raise ValueError("HYBRID_SELECTION_INVALID")
        chosen = (target_metric,) + feature_metrics
    if (len(set(chosen)) != len(chosen)
            or any(type(v) is not str or not (
                v.startswith("public.") or v.startswith("private."))
                or not _id(v) for v in chosen)
            or not any(v.startswith("public.") for v in chosen)
            or not any(v.startswith("private.") for v in chosen)):
        raise ValueError("HYBRID_METRIC_NAMESPACE_INVALID")
    joined = _build_joined(vault, principal,
            public_dataset_id=public_dataset_id,
            private_dataset_id=private_dataset_id, as_of=as_of)
    if joined["dataset"] is None:
        answer = {"status": "NO_ANALYSIS", "reason": joined["status"],
                  "insights": []}
    elif mode == "cross_section":
        answer = cross_section_fdr(joined["dataset"], metrics=metrics,
                observation_at=observation_at, as_of=as_of)
    else:
        answer = evaluate_lagged_regression(joined["dataset"],
                target_metric=target_metric, feature_metrics=feature_metrics,
                as_of=as_of)
    # The report is itself private derived information. No public endpoint,
    # outbound network, telemetry, or export adapter is provided.
    return {"schema": "kuodra.local-hybrid-insight.v1",
            "status": "LOCAL_RESTRICTED_REVIEW_ONLY", "mode": mode,
            "joined_entity_times": joined["joined_keys"],
            "analysis": deepcopy(answer), "access_level": "PRIVATE",
            "guard": "HOLD", "public_export_allowed": False,
            "host_egress_policy_verified": False,
            "network_requests": 0, "data_rows_disclosed": False,
            "source_rights_verified": False}
