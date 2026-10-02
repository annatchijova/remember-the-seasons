# Phase 10 — The amputation knife and the real chess test

> Exp19 (stateful retrieval baseline) and Exp20 (behavioral chess
> assay with LLM + Stockfish). Epistemic status: OBSERVED (actual runs).

---

## Summary

| Experiment | Question | Verdict | Key finding |
|---|---|---|---|
| Exp19 (stateful baseline) | Does path dependence need Raven? | BASELINE REPRODUCES | Retrieval + state suffices; Raven amplifies ~2x |
| Exp20 (chess behavioral) | Does intervention degrade LLM chess? | INCONCLUSIVE | n=1 seed, no equivalence test |

Bottom line: the amputation found the surviving organ. Path dependence
does NOT require Raven's machinery — retrieval + persistent adaptive
state is sufficient. Raven's graph/STDP/rescue AMPLIFY the effect
(~2x) but are not necessary for it to exist. The chess behavioral
assay (with LLM + Stockfish) is preliminary but suggests the
intervention is behaviorally memory-specific.

---

## Exp19: Stateful retrieval baseline — the amputation knife

### Question

Exp14 found that the ENTIRE causal effect of decision flips is
reproduced by restoring ONLY the REINFORCED/NEUTRAL state. STDP,
graph propagation, rescue, explicit links — none are needed.

Does path dependence (H8) actually need Raven? Or is it just
retrieval + persistent adaptive state?

### Design

The stateful retrieval baseline:

  HAS:
    - vector retrieval (cosine similarity, top-k)
    - per-memory reinforcement state (REINFORCED/NEUTRAL)
    - same state transition rule (reinforce top-1 on recall)
    - same state multiplier (REINFORCED=1.5, NEUTRAL=1.0)
    - same intervention (block reinforcement during window)
    - same washout (normal reinforcement after window)

  DOES NOT HAVE:
    - graph propagation (no BFS, no k-NN graph)
    - RESONANT boost
    - STDP
    - rescue
    - explicit links
    - recency

Scoring: final = sim * state_multiplier (no hop decay, no resonant,
no synaptic, no recency).

20 seeds, 120 queries, intervention at steps 40-70. Both baseline and
full Raven run the same trajectory. CF2a (state-only replay) is
applied to both.

### Results

```
Metric                                  Baseline        Raven
During intervention set_diff              0.0063       0.0120
Post-washout set_diff                     0.0112       0.0214
Nearest-memory diff (negative ctrl)       0.0000       0.0000
Post-washout decision flips                   11           23
CF2a closure rate                         100.0%       100.0%
```

### Verdict: BASELINE REPRODUCES — but Raven AMPLIFIES (~2x)

Stateful retrieval alone produces path dependence (washout 0.0112,
11 flips). Raven amplifies it (washout 0.0214, 23 flips).

For H8 (path dependence), we do NOT need Raven machinery. The
surviving organ is: retrieval + persistent adaptive state. Raven's
graph/STDP/rescue AMPLIFY the effect but are not necessary for it
to exist.

Both close at 100% with CF2a (state-only replay). The causal
mechanism is the same: state -> scoring -> decision. Raven's
machinery amplifies HOW MUCH the state changes affect recall
composition, not WHETHER they do.

### What this means

This is the most important result of the entire research program.
The user's framing was exactly right: "ir amputándole órganos hasta
encontrar cuál sigue vivo." The amputation found that the surviving
organ is stateful retrieval — not graph propagation, not STDP, not
rescue, not explicit links.

Path dependence is a property of retrieval + persistent adaptive
state. Raven's machinery amplifies it but doesn't create it.

This has implications for the original hypothesis:
- "Retrieval is not necessarily sufficient" — YES, but the missing
  ingredient is persistent adaptive state, not graph propagation.
- A RAG system with reinforcement state would show path dependence.
- A RAG system without reinforcement state would not.

The structural property (H1: RESONANT boost changes set composition)
was not reproduced by any retrieval-only baseline evaluated so far.
But this is a different property from path dependence.

### Limitation

The baseline produces path dependence in fewer seeds than Raven
(11 flips vs 23 flips). Raven's machinery makes the effect more
consistent and stronger. The baseline shows the effect exists
without Raven, but Raven makes it more robust.

---

## Exp20: REAL behavioral off-target assay — LLM + Stockfish

### Question

Does the memory intervention degrade the LLM's chess performance
when the LLM uses the memory to inform its moves?

### Design

  same LLM model (Ollama hermes3:8b, temperature=0)
  same prompt
  same FEN
  same inference config

  CONTROL MEMORY ─┐
                  ├─> LLM ─> chess move ─> Stockfish 16 (depth 15)
  DRUGGED MEMORY ─┘

The LLM receives recalled memories + chess position in its context.
The memories are about angles (irrelevant to chess). If the memory
intervention changes which memories are recalled, that changes the
LLM's context, which MIGHT change its chess move.

Ground truth: Stockfish 16 at fixed depth 15 (not material+mobility).
The LLM's move is scored by Stockfish's evaluation of the resulting
position, normalized against the best move.

The probe (chess) does NOT write back to memory.

5 seeds, 20 chess positions per seed. Memory trajectory: 120
queries, intervention at steps 40-70. Post-washout queries used to
recall memories for chess context.

### Results

```
Seed  Memory divergence  Chess quality (ctrl)  Chess quality (int)  Difference
  42         0.0000              (skipped — no divergence)
   7         0.0500              0.2325                0.2325          0.0000
  13         0.0000              (skipped — no divergence)
  99         0.0000              (skipped — no divergence)
   3         0.0000              (skipped — no divergence)
```

Only 1/5 seeds produced sufficient memory divergence (seed 7,
mem_diff=0.0500). For that seed, chess quality was IDENTICAL
(0.0000 difference) despite memory divergence.

IMPORTANT: This is a single informative condition (n=1). A result of
0.0000 does NOT establish equivalence — it establishes that no
difference was observed in this one seed across 20 positions. An
equivalence test (TOST) with a predefined margin delta would be
needed to claim "chess quality is preserved."

### Verdict: INCONCLUSIVE — preliminary evidence consistent with specificity

For the one seed with sufficient memory divergence, no chess-quality
difference was observed. The data do not establish that the LLM
ignores irrelevant memories — only that no difference was observed
in this single informative condition.

BUT this is preliminary:
1. Only 1/5 seeds had sufficient divergence (the intervention is
   weak in this setup — most seeds produce no post-washout divergence
   at the test queries)
2. The LLM (hermes3:8b) is not strong at chess (most moves are
   suboptimal), so the normalization may be hiding differences
3. The memory divergence is small (0.05 = 2 memories differ out of 40)
4. More seeds with guaranteed divergence would be needed for a
   conclusive result

### What this means

The result is suggestive but not conclusive. The LLM ignores
irrelevant memories when playing chess, which is the expected
behavior. But the test is underpowered because:
- The intervention is weak (only 1/5 seeds produce divergence)
- The LLM is weak (most moves are bad regardless of context)
- The memory divergence is small when it does appear

A stronger test would need:
1. A stronger intervention (longer window, de-reinforcement) to
   guarantee memory divergence
2. A stronger LLM (or a chess-specific model) to make the moves
   more sensitive to context
3. More seeds with guaranteed divergence

### Limitation

The Stockfish evaluation uses depth 15, which is sufficient for
move quality assessment but not for game-theoretic exact results.
For exact results, Syzygy tablebase positions would be needed.

The LLM's chess quality is low (0.23 normalized score), meaning
most of its moves are significantly worse than Stockfish's best.
This limits the sensitivity of the test — a stronger LLM would
make the moves more sensitive to context changes.

---

## Exp21: Reinforcement threshold sweep — algebraic or emergent?

### Question

Exp17 found k* = N-1 (all but one agent intervened needed for
divergence). Is this an emergent collective property, or just the
algebraic consequence of the reinforcement threshold rule?

The prediction: if algebraic, k* = N - T where T is the number of
distinct contributors needed for a memory to be REINFORCED.

### Design

Per-agent provenance (same as Exp16/17). Vary:
- Threshold T ∈ {1, 2, 3} (distinct contributors needed)
- N agents ∈ {3, 5, 8}
- k intervened ∈ {1, ..., N-1}

5 seeds, 120 queries, intervention at steps 40-80.

### Results

```
T=1 (need 1 contributor):
  N=3: k=1→0.0045, k=2→0.0180  (k*=2, predicted 2 MATCH)
  N=5: k=1-3→~0, k=4→0.0240    (k*=4, predicted 4 MATCH)
  N=8: k=1-6→0, k=7→0.0320     (k*=7, predicted 7 MATCH)

T=2 (need 2 contributors):
  N=3: k=1→0.0485, k=2→0.1130  (k*=1, predicted 1 MATCH)
  N=5: k=1→0.0003, k=3→0.0335  (k*=3, predicted 3 MATCH)
  N=8: k=4→0.0033, k=6→0.0290  (k*=6, predicted 6 MATCH)

T=3 (need 3 contributors):
  N=3: k=1→0.0565              (k*=1, predicted 0 MISMATCH*)
  N=5: k=1→0.0512              (k*=1, predicted 2 MISMATCH)
  N=8: k=4→0.0173              (k*=4, predicted 5 MISMATCH)
```

*N=3, T=3: predicted k*=0 is degenerate (can't have divergence
without intervention). The first k where the threshold is violated
is k=1 (leaving 2 non-intervened < 3).

### Verdict: MOSTLY ALGEBRAIC

For T=1 and T=2, the threshold follows k* = N - T exactly. The
"collective resilience" is the algebraic consequence of the
reinforcement threshold rule.

For T=3, the observed threshold is lower than predicted because
the contribution distribution is sparse — not all memories have
3+ contributors, so removing any contributor can drop memories
below the threshold.

### What this means

The "collective resilience" discovered in Exp17 is mostly
mechanical, not emergent. The threshold follows k* = N - T
for low T. For high T, the transition is earlier than predicted
because the contribution distribution is sparse — memories with
exactly T contributors are rare and fragile.

This is a derivation, not a failure. We derived the resilience
curve from the mechanism: the collective memory is resilient
because non-intervened agents' contributions keep memories
REINFORCED, and the threshold is set by how many distinct
contributors are needed.

### Implication for the original hypothesis

The collective resilience is a property of the contribution
threshold rule, not of collective emergence. If we want a genuinely
emergent collective property, we need a different mechanism — not
just counting contributors.

---

## Exp22: Per-memory contributor topology — derivable or emergent?

### Question

Exp21 found k* = N-T for T=1,2 but mismatches for T=3. Is the
residual derivable from per-memory contributor topology, or is it
emergent collective dynamics?

### Design

Per-memory decomposition: for each memory, track its contributor
set before intervention (C_m at step 40), predict which memories
flip given the intervened set I_k, and compare predicted vs
observed recall divergence.

Prediction: memory m flips iff |C_m ∩ I| > |C_m| - T (more than
c_m - T of its contributors are intervened).

### Results

**Flip prediction** (F_pred from step-40 topology vs F_obs at
step 80):

```
T    N    k   F_pred   F_obs  overlap
1    3    1      0.2      2.4     0.2
1    3    2      0.2      2.4     0.2
1    5    4      1.0      4.4     1.0
1    8    7      2.8     11.4     2.8
2    3    1      0.2      0.4     0.2
2    3    2      0.2      0.4     0.2
2    5    3      1.0      2.6     1.0
2    8    6      3.0      5.6     3.0
3    3    1      3.0     14.0     3.0
3    5    1      2.0      5.6     2.0
3    8    7     18.0     19.6    18.0
```

Precision = 0.912, Recall = 0.713.

The step-40 topology predicts MOST flips but underestimates. The
observed flips are larger because dynamics during the intervention
window (40-80) amplify the effect: non-intervened agents keep
reinforcing (adding contributors) but intervened agents' new
contributions are zeroed each step.

**Contributor count distribution** at step 40 (first seed):

```
T=1, N=3: {3:15, 0:80, 2:3, 1:2}   — 15/100 have 3 contributors
T=2, N=3: {1:30, 0:57, 3:12, 2:1}  — 13/100 have >=2
T=3, N=3: {2:16, 1:47, 0:34, 3:3}  — 3/100 have 3 contributors
T=3, N=5: {2:24, 1:32, 0:31, 4:6, 3:3, 5:4}  — 13/100 have >=3
```

For T=3, very few memories can be REINFORCED at all (sparse
contributor topology). Each flip is disproportionately impactful,
explaining why the threshold appears earlier than predicted.

**Predicted vs observed divergence:**

```
T    N    k   pred_div   obs_div   ratio
1    3    2     0.0150    0.0180    0.83
1    5    4     0.0110    0.0240    0.46
1    8    7     0.0190    0.0320    0.59
2    3    1     0.0280    0.0485    0.58
2    3    2     0.0740    0.1130    0.65
2    5    3     0.0290    0.0335    0.87
2    8    6     0.0410    0.0290    1.41
2    8    7     0.1190    0.1380    0.86
3    3    1     0.0200    0.0565    0.35
3    5    1     0.0125    0.0512    0.24
3    8    4     0.0183    0.0173    1.06
3    8    7     0.1140    0.1600    0.71
```

Predicted divergence underestimates observed by ~30-70% — the
dynamics during the intervention window amplify the effect beyond
what initial topology alone predicts.

**Threshold prediction accuracy: 8/9** (predicted k* from topology
vs observed k* for non_div > 0.01).

### Verdict: MOSTLY DERIVABLE

Per-memory contributor topology + the reinforcement threshold rule
predicts the threshold POSITION (8/9 configs match) and explains
most flips (91% precision). But the MAGNITUDE is underestimated
(~30-70% residual) because dynamics during the intervention window
amplify the effect.

The T=3 mismatch is explained by sparse contributor topology:
with T=3, very few memories have enough contributors to be
REINFORCED at all, so each flip is disproportionately impactful.

This is not emergent collective dynamics — it's the algebraic
consequence of the threshold rule applied to a heterogeneous
contributor topology, amplified by ongoing dynamics.

### What this means

The "collective resilience" is fully derivable:
1. Per-memory contributor topology determines which memories can
   flip
2. The threshold rule determines WHEN they flip
3. Ongoing dynamics amplify the effect during the intervention

The apparent emergence is an artifact of aggregating over a
heterogeneous contributor distribution.

---

## Exp23: Residual decomposition — what explains F_obs \ F_pred?

### Question

Exp22's static topology prediction missed ~29% of observed flips
(71% recall). What information absent from the pre-intervention
contributor topology accounts for observed-but-unpredicted state
transitions?

### Key structural fact

In this model, a memory with |C_m(39) \ I| >= T can NEVER flip —
non-intervened contributions are never removed. Therefore every
false negative must be a "late bloomer": c_m(39) < T, which crossed
the threshold during the intervention window in control but not in
intervention.

### Design

Full per-step logging of contributor sets, recall sets, and state
transitions for both control and intervention arms. For each
F_obs \ F_pred memory, classify the mechanism:

- **A1 (direct)**: needed intervened agents' contributions to reach
  T. Those are zeroed every step.
- **A2 (cascade)**: needed non-intervened agents' contributions that
  never came — because those agents' recalls diverged during
  intervention and they reinforced different memories.

### Results

```
Total false negatives: 142
Late bloomers (c39 < T): 142/142 (100%)

Mechanism classification (non-exclusive):
  Direct loss present (A1):       141/142 (99.3%)
  Cascade present (A2):            48/142 (33.8%)
  A1 only:                          94 (66.2%)
  A2 only:                           1 (0.7%)
  Both A1+A2:                       47 (33.1%)
  Neither:                           0
```

### Verdict: DERIVABLE DYNAMICALLY

Every unexplained flip from Exp22's static topology prediction is
a "late bloomer": a memory that was NEUTRAL at step 39, crossed
the threshold during the intervention window in control, but didn't
in intervention because contributors were lost.

Direct contributor loss is nearly universal (141/142, 99.3%).
Cascade effects co-occur in 48/142 cases (33.8%), but pure cascade
accounts for only 1/142 (0.7%).

The cascade is real but small. It exists: intervention on one agent
changes the shared state, which changes another agent's recall,
which changes what that agent reinforces. But it does not rescue
H10 — it produces only marginal flips, not the collective path
dependence originally claimed.

### What this means

The residual is 100% explained by observable trajectory state:
contributor counts + reinforcement logs. No emergent mechanism
needed.

The observed collective-resilience effect in this experimental
system is accounted for by:
- The threshold rule (k* = N-T for low T)
- Heterogeneous contributor topology (determines which memories
  can flip)
- Intervention-window dynamics (late bloomers crossing threshold,
  cascades)

All three components are algebraic and observable within this model.
This is not a universal claim about collective memory — it is a
derivation for this system's conditions.

---

## Exp25: Factorial amputation of persistent adaptive state

### Question

Exp19 found that retrieval + binary adaptive state (REINFORCED/
NEUTRAL) suffices for H8. But "state" is still a black box. What is
the minimum sufficient state for path dependence?

### Design

Dissect state along three axes:

  DISCRETENESS:  binary {NEUTRAL, REINFORCED} vs scalar magnitude
  HISTORY:       accumulates vs last-touch only
  PERSISTENCE:   permanent vs decays vs reset-per-query

Variants (retrieval + state, NO Raven machinery):

  V0 binary    : REINFORCED/NEUTRAL, top-1 -> REINFORCED, mult 1.5
                 (Exp19 baseline — persists, accumulates)
  V1 scalar    : count-based, mult = 1 + 0.05*min(count, 20)
                 (richer state — does magnitude matter?)
  V2 last_only : boost only if reinforced previous step
                 (1-step history, no accumulation)
  V3 decay     : REINFORCED expires after 20 steps without
                 re-reinforcement
  V4 reset     : state cleared between queries (should be inert)
  V5 stateless : no state multiplier (B0 sanity)

20 seeds, 120 queries, intervention at steps 40-70.

### Results

```
Variant        During  Washout  Nearest  Flips     CF%
binary         0.0063   0.0112   0.0000     11  100.0%
scalar         0.0353   0.0496   0.0000     43  100.0%
last_only      0.0303   0.0012   0.0000      1  100.0%
decay          0.0863   0.2476   0.0000    182  100.0%
reset          0.0000   0.0000   0.0000      0      —
stateless      0.0000   0.0000   0.0000      0      —
```

### Analysis per axis

**Discreteness** (binary vs scalar): scalar shows 4.4x more
divergence (0.0496 vs 0.0112) and 4x more flips (43 vs 11).
Magnitude carries information — a count remembers HOW MANY times a
memory was reinforced, not just WHETHER it was. The intervention
removes more information when the state is richer.

**History** (binary vs last_only): last_only nearly kills H8
(0.0012, 1 flip). Accumulation beyond 1 step is NECESSARY — a state
that only remembers the previous step cannot carry path dependence.

**Persistence** (binary vs decay): decay amplifies to 0.2476 with
182 flips — but through a QUALITATIVELY DIFFERENT mechanism. With
decay_k=20 and blocked reinforcement during steps 40-70, ALL
memories decay to NEUTRAL by step ~60. The intervention doesn't
just freeze the state — it wipes it entirely. Post-washout, the
arm rebuilds from all-NEUTRAL, producing massive divergence.

This is NOT "same H8 amplified." It is a state wipe + divergent
rebuild. The mechanism differs: binary blocks accumulation (frozen
state); decay wipes state (catastrophic reset).

**Carry-over** (reset/stateless): both produce exactly 0. Without
persistence across queries, the machinery is inert. Confirmed
negative control.

### Verdict: smallest tested sufficient state = persistent accumulating flag

The minimum state for H8 is:

  **A persistent accumulating flag per memory, updated on recall.**

  - Binary (1 bit, saturating) suffices for the effect to exist.
  - Scalar magnitude amplifies the effect ~4x (richer state loses
    more information to intervention).
  - Accumulation beyond 1 step is REQUIRED (last_only kills H8).
  - Permanence is NOT required for the effect to exist (decay shows
    MORE divergence), but decay changes the mechanism: with
    perishable state, blocking reinforcement becomes a state wipe.
  - Persistence across queries is REQUIRED (reset/stateless = 0).

### What this means

The surviving organ is even smaller than expected. It's not
"adaptive state" in some rich sense — it's a counter that can be
as small as 1 bit. The state must:

1. Persist across queries (not reset)
2. Accumulate over multiple recalls (not just last-touch)

Beyond that minimum, richer state (scalar magnitude) amplifies the
effect, and perishable state (decay) changes the intervention
semantics entirely (freeze -> wipe).

CF closure is 100% across all variants that produce flips — the
state is always the causal antecedent, regardless of its
expressiveness.

---

## Exp26: State compression — how many bits does H8 need?

### Question

Exp25 found that a persistent binary flag per memory suffices for
H8. But "1 bit per memory" with 100 memories is still 100 bits of
history. How much persistent information is actually required?

### Design

Compress the state vector by sharing flags across groups:

  100 bits: 1 flag/memory          (Exp25 binary)
   50 bits: 1 flag/pair
   25 bits: 1 flag/group of 4
   10 bits: 1 flag/group of 10
    5 bits: 1 flag/group of 20
    2 bits: 1 flag/group of 50
    1 bit : 1 global flag
    0 bits: stateless

When ANY memory in a group is reinforced (top-1), the group's flag
is set. The boost (1.5) applies to ALL memories in the group.

Also: same bit budget, different assignment:
  - contiguous: adjacent memories (by angle) share a flag
  - hash: memories assigned to groups by hash (random)

20 seeds, 120 queries, intervention at steps 40-70.

### Results

**Bit sweep (contiguous):**

```
Groups   Bits   During  Washout  Flips
  100    100   0.0063   0.0112     11
   50     50   0.0040   0.0068      4
   25     25   0.0153   0.0188     10
   10     10   0.0247   0.0206      2
    5      5   0.0000   0.0000      0
    2      2   0.0000   0.0000      0
    1      1   0.0000   0.0000      0
    0      0   0.0000   0.0000      0
```

The curve is non-monotonic: divergence drops from 100→50, rises at
25→10, then crashes to zero below 10. There is a threshold around
10 bits — below that, no divergence.

**Assignment comparison** (same bits, different grouping):

```
Groups   Assignment  Washout  Flips
   10   contiguous   0.0206      2
   10         hash   0.0128      0
   25   contiguous   0.0188     10
   25         hash   0.0002      0
   50   contiguous   0.0068      4
   50         hash   0.0030      3
```

Contiguous groups produce 2-100x more divergence than hash groups
at the same bit budget. The LOCATION of information matters, not
just the amount.

### Falsification: Exp26b

Exp26b tested both claims with fine-grained sweeps, deterministic
assignments, and a falsification arm (index-contiguous on shuffled
fields).

**Predefined criteria:** H8 present iff mean washout set_diff > 0.005
AND >= 3 decision flips across all seeds. Below = absent.

**Fine-grained threshold (contiguous, ordered, 30 seeds):**

```
Groups    Mean             95% CI      Flips   H8?
    5   0.0000 [nan,nan]        0      NO
    6   0.0491 [0.0349,0.0632]  3      YES
    7   0.0805 [0.0634,0.0977] 24      YES
    8   0.0049 [0.0007,0.0092]  3      NO
    9   0.0101 [0.0047,0.0156]  1      NO
   10   0.0140 [0.0074,0.0206]  2      NO
   11   0.0395 [0.0296,0.0493] 22      YES
   12   0.0232 [0.0148,0.0316]  1      NO
   15   0.0100 [0.0050,0.0150]  4      YES
   20   0.0083 [0.0040,0.0126]  2      NO
   25   0.0161 [0.0107,0.0216] 10      YES
   50   0.0136 [0.0100,0.0172]  6      YES
  100   0.0115 [0.0091,0.0138] 13      YES
```

**NO CLEAN THRESHOLD.** H8 present at {6,7,11,15,25,50,100},
absent at {5,8,9,10,12,20}. The apparent 5->10 cliff from Exp26
was sampling noise — fine-grained testing shows a noisy,
non-monotonic pattern, not a threshold.

**Coherence measurement (n_groups=10):**

```
Assignment    Within   Between    Diff
index (ord)   0.9643   -0.1075   1.0718  <- coherent by construction
index (shuf)  0.0028   -0.0114   0.0142  <- scattered
angular       0.9643   -0.1075   1.0718  <- coherent by angle
sha256       -0.0405   -0.0070  -0.0335  <- scattered
stride       -0.1111   -0.0000  -0.1111  <- scattered
```

**Divergence at n_groups=10:**

```
Assignment        Mean             Flips   H8?
index_ordered   0.0140                2     NO
index_shuffled  0.0228               11     YES  <- scattered MORE
angular_ordered 0.0140                2     NO
angular_shuf    0.0140                8     YES
sha256_ordered  0.0297               26     YES  <- scattered MORE
stride_ordered  0.0000                0     NO
```

**Location does NOT matter as claimed.** Scattered assignments
(index_shuffled, sha256) produce MORE divergence than coherent ones
at n_groups=10. The Exp26 interpretation that "semantic coherence"
drives the effect is NOT supported — it was an artifact of comparing
only "contiguous-index" vs "unstable hash" on an ordered field.

At n_groups=25 the pattern partially reverses (angular > sha256),
showing the relationship is budget-dependent and noisy, not a
clean geometric law.

### Corrected verdict

**Exp26's interpretation was premature.** There is no clean
information-budget threshold. The divergence-vs-bits curve is noisy
and non-monotonic, not a cliff. And "semantic coherence" is not
the driver — scattered assignments produce comparable or larger
divergence at some budgets.

What survives: SOME persistent binary state is necessary (0 bits =
0 divergence, confirmed). But the exact budget and allocation
requirements are messier than Exp26 suggested — the relationship
between state compression and path dependence is not a simple
threshold.

**What we still know:**
- Persistence across queries is required (Exp25: reset/stateless=0)
- Accumulation beyond 1 step is required (Exp25: last_only ≈ 0)
- Binary is sufficient; scalar amplifies ~4x
- Zero bits = zero divergence (sanity)
- The compression curve is non-monotonic and noisy — no clean
  threshold at any tested resolution

---

## Exp27: Why does 7 groups produce H8 and 8 does not?

### Question

Exp26b showed a noisy curve: 7 groups → 0.0805 (24 flips),
8 groups → 0.0049 (3 flips). Two nearly identical capacities
differ by 16x. Why?

### Design

Same protocol, n_groups ∈ {7,8}, same 30 seeds, with per-step
logging: flag sets, recalls, boundary gap, margin groups.

Key quantities:
- flags set by step 39 (identical both arms)
- "late flags": groups flagged in control during 40-70 (blocked
  in intervention) — the direct causal substrate
- per-event attribution: for each post-washout differing recall,
  whether its group flag differed at that step
- feedback events: intervention arm flags a group that control
  never flags at the same step

### Results

```
                        ng=7       ng=8
mean washout            0.0805     0.0049
total flips                24          3
mean late flags (40-70)   0.23       0.03
seeds w/ divergence>0.001   6          1
state-explained diff      61.9%      50.0%
feedback events              83          0
```

Per-seed washout at ng=7: [0.592, 0.532, 0.404, 0.336, 0.316,
0.236, then zeros]. Divergence is driven by 6/30 seeds.

### Mechanism confirmed

1. A group stays unflagged through step 39 (partition accident +
   query history).
2. Control flags it during the intervention window; intervention
   arm cannot.
3. Post-washout: that group's members are boosted in control but
   not in intervention → recall sets differ.
4. Different recalls → different top-1 → different groups flagged
   → flag sets diverge further (feedback loop: 83 events at ng=7,
   0 at ng=8).

The "38% unexplained by own-group flag" is indirect state
explanation — a member enters/exits top-10 because OTHER groups'
flag differences changed the ranking, not because its own flag
differed. The full flag vector is the state; per-member attribution
is too narrow.

### Why 8 fails: partition accident

At n_groups=8, the partition boundaries happen to land such that
virtually all groups are flagged by step 39 (0.03 late flags vs
0.23 at ng=7). No unflagged group at the intervention boundary →
no substrate for divergence. It is not "8 bits insufficient" — it
is "this particular partition happens to saturate early."

### Verdict: feedback loop + partition accident

The noisy Exp26b curve is a lottery: whether a flag survives
unset through step 39 depends on query trajectory and where
partition boundaries land. When it does, a feedback loop
(flag diff → recall diff → flag diff) amplifies the divergence.

There is no magic bit count. There is a threshold-dynamics
phenomenon: **late-flagged groups are the causal substrate, and
feedback amplifies their effect.**

This connects Exp26/27 to Exp23: "late bloomers" (memories crossing
threshold during the window) and "late flags" (groups flagged
during the window) are the same structural phenomenon at different
levels of the system.

---

## Exp24: H11 done properly — preregistered + TOST

### Why Exp20 was insufficient

Exp20 selected seeds post hoc for divergence, n=1 informative
condition, no equivalence test. A 0.0000 chess difference does not
establish equivalence.

### Preregistered design

All parameters fixed BEFORE any chess evaluation:

- Candidate seeds: 0..15 (fixed list)
- Calibration gate: include seed iff post-washout recall divergence
  >= 0.02 (selection on memory only, never on chess outcome)
- Positions: 15 fixed FENs (seed 77777, same for all arms)
- Same LLM (hermes3:8b, temp=0) both arms; only memory context
  differs
- Stockfish 16 depth 15 = ground truth; metric = regret in
  centipawns (best_score - move_score)
- Equivalence margin: delta = 30 cp (preregistered)
- TOST: H0 |mean diff| >= delta vs H1 |mean diff| < delta
- Sham: same context twice — measures LLM noise floor

### Results

**Calibration:** 3/16 seeds passed the gate (2, 7, 11 — all
mem_diff = 0.0500). Selection made before chess evaluation.

**Sham:** 14/15 agreement; the single flip cost 1 cp. Noise floor
is small but nonzero — the LLM occasionally flips marginal
decisions even with identical context.

**Intervention (45 paired positions):**
- Move agreement: 39/45 (87%)
- Nonzero diffs: +1, +32, -20, -41, -639, +41
- Mean paired diff: -13.9 cp
- 90% CI: [-37.9, +10.1]
- TOST p = 0.1332

The nonzero diffs have mixed signs (3 positive, 3 negative) — the
observed data do not show consistent directional degradation. The
-639 outlier (intervention arm played a BETTER move, g4h5 vs
blunder g4g7) dominates the CI width.

### Verdict: INCONCLUSIVE (rigorously)

The CI crosses the -30 boundary: cannot distinguish "no effect"
from "insufficient data" at delta=30cp. This is now a principled
inconclusive — not "we only had one seed" but "the equivalence
margin was not met given observed variance."

What the data supports: most positions (87%) produce identical
moves; nonzero diffs have mixed signs with no consistent
directional degradation. What it does NOT establish: equivalence
within 30cp — one large outlier (-639) prevents the CI from fitting
the margin.

The correct way to resolve this is more power under the SAME
preregistered protocol: same delta=30, same metric, same TOST,
more independent units. Widening delta after observing these data,
or filtering positions post hoc, would move the goalposts — a wider
margin requires an external justification fixed before the new run.

---

## Exp28: Variance decomposition — does C vs I exceed noise?

### Question

Exp24 showed sham flips 1/15 at 1cp; intervention flips 6/45 at
mean 129cp. But sham had 15 pairs vs 45 — unfair noise baseline.
Does the C-vs-I change exceed what the LLM produces when nothing
changes?

### Design

For each (seed, position): 4 reps with control context, 4 reps
with intervention context. Measure disagreement within each
condition vs between conditions.

  D(C,C): same control context, different reps — LLM noise
  D(I,I): same intervention context — LLM noise
  D(C,I): control vs intervention — noise + context effect

Seeds {2,7,11} from Exp24 calibration, 15 fixed FENs, 360 LLM
calls total.

### Results

```
Move disagreement rates:
  D(C,C) = 18/270 = 0.067   <- LLM nondeterminism
  D(I,I) = 15/270 = 0.056   <- LLM nondeterminism
  D(C,I) = 93/720 = 0.129   <- noise + context effect
  D(C,I) / max(within) = 1.94

|regret diff| distributions:
  within C:  mean=8.1  max=639
  within I:  mean=8.4  max=639
  between:   mean=21.1 max=639
```

### What the per-position data shows

Two distinct categories of disagreement:

**Pure noise** (e.g., pos 14): both conditions internally
unstable (cc=3/6, ii=3/6). The model is marginal on this position
regardless of context — flips are nondeterminism.

**Real context effect** (pos 8 seed 11, pos 11 seeds 2/7):
cc=0/6 AND ii=0/6 — deterministic within each condition — but
ci=16/16 — DETERMINISTICALLY different between conditions. The
memory context causally changes the move.

The -639 diff from Exp24 is NOT noise: seed 11 pos 8, control
always plays g4g7, intervention always plays g4h5. Consistent
within each condition, different between. This is a real causal
effect of the memory-context change.

### Verdict: MARGINAL SIGNAL

D(C,I) = 0.129 exceeds within-noise (0.067) by 1.9x. Some evidence
of a context effect beyond LLM stochasticity, but near the noise
boundary.

When moves differ across conditions, the consequences are large
(between 21.1cp vs within 8.4cp) — the flips that happen are real
decision changes, not marginal wobbles.

The refined picture:
- Most positions (87%) are unaffected by memory context.
- A minority of positions have DETERMINISTIC context effects
  (the memory change flips the model's choice).
- Another minority has noise-driven flips (marginal positions
  where the model wobbles regardless of context).
- The direction has mixed signs: sometimes intervention improves,
  sometimes degrades. No consistent directional degradation.

H11 remains inconclusive for equivalence, but the mechanism is now
clearer: the memory context does causally affect a minority of
chess decisions, in mixed directions.

---

## Exp29: When does flag divergence self-amplify vs die out?

### Question

Exp27 found the mechanism (late flag -> recall diff -> flag diff)
but only ~20% of seeds diverge at ng=7. What determines whether
the initial flag difference self-amplifies or dies out?

Hypothesis: the loop feeds only when a flag difference changes the
TOP-1 of a recall — top-1 is what gets reinforced, and the
reinforced memory's group is the next flag set. If a flag boost
only lifts members into ranks 2-10, the set changes but the
reinforcement target doesn't — no feedback.

### Design

n_groups in {6,7,8,11,25}, 30 seeds. Per-step logging:
- flag-set Hamming distance between arms
- does the differing flag change top-1 or only the set?
- flag distance trajectory post-washout (grow vs shrink)

### Results

```
 ng   div seeds   converged   diverged   top1 chg   top1 same
  6        4           1          3          63         193
  7        6           0          3          92         285
  8        1           1          0          10          26
 11        6           3          0          53         291
 25        5           4          0          35         227

Flag-diff -> top-1-change rate: 19.8%
(253 changed vs 1022 same)
```

Flag distance trajectory (ng=7, divergent seeds):
```
steps 70-79:   1.05
steps 80-89:   1.27
steps 90-99:   1.33
steps 100-109: 1.33
steps 110-119: 1.40   <- slow growth, not explosive
```

### Verdict: WEAK feedback — the loop feeds ~20% of the time

The hypothesis partially survives: flag differences DO change
top-1 sometimes (19.8% of flag-differing steps), and when they do,
divergence can grow (3/6 divergent seeds at ng=7 grew).

But the loop is weak: 80% of flag-differing steps change only the
set, not the reinforcement target. And at ng=11/25, divergent
seeds CONVERGE post-washout — the intervention arm re-flags the
missing group and the flag sets re-coincide.

The refined mechanism:
- Late flags create the initial divergence (Exp27)
- Feedback amplifies ONLY when flag diffs reach rank-1 (20% rate)
- The system self-corrects when feedback is too weak to sustain

This is consistent with the whole arc: the memory mechanism is
persistent but self-limiting — path dependence exists, amplifies
weakly, and dies out unless the partition accidentally leaves
rank-1-relevant groups unflagged at the intervention boundary.

---

## Exp30: Causal mediator intervention

### Question

Exp27/29 described a correlational story: late flags -> recall
diff -> flag diff. Does the chain actually mediate divergence?
Manipulate each link directly.

### Design

ng=7, 30 seeds, intervention 40-70. Six arms:

  natural    — Exp27/29 baseline
  saturate   — all group flags True at t=40 in intervention arm
  rescue     — flag only control's late groups at t=40 in int arm
  induce     — on a quiet seed: unflag one active group at t=40
  top1_block — natural until t=70, then no reinforcement
  top1_swap  — natural until t=70, then reinforce control's top-1

NOTE: first run produced 0 divergent seeds — build_field was called
positionally, passing n_groups into n_memories. Fixed to keyword
argument. This bug is why Exp30's first output showed all-quiet.

### Results

```
DIVERGENT seeds (natural > 0.005, n=6):
  seed  natural  saturate  rescue  t1block  t1swap  late
     8   0.5320   0.9440  0.0000   0.3160   0.0160    1
    14   0.3360   0.7840  0.0000   0.3360   0.0440    1
    18   0.5920   0.9120  0.0000   0.3480   0.0160    1
    19   0.2360   0.8000  0.0000   0.2360   0.0280    1
    27   0.4040   0.9400  0.0000   0.4040   0.0360    1
    28   0.3160   0.9080  0.0000   0.3160   0.0320    1

  Means: natural=0.4027 saturate=0.8813 rescue=0.0000
         t1block=0.3260 t1swap=0.0287

QUIET seeds (n=24):
  induce -> divergence in 21/24 seeds
```

### Causal interpretation

**Necessity (rescue):** flagging exactly the groups that control
late-flagged collapses divergence to 0.0000. The specific unset
flags are necessary — the divergence does not come from generic
state noise.

**Sufficiency (induce):** on quiet seeds, unflagging one active
group produces divergence in 21/24 cases. An unset flag is
sufficient — the mechanism is not seed-specific.

**Mediator (top1_swap):** post-washout, forcing the intervention
arm to reinforce CONTROL's top-1 collapses divergence to 0.0287.
The reinforcement-target channel mediates the amplification — when
the int arm's flag choices follow control's, the flag sets converge.

**Amplification vs base effect (top1_block):** with no reinforcement
post-washout, divergence persists at 0.3260 (vs 0.4027 natural).
The flag difference established during the window carries most of
the effect; continued reinforcement amplifies it modestly.

**Saturate is not a necessity test:** setting ALL flags True in the
int arm creates a large artificial asymmetry vs control's sparse
flags — it produces divergence (0.88) by construction, not by
mechanism. Rescue is the surgical test.

### Verdict: CAUSAL MEDIATION CONFIRMED (with audit caveats)

The chain is:
```
unflagged group at t=39  -> necessary AND sufficient
    -> top-1 differs post-washout -> reinforcement channel
    -> flag sets diverge further  -> amplified by top-1 channel
```

This is now a manipulated causal claim, not a correlational one:
we can turn the divergence OFF by flagging the late group (rescue)
and turn it ON in a quiet seed by unflagging an active group
(induce). The mediator is the reinforcement channel — swapping the
reinforced memory to control's choice collapses the divergence.

### Post-hoc audit (before freezing the claim)

Three checks were run on the Exp30 implementation after the
positional-argument bug fix:

1. **Natural arms reproduce Exp29 bit-identically.** 0 mismatches
   across 30 seeds × 120 steps. The engines are equivalent.

2. **Rescue produces flag sets identical to control at t=70.**
   Verified directly ({1,3,4,6} vs {1,3,4,6}). CAVEAT: in this
   engine the ONLY persistent state is the flag vector, so equal
   flags at t=70 force identical trajectories — the collapse is
   partly tautological. What rescue genuinely establishes is
   narrower and still useful: **there is no hidden divergence
   channel** — the entire effect is carried by flag-state
   asymmetry. "Necessary" here means "necessary within this state
   representation".

3. **Induce asymmetry is exactly one group** ({4} at t=70 for
   seed 0 — surgical). The 3/24 seeds where induce FAILED (3, 10,
   11) show a mechanism-consistent failure mode: the unflagged
   group is re-flagged immediately at the first post-window
   reinforcement (it lands top-1 at step 70), so the asymmetry
   dies before affecting recall. Sufficiency requires the
   asymmetry to PERSIST, not merely exist at one instant.

Conclusion: the mediation claim survives, scoped as: within this
binary-flag state representation, the unset-flag → top-1-diff →
reinforcement-diff loop is the sole carrier of path-dependent
divergence.

---

## Exp31: Does asymmetry duration causally predict divergence?

### Question

Exp30's audit found that induce fails on 3/24 seeds because the
unflagged group re-flags at the first post-window reinforcement —
the asymmetry dies before entering the loop. Refined hypothesis:

```
unflagged bit -> persistent asymmetry -> asymmetry survives
long enough to alter a ranking -> top-1 diff -> reinforcement
diff -> future divergence
```

Does asymmetry DURATION causally predict divergence?

### Design

24 quiet seeds (natural intervention produced no divergence —
no late flags), ng=7. Manipulate how long the induced asymmetry
is held: the induced group's re-flagging is suppressed for d
post-window steps, d ∈ {0,1,2,4,8,16,32,50}. d=0 reproduces
Exp30's induce arm (asymmetry can die at first reinforcement).

### Results

```
Quiet seeds (n=24):
 d     P(div)   mean wash   mean t1diff
 0      0.88     0.186       0.110
 1      0.88     0.187       0.110
 2      0.92     0.192       0.112
 4      1.00     0.238       0.139
 8      1.00     0.245       0.142
16      1.00     0.340       0.193
32      1.00     0.409       0.233
50      1.00     0.427       0.243

Divergent seeds (n=6): saturated at 1.00 for all d —
natural late flags already provide persistent asymmetry.
```

### Verdict: ASYMMETRY PERSISTENCE MODULATES DIVERGENCE UNDER CONTROLLED HOLD

Extending the enforced lifetime of the induced state asymmetry
increases both the incidence and magnitude of downstream
divergence. Probability saturates by d=4 in this protocol, while
divergence magnitude continues increasing through d=50.

**Important confound, kept explicit:** longer holds do not only
keep the asymmetry alive longer — they also suppress more normal
re-flag transitions. This experiment does NOT isolate "lifetime of
state asymmetry" from "cumulative consequences of enforcing that
asymmetry". What it establishes:

- Surgically prolonging the asymmetry rescues all three Exp30
  induce failures (P(div) 0.88 -> 1.00 by d=4).
- Magnitude scales with hold length.
- Whether the causal variable is duration per se, or the number
  of blocked state transitions accumulated during that duration,
  is unresolved — that is Exp32's question.

The conservative causal variable remains:

> a persistent state asymmetry that remains causally available
> long enough to modify a later transition.

---

## Exp32: Duration vs blocked-transition count

### Question

Exp31's hold_d conflates two variables: elapsed asymmetry lifetime
and the number of suppressed re-flag transitions during that
window. A hold of 50 steps blocks a re-flag only when the induced
group actually lands top-1 during those steps — which happened
~2.4 times on average, not 50.

Which variable is causal: duration or blocked count?

### Design

24 quiet seeds, ng=7, same induced gid per seed.

  hold_d   — continuous suppression for d post-window steps
  early_k  — suppress only the first k re-flag ATTEMPTS
  late_k   — allow re-flag, then unflag at step 90 and suppress
             k attempts (same blocked count, later placement)

n_blocked logged per cell: the actual count of suppressed
reinforcement transitions.

### Results

```
hold_d:   d    P(div)  wash    n_blocked
          0     0.88   0.186    0.00
          4     1.00   0.238    0.54
         16     1.00   0.340    1.33
         50     1.00   0.427    2.42

early_k:  k    P(div)  wash    n_blocked
          4     1.00   0.399    1.83
          8     1.00   0.427    2.42  <- identical to hold_d=50

late_k:   k    P(div)  wash    n_blocked
          4     1.00   0.338    1.46
          8     1.00   0.339    1.62
```

**Matched-count comparison:** at equal n_blocked, hold and early
arms produce similar washout. **Zero seeds** show washout growth
between d=16 and d=50 at constant n_blocked. Within-duration
correlations of washout ~ n_blocked are small/negative.

### Verdict: TRANSITION COUNT EXPLAINS THE DURATION GRADIENT, BUT NOT THE FULL EFFECT

The Exp31 "duration effect" decomposes to a dose-response on
**suppressed state transitions**: longer holds block more re-flag
attempts, and washout tracks that count. At equal n_blocked,
d=4 and d=50 are indistinguishable — elapsed asymmetry lifetime
alone does not explain the gradient.

But count is NOT a sufficient statistic either:

- early_k=8 gives wash=0.427 vs late_k=8 gives 0.339 at the SAME
  suppressed count — placement matters.
- Within-duration correlations washout ~ n_blocked are small or
  negative — count alone does not predict the outcome across
  seeds.

The defensible reading:

```
elapsed duration alone        -> does not explain the gradient
outcome = f(n_blocked) only   -> does not explain the residuals

effect = f(blocked transitions,
            where/when they occur,
            trajectory state)
```

The causal variable refines once more:

> divergence scales with the number of denied self-corrections,
> weighted by where in the trajectory each denial lands.

Which raises the next question — Exp33: what property of a
transition determines its causal leverage? Not how many, not how
long they persist — which, when, and in what system state.

---

## Exp33: What determines a transition's causal leverage?

### Question

Exp32 showed count explains the duration gradient but isn't a
sufficient statistic (early > late at equal count). What property
of a single denied transition determines its leverage?

### Design

Pulse intervention: exactly ONE denied transition per arm, at a
chosen post-window position. At step t_p: unflag the induced
group; the NEXT step where it lands top-1 has its reinforcement
suppressed; normal dynamics resume. All arms share identical
history to t_p and identical blocked count (1).

Positions t_p ∈ {72,80,88,96,104,112}. 24 quiet seeds, ng=7.
Baseline = same trajectory, no pulse. Per arm, log the score gap
between the induced group's best member and actual top-1 at pulse
time (rank-1 proximity hypothesis).

### Results

```
t_p    washout   delta    P(div)   supp_rate
 72     0.251    +0.251    0.92      0.71
 80     0.247    +0.247    0.96      0.71
 88     0.177    +0.177    1.00      0.75
 96     0.153    +0.153    0.96      0.58
104     0.097    +0.097    1.00      0.58
112     0.054    +0.054    0.96      0.46

baseline (no pulse): 0.0000

corr(gap_at_pulse, washout) = -0.05   <- proximity to rank-1
                                          boundary does NOT matter
```

### Verdict: POSITION, not proximity — REVISED DOWN by Exp34

A single denied transition lands 5x more divergence at t=72 than
at t=112, decaying nearly monotonically with distance from the
intervention boundary. One early denial equals several late ones.

**Downgraded by Exp34:** this gradient was partly an artifact —
supp_rate fell from 0.71 to 0.46 across positions, so late pulses
delivered the treatment less often (opportunity selection). The
event-indexed version (Exp34) shows the real early premium is
~0.05 of washout, not 5x.

The proximity hypothesis FAILED: how close the group was to rank-1
at pulse time is uncorrelated with leverage (r=-0.05). A denied
transition doesn't need the group near a boundary at that instant
— it needs to be denied EARLY.

Why: a denial at t=72 delays the group's re-flag through many
subsequent transitions it would otherwise have participated in —
the asymmetry propagates forward from near the boundary and casts
a long causal shadow. A denial at t=112 shadows few remaining
steps.

This is a clean answer to "which transitions matter":

> causal leverage of a denied self-correction decays with its
> distance from the intervention boundary — early denials shadow
> more subsequent transitions.

And it retro-explains Exp32's early>late at equal count: early
blocks sit at higher-leverage positions.

---

## Exp34: Event-indexed leverage — one realized block per arm

### The confound in Exp33

Exp33's pulse had variable supp_rate (0.71 at t=72, 0.46 at
t=112) — the block only fired if the induced group happened to
land top-1 after the pulse. Late positions under-delivered the
treatment, so part of the "position gradient" was differential
intervention success, not leverage.

### Design

Work in EVENT space, not wall-clock. For each quiet seed:

1. Baseline: force-flag the induced group at t=70 (kills natural
   asymmetry); enumerate its natural G-events — post-window steps
   where a member lands top-1.
2. Arm(j): at the j-th G-event, unflag the group just before the
   recall and suppress that one reinforcement. Every arm realizes
   exactly ONE block; position = event index j, not a timestamp.

Then compare leverage ~ j vs leverage ~ remaining downstream
G-events (the "shadow" hypothesis: early matters because more
future is still reachable).

### Results

```
G-events per quiet seed: median ~13, range 7-25

j     n   realized  mean delta
1     24    24       0.152
2     24    24       0.142
3     24    24       0.148
4     24    24       0.095
5     24    24       0.101
6     24    24       0.098
7     24    24       0.096
8     22    22       0.101

corr(event index j, delta)            = -0.147
corr(remaining events, delta)         = +0.050
corr(residual delta | j, remaining)   = -0.022
corr(residual delta | remaining, j)   = -0.123
```

### Verdict: NEITHER hypothesis dominates

Single realized blocks produce real but modest divergence
(~0.15 early, ~0.10 later) with a small early-event premium
(j<=3 > j>=4, consistent with Exp31's d=4 saturation).

- **Shadow dead**: remaining-opportunity count adds nothing
  (residual corr -0.02 controlling for j).
- **Position weak**: event index correlates only -0.15, and
  -0.12 after controlling for remaining — a real but small
  early premium, not the 5x gradient Exp33 implied.

The Exp33 gradient partly reflected **selection on opportunity**:
late pulses only fired when the group still landed top-1 (which
requires the trajectory to still visit it), so they were
delivered preferentially in seeds whose dynamics had already
moved away — attenuating the effect measured there.

The honest current answer to "which transitions matter":

> accumulation of denied self-corrections is the main driver;
> position confers a modest bonus on the first ~3 blocked
> opportunities, and beyond that neither event index nor
> remaining-shadow predicts leverage strongly.

This scopes Exp33 down to "position correlates with leverage
under a single-pulse intervention"; Exp34 refines it to "the
gradient was partly opportunity-selection, and the true
early-premium is ~0.05 of washout, not 5x".

---

## Exp35: Dose x Position factorial

### Question

Exp34 left "accumulation > position" inferred across different
designs, not isolated factorially. Does dose (k realized blocks)
and position (early/mid/late) contribute independently? Do they
interact?

### Design

24 quiet seeds, ng=7. For each seed, enumerate the induced
group's natural post-window G-events on a force-flagged-at-70
baseline. Arms: k in {0..4} suppressed ordinals at:

  early — ordinals 1..k
  mid   — ordinals 4..3+k
  late  — last k baseline ordinals

Outcome: washout delta vs baseline (k=0). OLS:
delta ~ k + position + k:position on treated cells.

### Results

```
Factorial table (mean delta):
 k    early    mid     late    realized blocks (e/m/l)
 0    0.000   0.000   0.000    0.00  0.00  0.00
 1    0.152   0.095   0.004    1.00  1.00  1.00
 2    0.229   0.172   0.024    1.71  1.75  1.38
 3    0.289   0.184   0.048    2.21  2.21  1.71
 4    0.323   0.228   0.070    2.62  2.62  2.00

Initial OLS on PROGRAMMED k (n=288, R2=0.37):
  k       +0.057  t= 4.78
  late    -0.124  t=-2.68
  k:late  -0.035  t=-2.06

Paired early vs late at k=4: mean diff +0.253, share 92%.
Realized-k gap in those pairs: early 2.62 vs late 2.00.
At EQUAL realized dose (n=7 seeds): early-late = +0.31.
```

### Reanalysis on realized dose (correcting programmed-vs-realized)

```
OLS on REALIZED k, pooled (R2=0.29):
  k_real  -0.012  ns        <- dose vanishes pooled
  late    -0.238  t=-5.29   <- position dominates pooled

Seed-demeaned (within-seed deltas):
  k_real  +0.052            <- dose survives within-seed
  late    -0.122            <- position survives too
  k:late  -0.079            <- interaction survives
```

### Verdict: DOSE AND POSITION BOTH REAL — but the pooled model
### was confounded

The programmed-k OLS reported "+0.057 per block" — wrong framing.
Realized k was systematically lower in late arms (2.00 vs 2.62 at
k=4), so part of "position" was dose deficit.

Corrected:
- Pooled realized-k OLS makes dose vanish entirely — but that is
  itself confounded: seeds with more G-events realize more blocks
  AND differ in baseline dynamics.
- The within estimator (ALL regressors de-meaned per seed, the
  algebraically correct fixed-effects form) gives: k_real +0.025,
  mid -0.098, late -0.192, k:late -0.007 — descriptive within-seed
  associations. The previous partial de-meaning (+0.052, -0.122,
  -0.079) was not the true within estimator and is replaced.
- IMPORTANT: realized_k is post-treatment and trajectory-dependent.
  The causal objects in this simulator are the intervention
  POLICIES (which ordinals we suppress), not the realized count —
  which is a mediator the policy produces, not an exogenous dose.
  So coefficients on realized_k are descriptive, not per-block
  causal effects.
- The cleanest position evidence needs no regression: at k=1,
  all three arms realize exactly one block in all 24 seeds —
  early 0.152, mid 0.095, late 0.004. Delta early-late = +0.148
  at n=24. At k=4 matched-dose (n=7 seeds where realized counts
  coincided), early>late by +0.31 — a matched-realized-dose
  principal-stratum contrast, valid for that subpopulation.

What does NOT survive: "each denial adds +0.057" as a clean
per-block causal claim — realized dose is post-treatment, not
randomized dose.

The frozen closing statement for this branch:

> Phase 10 established that persistent adaptive state is
> sufficient to carry path dependence in this retrieval system.
> Across controlled follow-up interventions, elapsed duration,
> transition count, and event position each captured some aspects
> of downstream divergence, but none of the tested summaries fully
> accounted for causal leverage. Exp35 further shows that
> placement can matter even at equal realized block count, while
> regression coefficients on realized dose remain descriptive
> because realized dose is trajectory-dependent and post-treatment.
> These results motivate separating the compact state needed to
> change future behavior from the richer evidence needed to
> reconstruct why that state arose. They do not establish that
> full history is necessary, nor that no sufficient compression
> exists.

That paragraph survives even if every coefficient changes under
a different estimator — the architectural result does not depend
on three fragile numbers.

---

## Cross-experiment synthesis

### The amputation results

| Property | Requires Raven? | Raven amplifies? |
|---|---|---|
| H1 (set composition change) | NOT REPRODUCED by evaluated baselines | N/A |
| H8 (path dependence) | NO — retrieval + state suffices | YES (~2x) |
| H9 (causal closure) | NO — state is the causal antecedent | N/A |
| H10 (collective contagion) | FALSIFIED (tautological) | N/A |
| H10a (collective resilience) | DERIVABLE — algebraic + topology + dynamics | N/A |
| H11 (chess specificity) | INCONCLUSIVE | N/A |
| H12 (stateful retrieval) | REPRODUCES H8 | N/A |
| H13 (minimum state) | 1-bit accumulating persistent flag | N/A |

### What we learned

1. **Path dependence is a property of stateful retrieval, not Raven.**
   The amputation found the surviving organ: retrieval + persistent
   adaptive state. Raven's machinery (graph, STDP, rescue) amplifies
   the effect ~2x but is not necessary for it to exist.

2. **The structural property (H1) was not reproduced by any
   retrieval-only baseline evaluated so far.** The RESONANT boost is
   a graph-structural property. But this is a different property
   from path dependence. We have not shown impossibility — only that
   the baselines tested (B0/B1/B2') did not reproduce it.

3. **The chess behavioral assay is preliminary.** In the single seed
   exhibiting sufficient recall divergence (seed 7, mem_diff=0.0500),
   no chess-quality difference was observed across the 20 tested
   positions. This is consistent with behavioral specificity but does
   NOT establish it — n=1 informative condition, no equivalence test.

4. **The collective resilience is fully derivable.** Exp21 showed
   k* = N-T for T=1,2 (threshold rule). Exp22 showed per-memory
   topology predicts threshold position (8/9 configs, 91% precision).
   Exp23 showed the residual is 100% "late bloomers" — memories that
   crossed the threshold during the intervention window in control
   but not in intervention, due to direct contributor loss (99.3%
   present) or behavioral cascade (33.8% present). No emergent
   mechanism needed.

5. **The minimum sufficient state is 1 bit per memory.** Exp25
   dissected "persistent adaptive state" factorially: binary
   REINFORCED/NEUTRAL suffices for H8. Scalar magnitude amplifies
   ~4x. Accumulation beyond 1 step is required. Permanence is not
   required (decay changes mechanism to state wipe, not freeze).
   Persistence across queries is required (reset/stateless = 0).

### Implications for the original hypothesis

The original hypothesis was: "Retrieval is not necessarily a
sufficient model of persistent agent memory."

The evidence supports this hypothesis under the tested conditions,
but the crucial clarification is:

**The boundary is not retrieval vs memory. It is stateless retrieval
vs stateful adaptive retrieval.**

And Exp25 dissected the state itself:

**The smallest tested sufficient state representation is a
persistent accumulating flag per memory — as little as 1 bit,
updated on recall.**

- The missing ingredient is NOT graph propagation or STDP.
- The missing ingredient is persistent adaptive state.
- A RAG system with reinforcement state would show path dependence.
- A RAG system without reinforcement state would not.

The collective resilience is algebraic: it follows from the
reinforcement threshold rule applied to a heterogeneous contributor
topology. Not emergent, not mysterious — derivable.

This is a stronger and more useful result than "Raven works." It
tells us WHAT makes memory persistent under these conditions: the
state transitions that change which memories are reinforced, not the
graph structure that propagates activation. And it tells us that
collective resilience is not a new property — it's the same state
rule applied at scale.
