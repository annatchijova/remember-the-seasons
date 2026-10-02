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

Skeleton. The core forensic loop works end-to-end offline, including
the trajectory counterfactual v1 (single-event excision on one
memory's chain; cross-effects through decisions/links not rewound —
documented in `seasons/trajectory.py`). Not wired: MCP server, and
the Nebius deployment path.
