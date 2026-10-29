from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import (
    ElasticNet,
    Lasso,
    LinearRegression,
    LogisticRegression,
    Ridge,
    RidgeClassifier,
    SGDClassifier,
    SGDRegressor,
)
from sklearn.svm import SVC, SVR, LinearSVC, LinearSVR


@dataclass
class ModelSelectionResult:
    task_type: str
    data_size_level: str
    selected_model_names: list[str]
    excluded_model_names: list[str]
    models: dict[str, Any]
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "data_size_level": self.data_size_level,
            "selected_model_names": self.selected_model_names,
            "excluded_model_names": self.excluded_model_names,
            "policy": self.policy,
        }


def _data_size_level(n_rows: int, n_features: int) -> str:
    """
    행 수와 컬럼 수 기준으로 데이터 크기 레벨 판단.
    """
    if n_rows <= 5_000:
        return "small"

    if n_rows <= 50_000:
        return "medium"

    if n_rows <= 200_000:
        return "large"

    return "very_large"


def _limit_models(
    models: dict[str, Any],
    max_models: int,
) -> dict[str, Any]:
    return dict(list(models.items())[:max_models])


def select_model_candidates(
    task_type: str | None,
    n_rows: int,
    n_features: int,
    has_categorical_features: bool,
    random_state: int = 42,
    max_models: int | None = None,
) -> ModelSelectionResult:
    """
    데이터 크기와 문제 유형을 보고 실제 실행할 모델 후보를 선택한다.

    핵심:
    - 모델 후보군은 넓게 보유
    - 실제 실행은 데이터 크기에 맞춰 3~7개 정도만 선택
    - 큰 데이터에서는 SVC/SVR/KNN 같은 무거운 모델 제외
    - sparse output 가능성이 있는 범주형 데이터에서는 HistGradientBoosting 계열 제외
    """

    normalized_task = (task_type or "classification").lower().strip()

    if normalized_task in ["regression", "regressor"]:
        normalized_task = "regression"
    else:
        normalized_task = "classification"

    size_level = _data_size_level(
        n_rows=n_rows,
        n_features=n_features,
    )

    if max_models is None:
        if size_level == "small":
            max_models = 7
        elif size_level == "medium":
            max_models = 6
        else:
            max_models = 5

    excluded: list[str] = []
    policy: dict[str, Any] = {
        "n_rows": n_rows,
        "n_features": n_features,
        "has_categorical_features": has_categorical_features,
        "max_models": max_models,
        "rules": [],
    }

    if normalized_task == "classification":
        return _select_classification_models(
            size_level=size_level,
            n_rows=n_rows,
            has_categorical_features=has_categorical_features,
            random_state=random_state,
            max_models=max_models,
            excluded=excluded,
            policy=policy,
        )

    return _select_regression_models(
        size_level=size_level,
        n_rows=n_rows,
        has_categorical_features=has_categorical_features,
        random_state=random_state,
        max_models=max_models,
        excluded=excluded,
        policy=policy,
    )


def _select_classification_models(
    size_level: str,
    n_rows: int,
    has_categorical_features: bool,
    random_state: int,
    max_models: int,
    excluded: list[str],
    policy: dict[str, Any],
) -> ModelSelectionResult:
    all_models: dict[str, Any] = {
        "dummy_classifier": DummyClassifier(strategy="most_frequent"),
        "logistic_regression": LogisticRegression(max_iter=1000),
        "ridge_classifier": RidgeClassifier(),
        "sgd_classifier": SGDClassifier(
            loss="log_loss",
            max_iter=1000,
            tol=1e-3,
            random_state=random_state,
        ),
        "random_forest_classifier": RandomForestClassifier(
            n_estimators=100,
            random_state=random_state,
            n_jobs=-1,
        ),
        "extra_trees_classifier": ExtraTreesClassifier(
            n_estimators=100,
            random_state=random_state,
            n_jobs=-1,
        ),
        "gradient_boosting_classifier": GradientBoostingClassifier(
            random_state=random_state,
        ),
        "hist_gradient_boosting_classifier": HistGradientBoostingClassifier(
            random_state=random_state,
        ),
        "linear_svc": LinearSVC(
            max_iter=3000,
            random_state=random_state,
        ),
        "svc": SVC(),
    }

    if size_level == "small":
        selected_names = [
            "dummy_classifier",
            "logistic_regression",
            "ridge_classifier",
            "random_forest_classifier",
            "extra_trees_classifier",
            "gradient_boosting_classifier",
            "svc",
        ]
        policy["rules"].append("small 데이터이므로 SVC까지 포함했습니다.")

    elif size_level == "medium":
        selected_names = [
            "dummy_classifier",
            "logistic_regression",
            "ridge_classifier",
            "sgd_classifier",
            "random_forest_classifier",
            "extra_trees_classifier",
            "gradient_boosting_classifier",
        ]
        excluded.extend(["svc"])
        policy["rules"].append("medium 이상 데이터에서는 SVC를 제외했습니다.")

    else:
        selected_names = [
            "dummy_classifier",
            "logistic_regression",
            "sgd_classifier",
            "extra_trees_classifier",
            "random_forest_classifier",
        ]
        excluded.extend(["svc", "linear_svc", "gradient_boosting_classifier"])
        policy["rules"].append("large 이상 데이터에서는 빠른 선형/트리 앙상블 위주로 선택했습니다.")

    if not has_categorical_features and size_level in ["small", "medium", "large"]:
        if "hist_gradient_boosting_classifier" not in selected_names:
            selected_names.append("hist_gradient_boosting_classifier")
            policy["rules"].append("범주형 feature가 없어 HistGradientBoosting을 후보에 추가했습니다.")
    else:
        excluded.append("hist_gradient_boosting_classifier")
        policy["rules"].append("범주형 인코딩으로 sparse matrix 가능성이 있어 HistGradientBoosting은 제외했습니다.")

    selected_models = {
        name: all_models[name]
        for name in selected_names
        if name in all_models
    }

    selected_models = _limit_models(
        models=selected_models,
        max_models=max_models,
    )

    selected_model_names = list(selected_models.keys())

    excluded_model_names = sorted(
        set(all_models.keys()) - set(selected_model_names)
    )

    return ModelSelectionResult(
        task_type="classification",
        data_size_level=size_level,
        selected_model_names=selected_model_names,
        excluded_model_names=excluded_model_names,
        models=selected_models,
        policy=policy,
    )


def _select_regression_models(
    size_level: str,
    n_rows: int,
    has_categorical_features: bool,
    random_state: int,
    max_models: int,
    excluded: list[str],
    policy: dict[str, Any],
) -> ModelSelectionResult:
    all_models: dict[str, Any] = {
        "dummy_regressor": DummyRegressor(strategy="mean"),
        "linear_regression": LinearRegression(),
        "ridge": Ridge(),
        "lasso": Lasso(max_iter=3000),
        "elastic_net": ElasticNet(max_iter=3000),
        "sgd_regressor": SGDRegressor(
            max_iter=1000,
            tol=1e-3,
            random_state=random_state,
        ),
        "random_forest_regressor": RandomForestRegressor(
            n_estimators=100,
            random_state=random_state,
            n_jobs=-1,
        ),
        "extra_trees_regressor": ExtraTreesRegressor(
            n_estimators=100,
            random_state=random_state,
            n_jobs=-1,
        ),
        "gradient_boosting_regressor": GradientBoostingRegressor(
            random_state=random_state,
        ),
        "hist_gradient_boosting_regressor": HistGradientBoostingRegressor(
            random_state=random_state,
        ),
        "linear_svr": LinearSVR(
            max_iter=3000,
            random_state=random_state,
        ),
        "svr": SVR(),
    }

    if size_level == "small":
        selected_names = [
            "dummy_regressor",
            "linear_regression",
            "ridge",
            "lasso",
            "random_forest_regressor",
            "extra_trees_regressor",
            "gradient_boosting_regressor",
        ]
        policy["rules"].append("small 회귀 데이터이므로 다양한 회귀 모델을 포함했습니다.")

    elif size_level == "medium":
        selected_names = [
            "dummy_regressor",
            "linear_regression",
            "ridge",
            "elastic_net",
            "random_forest_regressor",
            "extra_trees_regressor",
            "gradient_boosting_regressor",
        ]
        excluded.extend(["svr"])
        policy["rules"].append("medium 이상 데이터에서는 SVR을 제외했습니다.")

    else:
        selected_names = [
            "dummy_regressor",
            "ridge",
            "sgd_regressor",
            "extra_trees_regressor",
            "random_forest_regressor",
        ]
        excluded.extend(["svr", "linear_svr", "gradient_boosting_regressor"])
        policy["rules"].append("large 이상 회귀 데이터에서는 빠른 모델 위주로 선택했습니다.")

    if not has_categorical_features and size_level in ["small", "medium", "large"]:
        if "hist_gradient_boosting_regressor" not in selected_names:
            selected_names.append("hist_gradient_boosting_regressor")
            policy["rules"].append("범주형 feature가 없어 HistGradientBoostingRegressor를 후보에 추가했습니다.")
    else:
        excluded.append("hist_gradient_boosting_regressor")
        policy["rules"].append("범주형 인코딩으로 sparse matrix 가능성이 있어 HistGradientBoostingRegressor는 제외했습니다.")

    selected_models = {
        name: all_models[name]
        for name in selected_names
        if name in all_models
    }

    selected_models = _limit_models(
        models=selected_models,
        max_models=max_models,
    )

    selected_model_names = list(selected_models.keys())

    excluded_model_names = sorted(
        set(all_models.keys()) - set(selected_model_names)
    )

    return ModelSelectionResult(
        task_type="regression",
        data_size_level=size_level,
        selected_model_names=selected_model_names,
        excluded_model_names=excluded_model_names,
        models=selected_models,
        policy=policy,
    )