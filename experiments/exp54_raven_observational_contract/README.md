# Exp54: Raven Observational Contract

This isolated assay asks whether Exp53's `recall_count` difference is visible
only in retrieval or across Raven's wider operation surface, checks bounded
retrieval congruence under five same-input mutations, and tests whether a
truncated graph tie depends on SQLite row order.

Start with [`PREREGISTRATION.md`](PREREGISTRATION.md), then read the
epistemically labelled [`REPORT.md`](REPORT.md). The runner and tests use
temporary copies of Exp51's synthetic fixture. No Raven source snapshot files
or upstream working trees are changed.

```sh
python3 -m unittest -v test_exp54_raven_observational_contract.py
python3 exp54_raven_observational_contract.py
```

The stable result is in [`exp54_raven_observational_contract_run.json`](exp54_raven_observational_contract_run.json).
