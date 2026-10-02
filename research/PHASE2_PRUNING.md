# Phase 2 — Dependency and mechanism pruning

> Goal: explicitly REMOVE unnecessary dependencies and unnecessary inherited
> mechanisms. For every candidate mechanism ask: which hypothesis requires
> this? what observable property should it produce? can we test it? can we
> ablate it? what would falsify its usefulness? is an existing dependency
> justified? would a smaller implementation preserve the property we need?
>
> Rule from the brief: commodity infrastructure (HTTP servers, DB drivers,
> tokenizers, vector math, model serving) stays a dependency unless the
> implementation itself is the hypothesis. "Own the whole thing" does NOT
> mean reimplement the computing stack. Conversely, the semantics under
> investigation stay ours and inspectable.

---

## 1. Dependency audit (OBSERVED from requirements / pyproject)

### 1.1 raven-memory

| Dependency | Category | Verdict | Reason |
|---|---|---|---|
| numpy | vector math | **KEEP** | commodity; the field is numpy arrays |
| scipy (KDTree) | ANN index | **KEEP** (small scale) / swap to hnswlib at scale | commodity; KDTree is stdlib-ish and inspectable. At research scale (<10^4 cells) KDTree is fine and exact. Do not reimplement. |
| sentence-transformers + torch | embeddings | **KEEP as optional** | commodity model serving; embeddings are a *measurement*, not the semantics under investigation. Use a pinned local model or a deterministic stub for reproducibility. |
| fastapi/uvicorn/pydantic | REST API | **REMOVE for research** | serving shape, not under investigation. Research runs call the engine in-process. |
| gradio | demo UI | **REMOVE** | explicitly out of scope (no frontend, no demo). |
| scikit-learn | consolidation clustering | **KEEP if consolidation is tested** | commodity; agglomerative clustering is not the hypothesis. Only keep if a consolidation experiment is in the matrix. |
| requests | Qwen client | **REMOVE for research** | external LLM client; the LLM is out of the decision path. Keep only if an end-to-end agent experiment needs it, and then pin it. |
| mcp | MCP server | **REMOVE for research** | transport, not semantics. |
| hnswlib | ANN | **DEFER** | only if scale demands it; not for the property tests. |

**Net for research core:** numpy + scipy + a pinned embedding source
(deterministic stub or pinned sentence-transformers model). Everything else is
optional and should not enter the experimental core.

### 1.2 MNEME

| Dependency | Category | Verdict | Reason |
|---|---|---|---|
| (stdlib only for the core) | — | **KEEP** | MNEME's core is pure-Python stdlib (hashlib, json, decimal, fractions, sqlite3). This is a strength. |
| mcp | MCP server | **REMOVE for research** | transport. |
| trio | async runtime for MCP | **REMOVE with mcp** | only needed for the MCP stdio server. |

**Net for research core:** stdlib only. MNEME is the cheapest to lift.

### 1.3 STIGMERGY

| Dependency | Category | Verdict | Reason |
|---|---|---|---|
| psycopg | CockroachDB/Postgres driver | **KEEP only if multi-agent shared-state experiment runs** | commodity DB driver. Justified only when the stigmergic substrate is the thing tested. |
| CockroachDB (the database) | distributed substrate | **HEAVY — justify per experiment** | load-bearing for STIGMERGY's thesis (vector index prefix, changefeeds, multi-region). For a single-agent memory property test, this is dead weight. For a multi-agent propagation test, it may be the point. Decision deferred to the experimental matrix. |
| AWS Lambda (changefeed resolver, cron sweeper) | event-driven compute | **REMOVE for research** | deployment shape, not semantics. The sweep/resolver logic can run in-process for tests. |
| GCP Cloud Build / infra | deploy | **REMOVE** | deployment, not research. |
| embeddings (minilm, deterministic) | embeddings | **KEEP as optional** | same as raven: measurement, not semantics. |

**Net for research core:** STIGMERGY's *logic* (controller hysteresis,
recruitment, orphan sweep, custody, Merkle) is pure-Python and testable
in-process against a SQLite stand-in. The CockroachDB dependency is only
justified for the specific multi-agent experiments that need a real shared
substrate. **INFERRED:** most STIGMERGY mechanisms can be tested without
CockroachDB by substituting a SQLite-backed shared-state shim — but that
substitution must be validated against the real substrate before any
"collective memory" claim is made (otherwise we test the shim, not the
system).

---

## 2. Mechanism keep/remove/reimplement

For each candidate mechanism, the six questions from the brief. Verdicts are
**PROPOSED** pending the experimental matrix; they are not decisions.

### 2.1 raven-memory mechanisms

| Mechanism | Required by which hypothesis? | Observable property | Ablatable? | Falsifier | Verdict |
|---|---|---|---|---|---|
| KDTree seed + BFS propagation | "retrieval + propagation beats flat top-k" | rank displacement under suppression | yes (set hops=0 → flat top-k) | propagation adds no measurable recall/decision effect over top-k | **KEEP** (core candidate mechanism) |
| Ternary states (×multiplier) | "state-as-arithmetic beats state-as-flag" | reinforcement changes ranking measurably | yes (set all NEUTRAL) | state multiplier adds nothing over a metadata flag + rerank | **KEEP** |
| RESONANT/INHIBITORY links | "contradiction resistance / collapse-around-truth" | contradictory claims suppress each other | yes (disable link traversal) | links add nothing over metadata filtering | **KEEP** |
| Claim-tagged contradiction (auto INHIBITORY) | "contradiction resistance without NLI" | deterministic conflict detection | yes (turn off auto-link) | metadata contradiction detection ≠ semantic contradiction that matters | **KEEP** |
| STDP | "use-based association learning" | co-recalled memories strengthen | yes (freeze weights) | STDP changes no decision-relevant outcome | **KEEP but suspect** — likely weakest mechanism |
| Rescue rule | "validated truth survives unverified challenge" | REINFORCED memory not silenced by NEUTRAL | yes (disable rescue) | rescue changes no outcome because violation branch is currently unreachable (OBSERVED `intervention.py:221-232`) | **KEEP, but flag vacuity** |
| Audit chain | provenance, not retrieval quality | tamper-evidence | yes (drop chain) | audit improves auditability, not recall (expected) | **KEEP for provenance dimension only** |
| Sleep consolidation | "forgetting/merging improves later recall" | consolidated field recall quality | yes (skip consolidation) | consolidation does not improve downstream recall | **KEEP if consolidation experiment in matrix** |
| Stylometric verification | contamination detection | authorship anomaly → alert | yes (disable stylo) | stylo detects nothing a metadata check couldn't | **REMOVE from core** — tangential to the retrieval-sufficiency question; revisit only for contamination experiments |
| Spectral field | epistemic metadata | resonance/coherence readout | yes (drop spectral) | spectral metadata changes no decision | **REMOVE from core** — explicitly outside ranking by design |
| InterventionSpec | causal attribution | retrieval causal influence Δ | already ablatable (suppress vs no-op) | intervention Δ is always zero (no memory has causal influence on retrieval) | **KEEP** — this is the core probe for Phase 5 |

### 2.2 MNEME mechanisms

| Mechanism | Required by which hypothesis? | Observable property | Ablatable? | Falsifier | Verdict |
|---|---|---|---|---|---|
| Exact Fraction ranking | "verifiable ranking" | bit-reproducible receipts | yes (swap to float) | exact ranking changes recall quality vs float (INFERRED: it doesn't, only verifiability) | **KEEP for provenance; DO NOT expect recall-quality gain** |
| Custody chains | provenance, contamination tracing | per-memory history verifiable offline | yes (no chains) | custody improves auditability only | **KEEP for provenance/containment dimension** |
| Authority/capability model | authorization | unauthorized mutation refused | yes (open trust) | authority changes no recall outcome (expected) | **KEEP only if authorization is a tested property; else REMOVE** |
| Claims (propositions ≠ docs) | "standing derived not stored" | claim standing from evidence | yes (store confidence) | derived standing ≠ stored confidence in any tested case | **KEEP if claim-resolution experiment in matrix** |
| Recall→decision closure | causal attribution to decisions | decision cites only served memories | yes (no DECISION_USED_MEMORY) | closure adds no measurable decision-quality property | **KEEP — this is the decision-causality probe** |
| Counterfactual worlds | "what did the poison DO" | exact delta between sealed worlds | yes (no counterfactual) | counterfactual delta is always zero | **KEEP — pairs with raven intervention** |
| Taint/quarantine/containment | contamination containment | tainted memory cannot reach results | yes (no gate) | gate changes recall but is just a metadata filter | **KEEP for contamination dimension** |
| Graded exposure (blast radius) | "contain without silencing a field" | DIRECT/EXPOSED/CLEAN grading | yes (binary quarantine) | grading ≠ binary quarantine in outcome | **KEEP** |
| Offline verification / conformance | reproducibility | third-party verifies offline | — | — | **KEEP as method, not a mechanism under test** |

### 2.3 STIGMERGY mechanisms

| Mechanism | Required by which hypothesis? | Observable property | Ablatable? | Falsifier | Verdict |
|---|---|---|---|---|---|
| Stigmergic recruitment signals | "experience propagates via shared state" | late agent benefits from earlier agent's signals | yes (no recruitment) | propagation adds nothing over each agent's own retrieval | **KEEP — the only collective-memory mechanism** |
| memory_regions + lineage | "living regions" | region splits/merges reconstructable | yes (fixed partitions) | lineage adds no measurable property | **KEEP only if region-dynamics experiment in matrix** |
| state × tier axes | "forgetting ≠ orphaning" | ORPHANED can be rediscovered | yes (collapse to one axis) | two axes add nothing over one | **KEEP** |
| Hysteresis controller (Fraction) | "dwelling/roaming without local confidence" | stable mode switching | yes (single threshold) | hysteresis ≠ single threshold in stability | **KEEP if control experiment in matrix** |
| Migration cooldown | anti-oscillation | no A→C→A→C under noise | yes (no cooldown) | oscillation occurs without cooldown | **KEEP if multi-agent experiment** |
| Per-node audit + Merkle ledger | multi-node provenance | cross-node integrity without global order | yes (single chain) | Merkle adds nothing a single chain couldn't do | **KEEP only for multi-agent provenance** |
| CockroachDB substrate | shared-state semantics | — | n/a (infra) | — | **DEFER to multi-agent experiments** |

---

## 3. What we explicitly do NOT reimplement (OBSERVED decision)

- HTTP servers, REST/MCP transports, DB drivers, tokenizers, vector math
  (numpy/scipy), embedding model serving, ANN indexes, clustering (sklearn).
- These stay dependencies. The brief is explicit.

## 4. What stays ours and inspectable (OBSERVED decision)

- Memory state and transitions (ternary states, custody status, tier).
- Link semantics (RESONANT/INHIBITORY) and propagation rules.
- Intervention semantics (suppress/excite, field/readout, authority boundaries).
- Experimental contracts (what counts as a trial, a control, a falsifier).
- Evidence and evaluation (receipts, deltas, audit chains, conformance).
- Authority boundaries (probe ≠ stimulation ≠ learning).

## 5. Candidate minimal core (PROPOSED — pending evidence)

If the evidence supports proceeding, the smallest inspectable core that could
carry the hypotheses is INFERRED to be:

- A field with ternary states + RESONANT/INHIBITORY links + BFS propagation
  (raven's core, numpy/scipy).
- Exact ranking (MNEME's `field.py` Fraction version) IF any sealed/forensic
  claim is needed; float ranking otherwise.
- An intervention primitive (raven's `intervene`) for selective causal probes.
- A counterfactual/decision-closure layer (MNEME) IF decision-causality is
  tested.
- A shared-state shim (STIGMERGY logic on SQLite) IF multi-agent propagation
  is tested — promoted to a real substrate only after shim validation.

This is a PROPOSED shape, not a design. It exists to be falsified by Phase 3-4.
A valid Phase 2 outcome is: "the minimal core is even smaller — only the
intervention primitive over a flat top-k baseline carries any signal."
