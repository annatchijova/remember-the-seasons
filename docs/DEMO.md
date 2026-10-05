# Demo walkthrough — Remember the Seasons

Seven sections, one claim: an agent whose memory keeps the state it
needs to behave **and** the history it needs to explain that state.

```bash
cd product
python3 demo.py                     # offline, deterministic
NEBIUS_API_KEY=... python3 demo.py  # live: Nemotron-3-Nano +
                                    # Qwen3-Embedding-8B on Nebius
```

The first printed line says which inference path is live — the demo
never silently falls back. The offline path is bit-for-bit
reproducible; the live path runs the same protocol against the real
models.

## §1 — the field learns (`ask` as a sealed act)

```
served:     what retrieval offered          (the receipt's claim)
used:       what the model declared used    (the model's claim)
reinforced: what the deterministic engine honored (the only thing
            that changes the field)
receipt:    sealed — replayable and verifiable offline
```

Watch for: **served ≠ used ≠ reinforced is printed explicitly.**
Nemotron answers and declares; MNEME corroborates. A model that
declares a memory it was never served gets caught here — its
declaration lands on the custody chain as evidence of a lie, not as
authority.

## §2 — history happens

The same question returns a different served set and a different
receipt. No magic: a new memory was stored and the field adapted.
The point is that the *difference* is attributable — §4 shows why.

## §3 — `season(q, as_of=t1)`: the past recomputed, not remembered

The same query is run against chains truncated at `t1`. What the
field served then is *recomputed from the committed history* — no
snapshot was taken and none is needed. This is the property ordinary
memory cannot offer: the past state is provable, not recalled.

## §4 — the chain explains the change

The memory that entered in season 2 shows its whole custody chain:
STORED, DECISION_USED_MEMORY, REINFORCED — each event with actor,
reason, timestamp, hash. `impact()` reports how many receipts and
decisions it feeds. The "why did the answer change" question is
answered by *data*, not narrative.

## §5 — `do(T_i = ∅)`: the counterfactual that seals its own delta

One transition (a promotion) is excised; production recall runs in
a SAVEPOINT over the counterfactual world; the result is rolled back.
The report seals the delta:

```
actual served:        [mem-0000, mem-0001]
counterfactual served:[mem-0001, mem-0000]
rank_changed:         [(mem-0000, 0→1), (mem-0001, 1→0)]
```

One removed historical event flipped the top-1 — the causal weight
of a single transition, quantified and sealed. This is the part
retrieval-only memory cannot express at all.

## §6 — provenance at bounded depth

`summary` → just the anchor. `direct` → + chains + decisions using
it. `counterfactual` → + the excisable transitions. One facade,
three depths — the caller pays for exactly the provenance they need.

## §7 — the sealed bundle for a distrusting auditor

`export_cf_bundle` emits self-contained evidence: every chain, the
decision records, the receipts, the counterfactual report. An
offline verifier — a clean-room Go implementation, plus an
import-free Python one — recomputes the whole cascade and either
confirms the claim or says exactly where the evidence broke.
20/20 conformance artifacts agree across both implementations.

## The one-sentence version for a judge

> Ask a question, get an answer **and a receipt**; change the past,
> get a different answer **and a sealed report saying why** — and an
> independent verifier that confirms both without trusting the system
> that produced them.
