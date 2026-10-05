# Remember the Seasons

**English** · **[Español](README.es.md)** · **[Technical README](TECHNICAL.md)**

> We were asked to build the next frontier of AI. We cannot claim to
> have revolutionized it. This is our best attempt in one month.

> STATUS: research phase closed; a working prototype lives in
> `product/`. Sources remain read-only, claims stay labelled, and the
> honest limits are in the Technical README — not hidden.

## The problem

An agent can remember a fact. Can it explain *why* it knows it?

Retrieval answers "what is similar to this question". It does not
answer: why was this memory available, what decision depended on it,
what would change if one historical event had never happened, or
whether the answer it gave last month would still hold. For a personal
assistant, a debugging agent, or an auditor, the *why* is the product.

This repository investigates — and then builds — memory that keeps
both: the state it needs to behave, and the history it needs to
explain that state.

## What it does — observable first

`product/demo.py` runs the whole claim end to end (offline,
deterministic; a Nebius key switches it to real models):

```
ask: 'What do I need before deploying?'
served:    ['mem-0000','mem-0001']   <- what retrieval offered
used:      ['mem-0000','mem-0001']   <- the model's claim
reinforced:['mem-0000','mem-0001']   <- what the engine honored
receipt: 1b2107b9… — sealed, replayable, independently verifiable

later, same question           → different served set, different receipt
season(q, as_of=t1)            → the past recomputed, not a stored snapshot
do(T_i=∅) on a promotion       → the top-1 flips; the report seals
                                  exactly which transition caused it
```

Same script with a key:

```bash
NEBIUS_API_KEY=... python3 product/demo.py
# Nemotron-3-Nano (chat) + Qwen3-Embedding-8B on Nebius Token Factory
```

## Why it is different

| Typical retrieval memory | This system |
|---|---|
| returns similar documents | serves memories *and* seals the receipt |
| no record of why an answer was given | decision record: declared vs
corroborated use, on the chain |
| "trust the embedding" | the model may declare; only deterministic
corroboration changes the field |
| logs of what happened | hash-linked custody chains — tamper-evident |
| can't answer "what if it hadn't happened" | `do(T_i=∅)` excises a
transition, replays production recall, seals the delta |
| temporal proximity implies causation | only declared `causes[]` kill —
a clock is not a cause |

## How it works — three layers

```
operational state      the adaptive field: reinforcement, promotion,
                       taint, resonant links — what changes behavior now
forensic trajectory    per-memory custody chains + authority ledger +
                       receipts + decision records + causes[] —
                       why that state exists
counterfactual replay  do(T_i=∅): excise one transition, run production
                       recall in a SAVEPOINT, rollback, compare —
                       whether that transition mattered
```

The LLM interprets questions and phrases answers. It never sets state:
it *declares* which memories it used, and the deterministic engine
decides which declarations get corroborated. After thirteen
experiments killing accidental semantic authority, the model is a
subordinate of the protocol — by design.

## The evidence

- **Research**: `experiments/` — Exp19–35, the falsification chain
  (see `docs/HYPOTHESES.md`, `docs/EXPERIMENTS.md`).
- **Protocol conformance**: `mneme-cf-bundle/v1` + `cf-cascade/v2` +
  `causal_ontology 2.0.0` — a clean-room Go verifier reproduces every
  verdict: **18/18 artifacts agree**, corpus regenerates byte-for-byte,
  CI enforces it on every push.
- **Causal ontology**: spec `product/spec/causal-ontology-v2.md` —
  explicit `causes[]`, transitive-closure invalidation; adjacency
  alone can no longer kill anything.
- **Stigmergy adversarial series**: `product/tests/test_stigmergy_pure.py`
  — 16 invariants over concurrent multi-authority writes. It found
  real races (now fixed), proved serialization is not causality,
  proved legality is not confluence, and ended at a documented
  frontier: the sealed record cannot distinguish concurrent from
  ordered — yet.

## Layout

```
remember-the-seasons/
  sources/       read-only research snapshots (raven-memory, mneme,
                 stigmergy — each with PROVENANCE.md)
  research/      archaeology inventories, mechanism maps
  experiments/   Exp19–Exp35 — the falsification chain
  docs/          research package, hypotheses, stop conditions
  product/       the working skeleton — see product/README.md
    mneme/       custody, authority, receipts, claims, canonical JSON
    seasons/     the agent: field, embed/LLM wiring, trajectory,
                 vault import, MCP
    tests/       invariant suites (trajectory, bundle, stigmergy, …)
    spec/        protocol specs (cf-bundle/v1, causal-ontology/v2)
    conformance/ sealed corpus + Python↔Go differential
```

## Try it

```bash
cd product
python3 demo.py                     # offline, deterministic
python3 tests/test_stigmergy_pure.py
python3 conformance/cf/v1/generate.py --check   # corpus drift check
bash conformance/cf/v1/differential.sh          # Python ↔ Go, 18/18
```

Deep architecture, protocol versions, threat model, determinism
scope, and the honest list of what this does not guarantee:
**[TECHNICAL.md](TECHNICAL.md)**.

## Rules in force here

See `AGENTS.md`. In particular: no commit/push without explicit
authorization; `sources/` is read-only; every claim is labelled
OBSERVED / INFERRED / PROPOSED / UNKNOWN.

## License & attribution

Apache-2.0, Copyright 2026 Anna Tchijova — see `LICENSE`. Credits for
the source systems, method corpus, and runtime are in `NOTICE`.
