# Exp54: Raven Observational Contract and Transition Congruence

## Status

**PROPOSED, preregistered before Exp54 behavioral execution.** The experiment
uses disposable copies of the synthetic Exp51 Raven fixture and the copied
source snapshot pinned there. It will not modify `sources/`, upstream working
trees, product code, or project dependencies.

## Question and rival explanation

Exp53 found that `recall_count` is invisible to its four fixed retrieval-score
queries but visible through inspection, telemetry, and truncated graph export.
Exp54 asks whether that difference is specific to retrieval or extends to
Raven's wider declared operations, and whether the graph-selection observation
depends on SQLite row order.

The benign alternative is that Exp53 exposed incidental presentation only:
the counter changes visible summaries, but same-input state transitions retain
the same retrieval behavior, and graph tie outcomes are stable across equivalent
database layouts. A null result for any declared channel or transition counts
against the corresponding sensitivity claim.

## Epistemic and source boundary

The source inventory is a static inspection of the Exp51-pinned Raven snapshot.
The finite behavioral assay calls the copied engine directly; it does not run
the FastAPI or MCP servers, an embedding provider, or an agent. The report must
separate source observations, experiment observations, inferences, and unknowns.

Candidate exposed operations are inventoried from FastAPI route declarations
and MCP tool declarations. For the finite congruence assay, the selected
mutating engine actions are `recall`, `store`, `reinforce`, `forget`, and
`create_cell_link`, each with identical fixed inputs in cloned S5/S4 branches.
The `consolidate` route is inventoried, but actual consolidation is excluded
from the transition matrix because the four-memory fixture does not preregister
a nontrivial merge schedule. Its dry-run result is recorded as a read-only
maintenance observation. `intervene` is also inventoried; it records an audit
row, so it is not counted as a pure read.

## Equivalence relations

Let S5 and S4 be Exp53 states differing only in `C.recall_count` (5 versus 4).

- **Retrieval equivalence** means equality of complete score rows and ranked
  IDs for fixed query vectors A, B, C, and D under the Exp51 fixed clock,
  `top_k=4`, `hops=2`, and no current-turn source memories.
- **Operational observations** in this experiment include `get_stats()`,
  serialized memory inspection, truncated `export_graph(max_nodes=1)`,
  and each selected action's immediate engine result. This is a finite declared
  observation set, not a claim that it exhausts every public or downstream
  consumer.
- For each selected action `a`, retrieval congruence is tested as:
  if S5 and S4 are retrieval-equivalent before `a`, then their successor states
  must remain retrieval-equivalent after applying the same `a` and input.
  Immediate action outputs are compared separately. This finite check does not
  prove congruence for arbitrary inputs or schedules.

## SQLite tie-order falsifier

Build an S4 clone where B and C both have `recall_count=4`, preserve every
logical row value, then create a second clone whose `memories` rows are
reinserted in reverse physical row order. Compare:

1. Full untruncated graph export.
2. Four retrieval score/rank probes.
3. Original truncated graph export with `max_nodes=1`.
4. An experimental deterministic selector with explicit ordering
   `recall_count DESC, memory_id ASC`.

The key falsifier is whether a physical row permutation changes the original
truncated export's selected tied node. The deterministic selector is an
experimental comparator only; no upstream source is patched.

## Predictions and falsifiers

- If same-input selected actions cause any S5/S4 score or rank mismatch, the
  claim that the counter difference remains retrieval-inert under those actions
  is falsified.
- If the selected action return values diverge, the corresponding action
  exposes the counter difference directly; equality only bounds that action
  output in this fixture.
- If reversing physical insertion order changes the chosen tied node in the
  original truncating export, its tie behavior is storage-order-sensitive in
  this fixture. If not, that hypothesis is falsified for this SQLite plan and
  fixture.
- If the explicit secondary-key selector changes across the row permutation,
  the experimental deterministic comparator is falsified.
- Any equality claim is limited to the observed query set, actions, outputs,
  copied source version, and fixture.

## Exclusions

No production workload, arbitrary API payloads, live server/cache behavior,
concurrency, embedding backend, private deployment configuration, or real
agent decisions are tested. Store is invoked through the engine with a fixed
embedding and clock; API-level embedding/provider behavior remains outside the
behavioral assay. Non-dry-run consolidation is inventoried but not executed.
