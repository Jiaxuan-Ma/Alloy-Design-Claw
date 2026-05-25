# TC-Python Reference

Use this file before editing Thermo-Calc integration code.

## Official Documentation

- Thermo-Calc documentation portal: https://thermocalc.com/support/documentation/
- TC-Python help page: https://thermocalc.com/support/documentation/tc-python-help/
- TC-Python product page: https://thermocalc.com/products/software-development-kits/tc-python/

Prefer the locally installed documentation matching the user's Thermo-Calc version when available. The official portal notes that TC-Python has version-specific help, examples, and a generated API reference.

## Embedded Calculation

`scripts/append_thermocalc_results.py` now contains the Scheil calculation imported from the user-provided `tc-skill.py` workflow:

- Select the `TCNI12` database and the active alloy elements.
- Use a Scheil calculation with `CompositionUnit.MASS_PERCENT`.
- Read liquidus and solidus from the Scheil temperature series.
- Read solidification range, latent heat per gram, liquid dynamic viscosity, and surface tension from the Scheil result.
- Append those values to the intake workbook as `freeze range`, `melt viscosity`, `surface tension`, and `latent heat`.
- Keep row iteration, Excel I/O, selected output columns, and failure capture in the skill runner.

Use the locally installed TC-Python API for the user's Thermo-Calc version before changing these calls.

## Common Failure Points

- TC-Python package is not importable in the selected Python environment.
- Thermo-Calc license is missing or not active.
- Required thermodynamic database is unavailable.
- Composition contains unsupported elements for the selected database.
- Phase selection or equilibrium calculation fails for a row.
- Output units do not match the workbook convention.

Report failures with row index, composition, and exception message.
