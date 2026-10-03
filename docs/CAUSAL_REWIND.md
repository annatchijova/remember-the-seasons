# CAUSAL_REWIND — the semantics of `do(T_i = ∅)`

Status: **design spec, partially implemented.** v1 ships local
excision (`what_if_transition`). This document defines what a
*correct* intervention over the full trajectory means — the boundary
the local version stops at.

The wrong shape is "delete the event, replay everything". The history
mixes four different kinds of records and each needs a different rule:

```
historical fact        — it happened; evidence, not a recompute target
endogenous consequence — produced BY the trajectory; recompute or
                         invalidate
exogenous input        — happened TO the field from outside; preserved
counterfactual event   — exists only inside the excised world
```

## 1. Event ontology

| Record | Class | Rule under excision |
|---|---|---|
| `STORED` | exogenous input | content came from outside the field; preserved. (Excising STORE itself = "the memory never existed" — a different question, still refused.) |
| `REINFORCED` | endogenous consequence | it was issued because a decision declared use; if its motivating decision is invalid in the cf world, it is too. |
| `STATE_CHANGED` | endogenous consequence | recomputed: promotion survives only if confidence still crosses the threshold. |
| `CONTRADICTED_BY` | endogenous consequence | emitted by contradiction detection at birth; survives unless the motivating birth context changed — a birth we don't excise. |
| `SUPERSEDED_BY` | endogenous consequence | depends on the actor's update act; survives unless that act itself is invalidated (v1: no). |
| `QUARANTINED`/`TAINT_FLAGGED`/`REHABILITATED` | endogenous by actor intent | the ACT was someone's decision — a historical fact *about* the world that excision doesn't undo. Survives. |
| `DECISION_USED_MEMORY` | endogenous consequence | bilateral record of a decision's claim; dies if the citing decision is invalid. |
| `recall_receipts` | fact + endogenous content | the READ happened — fact. Its CONTENT (served set, ranks) is a function of field state — endogenous, recomputed under cf state. A cf receipt is a NEW hypothetical artifact, never a rewrite. |
| `decisions` | endogenous consequence | the model's declared act. Its *existence* happened — but its grounding (the receipt it cited, the used set it claims) is endogenous. |
| `memories` row state | derived | always recomputed, never fact. |
| `cell_links` | endogenous consequence | auto links depend on store-time context; manual links are actor intent → survive like QUARANTINED. |
| `seasons_decisions` (question text) | exogenous input | the question asked is an external fact; preserved for replay. |

## 2. The cascade

Excise `T_i` at time `t_i` on memory `M`. Then process the timeline
forward, `t > t_i`:

1. **cf state of M** — v1 machinery (`replay_excised`).
2. **For each receipt `r` with `persisted_at > t_i`** — recompute
   served under the cf world built so far. If served differs → `r` is
   *divergent*.
3. **For each decision `d` citing a divergent receipt** — `d` is
   *cf-ungrounded*: its used-set was chosen against a recall that
   would have served differently. The decision record stays (fact of
   record) but its consequences die: the `DECISION_USED_MEMORY`
   events AND the `REINFORCED` events it caused on every used memory
   are invalidated.
4. **Recompute the chains of every memory that lost an event** —
   new cf states. A memory that loses a promotion may itself stop
   being served in later receipts → the cascade feeds forward.
5. **Iterate to fixpoint** — one forward pass suffices: receipts are
   processed in timestamp order, each against cf states built only
   from events that survived invalidation.

Termination: invalidation only removes events; states converge on a
single forward pass.

## 3. Output of a correct `do(T_i = ∅)`

```
excised:        (memory_id, seq, event_type, ts)
cf_states:      {memory_id: {custody_status, field_state, confidence}}
divergent:      [receipt_sha256 — cf served != actual served]
ungrounded:     [decision_id — cited a divergent receipt]
invalidated:    [(memory_id, seq) — events dead in cf world]
propagation:    edges showing which invalidation caused which
report:         sealed, hypothetical: true
```

## 4. Open questions (the hard part, not yet decided)

- **Decision existence vs grounding.** If decision `d` cited receipt
  `r` and `r` diverges — does `d` "not happen" in cf, or happen with
  a different used-set? LLM output is non-reproducible: we cannot
  regenerate what the model *would have said*. Marked
  `cf-ungrounded` is the honest answer today — the answer the model
  produced is a fact of record, its declared evidence is what was
  endogenous.
- **Exogenous observations triggered by endogenous acts.** A memory
  stored because a decision prompted the agent to look something up:
  the store was triggered endogenously, the content is exogenous.
  Rule so far: STORED survives (input preserved); flag for review.
- **Cross-agent propagation.** If a shared field exists (stigmergy
  axis), does excision on one actor's chain invalidate another
  actor's receipts? Deferred until the shared-state axis opens.
- **Authority under cf.** A grant that issued inside the window —
  does it still hold in the cf world? Tentatively: authority events
  are actor intent (historical fact), preserved.

## 5. Verification — built

`trajectory.export_cf_bundle(mem, seq)` emits a self-contained
bundle (`mneme-cf-bundle/v1`): intervention, actual-world evidence
(memories with quantized embeddings, full chains, cell_links, actors,
decision-cited receipts), and each decision's query embedding as a
sealed exogenous input (a verifier cannot re-derive a model output).

`verify_cf_offline.py` rebuilds the world from that evidence and
RECOMPUTES the cascade — it imports `mneme.field` (the declared
recall protocol) but never `trajectory.py`:

- CF0 bundle digest;
- CF1 chain linkage (genesis-bound prev_hash → entry_hash);
- CF1.5 exogenous input integrity (query embedding digests);
- CF2 actual-world consistency — every decision-cited receipt's
  served set must recompute from the untampered evidence, or the
  "actual world" in the bundle is theatre;
- CF3 the cascade itself — divergent receipts, ungrounded decisions,
  invalidated events, propagation edges, cf states, report digest.

`tests/test_cf_bundle_pure.py` attacks it: 9 sealed mutants — wrong
excision, tampered chain event, dropped edge, orphan invalidation,
phantom ungrounding, missing kill, tampered exogenous input, swapped
seqs, and a coherent-but-false cascade — all rejected. The verifier
recomputes; it does not trust the propagation graph.

## 6. What this is NOT (yet)

- Not a claim of novelty — landscape pass pending (event sourcing,
  temporal databases, provenance semirings, SCM counterfactuals all
  have adjacent machinery; what exactly differs here is undocumented).
- Not a full causal model — there is no world model of agent→world
  effects; consequences outside the field are out of scope by
  declaration, not by discovery.
