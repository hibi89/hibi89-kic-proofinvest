from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class ScoringConfig:
    task_type: str
    primary_metric: str
    scoring: dict[str, str]
    greater_is_better: bool = True

    def summary(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "primary_metric": self.primary_metric,
            "scoring": self.scoring,
            "greater_is_better": self.greater_is_better,
        }


def get_scoring_config(task_type: str | None, y: pd.Series | None = None) -> ScoringConfig:
    """
    task_type에 따라 cross_validate에서 사용할 scoring 구성 반환.

    classification:
        - accuracy
        - balanced_accuracy
        - f1_weighted
        - precision_weighted
        - recall_weighted

    regression:
        - r2
        - neg_mean_absolute_error
        - neg_root_mean_squared_error

    sklearn은 loss 계열 지표를 음수로 반환한다.
    예: neg_mean_absolute_error = -MAE
    """

    normalized_task = (task_type or "").lower().strip()

    if normalized_task in ["regression", "regressor"]:
        return ScoringConfig(
            task_type="regression",
            primary_metric="r2",
            scoring={
                "r2": "r2",
                "neg_mae": "neg_mean_absolute_error",
                "neg_rmse": "neg_root_mean_squared_error",
            },
            greater_is_better=True,
        )

    # 기본값은 classification으로 둔다.
    return ScoringConfig(
        task_type="classification",
        primary_metric="f1_weighted",
        scoring={
            "accuracy": "accuracy",
            "balanced_accuracy": "balanced_accuracy",
            "f1_weighted": "f1_weighted",
            "precision_weighted": "precision_weighted",
            "recall_weighted": "recall_weighted",
        },
        greater_is_better=True,
    )


def summarize_cv_scores(
    cv_result: dict[str, Any],
    scoring_config: ScoringConfig,
) -> dict[str, dict[str, float]]:
    """
    sklearn.model_selection.cross_validate 결과를 보기 좋은 dict로 변환.

    반환 예:
    {
        "accuracy": {"mean": 0.82, "std": 0.03},
        "f1_weighted": {"mean": 0.80, "std": 0.04}
    }
    """

    metrics: dict[str, dict[str, float]] = {}

    for metric_name in scoring_config.scoring.keys():
        key = f"test_{metric_name}"

        if key not in cv_result:
            continue

        values = cv_result[key]

        display_name = metric_name
        converted_values = values

        # sklearn의 neg_* 지표는 사람이 보기 좋게 양수로 바꾼다.
        if metric_name == "neg_mae":
            display_name = "mae"
            converted_values = -values

        elif metric_name == "neg_rmse":
            display_name = "rmse"
            converted_values = -values

        metrics[display_name] = {
            "mean": float(converted_values.mean()),
            "std": float(converted_values.std()),
        }

    return metrics