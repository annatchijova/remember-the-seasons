# Exp59: Recall History Across Memory-ID Reuse

## Status and scope

**PROPOSED — preregistered before implementation and execution.** This bounded
assay uses the Raven source snapshot copied under Exp51, synthetic vectors, and
temporary SQLite clones. It does not modify `sources/`, upstream Raven,
product code, or add dependencies.

Pinned source commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

## Question and rival

Exp55–58 established that consolidation weights come from recall audit events
and that some history differences can persist in logs without changing the
tested retrieval trajectory. Exp59 asks:

> If a memory is replaced with new content under the same `memory_id`, do
> pre-replacement audit events still affect the new memory's consolidation?

The simple alternative is that historical counts belong effectively to a
memory incarnation, so replacing content resets its consolidation history.
The rival is that Raven joins history to the current row by the stable ID,
allowing earlier recall events to affect a later incarnation. Source
inspection predicts the rival: `get_recall_counts()` reads only
`memory_id` from historical `memories_retrieved` entries, while
`MemoryStore.store_memory()` uses `INSERT OR REPLACE` without clearing audit
rows. These are **OBSERVED** source facts at
[`sleep_consolidator.py:79–95`](../../sources/raven-memory/raven/sleep_consolidator.py#L79)
and [`memory_engine.py:856–875`](../../sources/raven-memory/raven/memory_engine.py#L856).
The assay outcome remains **PROPOSED** until execution.

## Conditions

Create two identical starting fixtures and generate actual recall histories:

| Branch | Historical audit recalls | Total events |
|---|---:|---:|
| R54 | C=5, D=4 | 9 |
| R45 | C=4, D=5 | 9 |

Then replace C and D using the copied engine's `store_memory()` storage path.
Keep their memory IDs, cell IDs, embeddings, associations, layer, state,
recency, and row counters matched across branches, but change their contents
and content hashes to identify new incarnations. Require that all current
memory and cell-link rows match between R54 and R45 before consolidation,
while their audit histories and audit-derived counts differ.

Run the same non-dry-run consolidation in both branches with the same threshold
and frozen clock. The predicted result is that the new C/D incarnation's
merged embedding differs because the old audit counts (5:4 vs 4:5) are still
applied. The C-query and D-query embedding similarities should shift in the
corresponding directions.

### New-ID control

Repeat each history branch after deleting C/D and storing the same new contents
and embeddings under fresh IDs `C_reborn` and `D_reborn`. The old audit entries
still refer to C/D, so the new IDs should have zero audit-derived recalls.
With both weights floored to one, the two new-ID branches should produce equal
merged embedding bytes. This control distinguishes history joined by ID from
an unrelated branch or fixture difference.

## Falsifiers and validity gates

- **Same-ID history falsifier:** if R54 and R45 produce equal merge weights
  and equal merged embeddings after the identical replacement, the predicted
  carry-over is refuted for this fixture.
- **Fresh-ID control:** if `C_reborn`/`D_reborn` still inherit old counts or
  their merge embeddings differ by history, the ID-join interpretation is not
  isolated and the result is inconclusive.
- **State equality gate:** current memories and cell links must be identical
  before the second consolidation; only audit history may differ across the
  same-ID R54/R45 pair.
- **Historical-incarnation gate:** audit records must retain the old content
  hashes while the current row contains the new content hash.
- **Mutation control:** in a temporary mutant, make the count reader ignore
  historical events whose recorded content hash differs from the current row.
  This should eliminate the same-ID divergence; if it does not, the assay has
  not isolated historical ID-based attribution.
- **Replay:** rebuild all branches from fresh clones and compare canonical
  result JSON exactly.

Any returned-ID, count, source-hash, eligibility-group, state-equality, or
replay failure invalidates the run rather than supporting either conclusion.

## Measurement and limits

Record old and new content hashes, audit counts, the full current-state
comparison before the second consolidation, merge metadata and embedding bytes,
and C/D vector similarities. This targets the offline consolidator only. Any
result applies to this pinned snapshot, synthetic fixture, and explicit
memory-ID replacement operation. It does not establish a vulnerability in a
deployed service or any effect on downstream agent decisions.
