# Alloy Excel Schema

Use this reference only when deciding how to interpret workbook columns.

## Composition Columns

* Preferred header form: exact element symbols such as `Ni`, `Co`, `Cr`, `Al`, `Ti`, `Ta`, `W`.

* Accept common unit suffixes only when the element is unambiguous, for example `Ni wt%`, `Al (at%)`.

* &#x20;

## Extra Columns

Examples: alloy name, batch id, heat-treatment state, source paper, UTS, EL, density, notes.

Ask before removing extra columns from the workflow. If the user declines removal, keep the original workbook untouched and create a composition-only working copy for calculations.

## Label Columns

Thermal labels appended by Thermo-Calc should be at the end of the workbook. Mechanical labels in a separate dataset may also be at the end, but `$alloy-mechanics-filter` must ask the user to confirm the exact label columns.
