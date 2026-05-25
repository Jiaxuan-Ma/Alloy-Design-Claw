---
name: alloy-mechanics-filter
description: Validate mechanical-property datasets and filter optimized alloy compositions by UTS and elongation predictions. Use when Codex needs to check whether UTS/EL models exist, ask the user whether to upload a mechanical dataset, confirm final label columns, train and select best regressors for UTS and EL by R2, predict mechanics for optimized compositions, ask for thresholds, and keep compositions meeting thresholds.
---

# Alloy Mechanics Filter

## Workflow

1. Check whether trained UTS and EL model artifacts already exist.
2. If missing, ask the user whether to upload a mechanical-property dataset.
3. If the user declines, report that casting-property optimization is complete and return the thermal optimization compositions.
4. If the user uploads data, inspect the workbook and ask the user to confirm which final columns are labels. Do not assume labels silently.
5. Train candidate regressors for UTS and EL using `$alloy-ml-model-select`.
6. Predict UTS and EL for the final NSGA-III compositions.
7. Ask the user for thresholds, for example `UTS >= 1000` and `EL >= 10`.
8. Run `Skills/alloy-mechanics-filter/scripts/filter_mechanics.py` and return only compositions satisfying all thresholds.

## Label Rule

Mechanical datasets often put labels in the last columns, but the user must confirm them. If more than two labels appear, ask which correspond to UTS and EL.

## ⚠️ 路径说明

该技能的脚本位于 `Skills/alloy-mechanics-filter/scripts/` 目录下。
请从**项目根目录**运行：

## Commands

Train models:

```bash
python Skills/alloy-ml-model-select/scripts/train_regressors.py mechanics.xlsx --targets UTS EL --output-dir mechanics_models
```

Filter compositions:

```bash
python Skills/alloy-mechanics-filter/scripts/filter_mechanics.py final_generation.csv --model-dir mechanics_models --threshold UTS>=1000 --threshold EL>=10 --output filtered_compositions.csv
```

## Failure Handling

If mechanics data has too few rows or poor R2, warn the user before filtering and include the residual risk in the final answer.
