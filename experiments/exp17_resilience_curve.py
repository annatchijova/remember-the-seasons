"""
Exp17: STIGMERGY — collective resilience curve.

Exp16 found that zeroing 1 agent's contributions out of 3 produces
near-zero divergence — the other agents' contributions keep memories
REINFORCED. This is collective resilience.

This experiment maps the resilience curve: how many agents need to be
intervened (as a fraction of total) before the effect appears?

  N agents × fraction-treated × dose

If there's a threshold, the collective memory amortizes perturbations
below it. Above it, the system tips.

This is the user's hypothesis:

  "¿La memoria colectiva amortigua perturbaciones individuales hasta
   superar un umbral crítico?"
"""
import sys
import numpy as np
import random
from typing import Dict, List

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT
from exp16_provenance import ProvenanceEngine, make_embedding, compare_traj


def run_resilience_arm(query_streams, intervened_agents, int_start, int_end,
                        seed=42):
    """Run with per-agent provenance. Zero contributions for all
    agents in intervened_agents list."""
    pe = ProvenanceEngine(seed=seed)
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
            recalled_scores = {r.memory.memory_id: round(r.final_score, 6)
                              for r in outcome.results}

            if recalled_ids:
                pe.reinforce(agent, recalled_ids[0])

            if prev_recalled[agent] and recalled_ids:
                pe.update_stdp(prev_recalled[agent], recalled_ids)

            pe.update_activations(recalled_ids, now)

            nearest = min(pe.memories.keys(),
                         key=lambda mid: abs(pe.memories[mid] - q_angle))

            trajectories[agent].append({
                "step": step,
                "recalled": recalled_ids,
                "scores": recalled_scores,
                "nearest_in_results": nearest in recalled_ids,
            })
            prev_recalled[agent] = recalled_ids

    return trajectories


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP17: STIGMERGY — collective resilience curve")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 80
seeds = list(range(5))

# Parametrize k_intervened DIRECTLY (not fractions that quantize silently)
configs = []
for n_agents in [2, 3, 5, 8, 10]:
    for k_int in range(n_agents + 1):
        configs.append((n_agents, k_int))

print(f"\n  Varying: N agents x k_intervened (direct, not fractions)")
print(f"  {n_queries} queries per agent, {len(seeds)} seeds")
print(f"  Intervention: steps {int_start}-{int_end}")
print(f"  Per-agent provenance (zero only intervened agents' contributions)")
print(f"  Configs: {len(configs)}")
print()

results = {}

for n_agents, k_int in configs:
    key = f"N={n_agents}, k={k_int}"
    total_int_div = 0.0
    total_non_div = 0.0
    total_non_near = 0.0
    n_non = n_agents - k_int

    for seed in seeds:
        query_streams = {}
        for a in range(n_agents):
            rng = random.Random(seed * 100 + a)
            query_streams[f"A{a}"] = [rng.uniform(0, 360) for _ in range(n_queries)]

        intervened = [f"A{i}" for i in range(k_int)]

        # Control
        control = run_resilience_arm(query_streams, [], 999, 999, seed=seed)
        # Intervention
        interv = run_resilience_arm(query_streams, intervened, int_start, int_end, seed=seed)

        # Measure divergence for intervened and non-intervened agents
        int_div = 0.0
        non_div = 0.0
        non_near = 0.0
        for agent in query_streams:
            d, near = compare_traj(control[agent], interv[agent], int_end, n_queries)
            if agent in intervened:
                int_div += d
            else:
                non_div += d
                non_near += near

        total_int_div += int_div / max(k_int, 1)
        if n_non > 0:
            total_non_div += non_div / n_non
            total_non_near += non_near / n_non

    n = len(seeds)
    results[key] = {
        "n_agents": n_agents,
        "k_int": k_int,
        "n_non": n_non,
        "int_div": total_int_div / n,
        "non_div": total_non_div / n,
        "non_near": total_non_near / n,
    }

# Print results
print("=" * 70)
print("RESULTS")
print("=" * 70)

print(f"\n{'N':>4} {'k':>4} {'n_non':>6} {'int_div':>10} {'non_div':>10} {'non_near':>10}")
print("-" * 44)
for key in sorted(results.keys(), key=lambda k: (results[k]["n_agents"], results[k]["k_int"])):
    r = results[key]
    print(f"{r['n_agents']:>4} {r['k_int']:>4} {r['n_non']:>6} "
          f"{r['int_div']:>10.4f} {r['non_div']:>10.4f} {r['non_near']:>10.4f}")

# Analysis
print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)

# For each N, find the threshold where non-intervened divergence appears
print("\n  Resilience surface R(N,k) — non-intervened divergence:")
for n_agents in [2, 3, 5, 8, 10]:
    vals = []
    for k in range(n_agents + 1):
        key = f"N={n_agents}, k={k}"
        vals.append(results[key]["non_div"])
    print(f"    N={n_agents}: " + " ".join(f"k={k}:{v:.4f}" for k, v in enumerate(vals)))

# Find threshold (first k where non_div > 0.01)
print("\n  Threshold (first k where non_div > 0.01):")
for n_agents in [2, 3, 5, 8, 10]:
    threshold_k = None
    for k in range(n_agents + 1):
        key = f"N={n_agents}, k={k}"
        if results[key]["non_div"] > 0.01:
            threshold_k = k
            break
    if threshold_k is not None:
        print(f"    N={n_agents}: threshold at k={threshold_k} ({threshold_k}/{n_agents} = {threshold_k/n_agents:.2f})")
    else:
        print(f"    N={n_agents}: no threshold found (all k tested)")

# Intervened agent divergence
print("\n  Intervened agent divergence:")
for n_agents in [2, 3, 5, 8, 10]:
    vals = []
    for k in range(n_agents + 1):
        key = f"N={n_agents}, k={k}"
        vals.append(results[key]["int_div"])
    print(f"    N={n_agents}: " + " ".join(f"k={k}:{v:.4f}" for k, v in enumerate(vals)))

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

# Find if there's a clear threshold
any_threshold = False
for n_agents in [2, 3, 5, 8, 10]:
    for k in range(1, n_agents):
        key = f"N={n_agents}, k={k}"
        r = results[key]
        if r["non_div"] > 0.01:
            any_threshold = True

if any_threshold:
    print(f"\n  SURVIVES — collective resilience with threshold.")
    print(f"  Below the threshold, non-intervened agents are unaffected.")
    print(f"  Above the threshold, the collective memory tips and")
    print(f"  non-intervened agents diverge.")
else:
    print(f"\n  RESILIENT — no stigmergic transmission at any k < N.")
    print(f"  The collective memory amortizes partial perturbations at all tested")
    print(f"  k values. Only intervening ALL agents produces full divergence.")
    print(f"\n  The intervened agents themselves show divergence, but it")
    print(f"  doesn't propagate to non-intervened agents via the shared")
    print(f"  field when per-agent provenance is used.")
