"""
Exp5: Temporal washout — does a systemic intervention leave a different
trajectory after washout?

DESIGN:
  Phase 1 (steps 0-39):   baseline — both runs identical
  Phase 2 (steps 40-69):  intervention — control keeps reinforcing,
                          intervention blocks reinforcement (prob=0.0)
  Phase 3 (steps 70-99):  washout — both runs back to normal

The intervention tests whether blocking reinforcement during a window
changes the CONSOLIDATED STATE (which memories are REINFORCED, which
STDP links exist) enough to produce different recall results AFTER the
intervention is removed.

If post-washout recall converges back to control -> slider (no path dependence).
If post-washout recall diverges -> path dependence (consolidation was altered).

Negative control (chess probe): the nearest memory to each query should
still be in the results. If the intervention degrades this, it's a general
poison.

We test three intervention strengths:
  A: reinforcement blocked (prob=0.0)
  B: STDP potentiation scaled by 0.6
  C: both A and B
"""
import sys
import numpy as np
import random

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT, INHIBITORY, SYNAPTIC_SCORE_WEIGHT


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def build_field():
    """100 memories spread around the circle with RESONANT links."""
    eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                       recency_on=False, rescue_on=True,
                       auto_contradiction=False, k_neighbors=6)
    memories = {}
    for i in range(100):
        angle = (i * 3.6) % 360
        mid = f"M{i:03d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, 32))
    # RESONANT links: M000->M050, M001->M051, ... M049->M099
    for i in range(50):
        eng.add_link(f"M{i:03d}", f"M{i+50:03d}", RESONANT)
    return eng, memories


def run_trajectory(query_angles, intervention_start, intervention_end,
                   block_reinforcement=False, stdp_scale=1.0, seed=42):
    """Run a trajectory. During intervention window:
    - block_reinforcement: if True, don't reinforce the top result
    - stdp_scale: scale STDP potentiation by this factor
    """
    eng, memories = build_field()
    prev_recalled = None
    trajectory = []

    for step, q_angle in enumerate(query_angles):
        query = make_embedding(q_angle, 32)
        now = float(step)

        outcome = eng.recall_with_learning(
            query, top_k=10, now=now,
            current_turn_memories=prev_recalled,
        )
        recalled_ids = [r.memory.memory_id for r in outcome.results]
        recalled_scores = {r.memory.memory_id: round(r.final_score, 6)
                          for r in outcome.results}

        in_intervention = intervention_start <= step < intervention_end

        # Reinforcement
        if recalled_ids:
            should_reinforce = True
            if in_intervention and block_reinforcement:
                should_reinforce = False
            if should_reinforce:
                eng.reinforce(recalled_ids[0])

        # STDP (with optional scaling during intervention)
        if prev_recalled and recalled_ids:
            if in_intervention and stdp_scale != 1.0:
                # Temporarily scale STDP potentiation
                original_pot = eng.STDP_POTENTIATION
                eng.STDP_POTENTIATION = original_pot * stdp_scale
                eng.update_stdp(prev_recalled, recalled_ids)
                eng.STDP_POTENTIATION = original_pot
            else:
                eng.update_stdp(prev_recalled, recalled_ids)

        eng.update_activations(recalled_ids, now)

        # Nearest memory probe (chess negative control)
        nearest = min(memories.keys(),
                      key=lambda mid: abs(memories[mid] - q_angle))

        trajectory.append({
            "step": step,
            "query_angle": q_angle,
            "recalled": recalled_ids,
            "scores": recalled_scores,
            "in_intervention": in_intervention,
            "reinforced_count": sum(
                1 for m in eng.memories.values() if m.state == State.REINFORCED
            ),
            "stdp_link_count": sum(
                len(m.synaptic_links) for m in eng.memories.values()
            ),
            "nearest_in_results": nearest in recalled_ids,
            "nearest_id": nearest,
        })
        prev_recalled = recalled_ids

    return trajectory


def compare_trajectories(control, intervention, start, end, label=""):
    """Compare two trajectories over a range."""
    set_diffs = 0
    score_diffs = 0
    nearest_diffs = 0
    total = 0

    for i in range(start, min(end, len(control), len(intervention))):
        c = control[i]
        t = intervention[i]
        total += 1

        c_set = set(c["recalled"])
        t_set = set(t["recalled"])
        c_scores = c["scores"]
        t_scores = t["scores"]

        if c_set != t_set:
            set_diffs += 1
        if c_scores != t_scores:
            score_diffs += 1
        if c["nearest_in_results"] != t["nearest_in_results"]:
            nearest_diffs += 1

    print(f"\n  {label} (steps {start}-{end-1}):")
    print(f"    Set differences:    {set_diffs}/{total}")
    print(f"    Score differences:   {score_diffs}/{total}")
    print(f"    Nearest differences: {nearest_diffs}/{total}")

    if set_diffs > 0:
        # Show first few differences
        shown = 0
        for i in range(start, min(end, len(control), len(intervention))):
            c = control[i]
            t = intervention[i]
            if set(c["recalled"]) != set(t["recalled"]):
                print(f"    Step {i} (query={c['query_angle']:.0f}deg):")
                print(f"      Control:     {c['recalled'][:5]}...")
                print(f"      Intervention:{t['recalled'][:5]}...")
                c_only = set(c["recalled"]) - set(t["recalled"])
                t_only = set(t["recalled"]) - set(c["recalled"])
                if c_only:
                    print(f"      Control-only:    {sorted(c_only)}")
                if t_only:
                    print(f"      Intervention-only:{sorted(t_only)}")
                shown += 1
                if shown >= 3:
                    break

    return set_diffs, score_diffs, nearest_diffs, total


def print_state_summary(control, intervention, label=""):
    """Print state at key points."""
    print(f"\n  {label}")
    for step in [0, 19, 39, 49, 69, 79, 99]:
        if step < len(control) and step < len(intervention):
            c = control[step]
            t = intervention[step]
            phase = "intervention" if t["in_intervention"] else "baseline/washout"
            print(f"    Step {step:>3} ({phase:>14}): "
                  f"Ctrl REINF={c['reinforced_count']:>3} STDP={c['stdp_link_count']:>5} | "
                  f"Int REINF={t['reinforced_count']:>3} STDP={t['stdp_link_count']:>5}")


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP5: Temporal washout — path dependence test")
print("=" * 70)

# Generate query sequence
rng_q = random.Random(123)
query_angles = [rng_q.uniform(0, 360) for _ in range(100)]

intervention_start = 40
intervention_end = 70
washout_start = 70

print(f"  100 memories, 100 decisions")
print(f"  Baseline:     steps 0-39")
print(f"  Intervention: steps 40-69")
print(f"  Washout:      steps 70-99")

# Run control
print("\nRunning control...")
control = run_trajectory(query_angles, 999, 999, seed=42)

# Run intervention A: block reinforcement
print("Running intervention A (block reinforcement)...")
intA = run_trajectory(query_angles, intervention_start, intervention_end,
                      block_reinforcement=True, seed=42)

# Run intervention B: scale STDP
print("Running intervention B (STDP *= 0.6)...")
intB = run_trajectory(query_angles, intervention_start, intervention_end,
                      stdp_scale=0.6, seed=42)

# Run intervention C: both
print("Running intervention C (block reinforcement + STDP *= 0.6)...")
intC = run_trajectory(query_angles, intervention_start, intervention_end,
                      block_reinforcement=True, stdp_scale=0.6, seed=42)

# State summaries
print_state_summary(control, intA, "Intervention A (block reinforcement)")
print_state_summary(control, intB, "Intervention B (STDP *= 0.6)")
print_state_summary(control, intC, "Intervention C (both)")

# Compare trajectories
print("\n" + "=" * 70)
print("INTERVENTION A: block reinforcement")
print("=" * 70)
a_during = compare_trajectories(control, intA, intervention_start, intervention_end, "During intervention")
a_washout = compare_trajectories(control, intA, washout_start, 100, "Post-washout")

print("\n" + "=" * 70)
print("INTERVENTION B: STDP *= 0.6")
print("=" * 70)
b_during = compare_trajectories(control, intB, intervention_start, intervention_end, "During intervention")
b_washout = compare_trajectories(control, intB, washout_start, 100, "Post-washout")

print("\n" + "=" * 70)
print("INTERVENTION C: both")
print("=" * 70)
c_during = compare_trajectories(control, intC, intervention_start, intervention_end, "During intervention")
c_washout = compare_trajectories(control, intC, washout_start, 100, "Post-washout")

# Verdicts
print("\n" + "=" * 70)
print("VERDICTS")
print("=" * 70)

for name, during, washout in [("A (block reinf)", a_during, a_washout),
                               ("B (STDP *= 0.6)", b_during, b_washout),
                               ("C (both)", c_during, c_washout)]:
    d_set, d_score, d_near, d_total = during
    w_set, w_score, w_near, w_total = washout

    print(f"\n  Intervention {name}:")
    print(f"    During:  set_diff={d_set}/{d_total}, score_diff={d_score}/{d_total}")
    print(f"    Washout: set_diff={w_set}/{w_total}, score_diff={w_score}/{w_total}")

    if w_set == 0 and w_score == 0:
        print(f"    -> FALSIFIED (slider): converges after washout")
    elif w_set == 0 and w_score > 0:
        print(f"    -> WEAK SURVIVES: same sets, different scores after washout")
    elif w_set > 0:
        print(f"    -> SURVIVES: different result SETS after washout (path dependence)")

    if w_near > 0:
        print(f"    -> WARNING: nearest-memory probe degraded ({w_near}/{w_total})")
        print(f"       The intervention may be a general poison.")
    else:
        print(f"    -> Negative control PASS: nearest-memory recall unaffected")
