---
name: alloy-nsga3-optimize
description: Optimize alloy compositions with NSGA-III using selected ML surrogate models. Use when the workflow needs to collect user-confirmed element bounds, confirm population size and iteration count, run multi-objective optimization for objectives such as minimizing liquidus-solidus temperature difference and maximizing latent heat, and export the final-generation compositions.
---

# Alloy NSGA-III Optimize

## Workflow

1. Start from optimizable elements selected by `$alloy-shap-screen`.
2. Ask the user for each selected element's lower and upper composition bound.
3. Ask the user to confirm NSGA-III population size and generation count. Default values live in `config/defaults.json`.
4. Confirm objective direction for every thermal property: `minimize` for `freeze range`, `melt viscosity`, and `surface tension`; `maximize` for `latent heat`.
5. Run `Skills/alloy-nsga3-optimize/scripts/optimize_nsga3.py` with best model artifacts and bounds.
6. Return final-generation compositions and objective predictions. Save CSV/Excel outputs.

## Composition Policy

- Keep all non-optimized element columns fixed at a baseline composition unless the user provides bounds for them.
- Enforce non-negative compositions.
- If composition units should sum to 100 or 1, confirm the convention and normalize only after user approval.
- Reject bounds where lower is greater than upper or where fixed plus lower bounds exceed the allowed total.

## ⚠️ 路径说明

该技能的脚本位于 `Skills/alloy-nsga3-optimize/scripts/` 目录下。
请从**项目根目录**运行：

```bash
python Skills/alloy-nsga3-optimize/scripts/optimize_nsga3.py --model-dir models --bounds bounds.json --objectives objectives.json --baseline baseline.json --output final_generation.csv
```

## Command

```bash
python Skills/alloy-nsga3-optimize/scripts/optimize_nsga3.py --model-dir models --bounds bounds.json --objectives objectives.json --baseline baseline.json --output final_generation.csv
```

## Handoff

After optimization, use `$alloy-mechanics-filter` if UTS/EL models exist or the user agrees to upload a mechanical-property dataset.
