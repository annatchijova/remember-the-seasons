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
on; only declared ids enter the decision record — and only the
**deterministically corroborated** subset earns reinforcement
(content-answer overlap; the payoff of steering the declaration dies
there). The declaration channel carries a Kassandra-style session
nonce (HMAC of the sealed receipt hash under `RTS_KASSANDRA_SALT`):
a `USED:` line without it is a forged declaration — flagged, ignored,
deterministic fallback. See `REDTEAM.md` for the audit that found it.

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

## The vault layer — the PKM surface

`a.import_vault(path)` turns an Obsidian-style vault into the field:
every `.md` becomes a custody-chained memory, every `[[wikilink]]`
becomes a RESONANT edge that actually changes what recall serves
(resonant boost — not a visual graph). `a.link(a, b)` adds an
explicit edge. `a.update(id, text)` is an "edit" done right:
supersession — the successor names its predecessor, the old note
becomes SUPERSEDED (invisible to recall, preserved as evidence).

What Obsidian gives you: notes, links, a graph. What this adds:
every note is provable history; every link changes behavior; every
edit has lineage; and you can replay, verify, and excise any of it.
`a.forget(id)` / `a.revive(id)` are deliberate forgetting as an
audited transition — the note leaves recall but not the record.

Contradictions surface themselves: `remember(content, topic=T,
claim=C)` — two notes on the same topic with different claims get
bidirectional INHIBITORY links and a `CONTRADICTED_BY` custody event
on **both** chains, automatically. The field knows when its notes
disagree; nobody has to declare it.

Frontmatter: `---` blocks are stripped on import; `title:` names the
note, `tags:` become the topic (minimal parse, not a YAML engine).

Honest gap: mneme's custody vocabulary has no link-event type, so
explicit links (`auto=0`) affect recall but aren't custody-evidenced
the way auto-contradiction links are. Named, not hidden.

## CLI

```bash
RTS_DB_PATH=seasons.db python3 -m seasons remember "a fact"
RTS_DB_PATH=seasons.db python3 -m seasons import ~/vault
RTS_DB_PATH=seasons.db python3 -m seasons ask "deploy?"
RTS_DB_PATH=seasons.db python3 -m seasons chain note-0000
```

Also: `update` `forget` `revive` `link` `provenance` `memories`
`bundle` `serve`. Same sqlite field across invocations — the agent
reopens it, bootstrap is idempotent.

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

`a.request_provenance(trace_id, depth=)` — the facade: resolve a
decision, receipt, or memory and expand bounded evidence.
`summary` (cheap) | `direct` (+chain events, decision links) |
`impact` (+blast radius) | `counterfactual` (+excisable transition
targets — expansion is a projection, not a replay). The projection
itself carries `projection_sha256` so the answer is addressable.

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

## MCP — the product IS the tool

`seasons_mcp_server.py` exposes the loop over FastMCP stdio — the
same transport as mneme, raven-memory, CRONOS, CORVUS. Any
MCP-capable agent that registers it gets verifiable memory:

```json
{"mcpServers": {"remember-the-seasons": {
  "command": "python3",
  "args": ["product/seasons_mcp_server.py"],
  "env": {"RTS_DB_PATH": "seasons.db",
          "NEBIUS_API_KEY": "..."}}}}
```

Tools: `remember` `ask` `season` `what_if_transition`
`request_provenance` `export_bundle`. The pitch is not "another
agent" — it is forensic memory ANY agent can plug in.

`server.py` is the human-facing demo UI (stdlib-only, :8420).

## Latency (bench.py, offline embedder)

| op | p50 @200 mem | p50 @1000 mem |
|---|---:|---:|
| recall | 38ms | 192ms |
| provenance/summary | ~0 | ~0 |
| provenance/counterfactual | 1ms | 4ms |
| what_if_transition | 75ms | 379ms |
| export_bundle | 12ms | 50ms |

Recall is O(N) over a sequential sqlite scan (~190μs/memory); the
counterfactual costs ~2× recall (recompute + one extra recall under
the savepoint). At ~10k notes recall approaches seconds — an
embedding index would fix it without changing the protocol. Named,
not hidden.

## Status

Skeleton, verified end-to-end on Nebius Token Factory
(`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` chat +
`Qwen/Qwen3-Embedding-8B` embeddings — hackathon requirement met:
Nebius execution + NVIDIA open-source model). Trajectory
counterfactual v1 live (single-event excision on one chain;
cross-effects through decisions/links not rewound). Not wired:
MCP server, hosted demo.
