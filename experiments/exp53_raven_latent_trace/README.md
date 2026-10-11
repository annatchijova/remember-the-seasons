# Exp53: Raven Latent Trace Activation Assay

This isolated H14 assay tests which copied Raven operations consume or expose
the persisted `recall_count` field. It varies only C's count (5 versus 4),
keeps B at 4 in both paired states, and checks retrieval, telemetry, graph
export, and sleep-consolidator dry run.

## Run

From this directory:

```sh
python3 -m unittest -v test_exp53_raven_latent_trace.py
python3 exp53_raven_latent_trace.py
```

The runner writes `exp53_raven_latent_trace_run.json`.

## Read in this order

1. [`PREREGISTRATION.md`](PREREGISTRATION.md)
2. [`REPORT.md`](REPORT.md)
3. [`PROVENANCE.md`](PROVENANCE.md)

All fixture data is synthetic. The experiment measures Raven retrieval and
declared inspection/export outputs, not downstream agent decisions or any
production deployment.
