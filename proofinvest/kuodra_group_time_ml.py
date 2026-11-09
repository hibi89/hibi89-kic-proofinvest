"""Private-local issuer + future-time held-out regression evaluation.

Selective extension of AI_AutoML_Analyst time CV/Dummy/Ridge evaluation policy.
Strict *cross-issuer and later-time* holdout, release embargo, no raw export.
Exploratory synthetic validation only: no causal/calibrated probability or trade.
No network, file I/O, telemetry, model persistence, or user authentication here.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import math
import re
from typing import Any

from .kuodra_unified_core import _id, _instant

_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _hold(reason: str) -> dict[str, Any]:
    return {"schema": "kuodra.ml.issuer-time-holdout.v1", "status": "NO_TRAIN",
            "reason": reason, "guard": "HOLD", "calibrated_probability": None,
            "production_ready": False, "network_requests": 0}


def _cv_mae(train: list[tuple], makers: dict, *, folds: int = 3):
    """CV on distinct training timestamps; apply release embargo on every fold."""
    from sklearn.metrics import mean_absolute_error
    from sklearn.model_selection import TimeSeriesSplit

    times = sorted({row[0] for row in train})
    if len(times) < 12:
        return None
    scores = {key: [] for key in makers}
    for idx_train, idx_val in TimeSeriesSplit(n_splits=folds).split(times):
        boundary = times[int(idx_val[0])]
        left = [r for r in train if r[0] in {times[i] for i in idx_train}
                and r[1] < boundary]
        right = [r for r in train if r[0] in {times[i] for i in idx_val}]
        if len(left) < 20 or len(right) < 4:
            return None
        xtr = [r[3] for r in left]
        ytr = [r[4] for r in left]
        xv = [r[3] for r in right]
        yv = [r[4] for r in right]
        for name, factory in makers.items():
            fit = factory().fit(xtr, ytr)
            scores[name].append(float(mean_absolute_error(yv, fit.predict(xv))))
    return {name: round(sum(scores[name]) / len(scores[name]), 6) for name in scores}


def evaluate_issuer_time_holdout(
    dataset: dict[str, Any], *, target_metric: str,
    feature_metrics: tuple[str, ...], as_of: str,
) -> dict[str, Any]:
    """Evaluate next-period regression on previously unseen issuers in a later period.

    Model selection uses CV on *training issuers and past timestamps only*.
    Holdout uses disjoint issuer identities AND the latest 25% timestamps.
    Return performance as a bounded, non-approval, non-probabilistic local result.
    """
    cutoff = _instant(as_of)
    if (type(dataset) is not dict or dataset.get("schema") != "kuodra.canonical.long.v1"
            or dataset.get("access_level") not in ("PUBLIC", "PRIVATE")
            or not _id(dataset.get("dataset_id")) or not _id(dataset.get("source_id"))
            or type(dataset.get("source_sha256")) is not str
            or _SHA.fullmatch(dataset["source_sha256"]) is None
            or type(dataset.get("records")) is not list
            or not 1 <= len(dataset["records"]) <= 5000
            or len(dataset["records"]) != dataset.get("rows")
            or type(feature_metrics) is not tuple or not 1 <= len(feature_metrics) <= 10
            or not _id(target_metric)
            or any(not _id(metric) for metric in feature_metrics)
            or target_metric in feature_metrics
            or len(set(feature_metrics)) != len(feature_metrics)):
        raise ValueError("GROUP_ML_CONTRACT_INVALID")

    rows_by_entity = defaultdict(lambda: defaultdict(dict))
    units: dict[str, str] = {}
    for r in dataset["records"]:
        if (type(r) is not dict
                or r.get("dataset_id") != dataset["dataset_id"]
                or r.get("source_id") != dataset["source_id"]
                or r.get("access_level") != dataset["access_level"]
                or r.get("evidence_sha256") != dataset["source_sha256"]
                or not all(_id(r.get(f)) for f in ("entity_id", "metric_id", "unit"))
                or type(r.get("value")) is not str):
            raise ValueError("GROUP_ML_LINEAGE_INVALID")
        observed, released = _instant(r.get("observation_at")), _instant(r.get("available_at"))
        if released < observed:
            raise ValueError("GROUP_ML_RELEASE_INVALID")
        if r["metric_id"] in units and units[r["metric_id"]] != r["unit"]:
            raise ValueError("GROUP_ML_UNIT_CONFLICT")
        units[r["metric_id"]] = r["unit"]
        try:
            value = float(Decimal(r["value"]))
        except (InvalidOperation, ValueError, OverflowError) as exc:
            raise ValueError("GROUP_ML_VALUE_INVALID") from exc
        if not math.isfinite(value):
            raise ValueError("GROUP_ML_VALUE_INVALID")
        cells = rows_by_entity[r["entity_id"]][r["observation_at"]]
        if r["metric_id"] in cells:
            raise ValueError("GROUP_ML_DUPLICATE_RECORD")
        cells[r["metric_id"]] = (released, value)

    if len(rows_by_entity) < 8:
        return _hold("INSUFFICIENT_DISTINCT_ISSUERS")
    unique_times = sorted({t for panel in rows_by_entity.values() for t in panel})
    if len(unique_times) < 48:
        return _hold("INSUFFICIENT_DISTINCT_TIMES")
    cut_at = unique_times[int(len(unique_times)*0.75)]
    cutoff_boundary = _instant(cut_at)
    # Deterministic issuer partitions avoid exposure of raw tenant identifiers.
    entities = sorted(rows_by_entity, key=lambda s: sha256(s.encode("utf-8")).hexdigest())
    hold_n = max(2, len(entities) // 4)
    unseen = set(entities[-hold_n:])
    training_entities = set(entities[:-hold_n])

    samples: list[tuple] = []
    for entity, panel in rows_by_entity.items():
        ordered = sorted(panel)
        for i in range(len(ordered)-1):
            t, future_t = ordered[i], ordered[i+1]
            observed = _instant(t)
            if observed > cutoff:
                continue
            features = []
            for metric in feature_metrics:
                v = panel[t].get(metric)
                if v is None or v[0] > observed:
                    break
                features.append(v[1])
            else:
                label = panel[future_t].get(target_metric)
                if label is not None and label[0] <= cutoff:
                    samples.append((observed, label[0], entity, features, label[1]))

    train = [s for s in samples if s[2] in training_entities
             and s[0] < cutoff_boundary and s[1] < cutoff_boundary]
    test = [s for s in samples if s[2] in unseen and s[0] >= cutoff_boundary]
    if (len(train) < 50 or len(test) < 12
            or len({s[2] for s in train}) < 5
            or len({s[2] for s in test}) < 2):
        return _hold("INSUFFICIENT_RELEASE_PURGED_GROUP_TIME_SAMPLES")
    if set(s[2] for s in train) & set(s[2] for s in test):
        raise ValueError("GROUP_ML_ISSUER_OVERLAP")
    if max(s[1] for s in train) >= min(s[0] for s in test):
        raise ValueError("GROUP_ML_TEMPORAL_LEAKAGE")

    try:
        from sklearn.dummy import DummyRegressor
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import mean_absolute_error
    except ImportError:
        return _hold("SKLEARN_OPTIONAL_DEPENDENCY_MISSING")
    factories = {"dummy_mean": lambda: DummyRegressor(strategy="mean"),
                 "ridge_scaled": lambda: make_pipeline(StandardScaler(), Ridge(alpha=1.0))}
    cv = _cv_mae(train, factories)
    if cv is None:
        return _hold("INSUFFICIENT_RELEASE_PURGED_FORWARD_CV")
    winner = min(cv, key=lambda name: (cv[name], name != "dummy_mean"))
    x_train = [s[3] for s in train]
    y_train = [s[4] for s in train]
    x_test = [s[3] for s in test]
    y_test = [s[4] for s in test]
    chosen = factories[winner]().fit(x_train, y_train)
    baseline = factories["dummy_mean"]().fit(x_train, y_train)
    selected_mae = float(mean_absolute_error(y_test, chosen.predict(x_test)))
    dummy_mae = float(mean_absolute_error(y_test, baseline.predict(x_test)))
    improvement = None if dummy_mae == 0 else round(100 * (dummy_mae-selected_mae) / dummy_mae, 3)
    return {"schema": "kuodra.ml.issuer-time-holdout.v1",
            "status": "EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED", "guard": "HOLD",
            "split": "DISJOINT_ISSUER_LATER_TIME_WITH_RELEASE_EMBARGO",
            "cv_policy": "FORWARD_TIME_TRAIN_ISSUERS_ONLY", "cv_folds": 3,
            "issuer_count": len(entities), "train_issuer_count": len(training_entities),
            "holdout_issuer_count": len(unseen), "train_n": len(train),
            "holdout_n": len(test), "cv_mae": cv, "selected_by_cv": winner,
            "holdout_mae": round(selected_mae, 6),
            "holdout_dummy_mae": round(dummy_mae, 6),
            "holdout_improvement_pct": improvement,
            "target_horizon": "NEXT_OBSERVATION",
            "calibrated_probability": None, "finance_validity_verified": False,
            "statistical_significance": "NOT_ESTABLISHED",
            "causal_claim": False, "production_ready": False, "network_requests": 0}


def evaluate_owner_local_group(vault: Any, principal: Any, *, dataset_id: str,
                               target_metric: str, feature_metrics: tuple[str, ...],
                               as_of: str) -> dict[str, Any]:
    """Trusted-local gateway wrapper: check ACL *before* copying data."""
    from copy import deepcopy
    from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
    if type(vault) is not OwnerLocalGateway or type(principal) is not VerifiedPrincipal:
        raise PermissionError("GATEWAY_ACCESS_DENIED")
    vault._check(principal, dataset_id=dataset_id)
    return evaluate_issuer_time_holdout(deepcopy(vault._datasets[dataset_id]),
        target_metric=target_metric, feature_metrics=feature_metrics, as_of=as_of)


def evaluate_owner_local_hybrid_group(vault: Any, principal: Any, *,
                                      public_dataset_id: str, private_dataset_id: str,
                                      target_metric: str, feature_metrics: tuple[str, ...],
                                      as_of: str) -> dict[str, Any]:
    """Same ACL-gated in-memory hybrid join; report is private, never exportable."""
    from .kuodra_hybrid import _build_joined
    if (type(target_metric) is not str or type(feature_metrics) is not tuple
            or not 1 <= len(feature_metrics) <= 10
            or not target_metric.startswith(("public.", "private."))
            or any(not isinstance(x, str) or not x.startswith(("public.", "private."))
                   for x in feature_metrics)
            or not {v.split(".")[0] for v in (target_metric, *feature_metrics)}
                   == {"public", "private"}):
        raise ValueError("HYBRID_GROUP_ML_SELECTION_INVALID")
    result = _build_joined(vault, principal,
        public_dataset_id=public_dataset_id, private_dataset_id=private_dataset_id,
        as_of=as_of)
    answer = (_hold("NO_OVERLAPPING_ISSUER_TIMES") if result["dataset"] is None
              else evaluate_issuer_time_holdout(result["dataset"],
                target_metric=target_metric, feature_metrics=feature_metrics, as_of=as_of))
    return {"schema": "kuodra.local-hybrid-group-time.v1",
            "status": "LOCAL_RESTRICTED_REVIEW_ONLY", "access_level": "PRIVATE",
            "guard": "HOLD", "public_export_allowed": False,
            "host_egress_policy_verified": False, "network_requests": 0,
            "data_rows_disclosed": False, "analysis": answer}
