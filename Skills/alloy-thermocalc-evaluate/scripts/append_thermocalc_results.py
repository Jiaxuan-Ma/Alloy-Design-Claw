#!/usr/bin/env python3
"""Append TCNI12 Scheil calculation results to an alloy workbook."""

from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
from pathlib import Path
from typing import Any


DATABASE = "TCNI12"
DEFAULT_TIMEOUT_MINUTES = 10.0
DEFAULT_HEARTBEAT_SECONDS = 30.0
OUTPUT_RESULT_KEYS = {
    "freeze range": "STR_K",
    "melt viscosity": "MV_Pa_s",
    "surface tension": "ST_N_per_m",
    "latent heat": "LH_J_per_g",
}
DEFAULT_OUTPUTS = list(OUTPUT_RESULT_KEYS)


class ProgressReporter:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.started_at = time.monotonic()

    def log(
        self,
        message: str,
        *,
        row_position: int | None = None,
        row_count: int | None = None,
        row_index: Any = None,
        stage: str | None = None,
        elapsed: float | None = None,
    ) -> None:
        if not self.enabled:
            return

        parts = [time.strftime("%Y-%m-%d %H:%M:%S")]
        if row_position is not None and row_count:
            percent = (row_position / row_count) * 100
            width = 20
            filled = max(0, min(width, int(width * row_position / row_count)))
            bar = "#" * filled + "-" * (width - filled)
            parts.append(f"[{bar}] {row_position}/{row_count} {percent:5.1f}%")
        if row_index is not None:
            parts.append(f"row={row_index}")
        if stage:
            parts.append(stage)

        seconds = elapsed if elapsed is not None else time.monotonic() - self.started_at
        parts.append(f"elapsed={format_duration(seconds)}")
        print(" | ".join(parts) + f" | {message}", file=sys.stderr, flush=True)


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h{minute:02d}m{sec:02d}s"
    if minute:
        return f"{minute:d}m{sec:02d}s"
    return f"{sec:d}s"


def start_heartbeat(
    reporter: ProgressReporter,
    *,
    heartbeat_seconds: float,
    row_position: int,
    row_count: int,
    row_index: Any,
    timeout_minutes: float,
) -> tuple[threading.Event, threading.Thread | None]:
    stop_event = threading.Event()
    if not reporter.enabled or heartbeat_seconds <= 0:
        return stop_event, None

    started_at = time.monotonic()

    def beat() -> None:
        while not stop_event.wait(heartbeat_seconds):
            elapsed = time.monotonic() - started_at
            reporter.log(
                f"Scheil calculation is still running; timeout limit is {timeout_minutes:g} min.",
                row_position=row_position,
                row_count=row_count,
                row_index=row_index,
                stage="calculate",
                elapsed=elapsed,
            )

    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    return stop_event, thread


def fail(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def require_pandas():
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover
        fail(f"pandas/openpyxl is required for workbook I/O: {exc}", 3)
    return pd


def require_tc_python():
    try:
        import tc_python as tc  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "tc_python is required. Run this script with the Thermo-Calc Python interpreter."
        ) from exc
    return tc


def read_table(path: Path):
    pd = require_pandas()
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


def finite_number(value: Any) -> float:
    try:
        number = float(value)
    except Exception as exc:
        raise ValueError(f"non-numeric value {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"non-finite value {value!r}")
    return number


def values_present(values: Any, minimum: int = 1) -> bool:
    return values is not None and len(values) >= minimum


def empty_result(row_index: Any) -> dict[str, Any]:
    return {
        "index": row_index,
        "STR_K": None,
        "LH_J_per_g": None,
        "MV_Pa_s": None,
        "ST_N_per_m": None,
        "status": "pending",
        "error": None,
    }


def run_scheil_calculation(
    row_index: Any,
    composition: dict[str, float],
    balance_element: str,
    timeout_minutes: float,
    reporter: ProgressReporter | None = None,
    row_position: int | None = None,
    row_count: int | None = None,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
) -> dict[str, Any]:
    """Run the single-alloy Scheil calculation used by tc-skill.py."""
    result = empty_result(row_index)
    reporter = reporter or ProgressReporter(False)
    row_position = row_position or 1
    row_count = row_count or 1
    row_started_at = time.monotonic()

    try:
        reporter.log(
            "Importing TC-Python.",
            row_position=row_position,
            row_count=row_count,
            row_index=row_index,
            stage="setup",
        )
        tc = require_tc_python()
        active_composition = {
            str(name).strip(): number
            for name, value in composition.items()
            if (number := finite_number(value)) != 0.0
        }
        balance_element = str(balance_element).strip()
        elements = list(dict.fromkeys([balance_element, *active_composition]))

        reporter.log(
            f"Opening Thermo-Calc session with {DATABASE}; elements={', '.join(elements)}.",
            row_position=row_position,
            row_count=row_count,
            row_index=row_index,
            stage="database",
        )
        with tc.TCPython() as start:
            calc = (
                start.select_database_and_elements(DATABASE, elements)
                .get_system()
                .with_scheil_calculation()
                .set_composition_unit(tc.CompositionUnit.MASS_PERCENT)
            )

            for element, value in active_composition.items():
                calc = calc.set_composition(element, value)

            reporter.log(
                f"Starting Scheil calculation; timeout limit is {timeout_minutes:g} min.",
                row_position=row_position,
                row_count=row_count,
                row_index=row_index,
                stage="calculate",
            )
            stop_heartbeat, heartbeat_thread = start_heartbeat(
                reporter,
                heartbeat_seconds=heartbeat_seconds,
                row_position=row_position,
                row_count=row_count,
                row_index=row_index,
                timeout_minutes=timeout_minutes,
            )
            try:
                scheil_result = calc.calculate(timeout_in_minutes=timeout_minutes)
            finally:
                stop_heartbeat.set()
                if heartbeat_thread is not None:
                    heartbeat_thread.join(timeout=1)
            reporter.log(
                "Scheil calculation finished; extracting thermal values.",
                row_position=row_position,
                row_count=row_count,
                row_index=row_index,
                stage="extract",
                elapsed=time.monotonic() - row_started_at,
            )
            temp, _ = scheil_result.get_values_of(
                tc.ScheilQuantity.temperature(),
                tc.ScheilQuantity.mole_fraction_of_all_liquid(),
            )

            if values_present(temp, 2):
                result["STR_K"] = round(temp[-1] - temp[0], 2)

            _, latent_heat_gram = scheil_result.get_values_of(
                tc.ScheilQuantity.temperature(),
                tc.ScheilQuantity.latent_heat_per_gram(),
            )
            if values_present(latent_heat_gram):
                result["LH_J_per_g"] = round(abs(latent_heat_gram[0]), 4)

            _, viscosity = scheil_result.get_values_of(
                tc.ScheilQuantity.temperature(),
                tc.ScheilQuantity.dynamic_viscosity("LIQUID"),
            )
            if values_present(viscosity):
                result["MV_Pa_s"] = round(viscosity[0], 6)

            _, surface_tension = scheil_result.get_values_of(
                tc.ScheilQuantity.temperature(),
                tc.ScheilQuantity.surface_tension("LIQUID"),
            )
            if values_present(surface_tension):
                result["ST_N_per_m"] = round(surface_tension[0], 6)

            result["status"] = "success"
            reporter.log(
                "Row completed successfully.",
                row_position=row_position,
                row_count=row_count,
                row_index=row_index,
                stage="success",
                elapsed=time.monotonic() - row_started_at,
            )
    except Exception as exc:
        result["status"] = "failed"
        tc_crash = getattr(locals().get("tc"), "UnrecoverableCalculationException", ())
        prefix = "Engine crashed" if isinstance(exc, tc_crash) else "Exception"
        result["error"] = f"{prefix}: {exc}"
        reporter.log(
            result["error"],
            row_position=row_position,
            row_count=row_count,
            row_index=row_index,
            stage="failed",
            elapsed=time.monotonic() - row_started_at,
        )

    return result


def write_result(df, row_index: Any, outputs: list[str], result: dict[str, Any]) -> None:
    for output in outputs:
        value = result.get(OUTPUT_RESULT_KEYS[output])
        if value is not None:
            value = finite_number(value)
        df.at[row_index, output] = value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--parameters", nargs="+", default=DEFAULT_OUTPUTS)
    parser.add_argument("--features", nargs="*", default=None)
    parser.add_argument("--balance-element", default="Fe")
    parser.add_argument("--timeout-minutes", type=float, default=DEFAULT_TIMEOUT_MINUTES)
    parser.add_argument("--heartbeat-seconds", type=float, default=DEFAULT_HEARTBEAT_SECONDS)
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failures-json", type=Path, default=None)
    parser.add_argument("--on-error", choices=["fail", "skip"], default="fail")
    args = parser.parse_args()

    if not args.workbook.exists():
        fail(f"Workbook not found: {args.workbook}")
    if args.timeout_minutes <= 0:
        fail("--timeout-minutes must be greater than zero.")
    if args.heartbeat_seconds < 0:
        fail("--heartbeat-seconds must be zero or greater.")

    unknown_outputs = [name for name in args.parameters if name not in OUTPUT_RESULT_KEYS]
    if unknown_outputs:
        fail(f"Unsupported Scheil output columns: {unknown_outputs}")

    pd = require_pandas()
    df = read_table(args.workbook)
    features = args.features or [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    missing = [col for col in features if col not in df.columns]
    if missing:
        fail(f"Feature columns not found: {missing}")
    if not features:
        fail("No composition feature columns were provided or detected.")

    for parameter in args.parameters:
        if parameter not in df.columns:
            df[parameter] = pd.NA

    failures: list[dict[str, Any]] = []
    reporter = ProgressReporter(enabled=not args.no_progress)
    reporter.log(
        (
            f"Loaded {len(df)} rows; features={', '.join(str(col) for col in features)}; "
            f"outputs={', '.join(args.parameters)}."
        ),
        stage="start",
    )
    for row_position, (row_index, row) in enumerate(df.iterrows(), start=1):
        composition = {str(col): finite_number(row[col]) for col in features}
        result = run_scheil_calculation(
            row_index,
            composition,
            balance_element=args.balance_element,
            timeout_minutes=args.timeout_minutes,
            reporter=reporter,
            row_position=row_position,
            row_count=len(df),
            heartbeat_seconds=args.heartbeat_seconds,
        )
        write_result(df, row_index, list(args.parameters), result)

        if result["status"] == "failed":
            failure = {
                "row_index": int(row_index) if isinstance(row_index, int) else str(row_index),
                "composition": composition,
                "error": result["error"],
            }
            failures.append(failure)
            if args.on_error == "fail":
                print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
                raise SystemExit(1)

    reporter.log(f"Writing results to {args.output}.", stage="write")
    write_table(df, args.output)
    if failures or args.failures_json:
        failures_path = args.failures_json or args.output.with_suffix(".failures.json")
        failures_path.write_text(json.dumps(failures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        reporter.log(f"Wrote failure report to {failures_path}.", stage="write")
    reporter.log("Thermo-Calc batch finished.", stage="done")
    print(json.dumps({"output": str(args.output), "rows": int(len(df)), "failures": len(failures)}, indent=2))


if __name__ == "__main__":
    main()
