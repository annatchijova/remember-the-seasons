# Exp56: Audit Projection Sufficiency for Consolidation

## Verdict

**OBSERVED, bounded synthetic Raven assay:** with per-memory audit counts held
at C=5 and D=4, changing event order or query text did not change the
consolidation weights, merged embedding bytes, or either fixed-query retrieval
trace. The histories remained distinguishable by their audit-log digests.
Changing the allocation to C=4 and D=5 while keeping nine total recalls changed
the merged embedding and shifted the fixed C/D scores in the preregistered
directions. The deliberately order-sensitive mutation was detected.

This supports the count-vector projection for the tested consolidation-derived
outputs in this fixture. It does not establish whole-system equivalence: audit
inspection and other operations can still distinguish the histories.

## Results

| Check | Result |
|---|---|
| H1: contiguous canonical history | weights C=5, D=4 |
| H2: interleaved canonical history | same weights and outputs as H1 |
| H3: contiguous alternate query text | same weights and outputs as H1 |
| H1/H2 audit-log digests | different |
| H1/H3 audit-log digests | different |
| H4: reversed allocation, same nine events | embedding changed; C score lower and D score higher than H1 |
| Order-sensitive mutation | H1/H2 merged embeddings diverged; detected |

The fixed retrieval base scores were:

| Query | H1/H2/H3 (C=5, D=4) | H4 (C=4, D=5) |
|---|---:|---:|
| C | 0.9833799554489762 | 0.9739065267557034 |
| D | 0.9739065170288086 | 0.9833799590694879 |

The row-level `recall_count` values reflect the initial fixture value of 4 plus
the generated recalls (H1/H2/H3: 9 and 8; H4: 8 and 9). The consolidator's
recorded merge weights match the audit-derived counts, not those initial row
values.

## Interpretation

- **OBSERVED:** `get_recall_counts()` scans recall audit entries and sums
  retrieved memory IDs; `merge_group()` uses the resulting counts as weights.
  See [`sleep_consolidator.py:79–95`](../../sources/raven-memory/raven/sleep_consolidator.py#L79)
  and [`sleep_consolidator.py:170–183`](../../sources/raven-memory/raven/sleep_consolidator.py#L170).
- **OBSERVED:** H1, H2, and H3 yielded identical target outputs under that
  implementation while their audit histories differed.
- **INFERRED:** in this fixture, the per-memory count vector is a sufficient
  projection of audit history for the merged embedding and the two declared
  retrieval traces. This inference would be refuted by a same-count history
  pair that differs on those outputs.
- **UNKNOWN:** whether other audit fields, broader consolidation inputs,
  observers, snapshots, or downstream agent decisions distinguish or depend
  on these histories.

## Method and reproducibility

The runner verifies the copied source hashes, creates independent temporary
SQLite clones, freezes time, uses the copied KDTree backend and fixed vectors,
checks each recall result and count schedule, applies non-dry-run consolidation,
and reopens the databases for retrieval measurement. The JSON artifact records
all weights, embedding bytes, scores, audit digests, parameters, and limits.
The test suite replays the full run and compares canonical JSON.

Run from the repository root:

```sh
python3 -m unittest -v experiments/exp56_raven_audit_projection/test_exp56_raven_audit_projection.py
python3 experiments/exp56_raven_audit_projection/exp56_raven_audit_projection.py
```

This is a copied-source synthetic assay. It does not establish behavior in a
deployed Raven service, MNEME, Stigmergy, or an agent's decisions.
