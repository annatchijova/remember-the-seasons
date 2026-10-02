"""
Exp22: Per-memory contributor topology — is the T=3 residual
derivable from topology?

Exp21 found k* = N-T for T=1,2 but mismatches for T=3. The user's
hypothesis: the deviation comes from heterogeneous per-memory
contributor topology, not from any emergent collective dynamics.

The aggregate model assumes every memory has all N agents as
potential contributors. But the real topology is sparse: each memory
has c_m contributors, and a memory flips iff |C_m ∩ I| > c_m - T
(more than c_m - T of its contributors are intervened).

This experiment decomposes the aggregate curve into per-memory
predictions:

  For each memory m:
    contributor_set_before (C_m at intervention onset)
    intervened_contributors (C_m ∩ I)
    contributor_count_after (|C_m \ I|)
    predicted_state_transition (|C_m \ I| < T)
    observed_state_transition (actual state at end of intervention)
    predicted recall consequence (does m leave top-10?)
    observed recall consequence

If per-memory topology + threshold rule predicts the aggregate
divergence curve, the "collective resilience" residual is fully
derivable — not emergent at all.

Also tests the user's correction: k* is the empirical threshold
(first k where non_div > 0.01), NOT the literal algebraic transition
point. A memory contributed by ALL N agents needs k=N to flip at
T=1. The observed k*=N-1 means the flipped memories are those whose
contributor sets are entirely within the intervened set.
"""
import sys
import numpy as np
import random
import copy
from typing import Dict, Set, List
from collections import defaultdict

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT
from exp16_provenance import make_embedding, compare_traj


class ThresholdEngine:
    """ProvenanceEngine with variable contribution threshold.
    Same as Exp21."""

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

        self.contributions: Dict[str, Dict[str, float]] = {
            mid: {} for mid in self.memories
        }
        self.agents = []
        self.threshold = threshold

    def init_agent(self, agent_id):
        self.agents.append(agent_id)

    def get_effective_state(self, mid):
        active = sum(1 for c in self.contributions[mid].values() if c > 0)
        return State.REINFORCED if active >= self.threshold else State.NEUTRAL

    def reinforce(self, agent, mid):
        self.contributions[mid][agent] = self.contributions[mid].get(agent, 0) + 1
        self.eng.memories[mid].state = self.get_effective_state(mid)

    def de_reinforce_agent(self, agent):
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

    def contributor_snapshot(self):
        """Deep copy of contributor sets (agent -> count, count>0 only)."""
        return {mid: {a: c for a, c in contrib.items() if c > 0}
                for mid, contrib in self.contributions.items()}


def run_arm(query_streams, intervened_agents, int_start, int_end,
            seed=42, threshold=1, snapshot_at=None):
    """Run with per-agent provenance. Returns trajectories + engine +
    contributor snapshots at specified steps."""
    pe = ThresholdEngine(seed=seed, threshold=threshold)
    for agent in query_streams:
        pe.init_agent(agent)

    n_steps = max(len(qs) for qs in query_streams.values())
    prev_recalled = {a: None for a in query_streams}
    trajectories = {a: [] for a in query_streams}
    snapshots = {}

    for step in range(n_steps):
        now = float(step)
        in_int = int_start <= step < int_end

        if in_int:
            for agent in intervened_agents:
                pe.de_reinforce_agent(agent)

        if snapshot_at and step in snapshot_at:
            snapshots[step] = pe.contributor_snapshot()

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

    return trajectories, pe, snapshots


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP22: Per-memory contributor topology — derivable or emergent?")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 80
seeds = list(range(5))

# Focus on T=3 mismatches from Exp21, plus T=1,2 for comparison
thresholds = [1, 2, 3]
n_agents_list = [3, 5, 8]

print(f"\n  Per-memory decomposition: contributor sets -> predicted flips")
print(f"  Thresholds: {thresholds}, N values: {n_agents_list}")
print(f"  {n_queries} queries, {len(seeds)} seeds")
print(f"  Intervention: steps {int_start}-{int_end}")
print()

results = []

for T in thresholds:
    for n_agents in n_agents_list:
        for seed in seeds:
            # Generate query streams
            query_streams = {}
            for a in range(n_agents):
                rng = random.Random(seed * 100 + a)
                query_streams[f"A{a}"] = [rng.uniform(0, 360)
                                          for _ in range(n_queries)]

            # Control arm: snapshot contributors at step 40 and 80
            ctrl_traj, ctrl_eng, ctrl_snaps = run_arm(
                query_streams, [], 999, 999,
                seed=seed, threshold=T,
                snapshot_at={int_start - 1, int_end - 1})

            # Step-40 contributor topology (same in both arms)
            C40 = ctrl_snaps[int_start - 1]

            # Contributor count distribution at step 40
            c_counts = [len(v) for v in C40.values()]
            c_dist = {}
            for c in c_counts:
                c_dist[c] = c_dist.get(c, 0) + 1

            # For each k, predict flips from topology
            for k_int in range(1, n_agents):
                I_k = {f"A{i}" for i in range(k_int)}
                n_non = n_agents - k_int

                # Predicted flips: memories REINFORCED at step 40 that
                # would go NEUTRAL with I_k removed
                F_pred = set()
                for mid, contrib in C40.items():
                    c_m = len(contrib)
                    if c_m >= T:  # was REINFORCED
                        remaining = c_m - len(set(contrib.keys()) & I_k)
                        if remaining < T:
                            F_pred.add(mid)

                # Predicted recall divergence: replay post-washout queries
                # with predicted states vs control states
                pred_divs = []
                for agent_id in query_streams:
                    if agent_id in I_k:
                        continue
                    queries = query_streams[agent_id]
                    for step in range(int_end, min(len(queries), n_queries)):
                        q = make_embedding(queries[step], dim=32)
                        ctrl_ids = set(ctrl_traj[agent_id][step]["recalled"])

                        # Save current states, apply predicted flips
                        saved = {mid: ctrl_eng.eng.memories[mid].state
                                 for mid in ctrl_eng.eng.memories}
                        for mid in F_pred:
                            if mid in ctrl_eng.eng.memories:
                                ctrl_eng.eng.memories[mid].state = State.NEUTRAL

                        pred_outcome = ctrl_eng.eng.recall(q, top_k=10)
                        pred_ids = set(r.memory.memory_id
                                       for r in pred_outcome.results)

                        # Restore
                        for mid, s in saved.items():
                            ctrl_eng.eng.memories[mid].state = s

                        pred_divs.append(len(ctrl_ids ^ pred_ids) / 10.0)

                pred_non_div = np.mean(pred_divs) if pred_divs else 0.0

                # Run actual intervention arm
                int_traj, int_eng, int_snaps = run_arm(
                    query_streams, list(I_k), int_start, int_end,
                    seed=seed, threshold=T,
                    snapshot_at={int_end - 1})

                # Observed non-intervened divergence
                obs_divs = []
                for agent_id in query_streams:
                    if agent_id in I_k:
                        continue
                    d, _ = compare_traj(ctrl_traj[agent_id],
                                       int_traj[agent_id],
                                       int_end, n_queries)
                    obs_divs.append(d)
                obs_non_div = np.mean(obs_divs) if obs_divs else 0.0

                # Observed flips at end of intervention
                C80_ctrl = ctrl_snaps[int_end - 1]
                C80_int = int_snaps[int_end - 1]
                F_obs = set()
                for mid in C80_ctrl:
                    ctrl_state = (State.REINFORCED if
                                  len(C80_ctrl.get(mid, {})) >= T
                                  else State.NEUTRAL)
                    int_contrib = C80_int.get(mid, {})
                    int_state = (State.REINFORCED if
                                 len(int_contrib) >= T
                                 else State.NEUTRAL)
                    if ctrl_state == State.REINFORCED and int_state == State.NEUTRAL:
                        F_obs.add(mid)

                results.append({
                    "T": T, "N": n_agents, "k": k_int, "seed": seed,
                    "n_non": n_non,
                    "F_pred": len(F_pred),
                    "F_obs": len(F_obs),
                    "F_overlap": len(F_pred & F_obs),
                    "pred_non_div": pred_non_div,
                    "obs_non_div": obs_non_div,
                    "c_dist": c_dist,
                })

# Print results
print("=" * 70)
print("RESULTS")
print("=" * 70)

# Per-memory flip prediction accuracy
print("\n  Per-memory flip prediction (F_pred vs F_obs):")
print(f"    {'T':>3} {'N':>4} {'k':>4} {'F_pred':>8} {'F_obs':>8} {'overlap':>8}")
print(f"    {'-'*36}")
for T in thresholds:
    for n_agents in n_agents_list:
        for k_int in range(1, n_agents):
            subset = [r for r in results
                      if r["T"] == T and r["N"] == n_agents and r["k"] == k_int]
            if subset:
                fp = np.mean([r["F_pred"] for r in subset])
                fo = np.mean([r["F_obs"] for r in subset])
                ov = np.mean([r["F_overlap"] for r in subset])
                print(f"    {T:>3} {n_agents:>4} {k_int:>4} {fp:>8.1f} "
                      f"{fo:>8.1f} {ov:>8.1f}")

# Contributor distribution at step 40
print("\n  Contributor count distribution at step 40 (first seed):")
for T in thresholds:
    for n_agents in n_agents_list:
        subset = [r for r in results
                  if r["T"] == T and r["N"] == n_agents and r["seed"] == 0]
        if subset:
            print(f"    T={T}, N={n_agents}: {subset[0]['c_dist']}")

# Predicted vs observed divergence
print("\n  Predicted vs observed non-intervened divergence:")
print(f"    {'T':>3} {'N':>4} {'k':>4} {'pred_div':>10} {'obs_div':>10} {'ratio':>8}")
print(f"    {'-'*40}")
for T in thresholds:
    for n_agents in n_agents_list:
        for k_int in range(1, n_agents):
            subset = [r for r in results
                      if r["T"] == T and r["N"] == n_agents and r["k"] == k_int]
            if subset:
                pd_ = np.mean([r["pred_non_div"] for r in subset])
                od_ = np.mean([r["obs_non_div"] for r in subset])
                ratio = pd_ / od_ if od_ > 0.001 else (1.0 if pd_ < 0.001 else 999)
                print(f"    {T:>3} {n_agents:>4} {k_int:>4} {pd_:>10.4f} "
                      f"{od_:>10.4f} {ratio:>8.2f}")

# Analysis: does topology explain the T=3 residual?
print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)

# For T=3, check if predicted divergence tracks observed
print("\n  T=3 detailed breakdown:")
for n_agents in n_agents_list:
    for k_int in range(1, n_agents):
        subset = [r for r in results
                  if r["T"] == 3 and r["N"] == n_agents and r["k"] == k_int]
        if subset:
            for r in subset:
                print(f"    N={n_agents}, k={k_int}, seed={r['seed']}: "
                      f"F_pred={r['F_pred']}, F_obs={r['F_obs']}, "
                      f"pred={r['pred_non_div']:.4f}, obs={r['obs_non_div']:.4f}")

# Check if per-memory flip prediction is accurate
print("\n  Flip prediction accuracy:")
total_pred = 0
total_obs = 0
total_overlap = 0
for r in results:
    total_pred += r["F_pred"]
    total_obs += r["F_obs"]
    total_overlap += r["F_overlap"]
if total_obs > 0:
    precision = total_overlap / max(total_pred, 1)
    recall = total_overlap / total_obs
    print(f"    Total F_pred={total_pred}, F_obs={total_obs}, "
          f"overlap={total_overlap}")
    print(f"    Precision={precision:.3f}, Recall={recall:.3f}")

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

# Compute how well predicted tracks observed
if total_obs > 0:
    # Check if predicted k* matches observed k* for each (T,N)
    matches = 0
    total_configs = 0
    for T in thresholds:
        for n_agents in n_agents_list:
            pred_k = None
            obs_k = None
            for k_int in range(1, n_agents):
                subset = [r for r in results
                          if r["T"] == T and r["N"] == n_agents
                          and r["k"] == k_int]
                if subset:
                    if np.mean([r["pred_non_div"] for r in subset]) > 0.01 and pred_k is None:
                        pred_k = k_int
                    if np.mean([r["obs_non_div"] for r in subset]) > 0.01 and obs_k is None:
                        obs_k = k_int
            total_configs += 1
            if pred_k == obs_k:
                matches += 1

    print(f"\n  Threshold prediction accuracy: {matches}/{total_configs}")
    print(f"  (predicted k* from topology vs observed k*)")

    if matches >= total_configs * 0.8:
        print(f"\n  DERIVABLE — per-memory contributor topology + threshold")
        print(f"  rule predicts the aggregate divergence curve.")
        print(f"  The 'collective resilience' is fully derivable from")
        print(f"  the reinforcement rule and contributor topology.")
        print(f"  No emergent collective dynamics needed.")
    elif matches >= total_configs * 0.5:
        print(f"\n  PARTIALLY DERIVABLE — topology explains most of the")
        print(f"  divergence but not all. Some residual remains.")
    else:
        print(f"\n  NOT DERIVABLE — per-memory topology alone does not")
        print(f"  predict the aggregate curve. Something else contributes.")
else:
    print(f"\n  No observed flips to analyze.")
