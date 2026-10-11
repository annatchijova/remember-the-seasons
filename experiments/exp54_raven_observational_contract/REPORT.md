# Exp54: Raven Observational Contract and Transition Congruence

## Result

**OBSERVED — copied Raven snapshot, synthetic Exp51 fixture:** the S5/S4
states, differing only in `C.recall_count` (5 versus 4), remained equivalent in
the four fixed retrieval probes. They remained retrieval-equivalent after the
same `recall`, `store`, `reinforce`, `forget`, and `create_cell_link` engine
actions. The five immediate action outputs also matched. The counter stayed
visible in stats and serialized memory inspection after each action; therefore
the pair is still not equivalent under the declared whole-system observation
set.

This is bounded transition-congruence evidence for the **retrieval
equivalence** relation, not operational equivalence. It covers the fixed
action inputs and query set in the preregistration only.

## Observational contract inventory

**OBSERVED — FastAPI declarations:** public route handlers include storage,
listing and single-memory inspection, reinforcement, forgetting, recall, cell
link creation, graph export, consolidation, stats, audit, metrics, alerts, and
WebSocket events. See [`api_server.py`](../../sources/raven-memory/api_server.py):
storage at lines 381–428; memory listing/inspection at 431–472; reinforce and
forget at 474–501; recall at 508–563; links and graph at 570–587;
consolidation at 594–611; stats/audit/metrics/alerts at 618–702; WebSocket at
709 onward.

**OBSERVED — MCP declarations:** the MCP surface declares store, recall,
reinforce, forget, link creation, stats, memory inspection, audit trail, graph
export, chain verification, consolidation, and info tools in
[`mcp_server.py`](../../sources/raven-memory/mcp_server.py#L109). The tool
definitions continue through line 492.

**OBSERVED — state-changing engine behavior:** `recall()` applies STDP when
current-turn memories are present, increments activation/recall counters, and
stores an audit row ([`memory_engine.py`](../../sources/raven-memory/raven/memory_engine.py#L1930)).
`intervene()` compares two scoring passes but writes an audit row
([same file](../../sources/raven-memory/raven/memory_engine.py#L2026)).
`reinforce()`, `forget()`, and `create_cell_link()` mutate memory state or
links ([same file](../../sources/raven-memory/raven/memory_engine.py#L2171)).
`store()` inserts a memory row ([same file](../../sources/raven-memory/raven/memory_engine.py#L1526));
consolidation can merge and replace rows unless `dry_run` is set
([same file](../../sources/raven-memory/raven/memory_engine.py#L2433)).

**OBSERVED — internal and storage helpers:** `_recall_core()` is an
underscore-prefixed engine method called by the public `recall()` and
`intervene()` implementations; `MemoryStore.load_top_recalled()` is a storage
helper used by `export_graph()`. These are implementation paths, not separately
declared API or MCP routes. Naming alone does not prove that external Python
callers never use them (**UNKNOWN**).

**INFERRED:** `GET` naming does not guarantee a side-effect-free observational
contract. `intervene()` is a method-level example that persists an audit event;
the `/metrics` handler also reads application counters and provider status.
Confirming effects of every transitive call would require tracing every
runtime dependency and deployment configuration.

## Equivalence and transitions

| Relation / check | Result | Scope |
|---|---|---|
| Retrieval equivalence before action | Preserved | Four fixed query vectors |
| Immediate results for selected actions | Equal | Five action/input pairs |
| Successor retrieval equivalence | Preserved | Same four queries after each action |
| Whole-system operational equivalence | Fails | Stats and memory inspection expose 5 vs 4 |

**OBSERVED:** all five action records report equal immediate results and equal
successor retrieval signatures. Their successor total-recall statistics
continue to differ by one. This makes the central distinction concrete:
retrieval equivalence is preserved by these transitions while whole-system
observational equivalence is already false.

**UNKNOWN:** whether retrieval equivalence is a congruence under arbitrary
inputs, all API/MCP operations, non-dry-run consolidation, background jobs,
concurrent calls, or downstream consumers. The `/memories` store endpoint also
calls an external embedder before engine storage; Exp54 tests only the engine
with a fixed embedding.

## SQLite tie-order assay

**OBSERVED:** the two S4 databases had identical logical memory rows and equal
canonical hashes, but their physical row orders were reversed. The four
retrieval signatures and full graph node order were equal. With B and C tied at
four recalls, the original `export_graph(max_nodes=1)` selected B in one copy
and C in the other.

The source query is `SELECT * FROM memories ORDER BY recall_count DESC LIMIT ?`
([`memory_engine.py`](../../sources/raven-memory/raven/memory_engine.py#L952));
`export_graph()` uses it only when it truncates the graph
([same file](../../sources/raven-memory/raven/memory_engine.py#L2257)). The
query specifies no secondary order. The observed row-permutation result shows
that this fixture's tied selection depends on physical row layout under the
tested SQLite query plan. It does not establish the exact behavior of every
SQLite version, index layout, or database file.

**OBSERVED:** an experiment-only selector using
`ORDER BY recall_count DESC, memory_id ASC` selected B in both copies.
**PROPOSED:** use an explicit stable secondary key if stable truncated graph
selection is part of Raven's public contract. This is not an upstream fix and
was not applied under `sources/`.

The negative control is the original unqualified ordering: it produces the
row-order divergence. The deterministic comparator is the positive
metamorphic control: the same logical rows produce the same selected ID after
physical permutation.

## Falsification record and limits

**OBSERVED:** the tested claim “the counter difference changes every future
behavior” is falsified for the five chosen action responses and four retrieval
queries; the tested claim “the counter difference is invisible outside
retrieval” is also falsified by stats and inspection. The graph tie selection
is not stable under the tested physical row permutation.

**UNKNOWN:** the complete public behavioral contract across arbitrary inputs,
all route outputs, WebSocket event sequences, application metrics, deployment
versions, and external Python consumers. Route/tool inventory is static source
inspection, not exhaustive runtime observation.

This is not evidence that Raven is behaviorally equivalent as a whole, nor a
demonstration about MNEME, Stigmergy, a deployed Raven service, or agent-level
decisions. It refines H14's observables and falsifies universal claims in both
directions: neither “the counter is behaviorally inert” nor “it affects every
operation” fits these observations.

## Reproduction

From the repository root:

```sh
python3 -m unittest -v experiments/exp54_raven_observational_contract/test_exp54_raven_observational_contract.py
python3 experiments/exp54_raven_observational_contract/exp54_raven_observational_contract.py
```

The run artifact is [`exp54_raven_observational_contract_run.json`](exp54_raven_observational_contract_run.json).
