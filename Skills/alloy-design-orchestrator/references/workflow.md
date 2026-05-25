# High-Temperature Alloy Design Workflow

## State Transitions

1. Intake: uploaded workbook -> composition report -> composition-only working workbook.
2. Thermal calculation: composition workbook -> Thermo-Calc results workbook.
3. Model selection: results workbook -> best model artifacts.
4. SHAP screening: thermal model artifacts -> optimizable elements.
5. NSGA-III: confirmed bounds and hyperparameters -> final-generation compositions.
6. Mechanics model selection: optional mechanics dataset -> reuse model selection from step 3 -> best mechanical model artifacts.
7. Mechanics filter: best mechanical model models -> threshold-filtered compositions.

## User Confirmations

Ask before:

- Dropping or excluding non-composition columns.
- Treating final columns as labels.
- Choosing optimization bounds.
- Choosing NSGA-III population size and generation count.
- Applying UTS/EL thresholds.

## Completion Cases

- If the user declines mechanics upload: report casting/thermal optimization complete and provide final-generation compositions.
- If mechanics models exist or are trained: report threshold-filtered compositions and include predicted UTS/EL columns.

## Runtime Dependencies

- Excel/model scripts: `pandas`, `openpyxl`, `scikit-learn`, `joblib`.
- SHAP analysis: `shap` preferred; permutation importance fallback is allowed only when disclosed.
- NSGA-III optimization: `pymoo` required.
- Thermo-Calc evaluation: user-owned TC-Python wrapper and valid Thermo-Calc license/database.
