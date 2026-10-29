"""KIC conditional AutoML: synthetic historical baseline *only* UI.

No real company/market training. No ML fit or Guard decision changes.
"""
from __future__ import annotations

import json

from .temporal_baseline import evaluate_historical_baseline, synthetic_temporal_rows

_MODE_KEY = "_kic_temporal_baseline_result"


def _safe_baseline(result: object) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("schema") != "proofinvest.temporal-baseline.v1":
        return False
    if any(result.get(k) is not False for k in (
        "model_trained", "external_source_authenticated", "guard_input_eligible",
        "investment_recommendation", "trade_executed", "live_api_called",
    )):
        return False
    if result.get("status") != "BASELINE_ONLY":
        return False
    if (result.get("mode") != "SYNTHETIC_POINT_IN_TIME_OFFLINE_ONLY"
            or result.get("baseline_evaluated") is not True
            or result.get("baseline") != "TRAIN_ONLY_MEAN_CONSTANT"):
        return False
    if not all(type(result.get(x)) is int and result[x] >= 0
               for x in ("train_n", "test_n", "purged_train_n")):
        return False
    metrics = result.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != {
        "train_mean", "heldout_mae", "heldout_rmse"
    }:
        return False
    from decimal import Decimal, InvalidOperation
    try:
        for value in metrics.values():
            if not isinstance(value, str) or not Decimal(value).is_finite():
                return False
    except InvalidOperation:
        return False
    return bool(result.get("train_n", 0) >= 24 and result.get("test_n", 0) >= 6
                and isinstance(result.get("train_end"), str)
                and isinstance(result.get("test_start"), str)
                and result["train_end"] < result["test_start"])


def render_temporal_baseline(st) -> None:
    st.title("ProofInvest — 시간순 AutoML 검증 게이트")
    st.warning(
        "SYNTHETIC_BASELINE_ONLY · AI AutoML Analyst의 평가/기준모델 개념만 선별 재사용. "
        "실제 SEC/시장/CPI 시계열은 출처·권리·공개시점 검증 미완료로 NO_TRAIN. "
        "ML 학습·수익률 예측·인과관계·투자 판단은 수행하지 않습니다."
    )
    st.info(
        "데이터 경계: 공개 발표시각·수정본 버전·원문 최초 확인시각이 예측시점 이후이면 제외. "
        "학습 목표값은 테스트 시작 전 확인된 것만 사용하며 테스트 기간을 분리합니다."
    )
    st.metric("실제 데이터 ML 학습", "NO_TRAIN")
    st.caption(
        "아래 버튼은 자체 생성한 40개 가상 기간만으로 학습 데이터의 평균값 기준선과 "
        "미래 구간의 MAE/RMSE를 계산합니다. 어떤 AI 모델도 훈련하지 않습니다."
    )
    if st.button("가상 40기간 기준 모델 검증", key="kic_temporal_baseline_run"):
        st.session_state.pop(_MODE_KEY, None)
        try:
            output = evaluate_historical_baseline(
                synthetic_temporal_rows(),
                evaluation_as_of="2025-01-01T00:00:00Z",
            )
            if not _safe_baseline(output):
                raise ValueError("Synthetic baseline gate refused")
            st.session_state[_MODE_KEY] = output
        except (ValueError, TypeError, ArithmeticError):
            st.error("시간순/출처 검증 불통과 — 기준모델 결과를 표시하지 않습니다.")
    result = st.session_state.get(_MODE_KEY)
    if result is None:
        return
    if not _safe_baseline(result):
        st.error("시계열 검증 기록 무결성 실패 — 보고서 내보내기를 차단했습니다.")
        return
    st.success("합성 기간 시간순 분리와 기준모델 홀드아웃 검증 통과")
    st.subheader("홀드아웃 검증 — 가상 기간 (단위 없음)")
    a, b, c = st.columns(3)
    a.metric("학습 기간 관측치", str(result["train_n"]))
    b.metric("테스트 기간 관측치", str(result["test_n"]))
    c.metric("지연 공개로 제외된 학습치", str(result["purged_train_n"]))
    st.dataframe([
        {"지표": "학습 평균 고정 기준선", "값": result["metrics"]["train_mean"]},
        {"지표": "미래 구간 MAE", "값": result["metrics"]["heldout_mae"]},
        {"지표": "미래 구간 RMSE", "값": result["metrics"]["heldout_rmse"]},
    ], use_container_width=True, hide_index=True)
    st.caption(
        "학습 " + result["train_start"] + " ~ " + result["train_end"]
        + " | 테스트 " + result["test_start"] + " ~ " + result["test_end"]
    )
    st.warning(
        "이 수치는 인공 데이터에 대한 기준선 오차이며 금융 예측 성능이 아닙니다. "
        "실제 금융 데이터와 Guard 판정으로 전파되지 않습니다."
    )
    st.download_button(
        "가상 시계열 기준선 JSON 다운로드",
        data=json.dumps(result, sort_keys=True, ensure_ascii=False,
                        indent=2, allow_nan=False),
        file_name="proofinvest_SYNTHETIC_BASELINE_ONLY.json",
        mime="application/json",
        key="kic_temporal_baseline_download",
    )
