#!/usr/bin/env python3
"""Run NSGA-III optimization over alloy composition variables."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


def fail(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def require_packages():
    try:
        import joblib  # type: ignore
        import numpy as np  # type: ignore
        import pandas as pd  # type: ignore
        from pymoo.algorithms.moo.nsga3 import NSGA3
        from pymoo.core.problem import Problem
        from pymoo.optimize import minimize
        from pymoo.util.ref_dirs import get_reference_directions
    except Exception as exc:  # pragma: no cover
        fail(f"Required packages are missing. Install pandas, joblib, scikit-learn, and pymoo: {exc}", 3)
    return {
        "joblib": joblib,
        "np": np,
        "pd": pd,
        "NSGA3": NSGA3,
        "Problem": Problem,
        "minimize": minimize,
        "get_reference_directions": get_reference_directions,
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"JSON file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail(f"Expected object JSON in {path}")
    return data


def load_artifacts(model_dir: Path, objectives: dict[str, str], joblib) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for path in model_dir.glob("*__best_model.joblib"):
        artifact = joblib.load(path)
        target = str(artifact.get("target") or path.stem.replace("__best_model", ""))
        artifacts[target] = artifact
    missing = [target for target in objectives if target not in artifacts]
    if missing:
        fail(f"Missing model artifacts for objectives: {missing}")
    return {target: artifacts[target] for target in objectives}


def validate_bounds(bounds: dict[str, Any]) -> tuple[list[str], list[float], list[float]]:
    variables: list[str] = []
    lower: list[float] = []
    upper: list[float] = []
    for element, pair in bounds.items():
        if not isinstance(pair, list) or len(pair) != 2:
            fail(f"Bounds for {element} must be [lower, upper].")
        lo, hi = float(pair[0]), float(pair[1])
        if not math.isfinite(lo) or not math.isfinite(hi):
            fail(f"Bounds for {element} must be finite.")
        if lo < 0 or hi < 0:
            fail(f"Bounds for {element} must be non-negative.")
        if lo > hi:
            fail(f"Lower bound exceeds upper bound for {element}.")
        variables.append(str(element))
        lower.append(lo)
        upper.append(hi)
    if not variables:
        fail("No optimization variables were provided.")
    return variables, lower, upper


def build_row(
    values: list[float],
    variables: list[str],
    baseline: dict[str, Any],
    feature_columns: list[str],
    sum_to: float | None,
    balance_element: str | None,
) -> tuple[dict[str, float], bool]:
    row = {str(k): float(v) for k, v in baseline.items()}
    for element, value in zip(variables, values):
        row[element] = float(value)

    if sum_to is not None:
        if balance_element:
            fixed_total = sum(v for k, v in row.items() if k != balance_element)
            balance_value = sum_to - fixed_total
            row[balance_element] = balance_value
        else:
            total = sum(row.get(f, 0.0) for f in feature_columns)
            if total <= 0:
                return row, False
            scale = sum_to / total
            for feature in feature_columns:
                row[feature] = row.get(feature, 0.0) * scale

    valid = all(row.get(feature, 0.0) >= 0 for feature in feature_columns)
    return row, valid


def write_table(df, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        df.to_excel(path, index=False)
    elif suffix in {".csv", ".txt"}:
        df.to_csv(path, index=False)
    else:
        fail(f"Unsupported output type: {suffix}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--bounds", type=Path, required=True)
    parser.add_argument("--objectives", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--population-size", type=int, default=120)
    parser.add_argument("--generations", type=int, default=200)
    parser.add_argument("--partitions", type=int, default=12)
    parser.add_argument("--sum-to", type=float, default=None)
    parser.add_argument("--balance-element", default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    deps = require_packages()
    np = deps["np"]
    pd = deps["pd"]
    bounds = load_json(args.bounds)
    objectives = {str(k): str(v).lower() for k, v in load_json(args.objectives).items()}
    baseline = load_json(args.baseline)
    variables, lower, upper = validate_bounds(bounds)

    for target, direction in objectives.items():
        if direction not in {"minimize", "maximize"}:
            fail(f"Objective direction for {target} must be minimize or maximize.")

    artifacts = load_artifacts(args.model_dir, objectives, deps["joblib"])
    first_artifact = next(iter(artifacts.values()))
    feature_columns = [str(f) for f in first_artifact.get("feature_columns", [])]
    if not feature_columns:
        fail("Model artifacts do not contain feature_columns metadata.")
    missing_baseline = [feature for feature in feature_columns if feature not in baseline and feature not in variables]
    if missing_baseline:
        fail(f"Baseline is missing fixed feature values: {missing_baseline}")

    Problem = deps["Problem"]

    class AlloyProblem(Problem):
        def __init__(self):
            super().__init__(
                n_var=len(variables),
                n_obj=len(objectives),
                n_constr=1,
                xl=np.array(lower, dtype=float),
                xu=np.array(upper, dtype=float),
            )

        def _evaluate(self, X, out, *args, **kwargs):
            rows: list[dict[str, float]] = []
            valid_flags: list[bool] = []
            for vector in X:
                row, valid = build_row(
                    list(vector), variables, baseline, feature_columns, args_sum_to, args_balance_element
                )
                rows.append(row)
                valid_flags.append(valid)

            frame = pd.DataFrame(rows)
            objective_values = []
            for target, direction in objectives.items():
                artifact = artifacts[target]
                model = artifact["model"]
                features = [str(f) for f in artifact["feature_columns"]]
                pred = model.predict(frame[features])
                if direction == "maximize":
                    pred = -pred
                objective_values.append(pred)
            F = np.column_stack(objective_values)
            G = np.array([0.0 if flag else 1.0 for flag in valid_flags]).reshape(-1, 1)
            out["F"] = F
            out["G"] = G

    args_sum_to = args.sum_to
    args_balance_element = args.balance_element
    ref_dirs = deps["get_reference_directions"]("das-dennis", len(objectives), n_partitions=args.partitions)
    algorithm = deps["NSGA3"](pop_size=args.population_size, ref_dirs=ref_dirs)
    result = deps["minimize"](
        AlloyProblem(),
        algorithm,
        ("n_gen", args.generations),
        seed=args.seed,
        verbose=False,
        save_history=False,
    )

    final_X = result.pop.get("X")
    rows: list[dict[str, float]] = []
    for vector in final_X:
        row, valid = build_row(list(vector), variables, baseline, feature_columns, args.sum_to, args.balance_element)
        if valid:
            rows.append(row)
    if not rows:
        fail("Optimization produced no valid final-generation compositions.")

    output_df = pd.DataFrame(rows)
    for target, direction in objectives.items():
        artifact = artifacts[target]
        features = [str(f) for f in artifact["feature_columns"]]
        output_df[target] = artifact["model"].predict(output_df[features])

    ordered = [col for col in feature_columns if col in output_df.columns]
    ordered += [col for col in output_df.columns if col not in ordered]
    output_df = output_df[ordered]
    write_table(output_df, args.output)
    print(json.dumps({"output": str(args.output), "rows": int(len(output_df))}, indent=2))


if __name__ == "__main__":
    main()
