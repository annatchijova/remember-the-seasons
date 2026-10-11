# Exp51: Raven Longitudinal Restoration Pilot

This is an isolated H14 experiment against a copied Raven source snapshot. It
uses a synthetic four-memory SQLite fixture and does not modify
`sources/raven-memory/` or any Raven, MNEME, or Stigmergy working tree.

## Run

From this directory:

```sh
python3 -m unittest -v test_exp51_raven_h14_longitudinal.py
python3 exp51_raven_h14_longitudinal.py
```

The runner writes `exp51_raven_h14_run.json`. The fixture vectors, query
schedule, seed database digest, source commit, full scored retrieval traces,
signed indirect effects, standardized propagation probes, and state summaries
are included in the artifact.

## Read in this order

1. [`PREREGISTRATION.md`](PREREGISTRATION.md)
2. [`PREREGISTRATION_AMENDMENT_1.md`](PREREGISTRATION_AMENDMENT_1.md)
3. [`PREREGISTRATION_AMENDMENT_2.md`](PREREGISTRATION_AMENDMENT_2.md)
4. [`PREREGISTRATION_AMENDMENT_3.md`](PREREGISTRATION_AMENDMENT_3.md)
5. [`PREREGISTRATION_AMENDMENT_4.md`](PREREGISTRATION_AMENDMENT_4.md)
6. [`REPORT.md`](REPORT.md)
7. [`PROVENANCE.md`](PROVENANCE.md)

Amendments explain why preliminary outputs were superseded. Only the final
run artifact is used in the report.

## Scope

The experiment measures Raven retrieval and stored memory state. It does not
measure a language model's downstream decision, does not use an embedding
provider, and does not validate a deployed agent workload. Raven's copied
source does not expose a persistent absence/restoration API; the longitudinal
driver and its current-turn suppression filter are experiment-only protocol
code.
