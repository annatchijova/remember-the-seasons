"""
Exp21: Reinforcement threshold sweep — is collective resilience
emergent or algebraic?

Exp17 found k* = N-1 (all but one agent intervened needed for
divergence). The user's question: is this an emergent collective
property, or just the algebraic consequence of the reinforcement
rule's threshold?

Current model (Exp16/17): a memory is REINFORCED if ANY agent
contributed (effective threshold T=1 on distinct contributors).

If we vary T (number of distinct contributors needed):
  T=1: need 1 contributor -> k* = N-1 (leave 1 non-intervened)
  T=2: need 2 contributors -> k* = N-2 (leave 2 non-intervened)
  T=3: need 3 contributors -> k* = N-3 (leave 3 non-intervened)

If k* = N-T holds, the "collective resilience" is algebraic.
If it deviates, something else is happening.

Uses the same ProvenanceEngine as Exp16/17 (from exp16_provenance).
"""
import sys
import numpy as np
import random
from typing import Dict, Set, List
from collections import defaultdict

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT
from exp16_provenance import make_embedding, compare_traj


class ThresholdEngine:
    """ProvenanceEngine with variable contribution threshold.

    A memory is REINFORCED if the number of DISTINCT agents that
    contributed to it is >= threshold.

    Intervention zeroes the intervened agents' contributions every
    step (same as Exp16/17).
    """

    def __init__(self, n_memories=100, dim=32, seed=42, threshold=1):
        self.eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                                 recency_on=False, rescue_on=True,
                                 auto_contradiction=False, k_neighbors=6)
        self.memories = {}
        for i in range(n_memories):
            angle = (i * 360.0 / n_memories) % 360
            mid = f"M{i:04d}"
            self.memories[mid] = angle
            self.eng.store(mid, make_embedding(angle, dim))
        half = n_memories // 2
        for i in range(half):
            self.eng.add_link(f"M{i:04d}", f"M{i+half:04d}", RESONANT)

        # Per-agent contributions: {mid: {agent: count}}
        self.contributions: Dict[str, Dict[str, float]] = {
            mid: {} for mid in self.memories
        }
        self.agents = []
        self.threshold = threshold

    def init_agent(self, agent_id):
        self.agents.append(agent_id)

    def get_effective_state(self, mid):
        """REINFORCED if >= threshold distinct agents contributed."""
        active = sum(1 for c in self.contributions[mid].values() if c > 0)
        return State.REINFORCED if active >= self.threshold else State.NEUTRAL

    def reinforce(self, agent, mid):
        self.contributions[mid][agent] = self.contributions[mid].get(agent, 0) + 1
        self.eng.memories[mid].state = self.get_effective_state(mid)

    def de_reinforce_agent(self, agent):
        """Zero ALL of this agent's contributions (every step during
        intervention). Does NOT touch other agents' contributions."""
        for mid in self.contributions:
            if agent in self.contributions[mid]:
                self.contributions[mid][agent] = 0
            self.eng.memories[mid].state = self.get_effective_state(mid)

    def recall(self, agent, query, top_k=10, now=0.0, prev_recalled=None):
        return self.eng.recall_with_learning(
            query, top_k=top_k, now=now,
            current_turn_memories=prev_recalled,
        )

    def update_stdp(self, prev_recalled, recalled_ids):
        self.eng.update_stdp(prev_recalled, recalled_ids)

    def update_activations(self, recalled_ids, now):
        self.eng.update_activations(recalled_ids, now)


def run_arm(query_streams, intervened_agents, int_start, int_end,
            seed=42, threshold=1):
    """Run with per-agent provenance and variable threshold.
    De-reinforce intervened agents EVERY step during intervention."""
    pe = ThresholdEngine(seed=seed, threshold=threshold)
    for agent in query_streams:
        pe.init_agent(agent)

    n_steps = max(len(qs) for qs in query_streams.values())
    prev_recalled = {a: None for a in query_streams}
    trajectories = {a: [] for a in query_streams}

    for step in range(n_steps):
        now = float(step)
        in_int = int_start <= step < int_end

        if in_int:
            for agent in intervened_agents:
                pe.de_reinforce_agent(agent)

        for agent, queries in query_streams.items():
            if step >= len(queries):
                continue
            q_angle = queries[step]
            query = make_embedding(q_angle, dim=32)

            outcome = pe.recall(agent, query, top_k=10, now=now,
                               prev_recalled=prev_recalled[agent])
            recalled_ids = [r.memory.memory_id for r in outcome.results]

            if recalled_ids:
                pe.reinforce(agent, recalled_ids[0])

            if prev_recalled[agent] and recalled_ids:
                pe.update_stdp(prev_recalled[agent], recalled_ids)

            pe.update_activations(recalled_ids, now)

            nearest = min(pe.memories.keys(),
                         key=lambda mid: abs(pe.memories[mid] - q_angle))

            trajectories[agent].append({
                "step": step, "recalled": recalled_ids,
                "nearest_in_results": nearest in recalled_ids,
            })
            prev_recalled[agent] = recalled_ids

    return trajectories


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP21: Reinforcement threshold sweep — emergent or algebraic?")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 80
seeds = list(range(5))

thresholds = [1, 2, 3]
n_agents_list = [3, 5, 8]

print(f"\n  Varying: threshold T x N agents x k_intervened")
print(f"  Thresholds: {thresholds} (distinct contributors needed)")
print(f"  N values: {n_agents_list}")
print(f"  {n_queries} queries per agent, {len(seeds)} seeds")
print(f"  Intervention: steps {int_start}-{int_end}")
print()

# Prediction: if algebraic, k* = N - T (need N-T intervened to leave
# <T non-intervened contributors)
print("  Prediction (algebraic): k* = N - T")
for T in thresholds:
    for N in n_agents_list:
        if N >= T:
            print(f"    T={T}, N={N}: predicted k* = {N-T} "
                  f"({N-T}/{N} = {(N-T)/N:.0%})")
print()

results = {}

for T in thresholds:
    for n_agents in n_agents_list:
        for k_int in range(1, n_agents + 1):
            n_non = n_agents - k_int
            if n_non == 0:
                continue

            key = f"T={T}, N={n_agents}, k={k_int}"
            total_non_div = 0.0
            total_non_near = 0.0

            for seed in seeds:
                query_streams = {}
                for a in range(n_agents):
                    rng = random.Random(seed * 100 + a)
                    query_streams[f"A{a}"] = [rng.uniform(0, 360)
                                              for _ in range(n_queries)]

                intervened = [f"A{i}" for i in range(k_int)]

                control = run_arm(query_streams, [], 999, 999,
                                  seed=seed, threshold=T)
                interv = run_arm(query_streams, intervened,
                                 int_start, int_end,
                                 seed=seed, threshold=T)

                non_div = 0.0
                non_near = 0.0
                for agent in query_streams:
                    if agent not in intervened:
                        d, near = compare_traj(control[agent], interv[agent],
                                               int_end, n_queries)
                        non_div += d
                        non_near += near

                total_non_div += non_div / n_non
                total_non_near += non_near / n_non

            results[key] = {
                "T": T, "N": n_agents, "k": k_int,
                "n_non": n_non,
                "non_div": total_non_div / len(seeds),
                "non_near": total_non_near / len(seeds),
            }

# Print results
print("=" * 70)
print("RESULTS")
print("=" * 70)

for T in thresholds:
    print(f"\n  T={T} (need {T} distinct contributor{'s' if T>1 else ''}):")
    print(f"    {'N':>4} {'k':>4} {'n_non':>6} {'non_div':>10}")
    print(f"    {'-'*26}")
    for n_agents in n_agents_list:
        for k_int in range(1, n_agents + 1):
            key = f"T={T}, N={n_agents}, k={k_int}"
            if key in results:
                r = results[key]
                print(f"    {r['N']:>4} {r['k']:>4} {r['n_non']:>6} "
                      f"{r['non_div']:>10.4f}")

# Analysis: does k* = N - T?
print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)

print("\n  Threshold (first k where non_div > 0.01):")
all_match = True
for T in thresholds:
    for n_agents in n_agents_list:
        if n_agents < T:
            continue
        threshold_k = None
        for k in range(1, n_agents + 1):
            key = f"T={T}, N={n_agents}, k={k}"
            if key in results and results[key]["non_div"] > 0.01:
                threshold_k = k
                break
        predicted = n_agents - T
        if threshold_k is not None:
            match = "MATCH" if threshold_k == predicted else "MISMATCH"
            if threshold_k != predicted:
                all_match = False
            print(f"    T={T}, N={n_agents}: observed k*={threshold_k}, "
                  f"predicted k*={predicted} ({match})")
        else:
            print(f"    T={T}, N={n_agents}: no threshold found "
                  f"(predicted k*={predicted})")
            all_match = False

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

if all_match:
    print(f"\n  ALGEBRAIC — the threshold follows k* = N - T exactly.")
    print(f"  The 'collective resilience' of Exp17 is NOT an emergent")
    print(f"  property. It is the algebraic consequence of the")
    print(f"  reinforcement threshold rule: a memory needs T distinct")
    print(f"  contributors to be REINFORCED, so you need N-T intervened")
    print(f"  agents to leave <T non-intervened contributors.")
    print(f"\n  This is not a failure — it's a derivation. We derived the")
    print(f"  resilience curve from the mechanism.")
else:
    print(f"\n  NOT PURELY ALGEBRAIC — some thresholds deviate from k*=N-T.")
    print(f"  The collective resilience is not fully explained by the")
    print(f"  reinforcement threshold rule. Something else is happening.")
