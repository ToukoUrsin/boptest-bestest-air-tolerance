# BOPTEST bestest_air: IAQ KPI vs. FMU solver tolerance

Evidence for an ibpsa/project1-boptest issue. The same frozen command sequence on the `bestest_air` FMU (blob `84db75c5026b6744fedf457b333be5354b145f1f`, identical on v0.9.0 and master `0f8a467`) gives an IAQ discomfort KPI 6.7% higher at the compiled default co-simulation tolerance (1e-6) than at 1e-8 or 1e-10, together with a fan-volume mass loss and zone-pressure drop that vanish at tighter tolerance.

| `_cs_rel_tol` | idis_tot (ppm h) | zone pressure drop (Pa) | fan mass loss (kg) |
| --- | ---: | ---: | ---: |
| 1e-6 (default) | 1301.764 | 468.57 | 2.54e-3 |
| 1e-8 | 1220.174 | 1.39 | 7.56e-6 |
| 1e-10 | 1219.949 | 0.0017 | 9.45e-9 |

Scenario: `peak_heat_day`, `highly_dynamic` prices, 7-day warmup, 14-day test, 300 s control step, 30 s result grid.

## Files

- `commands.json`: the exact command sequence (identical in every run).
- `default.npz`, `tight.npz` (+ `-hidden.npz`, `-row.json`): result traces at 1e-6 and 1e-10 on the original 30 s grid, including FMI internals for the fan volume and zone pressure.
- `expected.json`: KPIs and conservation diagnostics for 1e-6, 1e-8 and 1e-10.
- `official_kpi.py`: BOPTEST's `kpis/kpi_calculator.py` at `0f8a467` (unchanged, BOPTEST license).
- `check.py`: offline check. Recomputes the KPIs from the traces with the official calculator and an independent integrator.
- `reproduce.py`: full FMU replay in an existing BOPTEST/PyFMI environment.
- `manifest.json`: SHA-256 of every file.

## Run

Offline (numpy 2.2, pandas 2.2; the upstream KPI code does not run on pandas 3):

```sh
python check.py
```

Full replay (PyFMI 2.14, about 2-3 minutes per run):

```sh
python reproduce.py --boptest /path/to/project1-boptest --rtol 1e-6  --out out-default
python reproduce.py --boptest /path/to/project1-boptest --rtol 1e-10 --out out-tight
```

`--fmu /path/to/wrapped.fmu` works with a minimal source tree. The script asserts the FMU blob and the actual tolerance after initialization.
