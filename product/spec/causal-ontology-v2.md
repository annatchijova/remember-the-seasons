# causal-ontology/v2 — declared causes, transitive closure

Normative supplement to `cf-bundle-v1.md`. Declared in the bundle's
`semantics` block as `causal_rewind_protocol: cf-cascade/v2`.

## 1. The change

cf-cascade/v1 inferred dependency from **event type and adjacency**: a
REINFORCED was a decision's consequence iff it sat immediately after
that decision's DECISION_USED_MEMORY. That rule is silent about
anything more distant — a promotion, a link, a chain of effects —
because types cannot express "this event exists *because* that one
did."

v2 makes causality **declared, not inferred**. Events carry an
explicit antecedent list:

```json
"causes": [
  {"kind": "decision", "id": "dec-0001"},
  {"kind": "event", "memory_id": "mem-0000", "seq": 8},
  {"kind": "receipt", "id": "<sha256>"}
]
```

`kind` distinguishes what dies and what does not:

| kind | semantics |
|---|---|
| `decision` | causal — the event dies if that decision becomes ungrounded |
| `event` | causal — the event dies if that custody event dies |
| `receipt` | informational only — grounding is RECOMPUTED, never propagated; a dead receipt ref does not kill |

The pre-v2 spelling `caused_by_decision_id` is treated as exactly one
`{"kind": "decision"}` cause. Events with neither field have no
declared causes; the legacy adjacency rule covers them.

## 2. Write-path causes (mneme/seasons)

- `DECISION_USED_MEMORY` → `causes: [{decision}, {receipt}]` —
  the decision is causal; the receipt is informational (the decision's
  grounding is recomputed from it, never propagated through it).
- `REINFORCED` (decision-caused) → `causes: [{decision}]`
  alongside the legacy `caused_by_decision_id`.
- `STATE_CHANGED` (NEUTRAL→REINFORCED promotion) →
  `causes: [{event: the REINFORCED that crossed the threshold}]` —
  an event-cause. This is the multi-hop v1 could not express: kill
  the reinforcement and the promotion dies with it, because the
  promotion's declared cause is gone.

## 3. The closure rule

The cascade is a fixpoint over declared causes:

```
Dead_{n+1} = Dead_n ∪ { e | ∃ c ∈ causes(e) : c references Dead_n }
```

where Dead contains two node types: dead events `(memory_id, seq)`
and dead decisions `decision_id`. A decision dies when its evidence
base recomputes as ungrounded (semantic — replay decides, not the
graph); its declared consequences then die via the graph.

Iteration order is (created_at, decision_id) — deterministic, and
conservative at timestamp collisions: same-timestamp events are
excluded from a decision's own world evaluation.

## 4. What this proves

`do(T_i=∅)` now propagates through the declared dependency graph to
fixpoint — `decision → REINFORCED → STATE_CHANGED → ...` — rather
than through per-type rules that stop at depth one. Any further
consequence type (links, merges, STIGMERGY writes) joins the cascade
by declaring its causes; the closure needs no new code.
