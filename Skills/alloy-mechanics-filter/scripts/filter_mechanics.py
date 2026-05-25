#!/usr/bin/env python3
"""Predict UTS/EL for optimized compositions and filter by thresholds."""

from __future__ import annotations

import argparse
import json
import operator
import re
import sys
from pathlib import Path
from typing import Any, Callable


def fail(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def require_packages():
    try:
        import joblib  # type: ignore
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover
        fail(f"Required packages are missing: {exc}", 3)
    return joblib, pd


def read_table(path: Path):
    _, pd = require_packages()
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return pd.read_excel(path)
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    fail(f"Unsupported file type: {suffix}")


def write_table(df, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        df.to_excel(path, index=False)
    elif suffix in {".csv", ".txt"}:
        df.to_csv(path, index=False)
    else:
        fail(f"Unsupported output type: {suffix}")


OPS: dict[str, Callable[[Any, Any], Any]] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
}


def parse_threshold(text: str) -> tuple[str, str, float]:
    match = re.fullmatch(r"\s*([A-Za-z0-9_.-]+)\s*(>=|<=|>|<|==)\s*(-?\d+(?:\.\d+)?)\s*", text)
    if not match:
        fail(f"Invalid threshold: {text}. Use forms like UTS>=1000 or EL>=10.")
    target, op, value = match.groups()
    return target, op, float(value)


def load_artifacts(model_dir: Path, joblib) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for path in model_dir.glob("*__best_model.joblib"):
        artifact = joblib.load(path)
        target = str(artifact.get("target") or path.stem.replace("__best_model", ""))
        artifacts[target] = artifact
    if not artifacts:
        fail(f"No model artifacts found in {model_dir}")
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compositions", type=Path)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--threshold", action="append", default=[], help="Example: 'UTS>=1000'")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--predicted-output", type=Path, default=None)
    args = parser.parse_args()

    if not args.threshold:
        fail("At least one --threshold is required.")

    joblib, pd = require_packages()
    df = read_table(args.compositions)
    artifacts = load_artifacts(args.model_dir, joblib)
    thresholds = [parse_threshold(text) for text in args.threshold]
    missing_targets = [target for target, _, _ in thresholds if target not in artifacts]
    if missing_targets:
        fail(f"No model artifact found for threshold targets: {missing_targets}")

    for target, artifact in artifacts.items():
        features = [str(f) for f in artifact.get("feature_columns", [])]
        missing_features = [feature for feature in features if feature not in df.columns]
        if missing_features:
            fail(f"Compositions are missing features required by {target}: {missing_features}")
        X = df[features].copy()
        for col in features:
            X[col] = pd.to_numeric(X[col], errors="coerce")
        if X.isna().any().any():
            fail(f"Compositions contain missing or non-numeric values for model {target}.")
        df[f"pred_{target}"] = artifact["model"].predict(X)

    mask = pd.Series([True] * len(df), index=df.index)
    applied: list[dict[str, Any]] = []
    for target, op, value in thresholds:
        col = f"pred_{target}"
        mask &= OPS[op](df[col], value)
        applied.append({"target": target, "operator": op, "value": value, "prediction_column": col})

    filtered = df.loc[mask].copy()
    write_table(filtered, args.output)
    if args.predicted_output:
        write_table(df, args.predicted_output)
    summary = {
        "input_rows": int(len(df)),
        "kept_rows": int(len(filtered)),
        "thresholds": applied,
        "output": str(args.output),
        "predicted_output": str(args.predicted_output) if args.predicted_output else None,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
