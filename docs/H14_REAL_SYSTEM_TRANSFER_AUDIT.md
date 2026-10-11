# H14: Source-Level Transfer Audit for Raven, MNEME, and Stigmergy

## Scope and result

This is a read-only audit of the local source snapshots. No source snapshot was
edited, no test suite was run, and no runtime or production database was
examined.

**OBSERVED:** the snapshots identify Raven commit
`56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`, MNEME commit
`bde801a2029bf9f4cc2ef1f4f56b32c8a134231a`, and Stigmergy commit
`b80a7f9cf259d7b0965b659d410daca81167bf37`. See each snapshot's
[`PROVENANCE.md`](../sources/raven-memory/PROVENANCE.md),
[`PROVENANCE.md`](../sources/mneme/PROVENANCE.md), and
[`PROVENANCE.md`](../sources/stigmergy/PROVENANCE.md). These are snapshots,
not evidence about the current live repositories or deployments.

**INFERRED:** Raven is the strongest first target for a narrow transfer of
H14's retrieval-causality method because its recall core already accepts a
silenced-cell set, returns full scored results, and exposes a paired baseline
versus suppression probe. It does not natively implement the full longitudinal
absence and restoration protocol. A result from the existing one-query
intervention API would therefore be a transferability pilot, not a completed
H14 restoration experiment.

**UNKNOWN:** whether the exact transition and observation semantics in any
current deployment are deterministic, fully captured by the local snapshots,
or stable enough to yield an enumerable quotient. The next implementation step
needs a separate research harness and an explicit state/observation contract.

## Evidence matrix

| Requirement | Raven source snapshot | MNEME source snapshot | Stigmergy source snapshot |
|---|---|---|---|
| State domain | `MemoryEntry` includes vectors, mutable state, timestamps, metadata, and variable link maps; the SQLite field can grow. No bounded reachable closure is defined. **OBSERVED** ([`memory_engine.py:153–169`](../sources/raven-memory/raven/memory_engine.py#L153)) | A frozen DB has a finite set of rows and finite status vocabularies, but the repository does not enumerate a transition closure for H14. Embeddings are quantized model outputs; histories and links remain data-dependent. **OBSERVED / UNKNOWN** ([`field.py:85–117`](../sources/mneme/mneme/field.py#L85), [`schema.sql:53–71`](../sources/mneme/mneme/schema.sql#L53)) | Stored rows have discrete states but also vector data, timestamps, counters, and links. No H14 reachable closure is enumerated. **OBSERVED / UNKNOWN** ([`schema.sql:172–214`](../sources/stigmergy/schema.sql#L172)) |
| Transition determinism | The pure core is deterministic only with fixed field structures, query vector, `now`, and parameters. It uses float cosine/`exp`; default KDTree is exact, optional HNSW is approximate. Ordinary `recall()` applies STDP and activation updates; `intervene()` shares one snapshot and timestamp and writes only its audit row. **OBSERVED** ([`memory_engine.py:1614–1639`](../sources/raven-memory/raven/memory_engine.py#L1614), [`memory_engine.py:1795–1831`](../sources/raven-memory/raven/memory_engine.py#L1795), [`memory_engine.py:1979–1989`](../sources/raven-memory/raven/memory_engine.py#L1979), [`memory_engine.py:2025–2075`](../sources/raven-memory/raven/memory_engine.py#L2025)) | `field.recall()` uses exact rational ranking and deterministic ID tie-breaking for a fixed stored field and query. Embeddings originate as model values and are quantized at ingestion; provenance records can detect drift but do not make the model deterministic. `compare_worlds()` calls recall twice through the caller's cursor; it does not itself establish a transaction snapshot. **OBSERVED** ([`field.py:2–41`](../sources/mneme/mneme/field.py#L2), [`field.py:85–104`](../sources/mneme/mneme/field.py#L85), [`field.py:903–965`](../sources/mneme/mneme/field.py#L903), [`counterfactual.py:172–199`](../sources/mneme/mneme/counterfactual.py#L172)) | Reinforcement uses exact `Fraction` arithmetic, but `recall()` embeds text, orders by database vector distance, updates access timestamps/counts, and may transition ORPHANED memories. Repeated queries are not read-only transitions. **OBSERVED** ([`memories.py:258–365`](../sources/stigmergy/ops/memories.py#L258), [`memories.py:416–465`](../sources/stigmergy/ops/memories.py#L416)) |
| Observability | Intervention returns baseline and perturbed full scored sets, ranks, exclusions, and a decomposed delta. Its own documentation bounds the result to Raven retrieval; it does not observe a downstream agent's answer. **OBSERVED** ([`memory_engine.py:359–418`](../sources/raven-memory/raven/memory_engine.py#L359), [`memory_engine.py:2046–2050`](../sources/raven-memory/raven/memory_engine.py#L2046)) | Recall receipts seal query hash, served IDs, exclusions, `top_k`, `hops`, ranking protocol, counterfactual override, and `as_of`. Counterfactual comparison reports rank/score/claim changes, but explicitly does not rerun the downstream decision. **OBSERVED** ([`field.py:660–738`](../sources/mneme/mneme/field.py#L660), [`counterfactual.py:226–243`](../sources/mneme/mneme/counterfactual.py#L226)) | `RecallResult` returns hits plus `is_semantic`; each hit includes distance, state, tier, and confidence. The current recall path does not expose the full internal candidate set or a paired causal intervention result. **OBSERVED** ([`memories.py:234–255`](../sources/stigmergy/ops/memories.py#L234), [`memories.py:395–405`](../sources/stigmergy/ops/memories.py#L395)) |
| Reproducibility | Raven tests pin time for pure-core checks and compare non-clock fields exactly, while allowing bounded drift in recency and final scores. Cross-process spectral determinism is explicitly best-effort; HNSW and embedding provider must be controlled. **OBSERVED** ([`test_intervention_properties.py:168–204`](../sources/raven-memory/tests/test_intervention_properties.py#L168), [`spectral.py:14–22`](../sources/raven-memory/raven/spectral.py#L14), [`memory_engine.py:1277–1303`](../sources/raven-memory/raven/memory_engine.py#L1277)) | Canonical receipts and rational rank calculations improve replay for stored vectors. The embedding provenance boundary records model/revision and vector hashes, and historical state can be reconstructed from custody chains with `as_of`. **OBSERVED** ([`field.py:140–168`](../sources/mneme/mneme/field.py#L140), [`field.py:852–900`](../sources/mneme/mneme/field.py#L852), [`field.py:701–738`](../sources/mneme/mneme/field.py#L701)) | Canonical custody records and exact confidence updates support reproducible state transitions once inputs/timestamps are fixed. The recall path's provider and database vector-distance behavior still need pinning. **OBSERVED / UNKNOWN** ([`canonical.py:58–130`](../sources/mneme/mneme/canonical.py#L58), [`memories.py:416–465`](../sources/stigmergy/ops/memories.py#L416), [`minilm.py:21–54`](../sources/stigmergy/embeddings/minilm.py#L21)) |
| Stable behavioral classes | No source-level class refinement or quotient certificate found in the reviewed Raven files. **UNKNOWN** | Counterfactual comparisons are per query and per pair of custody worlds; no transition-stable state quotient is provided. **OBSERVED** ([`counterfactual.py:172–199`](../sources/mneme/mneme/counterfactual.py#L172)) | No source-level class refinement or H14 quotient is provided. **UNKNOWN** |

## Transfer implications

### Raven: closest intervention seam, incomplete longitudinal treatment

**OBSERVED:** Raven's `_recall_core()` is documented as pure with respect to
persistent state. A suppression blocks a target from seeding, relaying,
firing links, and ranking. `intervene()` executes the baseline and perturbed
core against one field snapshot and one `now`, then persists an audit record.
The supported intervention vocabulary is currently only `suppress` at
`field` stage; other intervention modes/stages are rejected by
[`InterventionSpec`](../sources/raven-memory/raven/memory_engine.py#L259).

**INFERRED:** this supports a direct, one-query falsifier using the real Raven
retrieval implementation. It does not implement H14's functional absence over
a window, post-absence re-exposure, restoration of historical state/links, or
relearning. Ordinary `recall()` performs STDP and activation writes, so a
longitudinal branch must define exactly which experience updates are blocked
while the target is absent ([`memory_engine.py:1953–1989`](../sources/raven-memory/raven/memory_engine.py#L1953)). The current pure suppression probe cannot be treated as that temporal intervention.

**OBSERVED:** Raven's score combines float cosine similarity, discrete state
boost, exponential hop decay, links, and recency; the score is clamped and
the final ordering has a memory-ID tie-break
([`memory_engine.py:1795–1831`](../sources/raven-memory/raven/memory_engine.py#L1795),
[`memory_engine.py:1898–1905`](../sources/raven-memory/raven/memory_engine.py#L1898)).
The configured embedding client can use local, remote, or deterministic dummy
vectors ([`qwen_client.py:66–77`](../sources/raven-memory/raven/qwen_client.py#L66),
[`qwen_client.py:143–165`](../sources/raven-memory/raven/qwen_client.py#L143)).

**PROPOSED:** if approved, the lowest-risk first harness would copy the
relevant Raven source into `experiments/` with the provenance commit recorded,
build a small fixture with fixed stored vectors, force the exact KDTree
backend, inject a fixed clock into the pure core, and branch an identical
SQLite snapshot for each condition. Its initial outcome should be the full
Raven retrieval trace: activated cells, complete scored candidates, ranks,
exclusions, and intervention delta. It should not claim downstream decision
effects unless those decisions are separately captured.

### MNEME: strongest exact replay substrate, custody-only counterfactual

**OBSERVED:** MNEME has exact rational recall ranking with deterministic
tie-breaking, sealed receipts, custody overrides, and historical
`logical_state_at()` reconstruction. `compare_worlds()` compares two custody
worlds for one query and reports exact score/rank and claim changes. Its
documented boundary is explicit: it does not replay the agent's reasoning or
know whether changed retrieval changes an action
([`counterfactual.py:59–69`](../sources/mneme/mneme/counterfactual.py#L59)).

**INFERRED:** MNEME is a strong independent control for reproducibility and
counterfactual readout, but its current counterfactual axis is custody
availability. It does not directly represent Exp50's arbitrary transition
alphabet or Raven's entire memory-state/link dynamics. A successful MNEME
result would validate a narrower reintroduction question unless additional
transition semantics are specified.

### Stigmergy: useful retrieval baseline, recall mutates trajectory

**OBSERVED:** Stigmergy's reinforcement moves confidence by an exact rational
rule and promotes `field_state` at a threshold. Its recall path embeds the
query, selects by vector distance, increments `recall_count`, updates
`last_accessed_at`, and may turn ORPHANED into SHORT_TERM
([`memories.py:258–405`](../sources/stigmergy/ops/memories.py#L258),
[`memories.py:416–465`](../sources/stigmergy/ops/memories.py#L416)).

**INFERRED:** a longitudinal protocol that simply repeats recall would
change metadata and sometimes tier as part of measurement. A frozen-database
branch or an explicit update policy is required. The simpler alternative,
that retrieval ranking already accounts for the relevant persistence, also
deserves a direct test: the observed SQL orders recall by vector distance,
while the selected confidence is not part of that `ORDER BY`
([`memories.py:322–346`](../sources/stigmergy/ops/memories.py#L322)). This is
only a claim about the shown recall query; downstream consumers may use
confidence.

## Falsifiers and next gate

The transfer premise would weaken or fail if, under a frozen Raven field and
fixed query set:

1. the complete retrieval output is reproducible across repeated runs and
   branch copies, but every restoration arm is behaviorally equivalent to
   ordinary retrieval;
2. any apparent difference disappears after controlling the embedding,
   clock, ANN backend, and engine snapshot;
3. a retrieval-only baseline predicts the same outputs and longitudinal
   effects as the intervention branches; or
4. an independently implemented quotient disagrees with the measured
   transition/output traces.

**UNKNOWN:** whether a finite, tractable state abstraction exists for any
real engine snapshot once its actual updates, query distribution, and
observables are included. Exp50's 118 classes cannot be transferred by
renaming its variables.

The next implementation would be an experiment-only adapter/harness under
`experiments/`, not product integration. The workspace's `AGENTS.md`
transition gate requires explicit maintainer approval before moving from the
completed synthetic research package into that implementation. This audit
therefore stops at a source-grounded target and test design.
