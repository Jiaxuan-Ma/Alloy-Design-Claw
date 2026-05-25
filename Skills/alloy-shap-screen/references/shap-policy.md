# SHAP Feature Screening Policy

Use mean absolute SHAP value as the feature-importance score.

## Selection Rule

1. Rank element features for each target.
2. Keep the top 5 features per target.
3. Count how many target rankings contain each element.
4. Select elements appearing at least twice.

When only one target is available, return the top 5 for that target and state that recurrence filtering was not applicable.

## Fallback

Permutation importance may be used only when `shap` is unavailable. Mark the output method as `permutation_importance`, not `shap`.

For production SHAP analysis, install `shap` in the active Python environment and rerun the script.
