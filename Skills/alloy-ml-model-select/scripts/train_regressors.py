#!/usr/bin/env python3
"""Train candidate alloy regressors and select the best model by R2."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def fail(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def require_packages():
    try:
        import joblib  # type: ignore
        import pandas as pd  # type: ignore
        from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
        from sklearn.impute import SimpleImputer
        from sklearn.metrics import r2_score
        from sklearn.model_selection import KFold, cross_val_score, train_test_split
        from sklearn.neighbors import KNeighborsRegressor
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.svm import SVR
    except Exception as exc:  # pragma: no cover
        fail(f"Required packages are missing: {exc}", 3)
    return {
        "joblib": joblib,
        "pd": pd,
        "ExtraTreesRegressor": ExtraTreesRegressor,
        "GradientBoostingRegressor": GradientBoostingRegressor,
        "RandomForestRegressor": RandomForestRegressor,
        "SimpleImputer": SimpleImputer,
        "r2_score": r2_score,
        "KFold": KFold,
        "cross_val_score": cross_val_score,
        "train_test_split": train_test_split,
        "KNeighborsRegressor": KNeighborsRegressor,
        "Pipeline": Pipeline,
        "StandardScaler": StandardScaler,
        "SVR": SVR,
    }


def read_table(path: Path):
    deps = require_packages()
    pd = deps["pd"]
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return pd.read_excel(path)
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    fail(f"Unsupported file type: {suffix}")


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "target"


def candidate_models(deps: dict[str, Any], n_rows: int, random_state: int) -> dict[str, Any]:
    Pipeline = deps["Pipeline"]
    SimpleImputer = deps["SimpleImputer"]
    StandardScaler = deps["StandardScaler"]
    SVR = deps["SVR"]
    KNeighborsRegressor = deps["KNeighborsRegressor"]
    RandomForestRegressor = deps["RandomForestRegressor"]
    ExtraTreesRegressor = deps["ExtraTreesRegressor"]
    GradientBoostingRegressor = deps["GradientBoostingRegressor"]

    neighbors = max(1, min(5, n_rows - 1))
    return {
        "svr_rbf": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", SVR(kernel="rbf", C=100.0, epsilon=0.1, gamma="scale")),
        ]),
        "knn": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", KNeighborsRegressor(n_neighbors=neighbors)),
        ]),
        "random_forest": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", RandomForestRegressor(n_estimators=300, random_state=random_state)),
        ]),
        "extra_trees": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", ExtraTreesRegressor(n_estimators=300, random_state=random_state)),
        ]),
        "gradient_boosting": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", GradientBoostingRegressor(random_state=random_state)),
        ]),
    }


def score_model(model, X, y, deps: dict[str, Any], cv: int, random_state: int) -> dict[str, Any]:
    import numpy as np

    n_rows = len(y)
    if n_rows >= max(12, cv):
        n_splits = min(cv, n_rows)
        splitter = deps["KFold"](n_splits=n_splits, shuffle=True, random_state=random_state)
        scores = deps["cross_val_score"](model, X, y, scoring="r2", cv=splitter)
        return {
            "method": f"{n_splits}-fold_cv",
            "r2_mean": float(np.mean(scores)),
            "r2_std": float(np.std(scores)),
        }
    if n_rows >= 5:
        X_train, X_test, y_train, y_test = deps["train_test_split"](
            X, y, test_size=max(1, int(round(n_rows * 0.2))), random_state=random_state
        )
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        return {
            "method": "holdout_small_n",
            "r2_mean": float(deps["r2_score"](y_test, pred)),
            "r2_std": None,
        }
    model.fit(X, y)
    pred = model.predict(X)
    return {
        "method": "in_sample_tiny_n",
        "r2_mean": float(deps["r2_score"](y, pred)),
        "r2_std": None,
        "warning": "Fewer than 5 rows; score is not reliable.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--features", nargs="*", default=None)
    parser.add_argument("--targets", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cv", type=int, default=5)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    deps = require_packages()
    pd = deps["pd"]
    joblib = deps["joblib"]
    if not args.dataset.exists():
        fail(f"Dataset not found: {args.dataset}")

    df = read_table(args.dataset)
    missing_targets = [target for target in args.targets if target not in df.columns]
    if missing_targets:
        fail(f"Target columns not found: {missing_targets}")

    if args.features:
        features = args.features
    else:
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        features = [c for c in numeric_cols if c not in args.targets]
    missing_features = [feature for feature in features if feature not in df.columns]
    if missing_features:
        fail(f"Feature columns not found: {missing_features}")
    if not features:
        fail("No feature columns were provided or inferred.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, Any] = {
        "dataset": str(args.dataset),
        "features": [str(f) for f in features],
        "targets": {},
    }

    for target in args.targets:
        work = df[list(features) + [target]].copy()
        for col in features + [target]:
            work[col] = pd.to_numeric(work[col], errors="coerce")
        before = len(work)
        work = work.dropna(axis=0, subset=list(features) + [target])
        dropped = before - len(work)
        if len(work) < 3:
            fail(f"Target {target} has fewer than 3 usable rows after dropping missing values.")

        X = work[list(features)]
        y = work[target]
        models = candidate_models(deps, len(work), args.random_state)
        target_metrics: dict[str, Any] = {"dropped_rows": int(dropped), "models": {}}

        best_name = None
        best_score = -float("inf")
        best_model = None
        for name, model in models.items():
            model_metrics = score_model(model, X, y, deps, args.cv, args.random_state)
            target_metrics["models"][name] = model_metrics
            score = model_metrics["r2_mean"]
            if score > best_score:
                best_name = name
                best_score = score
                best_model = model

        assert best_name is not None and best_model is not None
        best_model.fit(X, y)
        artifact = {
            "model": best_model,
            "target": str(target),
            "feature_columns": [str(f) for f in features],
            "model_name": best_name,
            "selection_metric": "r2",
            "r2_mean": float(best_score),
            "n_rows": int(len(work)),
        }
        artifact_path = args.output_dir / f"{safe_name(str(target))}__best_model.joblib"
        joblib.dump(artifact, artifact_path)
        target_metrics["best_model"] = best_name
        target_metrics["best_artifact"] = str(artifact_path)
        target_metrics["best_r2_mean"] = float(best_score)
        if best_score < 0:
            target_metrics["warning"] = "Best R2 is negative; predictions may be worse than a mean baseline."
        metrics["targets"][str(target)] = target_metrics

    metrics_path = args.output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"metrics": str(metrics_path), "model_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
