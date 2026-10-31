"""Bounded, deterministic explanation of operator-supplied ML evaluation data.

No model training, LLM, network access, source authentication, investment
advice, or Guard approvals. An explanation is not proof of a valid model.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any
from urllib.parse import urlsplit

MAX_ML_REPORT_BYTES = 65_536
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_IDENT = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
_NUMBER = re.compile(r"-?(?:0|[1-9]\d{0,11})(?:\.\d{1,8})?\Z")
_STATUSES = {"EVALUATED", "NO_TRAIN", "INSUFFICIENT_EVIDENCE"}


def _fail(code: str):
    raise ValueError(code)


def _text(value: Any, label: str, limit: int = 120) -> str:
    if (type(value) is not str or not 0 < len(value) <= limit
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        _fail("INVALID_ML_" + label)
    return value


def _date(value: Any, label: str) -> date:
    raw = _text(value, label, 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        _fail("INVALID_ML_" + label)
    try:
        return date.fromisoformat(raw)
    except ValueError:
        _fail("INVALID_ML_" + label)


def _number(value: Any, label: str) -> Decimal:
    if type(value) is not str or not _NUMBER.fullmatch(value):
        _fail("INVALID_ML_" + label)
    try:
        result = Decimal(value)
    except InvalidOperation:
        _fail("INVALID_ML_" + label)
    if not result.is_finite() or result < 0:
        _fail("INVALID_ML_" + label)
    return result


def _exact(obj: Any, fields: set[str], label: str) -> dict:
    if type(obj) is not dict or set(obj) != fields:
        _fail("INVALID_ML_" + label + "_FIELDS")
    return obj


def _source(obj: Any, as_of: date) -> dict:
    row = _exact(obj, {"id", "url", "published_at", "sha256"}, "SOURCE")
    sid = _text(row["id"], "SOURCE_ID", 64)
    if not _IDENT.fullmatch(sid):
        _fail("INVALID_ML_SOURCE_ID")
    url = _text(row["url"], "SOURCE_URL", 350)
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment or parsed.path.startswith("//")
            or parsed.hostname.lower() == "localhost"
            or "." not in parsed.hostname or not parsed.hostname[0].isalnum()
            or any(x in parsed.hostname for x in (" ", "_"))):
        _fail("INVALID_ML_SOURCE_URL")
    release = _date(row["published_at"], "SOURCE_PUBLICATION")
    if release > as_of:
        _fail("ML_SOURCE_AFTER_AS_OF")
    if type(row["sha256"]) is not str or not _SHA.fullmatch(row["sha256"]):
        _fail("INVALID_ML_SOURCE_HASH")
    return {"id": sid, "url": url, "published_at": release.isoformat(),
            "sha256": row["sha256"], "authenticated": False}


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_ML_JSON_KEY")
        result[key] = value
    return result


def parse_ml_evaluation_json(raw: bytes) -> dict:
    """Strictly parse one bounded JSON object; never write or fetch inputs."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_ML_REPORT_BYTES:
        _fail("INVALID_ML_JSON_SIZE")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates,
                           parse_constant=lambda _: _fail("INVALID_ML_NONFINITE"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail("INVALID_ML_JSON")
    if type(value) is not dict:
        _fail("INVALID_ML_JSON_ROOT")
    return value


def explain_ml_evaluation(payload: Any, *, expected_issuer_cik: str | None = None,
                          analysis_as_of: str | None = None) -> dict:
    """Explain claimed historical evaluation, explicitly NOT validating ML truth.

    The input must have exactly the public, source-addressable evaluation
    contract documented below. All claims are attributed to user input.
    """
    if type(payload) is not dict or payload.get("schema") != "kuodra.ml-evaluation.v1":
        _fail("INVALID_ML_SCHEMA")
    status = payload.get("status")
    if status not in _STATUSES:
        _fail("INVALID_ML_STATUS")
    issuer = _text(payload.get("issuer_cik"), "ISSUER_CIK", 10)
    if not re.fullmatch(r"\d{10}", issuer) or issuer == "0000000000":
        _fail("INVALID_ML_ISSUER_CIK")
    as_of = _date(payload.get("as_of"), "AS_OF")
    if expected_issuer_cik is not None and issuer != expected_issuer_cik:
        _fail("ML_ISSUER_MISMATCH")
    if analysis_as_of is not None and as_of != _date(analysis_as_of, "EXPECTED_AS_OF"):
        _fail("ML_AS_OF_MISMATCH")
    common = {"schema", "status", "issuer_cik", "as_of"}
    if status != "EVALUATED":
        _exact(payload, common | {"reason_code"}, "NO_TRAIN")
        reason = _text(payload["reason_code"], "REASON_CODE", 64)
        if not _IDENT.fullmatch(reason):
            _fail("INVALID_ML_REASON_CODE")
        return {
            "schema": "kuodra.ml-explanation.v1", "status": status,
            "headline": "ML 분석 보류 — 검증 가능한 모델 결과가 없습니다.",
            "summary": "학습 또는 독립 검증 자료가 충분하지 않아 ML 결론을 제시하지 않습니다.",
            "reason_code": reason, "metric_comparison": None,
            "factors": [], "sources": [],
            "caveats": ["관측된 재무 사실과 ML 추정을 구분하십시오."],
            "model_verified": False, "source_authenticated": False,
            "ai_generated": False, "trade_signal": False,
        }
    _exact(payload, common | {"model_name", "target", "evaluation", "features", "sources"},
           "EVALUATED")
    model = _text(payload["model_name"], "MODEL_NAME", 80)
    target = _text(payload["target"], "TARGET", 100)
    ev = _exact(payload["evaluation"], {
        "split", "train_end", "test_start", "test_end", "train_rows", "test_rows",
        "metric", "baseline_value", "model_value"}, "EVALUATION")
    if ev["split"] != "WALK_FORWARD":
        _fail("ML_TEMPORAL_SPLIT_REQUIRED")
    train_end = _date(ev["train_end"], "TRAIN_END")
    test_start = _date(ev["test_start"], "TEST_START")
    test_end = _date(ev["test_end"], "TEST_END")
    if not train_end < test_start <= test_end <= as_of:
        _fail("ML_FUTURE_OR_OVERLAPPING_HOLDOUT")
    if (type(ev["train_rows"]) is not int or type(ev["test_rows"]) is not int
            or not 1 <= ev["train_rows"] <= 1_000_000
            or not 1 <= ev["test_rows"] <= 1_000_000):
        _fail("INVALID_ML_SAMPLE_COUNTS")
    metric = ev["metric"]
    if metric not in ("MAE", "RMSE"):
        _fail("INVALID_ML_METRIC")
    baseline = _number(ev["baseline_value"], "BASELINE")
    measured = _number(ev["model_value"], "MODEL_VALUE")
    better = measured < baseline
    if type(payload["sources"]) is not list or not 1 <= len(payload["sources"]) <= 12:
        _fail("INVALID_ML_SOURCES")
    sources = [_source(s, as_of) for s in payload["sources"]]
    by_id = {x["id"]: x for x in sources}
    if len(by_id) != len(sources):
        _fail("DUPLICATE_ML_SOURCE_ID")
    if type(payload["features"]) is not list or not 1 <= len(payload["features"]) <= 3:
        _fail("INVALID_ML_FEATURES")
    features = []
    seen = set()
    for feature in payload["features"]:
        row = _exact(feature, {"name", "method", "importance", "source_ids"}, "FEATURE")
        name = _text(row["name"], "FEATURE_NAME", 80)
        if name in seen:
            _fail("DUPLICATE_ML_FEATURE")
        seen.add(name)
        if row["method"] not in ("PERMUTATION_IMPORTANCE", "SHAP_ABSOLUTE_MEAN"):
            _fail("INVALID_ML_ATTRIBUTION_METHOD")
        importance = _number(row["importance"], "FEATURE_IMPORTANCE")
        ids = row["source_ids"]
        if (type(ids) is not list or not 1 <= len(ids) <= 12
                or any(type(sid) is not str or sid not in by_id for sid in ids)
                or len(set(ids)) != len(ids)):
            _fail("INVALID_ML_FEATURE_SOURCE_REFS")
        features.append({"name": name, "method": row["method"],
                         "importance_reported": str(importance), "source_ids": ids,
                         "interpretation": "입력된 모델 설명값상 참고 변수이며 인과관계·방향·예측확률을 뜻하지 않습니다."})
    comparison = ("입력된 과거 평가값에서 기준모델보다 오차가 낮았습니다."
                  if better else "입력된 과거 평가값에서 기준모델 대비 개선이 확인되지 않았습니다.")
    return {
        "schema": "kuodra.ml-explanation.v1", "status": "REPORTED_UNVERIFIED",
        "headline": "ML 평가 결과 — 사용자 제공 자료 (독립 검증 전)",
        "summary": f"{model}의 {target}에 대한 {metric} 비교: {comparison}",
        "metric_comparison": {
            "metric": metric, "lower_is_better": True,
            "baseline_reported": str(baseline), "model_reported": str(measured),
            "reported_improvement": better, "split_reported": "WALK_FORWARD",
            "train_end": train_end.isoformat(), "test_start": test_start.isoformat(),
            "test_end": test_end.isoformat(), "train_rows": ev["train_rows"],
            "test_rows": ev["test_rows"],
        },
        "factors": features, "sources": sources,
        "caveats": [
            "모델·출처·데이터 권리·평가 재현 여부는 독립적으로 검증되지 않았습니다.",
            "공시 및 경제지표의 실제 공개시점·수정 이력·미래정보 누출은 별도 확인해야 합니다.",
            "중요도는 원인, 변수 효과의 방향, 투자수익 확률 또는 거래 권고가 아닙니다.",
        ],
        "model_verified": False, "source_authenticated": False,
        "ai_generated": False, "trade_signal": False,
    }
