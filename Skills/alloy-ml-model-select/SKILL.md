---
name: alloy-ml-model-select
description: Train and compare regression models for alloy thermophysical or mechanical properties. Use when user needs to build SVM/SVR, KNN, Random Forest, Extra Trees, or Gradient Boosting models from alloy composition features, score candidates with R2, select the best model per target property, and persist reusable model artifacts.
---

# Alloy ML Model Select

## Workflow

1. Confirm feature columns are alloy elements and target columns are known property labels.
2. Run `Skills/alloy-ml-model-select/scripts/train_regressors.py` once per workbook, passing all target columns.
3. Compare models by cross-validated R2 when enough rows exist; otherwise use a deterministic holdout split and report the limitation.
4. Select the model with the highest mean R2 for each target.
5. Save model artifacts and a metrics JSON file. Preserve feature order in every artifact.
6. Warn the user when R2 is negative, sample count is too small, labels contain missing values, or target leakage is suspected.

## ⚠️ 路径说明

该技能的脚本位于 `Skills/alloy-ml-model-select/scripts/` 目录下。
请从**项目根目录**运行：

```bash
python Skills/alloy-ml-model-select/scripts/train_regressors.py thermal_results.xlsx --targets "freeze range" "melt viscosity" "surface tension" "latent heat" --output-dir models
```

## Command

```bash
python Skills/alloy-ml-model-select/scripts/train_regressors.py thermal_results.xlsx --targets "freeze range" "melt viscosity" "surface tension" "latent heat" --output-dir models
```

Optional:

```bash
python Skills/alloy-ml-model-select/scripts/train_regressors.py mechanics.xlsx --features Ni Co Cr Al Ti Ta W Mo --targets UTS EL --cv 5 --output-dir mechanics_models
```

## Model Policy

Use models listed in `config/models.json` unless the user requests a change. Measure selection by `r2_mean`, and keep `r2_std` for confidence.

## Handoff

Use `$alloy-shap-screen` after thermal models are selected. Use `$alloy-mechanics-filter` for the later UTS/EL filtering phase.
