# Optimization Contract

Use this reference when preparing NSGA-III inputs.

## Runtime Dependency

Actual NSGA-III execution requires `pymoo` in the active Python environment. If `pymoo` is missing, stop and tell the user to install it before optimization.

## Bounds JSON

```json
{
  "Al": [1.0, 8.0],
  "Ti": [0.0, 5.0],
  "Ta": [0.0, 8.0]
}
```

## Objectives JSON

```json
{
  "freeze range": "minimize",
  "melt viscosity": "minimize",
  "surface tension": "minimize",
  "latent heat": "maximize"
}
```

Objective names must match model artifact target names.

## Baseline JSON

Provide fixed values for non-optimized elements:

```json
{
  "Ni": 60.0,
  "Co": 10.0,
  "Cr": 12.0,
  "Al": 4.0,
  "Ti": 3.0,
  "Ta": 2.0
}
```

If a balance element is used, its value is computed from the total composition after all other variables are set.
