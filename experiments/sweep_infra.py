"""
Sweep infrastructure for Exp7-9 (statistical robustness, dose-response,
washout curve).

Shared runner: builds a field, runs control + intervention trajectories,
returns structured metrics. All three experiments call this with
different parameter sweeps.

Metrics returned per trajectory pair:
  - during_set_diff: fraction of steps with different result SETS during intervention
  - washout_set_diff: fraction of steps with different result SETS after washout
  - during_score_diff: fraction with different scores during
  - washout_score_diff: fraction with different scores after
  - nearest_diff: fraction where nearest-memory probe differs (negative control)
  - reinf_gap: |control_reinforced - intervention_reinforced| at end
  - stdp_gap: |control_stdp - intervention_stdp| at end
  - washout_curve: set_diff per step after washout (for decay analysis)
"""
import sys
import numpy as np
import random
from typing import List, Dict, Any, Tuple

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT, INHIBITORY, SYNAPTIC_SCORE_WEIGHT


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def build_field(n_memories=100, n_resonant_links=50, dim=32, seed=42):
    """Build a field with n_memories spread around the circle."""
    eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                       recency_on=False, rescue_on=True,
                       auto_contradiction=False, k_neighbors=6)
    memories = {}
    for i in range(n_memories):
        angle = (i * 360.0 / n_memories) % 360
        mid = f"M{i:04d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim))
    # RESONANT links: first half -> second half
    half = n_memories // 2
    n_links = min(n_resonant_links, half)
    for i in range(n_links):
        eng.add_link(f"M{i:04d}", f"M{i+half:04d}", RESONANT)
    return eng, memories


def generate_queries(n_queries, distribution, seed):
    """Generate query angles according to a distribution type."""
    rng = random.Random(seed)
    if distribution == "uniform":
        return [rng.uniform(0, 360) for _ in range(n_queries)]
    elif distribution == "clustered":
        # 3 clusters at 0, 120, 240 degrees with noise
        centers = [0, 120, 240]
        queries = []
        for _ in range(n_queries):
            c = rng.choice(centers)
            queries.append(c + rng.gauss(0, 15))
        return queries
    elif distribution == "biased":
        # 70% of queries near 0 degrees, 30% spread
        queries = []
        for _ in range(n_queries):
            if rng.random() < 0.7:
                queries.append(rng.gauss(0, 20))
            else:
                queries.append(rng.uniform(0, 360))
        return queries
    else:
        return [rng.uniform(0, 360) for _ in range(n_queries)]


def run_trajectory(query_angles, intervention_start, intervention_end,
                   block_reinforcement_prob=0.0, stdp_scale=1.0,
                   n_memories=100, n_resonant_links=50, dim=32, seed=42):
    """Run a single trajectory. During intervention window:
    - block_reinforcement_prob: probability of NOT reinforcing the top result
      (0.0 = always reinforce, 1.0 = never reinforce)
    - stdp_scale: scale STDP potentiation by this factor
    """
    eng, memories = build_field(n_memories, n_resonant_links, dim, seed)
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
        recalled_scores = {r.memory.memory_id: round(r.final_score, 6)
                          for r in outcome.results}

        in_intervention = intervention_start <= step < intervention_end

        # Reinforcement
        if recalled_ids:
            should_reinforce = True
            if in_intervention:
                # block_reinforcement_prob = probability of NOT reinforcing
                if rng.random() < block_reinforcement_prob:
                    should_reinforce = False
            if should_reinforce:
                eng.reinforce(recalled_ids[0])

        # STDP
        if prev_recalled and recalled_ids:
            if in_intervention and stdp_scale != 1.0:
                original_pot = eng.STDP_POTENTIATION
                eng.STDP_POTENTIATION = original_pot * stdp_scale
                eng.update_stdp(prev_recalled, recalled_ids)
                eng.STDP_POTENTIATION = original_pot
            else:
                eng.update_stdp(prev_recalled, recalled_ids)

        eng.update_activations(recalled_ids, now)

        nearest = min(memories.keys(),
                      key=lambda mid: abs(memories[mid] - q_angle))

        trajectory.append({
            "step": step,
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
        })
        prev_recalled = recalled_ids

    return trajectory


def compare_trajectories(control, intervention, start, end):
    """Compare two trajectories over a range. Returns metrics."""
    set_diffs = 0
    score_diffs = 0
    nearest_diffs = 0
    total = 0
    per_step_set_diff = []

    for i in range(start, min(end, len(control), len(intervention))):
        c = control[i]
        t = intervention[i]
        total += 1

        c_set = set(c["recalled"])
        t_set = set(t["recalled"])
        c_scores = c["scores"]
        t_scores = t["scores"]

        sd = 1 if c_set != t_set else 0
        scd = 1 if c_scores != t_scores else 0
        nd = 1 if c["nearest_in_results"] != t["nearest_in_results"] else 0

        set_diffs += sd
        score_diffs += scd
        nearest_diffs += nd
        per_step_set_diff.append(sd)

    return {
        "set_diff_frac": set_diffs / total if total > 0 else 0.0,
        "score_diff_frac": score_diffs / total if total > 0 else 0.0,
        "nearest_diff_frac": nearest_diffs / total if total > 0 else 0.0,
        "total_steps": total,
        "per_step_set_diff": per_step_set_diff,
    }


def run_pair(query_angles, intervention_start, intervention_end,
              block_reinforcement_prob, stdp_scale,
              n_memories=100, n_resonant_links=50, dim=32, seed=42):
    """Run a control + intervention pair and return all metrics."""
    control = run_trajectory(
        query_angles, 999, 999,
        block_reinforcement_prob=0.0, stdp_scale=1.0,
        n_memories=n_memories, n_resonant_links=n_resonant_links,
        dim=dim, seed=seed,
    )
    intervention = run_trajectory(
        query_angles, intervention_start, intervention_end,
        block_reinforcement_prob=block_reinforcement_prob,
        stdp_scale=stdp_scale,
        n_memories=n_memories, n_resonant_links=n_resonant_links,
        dim=dim, seed=seed,
    )

    during = compare_trajectories(control, intervention,
                                   intervention_start, intervention_end)
    washout = compare_trajectories(control, intervention,
                                    intervention_end, len(query_angles))

    # Final state gap
    c_final = control[-1]
    t_final = intervention[-1]

    return {
        "during_set_diff": during["set_diff_frac"],
        "during_score_diff": during["score_diff_frac"],
        "during_nearest_diff": during["nearest_diff_frac"],
        "washout_set_diff": washout["set_diff_frac"],
        "washout_score_diff": washout["score_diff_frac"],
        "washout_nearest_diff": washout["nearest_diff_frac"],
        "washout_curve": washout["per_step_set_diff"],
        "reinf_gap": abs(c_final["reinforced_count"] - t_final["reinforced_count"]),
        "stdp_gap": abs(c_final["stdp_link_count"] - t_final["stdp_link_count"]),
        "control_reinf_final": c_final["reinforced_count"],
        "intervention_reinf_final": t_final["reinforced_count"],
    }
