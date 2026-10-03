# Remember the Seasons — Experimental Research Workspace

**[Versión en español →](README.es.md)**

> You asked us to build the next frontier of AI. We cannot claim to
> have revolutionized it. This is our best attempt in one month.

> STATUS: Phase 10 closed — the falsification branch is done. A minimal
> product skeleton now lives in `product/` (see `product/README.md`).
> The rest of the repo remains a lab: sources are read-only, claims stay
> labelled, no overclaiming.

## What this is

An experimental workspace to investigate the hypothesis:

> Retrieval is not necessarily a sufficient model of persistent agent memory.

More precisely: where does retrieval stop being sufficient as a model of
persistent agent memory, and what additional mechanisms produce measurable
properties that retrieval alone does not represent?

The goal of this phase is to **falsify** the hypothesis, not to confirm it.
Valid outcomes include "RAG is sufficient for most tested properties" or "the
entire premise is unsupported". See `docs/STOP_CONDITIONS.md`.

## What this is NOT

- Not the final Remember the Seasons implementation.
- Not a commitment to build anything.
- Not an integration of the three source systems. They are here as research
  material to be inspected, not adopted.

## Layout

```
remember-the-seasons/
  sources/      read-only snapshots of raven-memory, mneme, stigmergy (with PROVENANCE.md each)
  research/     archaeology inventories, mechanism maps, dependency audits
  experiments/  experimental matrix and ablation DESIGNS (not implementations)
  docs/         research package, hypotheses, stop conditions
```

## Source material

Three prior Python systems are included as read-only research snapshots under
`sources/`. Each has a `PROVENANCE.md` recording the exact source revision.

- `sources/raven-memory/` — memory dynamics (reinforcement, inhibition,
  forgetting, graph propagation, rescue invariant, STDP).
- `sources/mneme/` — per-memory custody, authority provenance, recall receipts,
  causal closure, counterfactual worlds, contamination/quarantine.
- `sources/stigmergy/` — shared memory as indirect coordination substrate,
  multi-agent interaction through shared state.

The descriptions above are orientation only. The repositories are the source of
truth; claims about mechanisms must point to code/tests/docs in `sources/`.

## Rules in force here

See `AGENTS.md`. In particular: no commit/push without explicit authorization;
`sources/` is read-only; every claim is labelled OBSERVED / INFERRED / PROPOSED /
UNKNOWN; no inference is silently promoted into a fact.

## License & attribution

Apache-2.0, Copyright 2026 Anna Tchijova — see `LICENSE`. Credits for
the source systems, method corpus, and runtime are in `NOTICE`.
