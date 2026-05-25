---
name: alloy-shap-screen
description: Run SHAP-based feature importance analysis for selected alloy property models. Use when user needs to rank element features for each thermal or mechanical target, take the top 5 important elements per property, count elements that appear in at least two property rankings, and return the optimizable element set for later composition optimization.
---

# Alloy SHAP Screen

## Workflow

1. Load best model artifacts produced by `$alloy-ml-model-select`.
2. Run `Skills/alloy-shap-screen/scripts/rank_shap_features.py` with the same dataset used for training.
3. For each target, rank features by mean absolute SHAP value and keep the top 5.
4. Count features appearing in top-5 lists across targets.
5. Select elements appearing at least twice as optimizable elements.
6. If fewer than two targets are analyzed, use the top-5 features from the single target and explicitly state that recurrence filtering cannot be applied.

## ⚠️ 路径说明

该技能的脚本位于 `Skills/alloy-shap-screen/scripts/` 目录下。
请从**项目根目录**运行：

```bash
python Skills/alloy-shap-screen/scripts/rank_shap_features.py thermal_results.xlsx --model-dir models --top-k 5 --min-count 2 --output-json shap_screen.json
```

## Command

```bash
python Skills/alloy-shap-screen/scripts/rank_shap_features.py thermal_results.xlsx --model-dir models --top-k 5 --min-count 2 --output-json shap_screen.json
```

## Failure Handling

- If `shap` is unavailable, use permutation importance only as a fallback and label the result as non-SHAP.
- If a model artifact lacks feature metadata, stop and retrain with `$alloy-ml-model-select`.
- If top features include non-elements, return to `$alloy-excel-intake` and fix the feature schema.

## Handoff

After user confirmation, pass the optimizable element list to `$alloy-nsga3-optimize` and ask the user for each element's lower and upper bound.
