# Product Exploration: Rusty Lake × MNEME

**Status:** exploratory line, separate from the confirmatory
experimental program. This is NOT a specification and NOT a roadmap.
No product code was written.

**Date:** phase after Exp30.
**Inputs:** `sources/mneme` (vendored), `sources/raven-memory`
(vendored), the Rusty Lake deep-research report, and the experiment
corpus (Exp14, 19, 24, 25, 26b, 27, 29, 30).

---

## 0. Epistemic discipline

Throughout this document every claim carries one of six tags:

- **A — RUSTY LAKE CANON/OBSERVED:** shown or mechanically enacted
  in the games or stated in official material.
- **B — RUSTY LAKE INTERPRETATION:** a reasonable reading, not
  established literally by the source.
- **C — OUR RESEARCH OBSERVED:** a property actually demonstrated
  by our experiments.
- **D — PRODUCT MAPPING:** a product analogy/affordance we propose.
- **E — REQUIRES EXTENSION:** interesting, but MNEME cannot back
  it today.
- **F — PURE METAPHOR:** visually/narratively useful, no technical
  equivalent. Never promoted to a claim.

Nothing tagged D/E/F is a scientific result. In particular, no
"cube = X" identity is asserted anywhere below.

---

## 1. What MNEME actually does (inventoried from code)

Inventoried by reading `sources/mneme/mneme/*.py`, `SPEC.md`,
`KNOWN_LIMITATIONS.md`, and `demo.py`. "Evidence" names the file and
function; "experimentally demonstrated" means our corpus exercised it.

| Capability | Evidence | Maturity | Demonstrated? |
|---|---|---|---|
| Per-memory custody chain (append-only, hash-chained, genesis-bound) | `custody.py`, `chain.py` | shipped, tested | indirectly (Exp14 CF2a is a weaker analog in minimal_raven) |
| Deterministic replay of chain → derived state | `custody.replay_state`, `authority.replay_authority`, `claims.replay_claim` | shipped; B4/B7/B9 re-derive state from evidence | no — our experiments replay trajectories, not chain events |
| Historical field reconstruction at a timestamp | `field.logical_state_at(cur, as_of)` — truncates every chain at `as_of`, refuses chains that don't replay | shipped | no |
| Recall against historical state | `field.recall(as_of=...)` — same ranking machinery over reconstructed state | shipped | no |
| Hypothetical custody worlds | `field.recall(custody_override={mid: status})` — servable-set override, authority-gated when widening | shipped | no |
| Exact sealed world-vs-world delta | `counterfactual.compare_worlds` → `CounterfactualDelta` (removed/entered/rank-changed/score-changed/claim-flipped/decision-dependency) | shipped | no |
| Named counterfactual queries | `counterfactual.containment_effect`, `exclusion_effect` | shipped | no |
| Blast radius per memory | `causality.impact(mid)` — DIRECT / DERIVED / POSSIBLE grading | shipped | no |
| Sealed recall receipts | `field.recall` → `RecallReceipt`, `persist_receipt`, `verify_receipts` | shipped, replayable (receipt_protocol 2.0.0) | no |
| Decision records (bilateral with custody) | `causality.record_decision`, `DECISION_USED_MEMORY` events | shipped | no |
| Authority ledger (capability grants, no amplification) | `authority.grant/revoke`, B7 check | shipped | no |
| Taint sweeps + exposure grading | `trust.quarantine_actor`, `influence_exposure` (exact rational influence budget) | shipped | no |
| Sealed exportable evidence bundles | `bundle.py` + `verify_offline.py` (stdlib-only) | shipped | no |
| Claims as first-class epistemic objects | `claims.py` — standing derived from evidence, never stored | shipped | no |
| Immutable content + supersession | `field.store/supersede`, M1 | shipped | yes (supersession unused by our experiments) |
| Exact rational ranking (no float in decision path) | `field.py`, `canonical.py`, M5 | shipped | analog in our engine is float — weaker |
| Protocol versioning sealed into evidence | `protocol.py` | shipped | n/a |

**What MNEME does NOT do (relevant here):**

- **No counterfactual over field-state history.** `custody_override`
  changes which memories are *servable*. It does not ask "what if
  the reinforcement events in steps 40–70 had not landed" — that is
  exactly the intervention our experiments manipulate. The field
  state (`REINFORCED/NEUTRAL/FORGOTTEN`) follows real custody events;
  there is no hypothetical-event-sequence replay. **(E)**
- **No editable memory.** Content is immutable (M1); the only
  "change the past" primitive is supersession — a new memory plus a
  `SUPERSEDED_BY` event, with the old chain preserved. Rusty Lake's
  in-place memory alteration has no equivalent and, by design,
  should never have one.
- **No forward simulation.** `compare_worlds` runs the same *query*
  in two worlds. It does not run the *system forward* under two
  intervention regimes — the thing Exp26–30 do.
- **Reinforcement is not custody-overridable.** There is no
  "pretend this memory was never reinforced" primitive; field_state
  is replayed from real events only.

---

## 2. Rusty Lake as a language of operations

Extracted from the deep-research report. Status column marks canon
(A) vs interpretation (B) — the report itself is careful about this
boundary and we keep it.

| Operation | Rusty Lake instance | Status |
|---|---|---|
| externalize | The Mill's Memory Extractor produces white/black cubes from Laura's memories | A — mechanical, canon |
| inspect / carry / store | Cubes persist across scenes and games; usable later | A — canon |
| revisit | Seasons: same room at different seasons navigable | A — canon |
| alter | Birthday's blue cube; official Laketober tag "Change the past" | A — canon |
| corrupt / purify | black↔white extraction, corruption → Corrupted Soul | A — canon |
| combine | black+white+blue → golden in The Cave | A — canon |
| compare past/present | The Past Within's two-player Past/Future split | A — canon (mechanic) |
| "past is causally active" | cross-game codes; "The past is never dead" | A for mechanics; B as metaphysics |
| memory as substance/resource | Russian-community reading ("memory is a resource") | B — fan synthesis, not canon |
| reconsolidation analogy | "The Lake is changing my memories" ↔ reconsolidation | B — our analogy, not authorial |
| cube as episodic memory | Tulving-style episode re-entry | B — structural fit, no demonstrated influence |
| alchemical nigredo/albedo/rubedo | black/white/gold staging | B — plausible, partially community-driven |

The canon-grounded primitive list that survives: **externalize,
inspect, revisit, alter-in-the-fiction, corrupt, combine,
compare-state-across-time, and let a past state change a later
state.** Every one of these is a state operation, not a narrative
beat. That is what makes Rusty Lake usable as an *interaction
vocabulary* rather than a skin.

---

## 3. The Rusty Lake → MNEME matrix

Mapping strength: **DIRECT** (MNEME primitive exists), **PARTIAL**
(exists but with a semantic gap worth naming), **METAPHORICAL**
(no real equivalent; safe only as presentation), **NONE**.

| RL concept | RL status | Abstract operation | MNEME capability | Evidence | Strength | Product affordance | Unsupported assumptions |
|---|---|---|---|---|---|---|---|
| Extract a memory into an object | A | externalize an internal state into an inspectable artifact | `store` + custody genesis + bundle export | `field.store`, `bundle` | DIRECT | A memory as a first-class object you can hold, point at, cite | none — this is what custody already is |
| Cube carries a verifiable provenance | B (canon shows extraction; "verifiable" is our gloss) | every artifact knows where it came from | custody chain + authority ledger | `custody.py`, `authority.py` | DIRECT | "show me this cube's whole history" is one chain read | the game's cubes don't carry provenance; MNEME *exceeds* canon here |
| Revisit the same room in another season | A | query the same space as it existed at another time | `recall(as_of=t)` over `logical_state_at` | `field.py:852–910` | DIRECT | "same question, different season" — one query replayed across history | as_of is *history*, not alternate history |
| Change the past (blue cube) | A | alter a prior state | supersession only; true alteration impossible by design | `field.supersede`, M1 | PARTIAL | "branch from here" ≠ "rewrite what happened" — MNEME refuses the RL primitive and the refusal is the feature | canon alteration is in-fiction; our analog is a new, linked artifact |
| Corrupt a memory / corruption spreads | A (narrative) | taint + propagation | `quarantine_memory`, `quarantine_actor`, `influence_exposure` | `trust.py` | DIRECT for flagging; PARTIAL for "spread" (exposure is a *finding*, never auto-acts) | visualize exposure radius without auto-purging | RL corruption is automatic; MNEME deliberately is not |
| The Lake feeds on cubes | B | collective memory has emergent dynamics | field dynamics (REINFORCED boost, inhibition) | `field.py` + our Exp1–30 | PARTIAL | we can show the field *does* have memory dynamics | "feeds on" implies agency; our findings show mechanics, not appetite |
| Two players, Past and Future, cooperate | A (mechanic) | two views of one causal chain | actual vs counterfactual world, side by side | `compare_worlds` | PARTIAL | paired panes: actual trajectory vs sealed counterfactual | canon is cooperative play; the operation (parallel world comparison) is what maps |
| "What did this memory cause?" | B | downstream blast radius | `causality.impact` DIRECT/DERIVED/POSSIBLE | `causality.py` | DIRECT | select a memory → see every decision it touched | requires callers to persist receipts/decisions — sparse history = sparse radius |
| "Would the outcome differ without this?" | B | counterfactual delta | `containment_effect`, `compare_worlds` | `counterfactual.py` | DIRECT for custody-scope; **NONE for reinforcement-history scope** | "what changed because this happened?" answerable as exact delta today | our Exp30-style intervention (block reinforcement in a window) is NOT expressible as a custody override — E |
| Combine cubes → golden | A (mechanic) | merge states into a new artifact | supersession + evidence links to claims | `field.supersede`, `claims` | PARTIAL | "derive this claim cube from these memory cubes" | canonical combination is alchemical synthesis; ours is provenance-preserving derivation |
| Cubes as physical objects in the world (ARG) | A (The White Door ARG) | memory leaves the system and is verifiable outside | sealed bundle + stdlib-only verifier | `bundle.py`, `verify_offline.py` | DIRECT | a bundle is the honest version of a physical cube: a sealed artifact that verifies offline | the ARG asked humans to *find* cubes; ours are *verifiable* — stronger property, different affordance |

---

## 4. What is a "cube"? Ontology analysis

Nine candidate ontologies, assessed for fidelity to MNEME:

| Candidate | What it would mean | Fits MNEME? | Problem |
|---|---|---|---|
| event | one custody-chain entry | technically real | too small; users don't think in chain entries |
| memory record | one row of `memories` | natural | loses the chain — the *identity* of a MNEME memory is its chain, not its row |
| state transition | one custody event's before→after | real but awkward | transitions are per-memory; product wants something graspable |
| snapshot | field state at `as_of` | real (`logical_state_at`) | not an object; a whole-field state is too big to be "a cube" |
| provenance bundle | memory + full chain + authority slice | real (bundle does this) | heavy; more "archive" than "cube" |
| causal episode | store→reinforce→contradict→serve arc of one memory | real (the chain *is* this) | emergent shape, not a schema object |
| branch point | a moment where two worlds diverge | real (compare_worlds anchors it) | discovered, not stored |
| counterfactual world | a sealed hypothetical | real (custody_override world) | plural-world UX is the harder lift |
| **inspectable state artifact** | **a unit that packages: the memory, its chain, its derived state, and its evidence** | **closest to honest** | needs to be defined as a view, not a new storage object |

**Conclusion:** the honest cube is not "a memory". It is a **unit of
causal history**:

```
cube := prior state
        + the events that acted on it (chain slice)
        + resulting derived state
        + provenance (who/what/when, authority-held)
        + seal (exportable, verifiable offline)
```

This is faithful to MNEME in a way "cube = memory" is not: MNEME's
own thesis is that a memory *is* its custody chain. A UI cube that
showed only content would reproduce the exact conflation
claims.py was written to eliminate (container vs epistemic unit).

**(D)** Product affordance: a cube may provide an interaction
metaphor for an inspectable, externalized memory/state artifact —
selectable, holdable, openable, and always carrying its own
evidence. It must never be presented as "the memory itself".

---

## 5. "Seasons" as an interaction model

Not branding — a candidate temporal interaction model.

**Concept (D):** the interface lets the user inspect the *same*
system at different points of its history and observe what changed
*because* earlier experience happened.

```
same apparent present
+ different history
→ different latent state
→ potentially different future
```

**What MNEME makes literal (DIRECT):** `recall(as_of=t)` is exactly
"the same room in another season". `logical_state_at` reconstructs
the field at any instant without touching later evidence. A
four-season view is four `as_of` recalls of the *same query* — the
room is held constant, the state changes.

**What our experiments add (C→D, carefully):** Exp19/25 showed
which state changes actually matter for path dependence;
Exp27/30 identified *where* to look — the interesting seasons
boundaries are intervention windows and late-flag events, not
uniform time slices. A seasons view that picks its boundaries by
state-transition events (rather than calendar quarters) would be
showing real mechanism, not decor.

**What it must not become (F):** a calendar-themed memory browser
with autumn leaves. "Season" earns its name only if the view shows
*the same question answered differently because history differs*.

---

## 6. The Counterfactual Memory Debugger (serious evaluation)

The candidate product core:

> User selects a historical memory/event/state transition and asks
> "what changed because this happened?"

```
ACTUAL:          H → S_t → recall/decision → future
COUNTERFACTUAL:  H − {event} → S'_t → recall/decision → future'
```

**How much already exists:**

- `compare_worlds` produces the sealed exact delta for one query —
  this IS the debugger's core readout for the custody scope.
- `containment_effect`/`exclusion_effect` are literally "what did
  removing/hiding this do", sealed.
- `impact` enumerates the downstream dependents.
- Receipts + decision records make ACTUAL inspectable end-to-end.
- All deltas are arithmetic facts over exact ranking — no LLM in
  the loop, matching the discipline that the narrative layer must
  never touch the sealed result.

**What would require extension (E):**

1. **Field-state counterfactuals.** "What if this reinforcement
   hadn't happened" is not a custody override. Needs hypothetical
   event-sequence replay: drop/replace custody events and re-derive
   field state. Doable — the replay machinery exists — but it is a
   new code path, not config.
2. **Forward trajectory comparison.** Today: same query, two
   worlds. Needed: same *query sequence*, two intervention regimes —
   our experiments' whole frame. This is a simulation harness over
   MNEME primitives.
3. **Receipt/decision density.** impact() is only as good as
   persisted receipts. A debugger over sparse receipts shows a
   sparse radius — deployment constraint, not code.

**Boundary that must stay (inherited from MNEME's own doctrine):**
the counterfactual pane must be *structurally* marked (receipt
digests already carry `custody_override` inside the seal precisely
so a hypothetical receipt cannot be laundered into actual
evidence). Any UI built on this must preserve the distinction
visually with the same rigor.

---

## 7. Experiments, used without overinterpreting

| Exp | What it actually shows (C) | What it licenses for product (D) |
|---|---|---|
| Exp14 (CF2a) | restoring replayed state closes the counterfactual gap (state-only replay, minimal engine) | state restoration is meaningful in this class of system; supports "restore/revisit" affordance |
| Exp19 | retrieval + persistent binary state reproduces H8; Raven amplifies ~2× | path dependence exists without the full stack; a minimal state widget is honest |
| Exp24/28 | TOST inconclusive; C↔I disagreement 1.9× noise floor; deterministic context effects on a minority of positions | memory context can causally change decisions — worth *displaying*, not claiming magnitude |
| Exp25 | binary accumulating persistent flag is the smallest *tested* sufficient representation | UI can show flag state per memory honestly; NOT a claim of information-theoretic minimum |
| Exp26b | no clean bit threshold; location claim falsified | do NOT build a "bits needed" metric into the product |
| Exp27 | divergence = late-flagged group + feedback; partition accident | the *boundary events* are where history matters — seasons-view anchors |
| Exp29 | top-1 flips only ~20% of flag-diff steps; weak self-limiting loop | feedback exists but is modest — don't oversell |
| Exp30 | rescue kills, induce creates, top1_swap converges — causal mediation *pending audit* | strong candidate for "turn a state on/off and watch the future change" demo; must be audited before being load-bearing |

Nothing here licenses "Rusty Lake predicted our results" or any
narrative coincidences as evidence.

---

## 8. Red team

Attempted destruction, honestly:

1. **"Rusty Lake is decoration on a provenance debugger."**
   Mostly true — and that is the finding. Strip the metaphor and
   what remains valuable is: sealed counterfactual comparison,
   historical reconstruction, blast-radius inspection, verifiable
   export. Those are real and rare. Rusty Lake contributes
   *interaction vocabulary* (objects you hold, seasons you revisit,
   paired worlds), not capability. If the vocabulary helps users
   form correct intuitions about provenance/counterfactuals, it is
   load-bearing UX; if it obscures the semantics, it's worse than
   nothing.

2. **"Cubes over-simplify MNEME semantics."**
   Real risk. A cube showing content alone teaches users that
   memory = record, which is the exact conflation MNEME exists to
   dissolve. Mitigation: cube = chain-bearing artifact (§4), always
   openable to its evidence.

3. **"Anthropomorphism."**
   The metaphor invites "the agent remembers like a person".
   Counter: cubes are *artifacts with provenance*, which is less
   anthropomorphic than chat history — arguably the metaphor is
   *deflationary*.

4. **"Memory content vs memory state confusion."**
   The sharpest risk. RL conflates them constantly (the fiction can
   afford to). MNEME separates them on purpose. Any UI must show
   state (field_state, custody_status, standing) as distinct from
   content.

5. **"Causal replay confused with time travel."**
   as_of is *reading* reconstructed history; nothing is changed. A
   user who thinks they "went back" misunderstands the guarantee.
   The receipts' sealed `as_of` field is the honest label.

6. **"Actual vs counterfactual confusion."**
   MNEME already solved this structurally (override inside the
   receipt seal). UI must inherit that distinction or forfeit the
   project's core claim.

7. **"Doesn't scale visually."**
   Thousands of memories = thousands of cubes = soup. Honest
   answer: cubes aren't a browsing surface; they're *selection
   results*. You don't wander a field of cubes; you pull one out
   by query/claim/decision and inspect its chain.

8. **"Capabilities the UI implies but MNEME can't guarantee."**
   The big one: altering the past. MNEME refuses it by design (M1,
   M4). A UI that even gestures at editing history betrays the
   system. The RL analog is supersession — always a new artifact,
   never a rewrite.

9. **"What survives with all Rusty Lake removed?"**
   - counterfactual memory debugger (sealed world-delta)
   - historical replay viewer (as_of seasons)
   - blast-radius inspector (impact)
   - verifiable evidence export (bundles)
   That is a complete, defensible product: a forensic memory
   workbench. The Rusty Lake layer is the difference between a
   forensic tool only auditors can read and one whose objects,
   seasons, and paired worlds give a non-specialist the right
   mental model. Valuable — but ornamental in the strict sense that
   removal leaves function intact.

---

## 9. Three product concepts (not ranked)

### A. Causal Memory Explorer ("the field, walkable")

- **User problem:** "Why does my agent believe X / where did this
  memory come from and what depends on it?"
- **Core interaction:** memories as selectable cubes; open one →
  full chain, authority slice, claim standing, impact radius.
  Navigation follows evidence links, not similarity alone.
- **MNEME capabilities:** custody chains, authority, claims,
  impact(), exact recall, bundles.
- **RL influence:** cube-as-object interaction grammar; rooms as
  topic/claim spaces (D — affordance only).
- **Scientific value:** makes provenance/blast-radius legible;
  aligns with Exp21–23's finding that mechanism is visible at the
  right granularity.
- **Engineering:** read-only UI over SQLite; graph layout; no new
  MNEME code.
- **Unsupported assumptions:** that spatial navigation beats
  table-of-chains for comprehension (testable, unproven).
- **Failure modes:** visual soup at scale; cube conflation risk (§8.2).
- **5-min demo:** poison demo — watch a cube's chain accuse the
  feed, quarantine sweep, gate closes, impact radius unfolds.

### B. Counterfactual Memory Debugger ("what changed because this happened")

- **User problem:** "Was the poison actually load-bearing? Did that
  quarantine change anything? What does this memory *do*?"
- **Core interaction:** select an event/memory → system shows
  ACTUAL vs COUNTERFACTUAL as paired sealed worlds; exact delta
  enumerated; receipts on both sides marked world-tagged.
- **MNEME capabilities:** compare_worlds, containment_effect,
  custody_override, as_of, receipts, impact.
- **RL influence:** Past/Future split view (The Past Within) —
  paired panes as interaction grammar (D); blue-cube "what if" as
  the question shape (D).
- **Scientific value:** this is Exp14/24/30's frame made usable —
  counterfactual closure as a product verb.
- **Engineering:** exists today for custody scope; field-state
  scope needs hypothetical-event replay (E, §6).
- **Unsupported assumptions:** that users need *field-state*
  counterfactuals (reinforcement history), not just custody ones —
  our experiments suggest it's the interesting case.
- **Failure modes:** user reads counterfactual as actual (§8.6);
  sparse receipts → misleadingly empty blast radius.
- **5-min demo:** run the poison incident, then ask "what did
  containment change?" — the sealed delta answers *in one query*
  "nothing" or "exactly these outputs", and shows it.

### C. Temporal/Seasons View ("same room, four seasons")

- **User problem:** "How did this system's memory state get here;
  when did this belief form and what formed it?"
- **Core interaction:** pick a query; slide across as_of anchors →
  the same recall answered at each era, with state diffs between
  anchors enumerated. Anchors placed at custody/state-transition
  events (Exp27-informed), not calendar ticks.
- **MNEME capabilities:** logical_state_at, recall(as_of),
  receipts, replay_state.
- **RL influence:** Seasons' same-room-different-era directly
  (D — the strongest single RL→product mapping found);
  Underground Blossom's station-per-life-stage as anchor grammar
  (D, looser).
- **Scientific value:** directly operationalizes "same present,
  different history → different latent state" — the project's
  research question made visible.
- **Engineering:** as_of recall exists; anchor selection and
  per-anchor diffing are new but shallow.
- **Unsupported assumptions:** that as_of granularity yields
  *informative* diffs on realistic histories — needs a synthetic
  rich-history fixture.
- **Failure modes:** uniform histories → boring identical seasons;
  degenerates to a timeline widget if state-diff isn't shown.
- **5-min demo:** one query replayed across a seeded history's
  intervention window — watch the same question serve different
  memories as flags land; then ask the debugger why.

---

## 10. Closing sections

### 1. What MNEME already makes possible
Per-memory custody chains; deterministic replay; historical field
reconstruction (`as_of`); hypothetical custody worlds with sealed
exact deltas (`compare_worlds`); graded blast radius (`impact`);
bilateral decision records; authority ledger; exportable bundles
verifiable offline with stdlib Python. This is already a forensic
memory workbench, without a front end.

### 2. What Rusty Lake adds conceptually
An interaction grammar, not a spec: memory as a *holdable object
with a history* (cube), time as *same-place-different-state*
(seasons), counterfactual as *paired worlds* (Past/Future), and
alteration as *branching, not rewriting* — though the games allow
in-fiction rewriting that MNEME correctly refuses.

### 3. What Rusty Lake does NOT justify
Altering content in place (violates M1/M4); cubes as bare memory
records (reproduces the container/proposition conflation);
"the field wants to remember" agency readings; any mapping where
the metaphor hides that counterfactual ≠ actual.

### 4. Product primitives worth preserving without the metaphor
Sealed world-vs-world delta; historical replay viewer; blast-radius
inspector; evidence-bearing objects; explicit actual/counterfactual
labeling. All survive the metaphor's removal.

### 5. Capabilities we would need to add
Hypothetical-event-sequence replay (field-state counterfactuals —
the Exp30 frame); forward trajectory simulation under two
regimes; anchor-selection heuristics for the seasons view; dense
receipt/decision capture for blast-radius legibility.

### 6. Open questions
- Does the counterfactual debugger's real value need *field-state*
  counterfactuals, or is custody scope sufficient for users?
- Is the seasons view informative on realistic (non-synthetic)
  histories?
- Does the cube artifact help or hurt the
  content-vs-state distinction in practice?
- Would Exp30's mediation hold under audit, and does the product
  demo depend on it?

### 7. Falsification / red-team findings
The strongest surviving objection: **the product is valuable
without Rusty Lake** — the metaphor is interaction design, not
capability. The strongest objection to the metaphor itself: any
gesture toward *rewriting* history contradicts MNEME's founding
invariants, so the design must always draw the line canon itself
draws — the past can be branched, revisited, and re-read; it cannot
be quietly edited.
