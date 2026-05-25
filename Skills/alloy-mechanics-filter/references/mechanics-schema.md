# Mechanical Dataset Schema

Use this reference when validating UTS/EL data.

## Expected Layout

- Feature columns: alloy element compositions.
- Label columns: usually final columns, but the user must confirm exact names.
- Common label names: `UTS`, `ultimate_tensile_strength`, `EL`, `elongation`.

## Confirmation Prompt

Ask: "I found these candidate label columns: ... Which columns are UTS and EL?"

Do not train models until labels are confirmed.

## Filtering

After predicting mechanics for optimized compositions, ask for thresholds such as:

```text
UTS >= 1000
EL >= 10
```

Return both the full predicted table and the filtered table when useful.
