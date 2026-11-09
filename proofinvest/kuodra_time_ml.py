"""Optional local-only time-held-out regression, selectively adapted from
AI_AutoML_Analyst@feature/kmong-v1 STANDARD chronology/Dummy/CV principles.

Only numeric rows already normalized by KUODRA. No persistence/HTTP/trading.
This is a *synthetic evaluation adapter*, not finance-validated forecasting.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from .kuodra_unified_core import _instant, _id


def evaluate_lagged_regression(dataset: dict[str, Any], *, target_metric: str,
                               feature_metrics: tuple[str, ...], as_of: str,
                               horizon_steps: int = 1) -> dict[str, Any]:
    cutoff = _instant(as_of)
    if (dataset.get("schema") != "kuodra.canonical.long.v1"
            or not _id(target_metric) or type(feature_metrics) is not tuple
            or not 1 <= len(feature_metrics) <= 10
            or len(set(feature_metrics)) != len(feature_metrics)
            or target_metric in feature_metrics
            or any(not _id(x) for x in feature_metrics)
            or type(horizon_steps) is not int or horizon_steps != 1):
        raise ValueError("ML_INPUT_CONTRACT_INVALID")
    # This adapter is deliberately one-issuer at a time until issuer-held-out
    # validation is added; mixing entities can spuriously inflate CV metrics.
    rows = dataset.get("records")
    if not isinstance(rows, list) or not rows or len(rows) != dataset.get("rows"):
        raise ValueError("ML_ROWS_CONTRACT_INVALID")
    entities = {r["entity_id"] for r in rows}
    if len(entities) != 1:
        return _withheld(dataset,"MULTI_ISSUER_GROUP_HOLDOUT_NOT_IMPLEMENTED")
    by_time: dict[str, dict[str, dict]] = {}
    for r in rows:
        if (r.get("dataset_id") != dataset["dataset_id"] or
                r.get("source_id") != dataset["source_id"] or
                r.get("access_level") != dataset["access_level"] or
                r.get("evidence_sha256") != dataset["source_sha256"]):
            raise ValueError("ML_LINEAGE_MISMATCH")
        observed,available=_instant(r["observation_at"]),_instant(r["available_at"])
        if available < observed:
            raise ValueError("ML_RELEASE_ORDER_INVALID")
        timestamp_rows=by_time.setdefault(r["observation_at"],{})
        if r["metric_id"] in timestamp_rows:
            raise ValueError("ML_DUPLICATE_TIMESERIES")
        timestamp_rows[r["metric_id"]]=r
    # Only the target's own dated observations establish forecasting periods.
    # Independent, unrelated high-frequency metrics must not silently split
    # NEXT_OBSERVATION labels or shift the chronological holdout.
    # An unreleased target row is not part of the operator's historical
    # as-of target calendar. It must not replace the next *known* target or
    # erase otherwise trainable samples merely because a later revision
    # arrived in the same source snapshot.
    times=sorted(t for t, cells in by_time.items()
                 if target_metric in cells
                 and _instant(t) <= cutoff
                 and _instant(cells[target_metric]["available_at"]) <= cutoff)
    samples=[]
    for index,t in enumerate(times[:-1]):
        next_t=times[index+1]
        features=[]
        for metric in feature_metrics:
            row=by_time[t].get(metric)
            if row is None or _instant(row["available_at"])>_instant(t):
                break
            features.append(float(Decimal(row["value"])))
        else:
            label=by_time[next_t].get(target_metric)
            if label is None or _instant(label["available_at"])>cutoff:
                continue
            # NEXT_OBSERVATION is not a constant calendar interval. Keep
            # its exact gap for the same pre-fit quality gate as group ML.
            days=(_instant(next_t)-_instant(t)).total_seconds()/86400.0
            samples.append((t,label["available_at"],features,
                            float(Decimal(label["value"])),days))
    if len(samples)<48:
        return _withheld(dataset,"INSUFFICIENT_POINT_IN_TIME_SAMPLES")
    hold_start=int(len(samples)*0.75)
    holdout=samples[hold_start:]
    hold_time=_instant(holdout[0][0])
    # Label embargo: a training label released after the holdout starts
    # cannot be used to fit any model used to predict that holdout.
    train=[s for s in samples[:hold_start] if _instant(s[1])<hold_time]
    if len(train)<30 or len(holdout)<10:
        return _withheld(dataset,"INSUFFICIENT_EMBARGOED_TRAIN_OR_HOLDOUT")
    gaps=[sample[4] for sample in train+holdout]
    low,high=min(gaps),max(gaps)
    if (low<=0 or high>366 or high>low*1.15+1e-9):
        return _withheld(dataset,"INCONSISTENT_NEXT_OBSERVATION_HORIZON")
    try:
        from sklearn.dummy import DummyRegressor
        from sklearn.linear_model import Ridge
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import mean_absolute_error
    except ImportError:
        return _withheld(dataset,"SKLEARN_OPTIONAL_DEPENDENCY_MISSING")
    candidates={"dummy_mean":lambda:DummyRegressor(strategy="mean"),
                "ridge_scaled":lambda:make_pipeline(StandardScaler(),Ridge(alpha=1.0))}
    folds=TimeSeriesSplit(n_splits=3)
    scores={k:[] for k in candidates}
    for train_ix,val_ix in folds.split(train):
        val_start=_instant(train[val_ix[0]][0])
        eligible=[i for i in train_ix if _instant(train[i][1])<val_start]
        if len(eligible)<8:
            return _withheld(dataset,"CV_LABEL_EMBARGO_TOO_SMALL")
        xtr=[train[i][2] for i in eligible]
        ytr=[train[i][3] for i in eligible]
        xv=[train[i][2] for i in val_ix]
        yv=[train[i][3] for i in val_ix]
        for name, maker in candidates.items():
            model=maker().fit(xtr,ytr)
            scores[name].append(float(mean_absolute_error(yv,model.predict(xv))))
    cv_mae={name:round(sum(errors)/len(errors),6) for name,errors in scores.items()}
    # Selection from training CV ONLY. Untouched holdout never used to select.
    best=min(cv_mae,key=lambda name:(cv_mae[name], name!="dummy_mean"))
    xtrain=[r[2] for r in train]
    ytrain=[r[3] for r in train]
    xhold=[r[2] for r in holdout]
    yhold=[r[3] for r in holdout]
    chosen=candidates[best]().fit(xtrain,ytrain)
    baseline=candidates["dummy_mean"]().fit(xtrain,ytrain)
    chosen_mae=float(mean_absolute_error(yhold,chosen.predict(xhold)))
    dummy_mae=float(mean_absolute_error(yhold,baseline.predict(xhold)))
    improvement=None if dummy_mae==0 else round(100*(dummy_mae-chosen_mae)/dummy_mae,3)
    return {"schema":"kuodra.ml.time-holdout.v1", "status":"EXPLORATORY_HOLDOUT_MEASURED",
            "dataset_id":dataset["dataset_id"], "access_level":dataset["access_level"],
            "source_sha256":dataset["source_sha256"], "single_entity_only":True,
            "feature_metrics":list(feature_metrics),"target_metric":target_metric,
            "target_horizon":"NEXT_OBSERVATION", "decision_as_of":as_of,
            "horizon_uniformity_policy":"INTERVAL_MAX_DIV_MIN_AT_MOST_1_15",
            "observed_horizon_min_days":round(low,6),
            "observed_horizon_max_days":round(high,6),
            "horizon_check_scope":"TRAIN_AND_HOLDOUT_INTERVALS_DATA_QUALITY_ONLY",
            "split":"CHRONOLOGICAL_WITH_RELEASE_EMBARGO", "cv_folds":3,
            "cv_mae":cv_mae,"selected_by_cv":best,
            "train_n":len(train),"holdout_n":len(holdout),
            "holdout_selected_mae":round(chosen_mae,6),
            "holdout_dummy_mae":round(dummy_mae,6),
            "holdout_improvement_pct":improvement,
            "statistical_significance":"NOT_ESTABLISHED",
            "calibrated_probability":None,"causal_claim":False,
            "production_ready":False,"guard":"HOLD", "network_requests":0}


def _withheld(dataset: dict, reason: str) -> dict:
    return {"schema":"kuodra.ml.time-holdout.v1","status":"NO_TRAIN",
            "reason":reason,"dataset_id":dataset["dataset_id"],
            "access_level":dataset["access_level"],"guard":"HOLD",
            "calibrated_probability":None,"production_ready":False,"network_requests":0}