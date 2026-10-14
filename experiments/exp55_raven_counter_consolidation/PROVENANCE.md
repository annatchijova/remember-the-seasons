# Exp55 Provenance

## Source and fixture

- **OBSERVED:** Raven snapshot commit:
  `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.
- **OBSERVED:** snapshot content SHA-256:
  `4eee9af6a22ec8311b0bf3d289bce166cb7d6a7b83c99687d004a490dcd302f4`,
  recorded in [`sources/raven-memory/PROVENANCE.md`](../../sources/raven-memory/PROVENANCE.md).
- **OBSERVED:** the runner imports Raven from Exp51's copied
  `experiments/exp51_raven_h14_longitudinal/vendor/raven/` package. At
  execution, `memory_engine.py` matched SHA-256
  `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0` and
  `sleep_consolidator.py` matched SHA-256
  `9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39`.
- **OBSERVED:** four synthetic Exp51 memories and fixed 8-dimensional vectors;
  C/D were changed to episodic neutral solely to create the preregistered
  merge group. All work used fresh temporary SQLite clones.
- **OBSERVED:** no files under `sources/` or any upstream Raven working tree
  were edited. No real memory, credential, model provider, network call, or
  live Raven deployment was used.

## Execution environment

- Python `3.12.3`
- NumPy `1.26.4`
- SciPy `1.11.4`
- scikit-learn `1.9.0`
- `RAVEN_ANN_BACKEND=kdtree`

The environment is recorded because floating-point embedding and score
calculations are part of this synthetic assay. The artifact's byte stability
was checked across separate runner processes in this environment; it is not a
cross-platform floating-point guarantee.

## Artifacts

- Preregistration: `PREREGISTRATION.md`
- Runner: `exp55_raven_counter_consolidation.py`
- Tests: `test_exp55_raven_counter_consolidation.py`
- Report: `REPORT.md`
- Result: `exp55_raven_counter_consolidation_run.json`
- Result SHA-256:
  `250304070d60d693886d32cb7a0cd464cdee66cc569ceab8842c7eb5a1544202`
- Common pre-treatment fixture SHA-256:
  `9185c9d60305b6e4a9fa71bd5513802bbdd1b17bdd47d6463671ceb012c8f498`
