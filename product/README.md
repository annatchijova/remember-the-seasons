# product/ — Remember the Seasons skeleton

The research said:

> state required to behave ≠ history required to explain the behavior

This is the minimal product built on that separation: **mneme is the
forensic layer** (custody chains, sealed receipts, decisions, bundles);
**seasons is the operational loop on top** (store → recall → answer →
reinforce). The adaptive state can be small; the trajectory it writes
cannot be.

## Layout

```
product/
  mneme/           vendored port of sources/mneme — the forensic core
                   (custody chains, recall receipts, decisions, claims,
                   counterfactual worlds, sealed bundles, protocols)
  tests/           mneme's ported test suite — 12 files, all passing
  conformance/     ported conformance vectors
  verify_offline.py  the standalone auditor (stdlib-only)
  seasons/         the product layer:
    db.py          sqlite + schema
    actors.py      authority bootstrap (agent, operator, root)
    embed.py       deterministic local embedder; Nebius when keyed
    llm.py         Nebius Token Factory chat + offline stub
    agent.py       SeasonsAgent: remember / ask / season / what_if
  demo.py          end-to-end: same question across two seasons,
                   difference explained from sealed chains
```

## served ≠ used ≠ reinforced

`ask()` does not conflate them. Recall serves candidates (sealed
receipt); the model answers and declares which ids it actually relied
on (`USED:` line, clamped to what was served — hallucinated ids are
dropped, not recorded); only declared ids enter the decision record
and get reinforced. A memory that was servable but ignored leaves no
false causal trace and no reinforcement.

## The loop

```python
a = SeasonsAgent()
a.remember("The deploy gate requires staging to pass.")
r = a.ask("What do I need before deploying?")
# recall -> sealed receipt -> answer -> decision record -> reinforce
```

Every `ask` writes evidence: a sealed recall receipt, a bilateral
decision record (`DECISION_USED_MEMORY` on each used chain), and a
`REINFORCED`/`STATE_CHANGED` custody event per used memory. The chain
of a memory *is* its biography — `a.chain(mid)` shows exactly what
happened to it and when.

## The product primitive

```python
s = a.season(question, as_of=t1)
```

The same query, reconstructed at an earlier instant by replaying the
custody chains truncated at `t1`. A "season" is a verifiable historical
cut of the field — `same query + different history -> different
served set`, and the difference is checkable, not narrated.

`a.what_if(question, world)` runs the sealed counterfactual
(`compare_worlds`): the same query against a hypothetical custody
state, with the delta exact.

`a.what_if_transition(question, memory_id, seq)` — the trajectory
counterfactual, the gap the research identified: same query in the
world where custody event `(memory_id, seq)` never happened. The
excised chain is replayed generously (transitions recomputed — an
excised REINFORCED means the promotion may never fire), the recall
runs unmodified inside a savepoint, and the sealed report is marked
`hypothetical: true`.

`a.decision_what_if(decision_id, memory_id, seq)` — replays the
question that fed a recorded decision in the excised world and names
which of the decision's used memories would still have been served
(`fallen` vs `survived`, `evidence_base_intact`). Seasons stores the
question text per decision (product table, outside mneme's verified
schema); a receipt alone cannot be replayed — it seals the question's
hash, not the question.

## LLM wiring

- `NEBIUS_API_KEY` + `NEBIUS_BASE_URL` (default
  `https://api.tokenfactory.nebius.com/v1`) — OpenAI-compatible.
- `SEASONS_MODEL` — default `nvidia/Llama-3.1-Nemotron-70B-Instruct-HF`.
- `SEASONS_EMBED_MODEL` — default `Qwen/Qwen3-Embedding-8B`.
- With no key: deterministic local embedder + stub LLM. Same recall,
  same answer, on every machine — receipts stay reproducible.

The LLM is a *narrator*, never the decision path: recall ranking,
receipts, and custody events are sealed before the model sees them
(§5.1 of the repo rules). Swapping the backend changes the wording —
never the verdict.

## Status

Skeleton, verified end-to-end on Nebius Token Factory
(`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` chat +
`Qwen/Qwen3-Embedding-8B` embeddings — hackathon requirement met:
Nebius execution + NVIDIA open-source model). Trajectory
counterfactual v1 live (single-event excision on one chain;
cross-effects through decisions/links not rewound). Not wired:
MCP server, hosted demo.
