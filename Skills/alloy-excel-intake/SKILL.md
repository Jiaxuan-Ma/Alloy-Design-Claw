---
name: alloy-excel-intake
description: Inspect high-temperature alloy Excel workbooks before Thermo-Calc or ML work. Read uploaded .xlsx/.xls/.csv alloy datasets, decide whether rows contain only alloy composition columns, identify extra metadata or label columns, ask the user before dropping columns, and create a composition-only working file without overwriting the source.
---

# Alloy Excel Intake

## Workflow

1. Run `python Skills/alloy-excel-intake/scripts/inspect_excel.py input.xlsx --output-json report.json`.
2. If `extra_columns` is non-empty, tell the user the exact extra columns and ask whether to exclude them from composition workflow.
3. Only after confirmation, run with `--write-clean` or `--clean-output`.
4. If the user agrees, create a composition-only working workbook. Never overwrite the original file.
5. If the user refuses deletion, preserve the original workbook and create a separate composition-only working workbook for Thermo-Calc and ML. Keep extra columns only as metadata unless the user explicitly maps them as labels.
6. Stop and ask for correction when compositions contain negative values, non-numeric values, duplicate columns, all-empty rows, or no element columns.

## ⚠️ 路径说明

该技能的脚本位于 `Skills/alloy-excel-intake/scripts/` 目录下。
执行命令时，请确保从**项目根目录**运行，并使用完整路径：

```bash
python Skills/alloy-excel-intake/scripts/inspect_excel.py input.xlsx --write-clean
```

## Commands

Use:

```bash
python Skills/alloy-excel-intake/scripts/inspect_excel.py input.xlsx --write-clean
```

Useful options:

```bash
python Skills/alloy-excel-intake/scripts/inspect_excel.py input.xlsx --sheet Sheet1 --output-json report.json --clean-output clean.xlsx
```

The script writes a JSON report with `composition_columns`, `extra_columns`, `issues`, and optional `clean_workbook`.

## Decisions

- Do not infer labels silently from extra columns in a composition-only thermal workflow.
- For mechanical-property datasets, use `$alloy-mechanics-filter` because label confirmation is a separate task.
- Use `config/elements.json` as the element-symbol source. Extend it only when the workbook uses approved aliases.

## References

Read `references/excel-schema.md` when the workbook has unusual units, label columns, or composition normalization questions.
