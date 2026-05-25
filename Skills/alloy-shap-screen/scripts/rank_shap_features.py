#!/usr/bin/env python3
"""Rank alloy features using SHAP, with a permutation fallback."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def fail(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def require_base_packages():
    try:
        import joblib  # type: ignore
        import numpy as np  # type: ignore
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover
        fail(f"Required packages are missing: {exc}", 3)
    return joblib, np, pd


def read_table(path: Path):
    _, _, pd = require_base_packages()
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return pd.read_excel(path)
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    fail(f"Unsupported file type: {suffix}")


def shap_importance(model, X, sample_size: int) -> tuple[str, list[float]]:
    import numpy as np
    import shap  # type: ignore

    """
    自动选择合适的 SHAP explainer，并返回每个特征的平均绝对 SHAP 分数。

    Returns
    -------
    ("shap", scores)
    """

    # 1. 抽样，减少 SHAP 计算量
    X_sample = (
        X.sample(n=min(sample_size, len(X)), random_state=42)
        if len(X) > sample_size
        else X
    )

    background = (
        X_sample.sample(n=min(50, len(X_sample)), random_state=42)
        if len(X_sample) > 50
        else X_sample
    )

    # 2. 判断模型类型
    model_name = (
        model.__class__.__name__.lower()
        + " "
        + model.__class__.__module__.lower()
    )

    tree_keywords = [
        "xgb",
        "xgboost",
        "lgbm",
        "lightgbm",
        "catboost",
        "forest",
        "tree",
        "gbm",
        "gradientboosting",
        "histgradientboosting",
        "extratrees",
    ]

    linear_keywords = [
        "linear",
        "logisticregression",
        "ridge",
        "lasso",
        "elasticnet",
        "sgdclassifier",
        "sgdregressor",
        "linearregression",
    ]

    is_tree_model = any(k in model_name for k in tree_keywords)
    is_linear_model = any(k in model_name for k in linear_keywords)

    # 3. 自动选择 explainer
    try:
        if is_tree_model:
            explainer = shap.TreeExplainer(model)
            values = explainer.shap_values(X_sample)

        elif is_linear_model:
            explainer = shap.LinearExplainer(model, background)
            values = explainer.shap_values(X_sample)

        else:
            # 通用解释器，通常比直接 KernelExplainer 更智能
            explainer = shap.Explainer(model.predict, background)
            values = explainer(X_sample)

    except Exception:
        # 兜底方案：最通用，但通常最慢
        explainer = shap.KernelExplainer(model.predict, background)
        values = explainer.shap_values(X_sample, nsamples=100)

    # 4. 统一提取 SHAP 数组
    if hasattr(values, "values"):
        arr = values.values
    else:
        arr = values

    # 5. 兼容分类模型返回 list 的情况
    # 例如 TreeExplainer 对二分类 / 多分类可能返回 [class0, class1, ...]
    if isinstance(arr, list):
        if len(arr) == 2:
            arr = arr[1]   # 二分类默认取正类
        else:
            arr = np.mean(np.abs(np.array(arr)), axis=0)

    arr = np.asarray(arr)

    # 6. 兼容三维输出
    # 常见形状：
    # (n_samples, n_features, n_classes)
    if arr.ndim == 3:
        if arr.shape[2] == 2:
            arr = arr[:, :, 1]   # 二分类取正类
        else:
            arr = np.mean(np.abs(arr), axis=2)

    # 7. 计算每个特征的重要性
    scores = np.abs(arr).mean(axis=0)

    return "shap", [float(x) for x in scores]

def permutation_importance(model, X, y) -> tuple[str, list[float]]:
    from sklearn.inspection import permutation_importance as sklearn_permutation_importance

    result = sklearn_permutation_importance(model, X, y, scoring="r2", n_repeats=10, random_state=42)
    return "permutation_importance", [float(x) for x in result["importances_mean"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    joblib, _, pd = require_base_packages()
    df = read_table(args.dataset)
    artifact_paths = sorted(args.model_dir.glob("*__best_model.joblib"))
    if not artifact_paths:
        fail(f"No best model artifacts found in {args.model_dir}")

    rankings: dict[str, Any] = {}
    counter: Counter[str] = Counter()
    methods: set[str] = set()

    for artifact_path in artifact_paths:
        artifact = joblib.load(artifact_path)
        model = artifact.get("model")
        target = str(artifact.get("target") or artifact_path.stem.replace("__best_model", ""))
        features = [str(f) for f in artifact.get("feature_columns", [])]
        if not model or not features:
            fail(f"Artifact missing model or feature metadata: {artifact_path}")
        missing = [feature for feature in features if feature not in df.columns]
        if missing:
            fail(f"Dataset is missing features required by {artifact_path.name}: {missing}")
        X = df[features].copy()
        for col in features:
            X[col] = pd.to_numeric(X[col], errors="coerce")
        X = X.dropna(axis=0)
        if X.empty:
            fail(f"No usable rows for SHAP analysis of target {target}")

        try:
            method, scores = shap_importance(model, X, args.sample_size)
        except Exception as exc:
            if target not in df.columns:
                fail(f"SHAP failed for {target} and permutation fallback needs target column: {exc}")
            y = pd.to_numeric(df.loc[X.index, target], errors="coerce")
            valid = y.notna()
            if not bool(valid.any()):
                fail(f"No usable target values for permutation fallback on {target}")
            method, scores = permutation_importance(model, X.loc[valid], y.loc[valid])

        methods.add(method)
        ranked = sorted(zip(features, scores), key=lambda item: item[1], reverse=True)
        top = [{"feature": f, "importance": s} for f, s in ranked[: args.top_k]]
        for item in top:
            counter[item["feature"]] += 1
        rankings[target] = {"method": method, "top_features": top}

    threshold = args.min_count if len(rankings) > 1 else 1
    selected = [feature for feature, count in counter.items() if count >= threshold]
    output = {
        "dataset": str(args.dataset),
        "model_dir": str(args.model_dir),
        "top_k": args.top_k,
        "min_count": args.min_count,
        "effective_min_count": threshold,
        "methods": sorted(methods),
        "target_rankings": rankings,
        "feature_counts": dict(counter),
        "selected_features": sorted(selected),
    }
    args.output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_json": str(args.output_json), "selected_features": sorted(selected)}, indent=2))


if __name__ == "__main__":
    main()
