# Exp55: Recall Counter Through Consolidation

## Status

**PROPOSED — preregistered before implementation and execution.** This is a
bounded assay against the Raven source snapshot copied under Exp51. It will use
temporary SQLite clones and synthetic vectors only. It will not edit
`sources/`, upstream Raven, product code, or add dependencies.

Preregistration date: 2026-10-13. Source commit:
`56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

## Question and rival explanation

Exp53 found that two states differing only in a persisted
`memories.recall_count` value were equivalent on four fixed retrieval probes,
but the count was visible in inspection and statistics. Exp54 found that this
retrieval equivalence survived five selected engine actions. Its real
consolidation behavior was not exercised because the fixture had no declared
nontrivial merge schedule.

Exp55 asks one narrower question:

> With audit history held identical, can a difference in the persisted
> `recall_count` column alone alter a real sleep-consolidation result and then
> alter fixed-query retrieval?

The simpler alternative is that this column is not the consolidator's input:
it reconstructs per-memory merge weights from `audit_log.memories_retrieved`,
so a counter-only difference is operationally visible but has no path through
this operation to future retrieval. This is **OBSERVED** in source at
[`sleep_consolidator.py:79–95`](../../sources/raven-memory/raven/sleep_consolidator.py#L79)
and [`sleep_consolidator.py:416–436`](../../sources/raven-memory/raven/sleep_consolidator.py#L416);
the counter-derived weighting and merged embedding are at
[`sleep_consolidator.py:170–183`](../../sources/raven-memory/raven/sleep_consolidator.py#L170).
Exp53 observed equal *dry-run* outputs with matched audit logs. Exp55 tests
actual application and its later retrieval consequences.

## Hypotheses and exact predictions

### Primary counter-only comparison

Create two clones identical in every database field except
`C.recall_count`:

- S5: `C.recall_count = 5`, `D.recall_count = 4`.
- S4: `C.recall_count = 4`, `D.recall_count = 4`.
- Both audit logs are empty and byte-identical.

The source-derived prediction is:

1. Before consolidation, the core retrieval traces for fixed C and D query
   vectors (`top_k=4`, `hops=0`, fixed `now`, no current-turn memories) are
   equal.
2. Both branches form exactly one merge group containing C and D.
3. The consolidator assigns both members weight 1 in both branches because
   its audit-derived counts are zero and `merge_group` floors each weight at
   1. The merged embeddings, normalized persistent database snapshots, and
   fixed-query retrieval traces are therefore exactly equal after
   consolidation.

This prediction is **PROPOSED** until the run. It would be falsified if the
counter-only branches produce different normalized merged embeddings, other
than time-derived or generated identifiers before the declared normalization,
or any unequal fixed-query score/rank trace after consolidation.

### Positive sensitivity control

Create another pair with identical persisted memory counters, but generate
actual recall audit rows under a fixed clock and `top_k=1`, `hops=0`:

- A5/4: five recalls that return C and four that return D.
- A4/4: four recalls that return C and four that return D.

Use `layer_filter='episodic'` on these canary recalls so only C and D can be
returned; the fixture gate must verify each call's single returned ID before
the resulting audit rows are used.

After generating those rows, reset the persisted `recall_count` values to the
same values in both branches while preserving the audit entries. The exact
source-derived prediction is that non-dry-run consolidation uses audit weights
5:4 in A5/4 and 4:4 in A4/4. Thus the merged embedding must differ; its cosine
similarity and base score for the C query must be higher in A5/4, while those
for the D query must be lower. This is the canary that the assay reaches the
consolidator's declared weight input rather than merely running a no-op.

If the canary does not satisfy those directional checks, Exp55 is
**inconclusive as an instrument**, regardless of the primary result. If it
does, but S5 and S4 remain equal as predicted, the result supports a bounded
negative conclusion: the persisted counter difference alone did not alter
consolidation or the subsequent retrieval traces in this fixture.

## Fixture and execution contract

**OBSERVED:** Exp51 provides four synthetic memories with fixed 8-dimensional
vectors and an exact KDTree backend. Exp55 will reuse that copied fixture and
its source provenance, changing only the declared fields needed to create the
consolidation condition.

**PROPOSED fixture rules:**

1. Clone one Exp51 seed database independently for every condition.
2. Make only C and D eligible for consolidation by setting them to
   `layer='episodic'`, `state='NEUTRAL'`; keep A and B outside that input set.
3. Confirm before any branch execution that C and D have cosine similarity
   above the preregistered `0.90` threshold and are the sole merge group.
   Otherwise stop before outcome inspection and repair the fixture in a new
   preregistration version.
4. Freeze all source-visible time reads used by the consolidation and query
   paths to the same declared value in every branch. Use the copied exact
   KDTree backend and fixed stored vectors; make no embedding or LLM calls.
5. Run `run_consolidation(threshold=0.90, dry_run=False,
   rebuild_spectral=False)` on each disposable clone. Reopen each resulting
   database in a fresh engine before measuring post-consolidation retrieval.
6. Run the same fixed query vectors C and D with fixed `now`, `top_k=4`,
   `hops=0`, and no current-turn memories. Record all scored rows and ranks,
   not only the winner.

The implementation must include a pre-outcome fixture gate that checks row
equality except for the declared treatment field(s), the audit-row schedule,
and the exact merge group. A failed gate invalidates the run; it is not a
negative result.

## Observations and normalization

The primary outcome is the merged node's stored embedding and the complete
fixed-query core score/rank traces after reopening the database. Also record:

- exact merge group membership and audit-derived input counts;
- all persistent database differences before and after consolidation;
- returned consolidation summaries and generated node identifiers;
- a canonical JSON artifact containing condition, source commit, fixture
  digest, fixed parameters, outputs, and limitations.

Time values are frozen. Generated identifiers and database metadata are
compared exactly when the fixed clock makes them deterministic. Any unavoidable
environmental values must be explicitly normalized and retained in raw
artifacts; they must not be silently dropped. Floating scores are compared
exactly within the same process/build and also reported at full serialized
precision. No cross-platform floating-point claim is made.

This is an engine/offline-consolidator alphabet only. It does not exercise the
FastAPI or MCP adapters, their caches, rate limits, WebSockets, or provider
fallbacks. It does not establish downstream agent behavior or generalize
beyond the pinned Raven snapshot and declared synthetic fixture.

## Controls and reproducibility

- **Counter isolation:** canonicalize both primary database snapshots after
  excluding only the one declared `C.recall_count` column; all remaining rows,
  links, and audit entries must match.
- **History isolation:** the primary S5/S4 audit logs must match exactly.
- **Weight canary:** the A5/4 versus A4/4 pair changes audit-derived counts
  while holding persisted counters equal; this must produce the predicted
  merged-embedding and directional retrieval differences.
- **Equalized negative control:** repeat the primary operation after setting
  both C counters to 4. Its normalized outputs must match the S4 branch.
- **Replay:** run the complete experiment twice from freshly built temporary
  clones and compare canonical result JSON byte-for-byte.
- **Mutation falsifier:** in a separate temporary test copy, deliberately
  alter the adapter's consolidation input to use persisted row counters. The
  counter-only comparison must then become distinguishable or the mutation
  check fails to demonstrate sensitivity. This mutant is never included in
  the unmodified Raven result.

## Verdict rules

| Observation | Verdict |
|---|---|
| Fixture gate fails | Invalid run; repair and preregister the changed fixture before inspecting outcomes |
| Canary does not diverge in merged vector and directional query scores | Instrument inconclusive; do not interpret primary equality |
| Canary passes; counter-only branches diverge in merged vector or retrieval | Falsifies the prediction that this operation ignores the persisted counter; inspect provenance and rerun before interpreting mechanism |
| Canary passes; counter-only branches match through the declared retrieval trace | Bounded negative result: this persisted counter difference has no observed path through this consolidation schedule to retrieval |
| Replay differs after declared normalization | Reproducibility failure; no causal verdict |

Neither equality nor divergence here proves that the counter is universally
causally inert or that it represents a latent memory mechanism. The explicit
consumer inventory in
[`docs/RAVEN_OBSERVATIONAL_CONTRACT.md`](../../docs/RAVEN_OBSERVATIONAL_CONTRACT.md)
and source grep bound the claim to this pinned code and these operations.

## Safety and provenance

Only synthetic fixture data and temporary database copies are permitted. No
personal memories, credentials, live Raven service, network, or external model
provider is used. The copied Raven source must remain byte-identical to the
Exp51 provenance record. The runner, tests, raw JSON, and report will be
separate from `sources/` and will label source facts, predictions, and runtime
results distinctly.

**Execution status: NOT RUN.** No implementation or runtime result is implied
by this preregistration.
