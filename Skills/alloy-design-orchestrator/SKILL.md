---
name: alloy-design-orchestrator
description: Coordinate the full high-temperature alloy intelligent-design workflow across specialized skills. Use when user needs to orchestrate Excel intake, Thermo-Calc thermal property calculation, ML model selection, SHAP feature screening, NSGA-III multi-objective optimization, and optional UTS/EL mechanical-property filtering while keeping user confirmations explicit.
---

# Alloy Design Orchestrator

## Skill Map

Use the smallest needed skill for each step:

1. `$alloy-excel-intake`: inspect uploaded alloy workbook and create composition-only working data.
2. `$alloy-thermocalc-evaluate`: append Thermo-Calc thermal property calculations.
3. `$alloy-ml-model-select`: train candidate regressors and pick best R2 models.
4. `$alloy-shap-screen`: rank element features and select recurring top features.
5. `$alloy-nsga3-optimize`: collect bounds and optimize final-generation compositions.
6. `$alloy-mechanics-filter`: optionally train/predict UTS and EL and filter by thresholds.

## Conversation Flow

1. Confirm the user objective and uploaded workbook path. 
2. Do not delete columns, assume label columns, choose optimization bounds, or choose algorithm hyperparameters without user confirmation. 
3. Keep every intermediate file path visible in the working notes.
4. If the user declines mechanical-property upload, finish with the casting/thermal optimization result. 
5. If the user supplies mechanical data, construct UTS/EL regression models, 
6. If UTS/EL models are existing, use them to predict UTS/EL for the optimized compositions and finally ask the user to confirm the UTS/EL thresholds. and filter the optimized compositions accordingly.
7. At the end of each major stage, summarize what was done, list generated files, and ask the user to confirm whether to continue.


## Defaults

- Thermal objective examples: minimize `freezing_range`, miniminze `melt_viscosity`; minimize `surface_tension`; maximize `latent_heat`.
- Model selection metric: R2.
- Feature selection: SHAP top 5 per property, repeated in at least two properties.
- Optimization algorithm: NSGA-III.

## References

Read `references/workflow.md` for detailed state transitions and user-confirmation checkpoints.
