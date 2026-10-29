"""Evidence-gated, chronology-safe historical BASELINE evaluation for KIC.

Adapted narrowly from AI_AutoML_Analyst's DummyRegressor/holdout evaluation
approach; deliberately no pandas/sklearn model runner, internet or training.
Only self-authored synthetic point-in-time evidence is runnable here. Actual
issuer/macro observations remain NO_TRAIN until independently validated.
Results are research diagnostics, NEVER Guard evidence or investment advice.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from math import isqrt
from typing import Any

_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z", re.ASCII)
_NUM = re.compile(r"-?(?:0|[1-9]\d{0,11})(?:\.\d{1,6})?\Z", re.ASCII)
_MAX_ROWS = 2400
_MIN_TRAIN = 24
_MIN_TEST = 6
_ALLOWED_RIGHTS = "SYNTHETIC_SELF_AUTHORED"
_FORBIDDEN_FEATURE_PARTS = ("target", "label", "future", "response", "outcome")


def _instant(value: Any) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise ValueError("TIME_NOT_PINNED_UTC")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("TIME_NOT_PINNED_UTC") from exc


def _number(value: Any) -> Decimal:
    if not isinstance(value, str) or _NUM.fullmatch(value) is None:
        raise ValueError("NUMERIC_VALUE_INVALID")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("NUMERIC_VALUE_INVALID") from exc
    if not result.is_finite() or abs(result) > Decimal("999999999999"):
        raise ValueError("NUMERIC_VALUE_INVALID")
    return result


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "proofinvest.temporal-baseline.v1",
        "status": "NO_TRAIN",
        "reason_code": reason,
        "model_trained": False,
        "baseline_evaluated": False,
        "external_source_authenticated": False,
        "guard_input_eligible": False,
        "investment_recommendation": False,
        "trade_executed": False,
        "live_api_called": False,
        "metrics": None,
    }


def evaluate_historical_baseline(rows: Any, *, evaluation_as_of: str) -> dict[str, Any]:
    """Train-only historical mean vs later holdout labels, synthetic fixtures only.

    All timestamps MUST be documented UTC *available-at* times rather than
    period labels alone. Split is by unique prediction clock across issuers,
    avoiding same-date panel leakage; training targets published at/after
    the first test prediction are purged, not retroactively learned.
    Every holdout label must actually be available by evaluation_as_of.
    Normalization/model selection must be refitted on train in a future ML
    pipeline; this function NEVER trains a statistical model.
    """
    try:
        as_of = _instant(evaluation_as_of)
    except ValueError:
        return _blocked("INVALID_EVALUATION_CLOCK")
    if not isinstance(rows, list) or not _MIN_TRAIN + _MIN_TEST <= len(rows) <= _MAX_ROWS:
        return _blocked("INSUFFICIENT_INDEPENDENT_OBSERVATIONS")
    parsed = []
    seen = set()
    prior_targets: dict[str, datetime] = {}
    prior_dates: dict[str, datetime] = {}
    try:
        for row in rows:
            if not isinstance(row, dict) or row.get("source_kind") != "SYNTHETIC_FIXTURE":
                return _blocked("SOURCE_PROVENANCE_NOT_ELIGIBLE")
            if row.get("rights_status") != _ALLOWED_RIGHTS:
                return _blocked("SOURCE_RIGHTS_NOT_CLEARED")
            issuer = row.get("issuer_id")
            if not isinstance(issuer, str) or re.fullmatch(r"[A-Za-z0-9_-]{2,40}", issuer, re.ASCII) is None:
                return _blocked("INVALID_ISSUER_ID")
            pred = _instant(row.get("prediction_at"))
            label_end = _instant(row.get("target_period_end"))
            label_available = _instant(row.get("target_available_at"))
            label_seen = _instant(row.get("target_first_seen_at"))
            if not (pred < label_end <= label_available <= label_seen <= as_of):
                return _blocked("FUTURE_OR_BACKFILLED_TARGET")
            value = _number(row.get("target_value"))
            target_ref = row.get("target_source_ref")
            if not isinstance(target_ref, str) or not 1 <= len(target_ref) <= 128:
                return _blocked("TARGET_SOURCE_NOT_PINNED")
            key = (issuer, pred)
            if key in seen:
                return _blocked("DUPLICATED_ISSUER_PERIOD")
            seen.add(key)
            features = row.get("features")
            if not isinstance(features, dict) or not 1 <= len(features) <= 8:
                return _blocked("FEATURE_LINEAGE_MISSING")
            for name, feature in features.items():
                if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,40}", name, re.ASCII)
                        or any(word in name.lower() for word in _FORBIDDEN_FEATURE_PARTS)
                        or not isinstance(feature, dict)):
                    return _blocked("FEATURE_OR_TARGET_LEAKAGE")
                _number(feature.get("value"))
                released = _instant(feature.get("released_at"))
                vintage = _instant(feature.get("vintage_at"))
                seen_at = _instant(feature.get("first_seen_at"))
                if not released <= vintage <= seen_at <= pred:
                    return _blocked("FUTURE_FEATURE_OR_REVISION_LEAKAGE")
                reference = feature.get("source_ref")
                if not isinstance(reference, str) or not 1 <= len(reference) <= 128:
                    return _blocked("FEATURE_LINEAGE_MISSING")
            parsed.append((pred, issuer, label_end, label_available, label_seen, value, target_ref))
    except ValueError as exc:
        code = str(exc)
        return _blocked(code if code in ("TIME_NOT_PINNED_UTC", "NUMERIC_VALUE_INVALID") else
                        "INVALID_TEMPORAL_INPUT")
    # The label observation must not overlap the next prediction of the same
    # issuer, otherwise adjacent examples can encode the same future outcome.
    for pred, issuer, end, _, _, _, _ in sorted(parsed):
        if issuer in prior_dates and pred <= prior_dates[issuer]:
            return _blocked("DUPLICATED_ISSUER_PERIOD")
        if issuer in prior_targets and pred <= prior_targets[issuer]:
            return _blocked("OVERLAPPING_LABEL_HORIZONS")
        prior_dates[issuer], prior_targets[issuer] = pred, end
    if len({x[-1] for x in parsed}) != len(parsed):
        return _blocked("DUPLICATED_TARGET_SOURCE")
    # Prevent splitting multiple issuers' observations from the same date
    # across train/test.
    dates = sorted({r[0] for r in parsed})
    if len(dates) < _MIN_TRAIN + _MIN_TEST:
        return _blocked("INSUFFICIENT_INDEPENDENT_PERIODS")
    test_periods = max(_MIN_TEST, (len(dates) + 4) // 5)
    split = dates[-test_periods]
    train = [r for r in parsed if r[0] < split and r[4] < split]
    test = [r for r in parsed if r[0] >= split]
    purged = sum(r[0] < split for r in parsed) - len(train)
    if len(train) < _MIN_TRAIN or len({r[0] for r in train}) < _MIN_TRAIN or len(test) < _MIN_TEST:
        return _blocked("INSUFFICIENT_LEAK_FREE_TRAIN_HOLDOUT")
    if any(r[0] >= split or r[4] >= split for r in train):
        return _blocked("TARGET_TRAIN_CUTOFF_VIOLATION")
    # Deterministic baseline copied as a *pattern* from generic AutoML;
    # no sklearn imports, no fitted ML estimator and no test-value selection.
    with localcontext() as context:
        context.prec = 42
        mean = sum((r[5] for r in train), Decimal(0)) / Decimal(len(train))
        diffs = [abs(r[5] - mean) for r in test]
        mae = sum(diffs, Decimal(0)) / Decimal(len(test))
        rmse = (sum((d * d for d in diffs), Decimal(0)) / Decimal(len(test))).sqrt()
        q = Decimal("0.0001")
        values = {
            "train_mean": str(mean.quantize(q)),
            "heldout_mae": str(mae.quantize(q)),
            "heldout_rmse": str(rmse.quantize(q)),
        }
    canonical = json.dumps(rows, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), allow_nan=False)
    return {
        "schema": "proofinvest.temporal-baseline.v1",
        "status": "BASELINE_ONLY",
        "reason_code": "NO_ELIGIBLE_ML_MODEL_OR_AUTHENTICATED_DATA",
        "mode": "SYNTHETIC_POINT_IN_TIME_OFFLINE_ONLY",
        "model_trained": False,
        "baseline_evaluated": True,
        "external_source_authenticated": False,
        "guard_input_eligible": False,
        "investment_recommendation": False,
        "trade_executed": False,
        "live_api_called": False,
        "as_of": evaluation_as_of,
        "train_start": min(r[0] for r in train).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "train_end": max(r[0] for r in train).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "test_start": split.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "test_end": max(r[0] for r in test).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "train_n": len(train),
        "test_n": len(test),
        "purged_train_n": purged,
        "baseline": "TRAIN_ONLY_MEAN_CONSTANT",
        "metrics": values,
        "source_fixture_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "limitations": [
            "Synthetic-only; not an issuer, SEC, CPI or stock-market evaluation.",
            "Historical holdout evaluation of a fixed training mean; no ML trained.",
            "Train labels are available before first test prediction; no hindsight vintages.",
            "No cross-issuer extrapolation, causality, profitable alpha or risk advice.",
        ],
    }


def synthetic_temporal_rows(n: int = 40) -> list[dict[str, Any]]:
    """Reproducible invented 40-month style sample; never real issuer evidence."""
    from datetime import timedelta
    if type(n) is not int or not 30 <= n <= 120:
        raise ValueError("Synthetic sample size must be 30..120")
    first = datetime(2020, 1, 1)
    result = []
    for i in range(n):
        pred = first + timedelta(days=30 * i)
        end = pred + timedelta(days=15)
        observed = end + timedelta(days=3)
        feature_time = pred - timedelta(days=2)
        stamp = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        result.append({
            "source_kind": "SYNTHETIC_FIXTURE",
            "rights_status": _ALLOWED_RIGHTS,
            "issuer_id": "SYNTHETIC_ISSUER",
            "prediction_at": stamp(pred),
            "target_period_end": stamp(end),
            "target_available_at": stamp(observed),
            "target_first_seen_at": stamp(observed),
            "target_value": str(100 + (i // 3) * 2),
            "target_source_ref": f"self-authored:target:{i}",
            "features": {
                "lagged_context": {
                    "value": str(10 + i),
                    "released_at": stamp(feature_time),
                    "vintage_at": stamp(feature_time),
                    "first_seen_at": stamp(feature_time),
                    "source_ref": f"self-authored:feature:{i}",
                },
            },
        })
    return result
