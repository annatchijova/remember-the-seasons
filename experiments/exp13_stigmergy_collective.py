"""
Exp13: STIGMERGY — collective path dependence.

The user's question:

  Agent A --\
  Agent B --+--> shared memory field
  Agent C --/
               |
       intervene only A
               |
               v
  Does A's altered history change what B/C later learn?
               |
               v
  washout A (A returns to normal reinforcement)
               |
               v
  Does collective state retain the intervention's history?

If a perturbation to one agent leaves a trace in the collective memory
that persists after that agent returns to baseline, we have collective
path dependence — not just individual memory dynamics.

Design: three agents share one MinimalRaven engine. Each agent has its
own query stream and reinforces the top result of its own queries, but
the field (memories, states, STDP links) is shared. During the
intervention window, agent A's reinforcement is blocked; B and C
reinforce normally. After the intervention, all agents reinforce
normally (washout).

We compare B and C's recall trajectories to a control where no agent
was intervened on. If B/C's trajectories diverge from control, the
intervention on A left a trace in the shared state that affects B/C.
"""
import sys
import numpy as np
import random
from typing import List, Dict, Tuple

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def build_shared_field(n_memories=100, dim=32, seed=42):
    eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                       recency_on=False, rescue_on=True,
                       auto_contradiction=False, k_neighbors=6)
    memories = {}
    for i in range(n_memories):
        angle = (i * 360.0 / n_memories) % 360
        mid = f"M{i:04d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim))

    half = n_memories // 2
    for i in range(half):
        eng.add_link(f"M{i:04d}", f"M{i+half:04d}", RESONANT)

    return eng, memories


def run_multi_agent_trajectory(query_streams, intervention_agent, intervention_start,
                                intervention_end, n_memories=100, dim=32, seed=42,
                                de_reinforce=True):
    """Run a multi-agent trajectory with a shared memory field.

    query_streams: dict of agent_id -> list of query angles
    intervention_agent: agent_id whose reinforcement is blocked during intervention
    de_reinforce: if True, actively de-reinforce the intervened agent's
                  previously reinforced memories during intervention
                  (stronger than just blocking new reinforcement)
    """
    eng, memories = build_shared_field(n_memories, dim, seed)
    n_steps = max(len(qs) for qs in query_streams.values())
    prev_recalled = {agent: None for agent in query_streams}
    trajectories = {agent: [] for agent in query_streams}
    # Track which memories each agent has reinforced
    agent_reinforced = {agent: set() for agent in query_streams}

    for step in range(n_steps):
        now = float(step)
        in_intervention = intervention_start <= step < intervention_end

        # Active de-reinforcement of the intervened agent's memories
        if in_intervention and de_reinforce and intervention_agent is not None:
            for mid in agent_reinforced[intervention_agent]:
                mem = eng.memories.get(mid)
                if mem and mem.state == State.REINFORCED:
                    mem.state = State.NEUTRAL

        # Each agent recalls in turn (shared field)
        for agent, queries in query_streams.items():
            if step >= len(queries):
                continue
            q_angle = queries[step]
            query = make_embedding(q_angle, dim)

            outcome = eng.recall_with_learning(
                query, top_k=10, now=now,
                current_turn_memories=prev_recalled[agent],
            )
            recalled_ids = [r.memory.memory_id for r in outcome.results]
            recalled_scores = {r.memory.memory_id: round(r.final_score, 6)
                              for r in outcome.results}

            # Reinforcement (with intervention blocking for one agent)
            should_reinforce = True
            if in_intervention and agent == intervention_agent:
                should_reinforce = False

            if recalled_ids and should_reinforce:
                eng.reinforce(recalled_ids[0])
                agent_reinforced[agent].add(recalled_ids[0])

            # STDP (per-agent, but links are shared)
            if prev_recalled[agent] and recalled_ids:
                eng.update_stdp(prev_recalled[agent], recalled_ids)

            eng.update_activations(recalled_ids, now)

            # Nearest memory
            nearest = min(memories.keys(),
                         key=lambda mid: abs(memories[mid] - q_angle))

            trajectories[agent].append({
                "step": step,
                "query_angle": q_angle,
                "recalled": recalled_ids,
                "scores": recalled_scores,
                "in_intervention": in_intervention,
                "nearest_in_results": nearest in recalled_ids,
                "reinforced": should_reinforce and bool(recalled_ids),
            })
            prev_recalled[agent] = recalled_ids

    return trajectories


def compare_trajectories(traj_a, traj_b, start, end):
    """Compare two trajectories over a range of steps."""
    set_diffs = []
    nearest_diffs = []
    for i in range(start, min(end, len(traj_a), len(traj_b))):
        a_set = set(traj_a[i]["recalled"])
        b_set = set(traj_b[i]["recalled"])
        set_diffs.append(len(a_set.symmetric_difference(b_set)) / 10.0)
        nearest_diffs.append(
            1.0 if traj_a[i]["nearest_in_results"] != traj_b[i]["nearest_in_results"] else 0.0
        )
    if not set_diffs:
        return 0.0, 0.0
    return sum(set_diffs) / len(set_diffs), sum(nearest_diffs) / len(nearest_diffs)


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP13: STIGMERGY — collective path dependence")
print("=" * 70)

n_queries = 120
intervention_start = 40
intervention_duration = 40
intervention_end = intervention_start + intervention_duration
seeds = list(range(10))

print(f"\n  3 agents (A, B, C) sharing one memory field")
print(f"  {n_queries} queries per agent")
print(f"  Intervention: agent A de-reinforced + blocked at steps {intervention_start}-{intervention_end}")
print(f"  Agents B and C reinforce normally throughout")
print(f"  Seeds: {len(seeds)}")
print()

# For each seed, run:
# 1. Control: no intervention on any agent
# 2. Intervention: block agent A only
# Compare B and C's trajectories between control and intervention

total_b_during = 0.0
total_b_washout = 0.0
total_c_during = 0.0
total_c_washout = 0.0
total_b_nearest = 0.0
total_c_nearest = 0.0
total_a_during = 0.0
total_a_washout = 0.0

n_seeds = len(seeds)

for seed in seeds:
    # Generate query streams for each agent
    rng_a = random.Random(seed * 3 + 0)
    rng_b = random.Random(seed * 3 + 1)
    rng_c = random.Random(seed * 3 + 2)

    query_streams = {
        "A": [rng_a.uniform(0, 360) for _ in range(n_queries)],
        "B": [rng_b.uniform(0, 360) for _ in range(n_queries)],
        "C": [rng_c.uniform(0, 360) for _ in range(n_queries)],
    }

    # Control: no intervention
    control_traj = run_multi_agent_trajectory(
        query_streams, intervention_agent=None,
        intervention_start=999, intervention_end=999,
        seed=seed)

    # Intervention: block agent A
    int_traj = run_multi_agent_trajectory(
        query_streams, intervention_agent="A",
        intervention_start=intervention_start, intervention_end=intervention_end,
        seed=seed)

    # Compare B and C between control and intervention
    b_during, b_near = compare_trajectories(
        control_traj["B"], int_traj["B"], intervention_start, intervention_end)
    b_washout, b_near_w = compare_trajectories(
        control_traj["B"], int_traj["B"], intervention_end, n_queries)

    c_during, c_near = compare_trajectories(
        control_traj["C"], int_traj["C"], intervention_start, intervention_end)
    c_washout, c_near_w = compare_trajectories(
        control_traj["C"], int_traj["C"], intervention_end, n_queries)

    a_during, _ = compare_trajectories(
        control_traj["A"], int_traj["A"], intervention_start, intervention_end)
    a_washout, _ = compare_trajectories(
        control_traj["A"], int_traj["A"], intervention_end, n_queries)

    total_b_during += b_during
    total_b_washout += b_washout
    total_c_during += c_during
    total_c_washout += c_washout
    total_b_nearest += (b_near + b_near_w) / 2
    total_c_nearest += (c_near + c_near_w) / 2
    total_a_during += a_during
    total_a_washout += a_washout

# Averages
avg_b_during = total_b_during / n_seeds
avg_b_washout = total_b_washout / n_seeds
avg_c_during = total_c_during / n_seeds
avg_c_washout = total_c_washout / n_seeds
avg_b_nearest = total_b_nearest / n_seeds
avg_c_nearest = total_c_nearest / n_seeds
avg_a_during = total_a_during / n_seeds
avg_a_washout = total_a_washout / n_seeds

print("=" * 70)
print("RESULTS")
print("=" * 70)

print(f"\n  Agent A (intervened):")
print(f"    During intervention:  set_diff={avg_a_during:.4f}")
print(f"    Post-washout:        set_diff={avg_a_washout:.4f}")

print(f"\n  Agent B (non-intervened, shared field):")
print(f"    During intervention:  set_diff={avg_b_during:.4f}, nearest_diff={avg_b_nearest:.4f}")
print(f"    Post-washout:        set_diff={avg_b_washout:.4f}")

print(f"\n  Agent C (non-intervened, shared field):")
print(f"    During intervention:  set_diff={avg_c_during:.4f}, nearest_diff={avg_c_nearest:.4f}")
print(f"    Post-washout:        set_diff={avg_c_washout:.4f}")

# Verdict
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

# The key question: does B/C diverge from control after washout?
# If yes, the intervention on A left a trace in the shared state
# that affects B/C even after A returns to normal.

if avg_b_washout > 0.02 or avg_c_washout > 0.02:
    print(f"  SURVIVES — collective path dependence detected.")
    print(f"  Agent A's intervention left a trace in the shared memory")
    print(f"  field that affects B and C's recall after washout.")
    print(f"  B washout set_diff: {avg_b_washout:.4f}")
    print(f"  C washout set_diff: {avg_c_washout:.4f}")
    print(f"  The perturbation to one agent propagated to others via")
    print(f"  the shared state (memory states, STDP links).")
elif avg_b_washout > 0.005 or avg_c_washout > 0.005:
    print(f"  WEAK — small collective effect detected.")
    print(f"  B washout set_diff: {avg_b_washout:.4f}")
    print(f"  C washout set_diff: {avg_c_washout:.4f}")
    print(f"  The effect is small but non-zero.")
else:
    print(f"  FALSIFIED — no collective path dependence.")
    print(f"  B washout set_diff: {avg_b_washout:.4f}")
    print(f"  C washout set_diff: {avg_c_washout:.4f}")
    print(f"  The intervention on A did not leave a detectable trace")
    print(f"  in B/C's recall after washout.")

# Also report A's own path dependence
print(f"\n  Agent A's own path dependence (for reference):")
print(f"    Post-washout set_diff: {avg_a_washout:.4f}")
print(f"    (This should be non-zero — A was directly intervened on)")
