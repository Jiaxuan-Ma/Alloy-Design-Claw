#!/usr/bin/env python3
"""Inspect alloy composition workbooks and optionally write a clean copy."""

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


def require_pandas():
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover
        fail(f"pandas/openpyxl is required to inspect workbooks: {exc}", 3)
    return pd


def load_elements() -> tuple[set[str], dict[str, str]]:
    config_path = Path(__file__).resolve().parents[1] / "config" / "elements.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    elements = set(data["elements"])
    aliases = {k.lower(): v for k, v in data.get("aliases", {}).items()}
    return elements, aliases


def canonical_symbol(token: str, elements: set[str], aliases: dict[str, str]) -> str | None:
    token = str(token).strip()
    if not token:
        return None
    if token in elements:
        return token
    lower = token.lower()
    if lower in aliases:
        return aliases[lower]
    if len(token) <= 2:
        candidate = token[0].upper() + token[1:].lower()
        if candidate in elements:
            return candidate
    return None


def column_to_element(name: Any, elements: set[str], aliases: dict[str, str]) -> str | None:
    raw = str(name).strip()
    direct = canonical_symbol(raw, elements, aliases)
    if direct:
        return direct

    cleaned = re.sub(r"\([^)]*\)|\[[^]]*\]|\{[^}]*\}", " ", raw)
    cleaned = re.sub(
        r"(?i)\b(wt|at|mass|atomic|mol|mole|fraction|frac|pct|percent|composition|content)\b",
        " ",
        cleaned,
    )
    cleaned = cleaned.replace("%", " ")
    compact = re.sub(r"[^A-Za-z]", "", cleaned)
    direct = canonical_symbol(compact, elements, aliases)
    if direct:
        return direct

    tokens = [t for t in re.split(r"[^A-Za-z]+", cleaned) if t]
    matches = [canonical_symbol(t, elements, aliases) for t in tokens]
    matches = [m for m in matches if m]
    unique = sorted(set(matches))
    return unique[0] if len(unique) == 1 else None


def read_table(path: Path, sheet: str | int | None):
    pd = require_pandas()
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return pd.read_excel(path, sheet_name=sheet if sheet is not None else 0)
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    fail(f"Unsupported file type: {suffix}")


def write_table(df, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        df.to_excel(path, index=False)
    elif suffix in {".csv", ".txt"}:
        df.to_csv(path, index=False)
    else:
        fail(f"Unsupported clean output type: {suffix}")


def default_clean_path(path: Path) -> Path:
    suffix = path.suffix.lower()
    clean_suffix = ".csv" if suffix in {".csv", ".txt"} else ".xlsx"
    return path.with_name(f"{path.stem}_composition_only{clean_suffix}")


def inspect(path: Path, sheet: str | None, write_clean: bool, clean_output: Path | None) -> dict[str, Any]:
    pd = require_pandas()
    elements, aliases = load_elements()
    df = read_table(path, sheet)

    issues: list[dict[str, Any]] = []
    mapping: dict[str, str] = {}
    duplicate_elements: dict[str, list[str]] = {}

    for col in df.columns:
        element = column_to_element(col, elements, aliases)
        if element:
            col_name = str(col)
            mapping[col_name] = element
            duplicate_elements.setdefault(element, []).append(col_name)

    composition_columns = list(mapping.keys())
    extra_columns = [str(c) for c in df.columns if str(c) not in mapping]

    for element, cols in duplicate_elements.items():
        if len(cols) > 1:
            issues.append({"type": "duplicate_element_columns", "element": element, "columns": cols})

    if not composition_columns:
        issues.append({"type": "no_composition_columns", "message": "No element-symbol columns were detected."})

    clean_df = df[composition_columns].copy() if composition_columns else df.iloc[:, 0:0].copy()
    numeric_summary: dict[str, Any] = {}
    for col in composition_columns:
        numeric = pd.to_numeric(clean_df[col], errors="coerce")
        missing_count = int(numeric.isna().sum())
        negative_count = int((numeric < 0).sum())
        if missing_count:
            issues.append({"type": "non_numeric_or_missing", "column": col, "count": missing_count})
        if negative_count:
            issues.append({"type": "negative_values", "column": col, "count": negative_count})
        clean_df[col] = numeric
        numeric_summary[col] = {
            "min": None if numeric.dropna().empty else float(numeric.min()),
            "max": None if numeric.dropna().empty else float(numeric.max()),
            "missing": missing_count,
        }

    empty_rows = clean_df.isna().all(axis=1)
    if bool(empty_rows.any()):
        issues.append({"type": "all_empty_composition_rows", "rows": [int(i) for i in clean_df.index[empty_rows].tolist()]})

    clean_path = None
    if write_clean and composition_columns:
        clean_path = clean_output or default_clean_path(path)
        write_table(clean_df, clean_path)

    report = {
        "input": str(path),
        "sheet": sheet if sheet is not None else 0,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "composition_columns": composition_columns,
        "composition_mapping": mapping,
        "extra_columns": extra_columns,
        "issues": issues,
        "numeric_summary": numeric_summary,
        "clean_workbook": str(clean_path) if clean_path else None,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--sheet", default=None, help="Excel sheet name. Defaults to the first sheet.")
    parser.add_argument("--write-clean", action="store_true", help="Write a composition-only workbook.")
    parser.add_argument("--clean-output", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    args = parser.parse_args()

    if not args.workbook.exists():
        fail(f"Workbook not found: {args.workbook}", 2)

    report = inspect(args.workbook, args.sheet, args.write_clean, args.clean_output)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json:
        args.output_json.write_text(text + "\n", encoding="utf-8")

    blocking = {"no_composition_columns", "duplicate_element_columns", "non_numeric_or_missing", "negative_values"}
    if any(issue["type"] in blocking for issue in report["issues"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
