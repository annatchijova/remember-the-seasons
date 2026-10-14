# Exp55: Raven Recall Counter Through Consolidation

## Result

**OBSERVED, copied Raven snapshot with synthetic Exp51 fixture:** the
preregistered counter-only branches produced identical real consolidation
outputs and identical later retrieval traces. The audit-weight canary
diverged in the predicted direction, so the assay detected the consolidator's
actual history input.

| Measurement | Counter-only S5/S4 | Audit canary A5/4/A4/4 |
|---|---|---|
| C/D merge weights | 1:1 in both; source audit counts were 0:0 | 5:4 versus 4:4 from audit rows |
| Merged embedding | Byte-identical | Different |
| C query base score | Equal: `0.9789063349028255` | A5/4 higher: `0.9833799554489762` vs `0.9789063349028255` |
| D query base score | Equal: `0.9789063321892221` | A5/4 lower: `0.9739065170288086` vs `0.9789063321892221` |
| Post-consolidation retrieval traces | Equal for both fixed queries | Different score vectors, with the declared directional change |

The only primary-branch input difference was `C.recall_count` (5 versus 4);
`D.recall_count` was 4 in both. The C/D cosine similarity was
`0.916515138991168`, above the preregistered threshold `0.90`, and C/D were
the sole merge group. Both histories had identical empty audit logs.

## Interpretation

**OBSERVED:** the real non-dry-run consolidator rebuilt its weights from
`audit_log.memories_retrieved`. With empty audit histories, both members got
the same effective weight (`max(1, 0) = 1`) in S5 and S4. Consolidation
replaced C and D with the same node, and the resulting logical database
snapshots and complete C/D retrieval score/rank traces were equal. The
primary branches also matched the separately built equalized 4/4 control.

**OBSERVED:** the canary produced actual Raven recall audit rows for five C
retrievals and four D retrievals, versus four and four. The persisted C/D
counters were then reset to 4/4 in both branches. The consolidator used the
audit-derived 5:4 and 4:4 weights; the merged vector changed, as did later
retrieval scores. This demonstrates that the assay reaches the weight source
the implementation actually consumes.

**INFERRED, bounded:** the isolated persisted `recall_count` difference has no
observed causal path through this consolidation schedule to post-consolidation
retrieval. The different audit histories do have such a path. That effect is
fully accounted for by the explicit audit-derived consolidation rule in this
snapshot; it is not evidence for an additional hidden memory mechanism.

This narrows the Exp52–54 result. `recall_count` is observable in inspection,
stats, and graph export, but Exp55 found no effect from this stored field in
the tested consolidation pathway. Conversely, retained audit history can
change a future memory vector through consolidation. Exp55 does not show that
an agent decision changes, that retrieval alone is insufficient in general,
or that Raven implements biological memory pharmacology.

## Falsification and test integrity

**OBSERVED:** all five Exp55 tests passed. The suite covers the pre-treatment
state gate, one exact C/D merge, primary branch equality, audit-weight canary
direction, source-copy hashes, and deterministic replay.

The mutation test replaced the consolidator's audit-count reader with a
temporary reader of the persisted `memories.recall_count` column. Under that
mutant, S5 and S4 produced different merged embeddings and C-query scores; the
test detected the divergence. The mutation was applied only through a scoped
test patch and was not written to Raven source or the copied source files.

The runner was executed in separate processes and emitted identical canonical
JSON bytes both times. Artifact SHA-256:
`250304070d60d693886d32cb7a0cd464cdee66cc569ceab8842c7eb5a1544202`.
Common pre-treatment fixture SHA-256:
`9185c9d60305b6e4a9fa71bd5513802bbdd1b17bdd47d6463671ceb012c8f498`.

## Scope limits

- One Raven snapshot, pinned at commit
  `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.
- One synthetic four-memory fixture; only C and D could consolidate.
- Fixed stored vectors, exact KDTree, fixed clock, C/D queries, and
  `hops=0`.
- Engine and offline consolidator methods only; no HTTP or MCP server, live
  service, provider, network, personal data, concurrency, or agent reasoning.
- No equivalence or minimality claim for Raven's complete state or operation
  surface.

## Reproduction

From this directory:

```sh
python3 -m unittest -v test_exp55_raven_counter_consolidation.py
python3 exp55_raven_counter_consolidation.py
```

The raw result is
[`exp55_raven_counter_consolidation_run.json`](exp55_raven_counter_consolidation_run.json).
The preregistered protocol is
[`PREREGISTRATION.md`](PREREGISTRATION.md).
