# Modeling Notes

Use this reference when model results look suspicious.

## Data Checks

- Confirm features are element composition columns only.
- Confirm targets are calculated thermal properties or confirmed mechanical labels.
- Drop rows with missing feature or target values for the current target, but report how many rows were removed.
- Preserve feature order in model artifacts.

## Scoring

Use R2 for model selection. Prefer cross-validation when enough rows exist. If rows are limited, use a deterministic holdout split and report the limitation. Negative R2 means the model is worse than predicting the target mean.

## Leakage

Do not include target-derived columns as features. Examples: do not use `freeze range` as a feature when training `latent heat` unless the user explicitly wants chained surrogate modeling.
