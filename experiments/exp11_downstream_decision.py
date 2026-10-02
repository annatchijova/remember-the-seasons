"""
Exp11: Downstream decision test.

If the intervention changes which memories are recalled but never changes
a DECISION, the effect is scientifically curious but operationally
irrelevant.

Design: model a simple "decision" that consumes recalled memories.
The decision: given a set of recalled memories, each with an associated
"vote" (a value), the decision is the weighted majority vote.

Each memory has a "vote" attribute (e.g., "yes" or "no" on some question).
The agent's decision = the majority vote among the top-k recalled memories,
weighted by their scores.

If the intervention changes the recalled set enough to flip a decision
(from "yes" to "no" or vice versa), the effect is operationally relevant.
If the recalled set changes but the decision is always the same, the
effect is scientifically curious but doesn't change behavior.

We run many decision points (queries) and count how often the decision
flips between control and intervention trajectories.
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


def build_field_with_votes(n_memories=100, dim=32, seed=42):
    """Build a field where each memory has a 'vote' attribute."""
    eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                       recency_on=False, rescue_on=True,
                       auto_contradiction=False, k_neighbors=6)
    memories = {}
    votes = {}
    rng = random.Random(seed)

    for i in range(n_memories):
        angle = (i * 360.0 / n_memories) % 360
        mid = f"M{i:04d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim))
        # Assign votes: 60% "yes", 40% "no" (not perfectly balanced,
        # so the decision depends on WHICH memories are recalled)
        votes[mid] = "yes" if rng.random() < 0.6 else "no"

    # RESONANT links
    half = n_memories // 2
    for i in range(half):
        eng.add_link(f"M{i:04d}", f"M{i+half:04d}", RESONANT)

    return eng, memories, votes


def make_decision(recalled_results, votes):
    """Weighted majority vote among recalled memories.

    Decision = "yes" if sum of yes-voters' scores > sum of no-voters' scores.
    Ties broken as "abstain".
    """
    yes_weight = 0.0
    no_weight = 0.0
    for r in recalled_results:
        vote = votes.get(r.memory.memory_id, "abstain")
        if vote == "yes":
            yes_weight += r.final_score
        elif vote == "no":
            no_weight += r.final_score

    if yes_weight > no_weight:
        return "yes"
    elif no_weight > yes_weight:
        return "no"
    else:
        return "abstain"


def run_decision_trajectory(query_angles, intervention_start, intervention_end,
                            block_reinforcement_prob=0.0,
                            n_memories=100, dim=32, seed=42):
    """Run a trajectory and record decisions at each step."""
    eng, memories, votes = build_field_with_votes(n_memories, dim, seed)
    prev_recalled = None
    trajectory = []
    rng = random.Random(seed * 7 + 1)

    for step, q_angle in enumerate(query_angles):
        query = make_embedding(q_angle, dim)
        now = float(step)

        outcome = eng.recall_with_learning(
            query, top_k=10, now=now,
            current_turn_memories=prev_recalled,
        )
        recalled_ids = [r.memory.memory_id for r in outcome.results]

        in_intervention = intervention_start <= step < intervention_end

        if recalled_ids:
            should_reinforce = True
            if in_intervention and rng.random() < block_reinforcement_prob:
                should_reinforce = False
            if should_reinforce:
                eng.reinforce(recalled_ids[0])

        if prev_recalled and recalled_ids:
            eng.update_stdp(prev_recalled, recalled_ids)
        eng.update_activations(recalled_ids, now)

        # Make a decision
        decision = make_decision(outcome.results, votes)

        trajectory.append({
            "step": step,
            "query_angle": q_angle,
            "recalled": recalled_ids,
            "decision": decision,
            "in_intervention": in_intervention,
        })
        prev_recalled = recalled_ids

    return trajectory


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP11: Downstream decision test")
print("=" * 70)

n_queries = 120
intervention_start = 40
intervention_duration = 30
intervention_end = intervention_start + intervention_duration
intensity = 1.0  # full block
seeds = list(range(20))

print(f"  {n_queries} queries, intervention at {intervention_start}-{intervention_end}")
print(f"  Intensity: {intensity} (full reinforcement block)")
print(f"  Seeds: {len(seeds)}")
print(f"  Decision: weighted majority vote (yes vs no) among top-10 recalled")
print()

# Run across seeds
total_decision_flips_during = 0
total_decision_flips_washout = 0
total_during_steps = 0
total_washout_steps = 0
total_abstain_during = 0
total_abstain_washout = 0

for seed in seeds:
    rng_q = random.Random(seed)
    query_angles = [rng_q.uniform(0, 360) for _ in range(n_queries)]

    control = run_decision_trajectory(
        query_angles, 999, 999,
        block_reinforcement_prob=0.0,
        n_memories=100, seed=seed,
    )
    intervention = run_decision_trajectory(
        query_angles, intervention_start, intervention_end,
        block_reinforcement_prob=intensity,
        n_memories=100, seed=seed,
    )

    for i in range(n_queries):
        c_dec = control[i]["decision"]
        t_dec = intervention[i]["decision"]

        if intervention_start <= i < intervention_end:
            total_during_steps += 1
            if c_dec != t_dec:
                total_decision_flips_during += 1
            if c_dec == "abstain" or t_dec == "abstain":
                total_abstain_during += 1
        elif i >= intervention_end:
            total_washout_steps += 1
            if c_dec != t_dec:
                total_decision_flips_washout += 1
            if c_dec == "abstain" or t_dec == "abstain":
                total_abstain_washout += 1

# Summary
print("=" * 70)
print("RESULTS")
print("=" * 70)

during_flip_rate = total_decision_flips_during / total_during_steps
washout_flip_rate = total_decision_flips_washout / total_washout_steps
during_abstain_rate = total_abstain_during / total_during_steps
washout_abstain_rate = total_abstain_washout / total_washout_steps

print(f"\n  During intervention ({total_during_steps} decision points):")
print(f"    Decision flips:     {total_decision_flips_during}/{total_during_steps} "
      f"({during_flip_rate:.3f})")
print(f"    Abstains:           {total_abstain_during}/{total_during_steps} "
      f"({during_abstain_rate:.3f})")

print(f"\n  Post-washout ({total_washout_steps} decision points):")
print(f"    Decision flips:     {total_decision_flips_washout}/{total_washout_steps} "
      f"({washout_flip_rate:.3f})")
print(f"    Abstains:           {total_abstain_washout}/{total_washout_steps} "
      f"({washout_abstain_rate:.3f})")

print(f"\n  Memory set divergence (from Exp5, for comparison):")
print(f"    The intervention produces ~20% set differences post-washout.")
print(f"    Decision flip rate: {washout_flip_rate:.3f}")

# Verdict
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

if washout_flip_rate > 0.05:
    print(f"  SURVIVES — {washout_flip_rate:.1%} of post-washout decisions flip.")
    print(f"  The memory change is operationally relevant: it changes")
    print(f"  what the agent would DO, not just what it recalls.")
elif washout_flip_rate > 0:
    print(f"  WEAK — {washout_flip_rate:.1%} of decisions flip.")
    print(f"  The effect rarely changes decisions but does occasionally.")
else:
    print(f"  FALSIFIED — no decision flips post-washout.")
    print(f"  The memory change is scientifically curious but")
    print(f"  operationally irrelevant: the agent would make the same")
    print(f"  decisions regardless of the intervention.")

if during_flip_rate > washout_flip_rate:
    print(f"\n  Note: during-intervention flip rate ({during_flip_rate:.3f}) > "
          f"washout ({washout_flip_rate:.3f}).")
    print(f"  The effect is stronger during intervention but persists after.")
