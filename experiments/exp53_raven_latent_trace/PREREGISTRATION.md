# Exp53: Raven Latent Trace Activation Assay

## Status and scope

**PROPOSED, preregistered before behavioral execution.** This experiment
isolates the persistent `recall_count` column in the copied Raven source
snapshot used by Exp51/52. It uses synthetic fixture data only and changes no
file under `sources/` or in an original Raven working tree.

Exp51's post-observation amendments remain documented as pilot history; they
are not treated as preregistration for Exp53. This is a separate protocol
written before Exp53's first run.

## Question and competing claims

Given two states identical in every stored field except `C.recall_count` (5
versus 4), which Raven operations produce different observable outputs or
future transitions?

The central falsifier is that the counter is irrelevant under every declared
operation. A narrower rival is that it does not affect retrieval decisions,
but remains visible through inspection/telemetry or affects maintenance
selection. Both can be true in the same system.

## Operation inventory to verify

Before execution, code inspection identified these candidate uses in the
pinned snapshot:

- Retrieval: determine whether `_recall_core()` reads the field for score or
  rank.
- Update: `update_activation(s)` increments the field.
- Maintenance/export: `load_top_recalled()` orders by it and `export_graph()`
  uses that query when truncating nodes.
- Telemetry/inspection: `count_stats()` sums it; `/memories` and graph output
  serialize it.
- Consolidation: determine whether the sleep consolidator reads the memory
  column or derives recall frequencies from audit-log rows.
- Persistence/portability: determine whether the field is stored and exported.

Every classification will be tied to the exact source lines in the report.

## Paired states and operations

- Build one Exp51 seed and clone it with SQLite's backup API.
- In both copies set `B.recall_count=4`; set `C.recall_count=5` in state S5
  and `C.recall_count=4` in state S4. All other memory columns, cell links,
  and audit rows must match exactly.
- Run the same read-only `_recall_core()` queries (`A`, `B`, `C`, `D`) with
  the same clock, top-k, hop count, and current-turn input. Compare complete
  score maps and ranked IDs.
- Read `get_stats()`, `list_memories()` serialization, and
  `export_graph(max_nodes=1)` from each state. These are outputs, not retrieval
  decisions.
- As a matched control, set `C.recall_count=5` in both copies and repeat the
  output comparisons.
- Call the same activation update in both copies and record the resulting
  counters; do not interpret equal increments as proof of equal history.
- Convert the same two records to episodic neutral memories in both copies
  and run the sleep consolidator in dry-run mode with unchanged, empty audit
  logs. Compare the results to test whether that operation reads this column
  directly or derives weights from audit history.

## Predictions and falsifiers

- If retrieval score maps or ranked IDs differ between S5 and S4, the claim
  that this field is retrieval-inert is falsified. Exact equality supports
  retrieval invariance only for the four fixed queries and this source
  snapshot.
- If stats, serialized inspection, or graph output differs, the counter is
  externally observable even if retrieval is invariant. If all match, that
  output channel's claimed sensitivity is falsified.
- If truncated graph node selection differs because of S5/S4, the field
  changes a maintenance/export selection. If selection does not differ, that
  specific consequence is falsified for the fixture; serialized count values
  remain a separate observation.
- If dry-run consolidation differs with identical audit logs, the hypothesis
  that the field is ignored by that path is falsified. If results match, the
  conclusion is limited to the copied consolidator and the declared fixture.
- After equalizing the counter, any remaining difference in these outputs
  falsifies the claim that the counter alone mediated the observed effect.

## Limits

This assay does not establish impact on every Raven deployment, arbitrary
queries, other maintenance jobs, concurrent operation, or downstream agent
choices. A visible telemetry difference is not automatically a decision-level
effect. Missing one unsearched dynamic/reflection caller remains possible and
must be reported as a blind spot.
