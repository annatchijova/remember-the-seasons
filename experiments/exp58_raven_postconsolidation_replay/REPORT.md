# Exp58: Post-Consolidation Longitudinal Replay

## Verdict

**OBSERVED, copied Raven snapshot and synthetic fixture:** starting memory and
cell-link state matched across the two Exp57 branches while their audit
histories differed. Under the same eight real recall operations and timestamps,
the returned IDs, all recorded score components, and memory/link state matched
after every step. Audit entry hashes remained different at every step, and
both audit chains passed linkage and hash-integrity verification. A control
that changed the merged node's `last_activation` produced a different recency
bonus, showing the measurement detects a real state-mediated change.

The bounded result is that these divergent histories did not propagate into
the tested post-consolidation retrieval trajectory. The audit histories remain
operationally distinguishable, and no claim is made for other observers or
inputs.

## Measurements

| Measure | Result |
|---|---|
| Initial memories and cell links | Equal |
| Initial audit history digests | Different |
| Shared inputs | C, D, D, C, D, C, C, D |
| Calls with matching outputs and state | 8/8 |
| New audit-entry hashes matching | 0/8 |
| Final audit-history digests | Different |
| Audit chain linkage and hash integrity | Valid in both branches |
| State-sensitivity control | Detected changed recency score |

The behavioral comparison excludes audit hashes by design and records them as
a separate observable. Each step compares returned order, base/state/hop/
synaptic/recency/final score fields, and a digest of the complete logical
`memories` and `cell_links` tables. Audit rows are excluded from that state
digest because the initial audit histories are the treatment contrast.

## Epistemic assessment

- **OBSERVED:** eight repeated actual `recall()` calls yielded identical
  behavioral outputs and persistent memory/link state after every step.
- **OBSERVED:** audit hashes diverged at each step, while Raven's chain and hash
  integrity checks passed in both branches.
- **INFERRED:** the selected audit-history divergence was not a causal input to
  this retrieval transition sequence; a counterexample under another operation
  or sequence would refute this bounded inference.
- **UNKNOWN:** whether other outputs, transitions, concurrency patterns, Raven
  snapshots, or downstream agents behave equivalently.

## Reproduction

```sh
python3 -m unittest -v experiments/exp58_raven_postconsolidation_replay/test_exp58_raven_postconsolidation_replay.py
python3 experiments/exp58_raven_postconsolidation_replay/exp58_raven_postconsolidation_replay.py
```

Five tests cover per-step trajectory equality, distinct audit observations,
valid audit chains, a state-sensitivity control, and canonical full-run replay.
This is a copied-source assay on synthetic data, not deployed-agent evidence.
