# Phase 8 — MNEME causal closure and STIGMERGY collective memory

> MNEME and STIGMERGY experiments authorized after the statistical
> trials. Epistemic status: OBSERVED (actual runs).

---

## Summary

| Experiment | Question | Verdict | Strength |
|---|---|---|---|
| Exp12 (MNEME closure) | Per-instance causal closure? | WEAK | 56.5% closure rate |
| Exp13 (STIGMERGY) | Collective path dependence? | SURVIVES | B: 17.2%, C: 16.6% washout divergence |

---

## Exp12: MNEME — causal closure per instance

### Question

Can we convert the aggregate finding ("23 decisions changed") into a
per-instance causal claim ("THIS decision changed because the
intervention at step T blocked the reinforcement of memory M; without
that intervention, the decision would not have changed")?

### Design

Minimal MNEME-style custody chain on top of the minimal raven engine:
- Per-memory, append-only, hash-linked custody events
- Event types: STORED, RECALLED, DECISION_USED_MEMORY, REINFORCED,
  REINFORCEMENT_BLOCKED
- Each decision is sealed with its evidence base (which memories
  contributed, with their votes and scores)
- For each decision that flipped between control and intervention,
  trace the causal chain backwards and run a counterfactual

The counterfactual: restore the missing memories from control's
evidence base to the intervention's, recompute the decision. If it
flips back to control's decision, we have causal closure.

### Results

```
Total decision flips: 31
Post-washout flips: 23
Counterfactual restored control decision: 13 (56.5%)
Counterfactual did NOT restore: 10 (43.5%)
```

### Two kinds of flips

**Set-difference flips (56.5% — closure achieved):**

The control's evidence base contained a memory that was absent from
the intervention's. Example (step 77):

```
Control:     yes (yes=7.014, no=5.814)  evidence includes M0084 (vote=yes, score=1.02)
Intervention: no  (yes=5.993, no=6.525)  evidence does NOT include M0084
Counterfactual: add M0084 back -> yes (yes=7.014, no=5.814) -> MATCHES control
```

M0084 was recalled in control (score 1.02) but not in intervention
(score 0.0). The intervention blocked M0084's reinforcement, which
changed its state, which changed whether it gets recalled, which
changed the decision. Causal closure achieved.

**Score-only flips (43.5% — closure NOT achieved):**

The evidence base is the SAME (same memories recalled) but the scores
differ. Example (step 83):

```
Control:     no  (yes=6.200, no=6.383)
Intervention: yes (yes=6.200, no=5.954)
Missing from intervention: []
Added in intervention: []
Counterfactual: no memories to add/remove -> cannot restore
```

The same memories are recalled, but their scores differ (the no-voters
lost weight in the intervention). The simple counterfactual (add/remove
memories) cannot capture this because the evidence base is identical.
A more sophisticated counterfactual would need to restore the control's
SCORES, not just the memory set.

### Verdict: WEAK — 56.5% closure rate

MNEME's custody chain provides causal closure for 56.5% of flipped
decisions — the ones where the intervention changed WHICH memories were
recalled. For the remaining 43.5%, the intervention changed the SCORES
of the same memories, and the simple counterfactual cannot capture that.

### What MNEME adds

The custody chain converts the aggregate finding ("23 decisions
changed") into per-instance claims:

- "Step 77: decision flipped from yes to no because M0084 (vote=yes,
  score=1.02 in control) was not recalled in intervention. M0084's
  reinforcement was blocked during the intervention window. Without
  that block, M0084 would have been recalled and the decision would
  have been yes."

This is much stronger than "23 decisions changed." It's a specific,
falsifiable, per-instance causal claim with a counterfactual.

### Limitation

The 43.5% of flips without closure are score-only differences. The
intervention changed the scores of the same memories (via state
changes affecting the state multiplier), but not which memories were
recalled. A complete counterfactual would need to restore both the
memory set AND the scores, which requires a deeper state-level
counterfactual (not just evidence-base manipulation).

This is a property of the simple vote model, not necessarily of MNEME.
A more complex decision model might show different closure rates.

---

## Exp13: STIGMERGY — collective path dependence

### Question

Can a temporal perturbation applied to a single agent leave a
persistent trace in the collective memory after that agent has
returned to baseline?

### Design

Three agents (A, B, C) share one MinimalRaven engine (shared memory
field). Each agent has its own query stream and reinforces the top
result of its own queries, but the field (memories, states, STDP
links) is shared. During the intervention window (steps 40-80), agent
A's reinforcement is blocked AND its previously reinforced memories
are actively de-reinforced (set to NEUTRAL). Agents B and C reinforce
normally throughout. After the intervention, all agents reinforce
normally (washout, steps 80-120).

We compare B and C's recall trajectories to a control where no agent
was intervened on. If B/C's trajectories diverge from control after
washout, the intervention on A left a trace in the shared state that
affects B/C.

10 seeds, 100 memories, 120 queries per agent.

### Results

```
Agent A (intervened):
  During intervention:  set_diff=0.152
  Post-washout:        set_diff=0.178

Agent B (non-intervened, shared field):
  During intervention:  set_diff=0.155, nearest_diff=0.000
  Post-washout:        set_diff=0.172

Agent C (non-intervened, shared field):
  During intervention:  set_diff=0.152, nearest_diff=0.000
  Post-washout:        set_diff=0.166
```

### Verdict: SURVIVES — collective path dependence

The intervention on agent A left a trace in the shared memory field
that affects B and C's recall after washout. B and C were never
directly intervened on, but their recall trajectories diverge from
control by 17.2% and 16.6% post-washout — almost as much as A's own
divergence (17.8%).

The nearest-memory probe passes for B and C (0% nearest_diff) — the
top match is preserved, but the broader context changes.

### Why it works

The shared field means A's de-reinforcement changes the state of
memories that B and C also use. When A's memories are de-reinforced,
the shared state (REINFORCED/NEUTRAL) changes, which changes the
state multiplier in scoring, which changes which memories B and C
recall. The STDP links are also shared, so A's altered activation
patterns change the synaptic weights that affect B and C's
propagation.

The effect is almost as strong for B and C as for A because the
shared state is the dominant factor — the memories A de-reinforced
are the same memories B and C would have recalled.

### What this means

This is collective path dependence: a perturbation to one agent
propagated to others via the shared memory state, and the effect
persisted after the intervened agent returned to normal. The
Frankensteins ended up with different histories depending on what
one of them experienced.

The nearest-memory probe passes — the primary recall capability is
preserved. But the broader context (which memories beyond the top
match enter the result set) changes for all agents.

### Limitation

This used active de-reinforcement (setting memories to NEUTRAL),
which is a strong intervention. Mere blocking of new reinforcement
(diluted by B and C's ongoing reinforcement) produced no detectable
effect in a preliminary run. The collective effect requires a strong
enough intervention to overcome the dilution from other agents'
ongoing reinforcement.

The nearest-memory probe passes, so this is a context-composition
effect, not a primary-capability degradation. Whether the changed
context would flip downstream decisions for B and C was not tested
(separate experiment needed).
