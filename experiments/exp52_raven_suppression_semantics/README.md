# Exp52: Raven Suppression Semantics and Causal Isolation

Isolated H14 assay against the copied Raven snapshot and Exp51's synthetic
fixture. It tests result exclusion, causal influence exclusion through the
current-turn synaptic source path, and operational deletion of a memory plus
its incident links. It does not change Raven or product code.

## Run

From this directory:

```sh
python3 -m unittest -v test_exp52_raven_suppression_semantics.py
python3 exp52_raven_suppression_semantics.py
```

The runner writes `exp52_raven_suppression_semantics_run.json`.

## Read in this order

1. [`PREREGISTRATION.md`](PREREGISTRATION.md)
2. [`REPORT.md`](REPORT.md)
3. [`PROVENANCE.md`](PROVENANCE.md)

All artifacts use synthetic data. Results concern retrieval scores and
persisted fixture state only; they do not establish downstream agent effects
or behavior in a deployed Raven system.
