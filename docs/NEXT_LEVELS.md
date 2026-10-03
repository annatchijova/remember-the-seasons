# Construction axes — Remember the Seasons

This document replaces the earlier linear level map. The axes are
independent fronts with their own gates; they are not successive
levels of a single property. A linear map was the wrong shape for
this problem — hosted deployment, causal semantics and shared state
do not sit on one line.

## Destination

> **Infrastructure for agent memory whose behavioral effects are
> causally inspectable and whose history is independently
> verifiable.**

The PKM/tool surface is a demonstration surface, not the product.
The verifiable protocol is part of the architecture. Whether it ever
becomes a *standard* depends on adoption — that is a consequence, not
something we can declare. Novelty claims are suspended pending a
serious landscape pass (causal provenance, event sourcing, temporal
databases, provenance semirings, SCM/counterfactual systems,
agent-memory auditing).

## Axes and their hard questions

| Axis | The hard question | State |
|---|---|---|
| **Adaptive state** | Can history causally change future behavior? | **closed at this scale** — Exp19–35; adaptive flag state produces path dependence |
| **Forensics** | Can a third party verify what happened and under whose authority? | **built** — chains, receipts, decisions, bundles B0–B9, offline verifier |
| **Causal reconstruction** | Can we intervene on a trajectory and correctly recompute its consequences? | **built at field scale** — `do_transition` cascade + independently verifiable cf bundles (CF0–CF3, 9 mutants rejected); spec in CAUSAL_REWIND.md |
| **Counterfactual integrity** | Do actual and counterfactual worlds stay explicitly separated? | **built** — hypothetical flags, write-nothing, laundering refusals, Kassandra |
| **Shared state** | Does it still work with multiple agents/authorities on one field? | **not attacked** — H10's strong collective claim stays falsified |
| **Interoperability** | Can another system produce/consume/verify evidence without trusting our implementation? | **partial** — spec + conformance vectors + stdlib verifier exist |
| **Operations** | Does it survive persistence, concurrency, scale, failure, real deployment? | **partial** — persistence + benchmarks measured; hosted deployment open |

## The open core — causal reconstruction

v1 answers "same query, world where event `(mem, seq)` never
happened" by excising one event on one chain. That is not yet
`do(T_i = ∅)` — and "delete the event, replay everything" is NOT
automatically a valid causal intervention. The semantics requires
declaring what stays fixed, because the field's history mixes
different kinds of records:

```
historical fact      — it happened; the record is evidence, not
                       a recomputation target
endogenous consequence — produced BY the trajectory; must be
                       invalidated or recomputed
exogenous input      — happened to the agent from outside; not
                       caused by the trajectory we excise
counterfactual event — exists only in the excised world
```

Concretely: excising `REINFORCED @mem-A seq k` must invalidate
`mem-A`'s promotion if confidence no longer crosses the threshold
(done in v1). But it must ALSO re-derive every recall that served
A differently afterward — which means every decision citing those
receipts, every `DECISION_USED_MEMORY` bilateral event, every
reinforcement those decisions triggered on OTHER memories — a cascade
whose boundary is the actual scientific problem.

Open questions the spec must answer:
- A decision citing a now-different recall: void, replayed, or kept
  as historical fact-of-record?
- An exogenous observation that entered the field because a decision
  prompted it: does the counterfactual still receive it?
- LLM output as evidence: frozen, re-sampled, or marked
  non-reproducible?
- What does the verifier need to check an excised world is
  *internally* consistent?

Spec in progress: `docs/CAUSAL_REWIND.md`.

## Falsified — stays falsified

- Collective contagion / emergent multi-agent path dependence (H10).
- "Duration/count/position explains causal leverage" as scalar
  summaries (Exp31–35).
- Any claim that the tested compressions prove "history cannot be
  summarized" — they only failed under our controls.

## Non-negotiables

- Gates close on evidence, not demos.
- Under deadline: fewer axes advanced deeply, never all thinly.
- No novelty claims until the landscape pass is done and written down.
