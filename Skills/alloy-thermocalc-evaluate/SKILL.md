---
name: alloy-thermocalc-evaluate
description: Run TCNI12 Scheil Thermo-Calc calculations for high-temperature alloy compositions and append freeze range, melt viscosity, surface tension, and latent heat to Excel workbooks created by alloy-excel-intake.
---

# Alloy Thermo-Calc Evaluate

## Workflow

1. Use the composition-only workbook created by `$alloy-excel-intake`.
2. Append the four thermal label columns `freeze range`, `melt viscosity`, `surface tension`, and `latent heat`.
3. Confirm the balance element when the workbook does not make it obvious.
4. Run `Skills/alloy-thermocalc-evaluate/scripts/append_thermocalc_results.py` with the default project Python interpreter `D:\anaconda3\envs\pytorch_gpu\python.exe`, which is the configured Thermo-Calc/TC-Python environment. Do not search for other Conda environments unless the user explicitly asks.
5. Save a new workbook. Never overwrite the uploaded source unless the user explicitly asks.
6. If TC-Python licensing, database, phase selection, or convergence fails, report the failed row, composition, and exception message; continue only if the user approves skipping failed rows.

## Calculation Contract

The script includes the single-alloy Scheil calculation:

- Database: `TCNI12`
- Calculation type: Scheil-Gulliver
- Composition unit: `MASS_PERCENT`
- Per-alloy timeout: 10 minutes by default
- Progress is printed to stderr by default, including row progress, current stage, elapsed time, failure details, and heartbeat messages while a Scheil calculation is blocked.
- Workbook output columns:
  - `freeze range`: Scheil `STR_K`, unit K
  - `melt viscosity`: Scheil `MV_Pa_s`, unit Pa*s
  - `surface tension`: Scheil `ST_N_per_m`, unit N/m
  - `latent heat`: Scheil `LH_J_per_g`, unit J/g

## Path Note

Run the script from the project root on the intake-generated composition workbook. Use `--features` if the workbook contains numeric non-composition columns.

## Command

```bash
D:\anaconda3\envs\pytorch_gpu\python.exe Skills/alloy-thermocalc-evaluate/scripts/append_thermocalc_results.py intake_clean.xlsx --balance-element Ni --output thermal_results.xlsx
```

Use `--heartbeat-seconds 10` to show long-running Scheil heartbeat messages more frequently, or `--no-progress` to suppress progress output.

## References

Read `references/tc-python.md` before changing Thermo-Calc calls or troubleshooting TC-Python setup.
