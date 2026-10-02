"""
Exp15: STIGMERGY — factorial decomposition.

Exp13 changed TWO variables at once (blocking -> blocking + de-reinforce,
AND duration 30 -> 40). This experiment disentangles them.

Factorial arms:

| Arm           | Block | De-reinf | Duration | STDP shared | State shared |
|---------------|-------|----------|----------|-------------|--------------|
| C (control)   | no    | no       | 40       | yes         | yes          |
| A (block)     | yes   | no       | 40       | yes         | yes          |
| B (de-reinf)  | no    | yes      | 40       | yes         | yes          |
| AB (both)     | yes   | yes      | 40       | yes         | yes          |
| AB-short      | yes   | yes      | 30       | yes         | yes          |
| AB-noSTDP     | yes   | yes      | 40       | no          | yes          |
| AB-private    | yes   | yes      | 40       | yes         | no           |

AB-noSTDP: STDP links are NOT shared (each agent has its own STDP).
AB-private: reinforcement state is NOT shared (each agent has its own
            REINFORCED/NEUTRAL states).

The key question: what transports the perturbation from A to B/C?
  - shared reinforcement state?
  - shared STDP?
  - both?
  - duration?
  - interaction?
"""
import sys
import numpy as np
import random
from typing import List, Dict, Set, Tuple

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def build_shared_field(n_memories=100, dim=32, seed=42,
                        shared_state=True, shared_stdp=True):
    """Build a shared field. If shared_state=False, each agent gets its
    own copy of memory states. If shared_stdp=False, each agent gets its
    own copy of STDP links."""
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


class MultiAgentEngine:
    """Wraps MinimalRaven for multi-agent experiments with configurable
    sharing of state and STDP."""

    def __init__(self, n_memories=100, dim=32, seed=42,
                 shared_state=True, shared_stdp=True):
        self.eng, self.memories = build_shared_field(n_memories, dim, seed)
        self.shared_state = shared_state
        self.shared_stdp = shared_stdp
        self.n_memories = n_memories

        # Per-agent state copies (used when not shared)
        self.agent_states = {}  # agent -> {mid: State}
        self.agent_stdp = {}     # agent -> {mid: {target_mid: weight}}
        self.agent_activations = {}  # agent -> {mid: last_activation}

    def init_agent(self, agent_id):
        """Initialize per-agent state copies."""
        self.agent_states[agent_id] = {}
        self.agent_stdp[agent_id] = {}
        self.agent_activations[agent_id] = {}
        for mid in self.memories:
            self.agent_states[agent_id][mid] = State.NEUTRAL
            self.agent_stdp[agent_id][mid] = {}
            self.agent_activations[agent_id][mid] = 0.0

    def get_state(self, agent_id, mid):
        if self.shared_state:
            return self.eng.memories[mid].state
        return self.agent_states[agent_id].get(mid, State.NEUTRAL)

    def set_state(self, agent_id, mid, state):
        if self.shared_state:
            self.eng.memories[mid].state = state
        else:
            self.agent_states[agent_id][mid] = state

    def get_stdp(self, agent_id, mid):
        if self.shared_stdp:
            return self.eng.memories[mid].synaptic_links
        return self.agent_stdp[agent_id].get(mid, {})

    def recall(self, agent_id, query, top_k=10, now=0.0, prev_recalled=None):
        """Recall with per-agent state/STDP if not shared."""
        # Temporarily apply this agent's state/STDP to the engine
        if not self.shared_state:
            for mid, state in self.agent_states[agent_id].items():
                self.eng.memories[mid].state = state
        if not self.shared_stdp:
            for mid, links in self.agent_stdp[agent_id].items():
                self.eng.memories[mid].synaptic_links = dict(links)

        outcome = self.eng.recall_with_learning(
            query, top_k=top_k, now=now,
            current_turn_memories=prev_recalled,
        )

        # Save back per-agent state/STDP if not shared
        if not self.shared_state:
            for mid in self.memories:
                self.agent_states[agent_id][mid] = self.eng.memories[mid].state
        if not self.shared_stdp:
            for mid in self.memories:
                self.agent_stdp[agent_id][mid] = dict(self.eng.memories[mid].synaptic_links)

        return outcome

    def reinforce(self, agent_id, mid):
        self.set_state(agent_id, mid, State.REINFORCED)

    def update_stdp(self, agent_id, prev_recalled, recalled_ids):
        if self.shared_stdp:
            self.eng.update_stdp(prev_recalled, recalled_ids)
        else:
            # Per-agent STDP
            for pre_id in prev_recalled:
                for post_id in recalled_ids:
                    if pre_id == post_id:
                        continue
                    links = self.agent_stdp[agent_id].setdefault(pre_id, {})
                    links[post_id] = min(links.get(post_id, 0.0) + 0.10, 2.0)

    def update_activations(self, agent_id, recalled_ids, now):
        if self.shared_state:
            self.eng.update_activations(recalled_ids, now)
        else:
            for mid in recalled_ids:
                self.agent_activations[agent_id][mid] = now


def run_arm(query_streams, intervention_agent, int_start, int_end,
            block, de_reinforce, shared_state=True, shared_stdp=True,
            n_memories=100, dim=32, seed=42):
    """Run one factorial arm."""
    mae = MultiAgentEngine(n_memories, dim, seed, shared_state, shared_stdp)
    for agent in query_streams:
        mae.init_agent(agent)

    n_steps = max(len(qs) for qs in query_streams.values())
    prev_recalled = {a: None for a in query_streams}
    trajectories = {a: [] for a in query_streams}
    agent_reinforced = {a: set() for a in query_streams}

    for step in range(n_steps):
        now = float(step)
        in_int = int_start <= step < int_end

        # De-reinforcement
        if in_int and de_reinforce and intervention_agent is not None:
            for mid in agent_reinforced[intervention_agent]:
                if mae.get_state(intervention_agent, mid) == State.REINFORCED:
                    mae.set_state(intervention_agent, mid, State.NEUTRAL)

        for agent, queries in query_streams.items():
            if step >= len(queries):
                continue
            q_angle = queries[step]
            query = make_embedding(q_angle, dim)

            outcome = mae.recall(agent, query, top_k=10, now=now,
                                prev_recalled=prev_recalled[agent])
            recalled_ids = [r.memory.memory_id for r in outcome.results]
            recalled_scores = {r.memory.memory_id: round(r.final_score, 6)
                              for r in outcome.results}

            should_reinforce = True
            if in_int and block and agent == intervention_agent:
                should_reinforce = False

            if recalled_ids and should_reinforce:
                mae.reinforce(agent, recalled_ids[0])
                agent_reinforced[agent].add(recalled_ids[0])

            if prev_recalled[agent] and recalled_ids:
                mae.update_stdp(agent, prev_recalled[agent], recalled_ids)

            mae.update_activations(agent, recalled_ids, now)

            nearest = min(mae.memories.keys(),
                         key=lambda mid: abs(mae.memories[mid] - q_angle))

            trajectories[agent].append({
                "step": step,
                "recalled": recalled_ids,
                "scores": recalled_scores,
                "nearest_in_results": nearest in recalled_ids,
            })
            prev_recalled[agent] = recalled_ids

    return trajectories


def compare_traj(ta, tb, start, end):
    set_diffs = []
    nearest_diffs = []
    for i in range(start, min(end, len(ta), len(tb))):
        a_set = set(ta[i]["recalled"])
        b_set = set(tb[i]["recalled"])
        set_diffs.append(len(a_set.symmetric_difference(b_set)) / 10.0)
        nearest_diffs.append(
            1.0 if ta[i]["nearest_in_results"] != tb[i]["nearest_in_results"] else 0.0)
    if not set_diffs:
        return 0.0, 0.0
    return sum(set_diffs) / len(set_diffs), sum(nearest_diffs) / len(nearest_diffs)


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP15: STIGMERGY — factorial decomposition")
print("=" * 70)

n_queries = 120
seeds = list(range(5))

arms = {
    "C (control)":       dict(block=False, de_reinf=False, dur=40,
                              shared_state=True, shared_stdp=True),
    "A (block only)":    dict(block=True,  de_reinf=False, dur=40,
                              shared_state=True, shared_stdp=True),
    "B (de-reinf only)": dict(block=False, de_reinf=True,  dur=40,
                              shared_state=True, shared_stdp=True),
    "AB (both)":         dict(block=True,  de_reinf=True,  dur=40,
                              shared_state=True, shared_stdp=True),
    "AB-short (dur=30)": dict(block=True,  de_reinf=True,  dur=30,
                              shared_state=True, shared_stdp=True),
    "AB-noSTDP":         dict(block=True,  de_reinf=True,  dur=40,
                              shared_state=True, shared_stdp=False),
    "AB-private-state":  dict(block=True,  de_reinf=True,  dur=40,
                              shared_state=False, shared_stdp=True),
}

print(f"\n  3 agents (A intervened, B/C non-intervened)")
print(f"  {n_queries} queries per agent, 5 seeds")
print(f"  7 factorial arms")
print()

results = {arm: {"a_washout": 0, "b_washout": 0, "c_washout": 0,
                  "b_nearest": 0} for arm in arms}

for seed in seeds:
    rng_a = random.Random(seed * 3)
    rng_b = random.Random(seed * 3 + 1)
    rng_c = random.Random(seed * 3 + 2)
    query_streams = {
        "A": [rng_a.uniform(0, 360) for _ in range(n_queries)],
        "B": [rng_b.uniform(0, 360) for _ in range(n_queries)],
        "C": [rng_c.uniform(0, 360) for _ in range(n_queries)],
    }

    # Control (no intervention) — same for all arms
    control = run_arm(query_streams, None, 999, 999,
                      block=False, de_reinforce=False,
                      shared_state=True, shared_stdp=True, seed=seed)

    for arm_name, params in arms.items():
        int_start = 40
        int_end = int_start + params["dur"]

        traj = run_arm(query_streams, "A", int_start, int_end,
                       block=params["block"], de_reinforce=params["de_reinf"],
                       shared_state=params["shared_state"],
                       shared_stdp=params["shared_stdp"], seed=seed)

        a_d, _ = compare_traj(control["A"], traj["A"], int_end, n_queries)
        b_d, b_n = compare_traj(control["B"], traj["B"], int_end, n_queries)
        c_d, _ = compare_traj(control["C"], traj["C"], int_end, n_queries)

        results[arm_name]["a_washout"] += a_d
        results[arm_name]["b_washout"] += b_d
        results[arm_name]["c_washout"] += c_d
        results[arm_name]["b_nearest"] += b_n

n = len(seeds)
print("=" * 70)
print("RESULTS (washout set_diff, averaged over 5 seeds)")
print("=" * 70)
print(f"\n{'Arm':<22} {'A (intervened)':>16} {'B (non-int)':>12} {'C (non-int)':>12} {'B nearest':>12}")
print("-" * 74)
for arm_name in arms:
    r = results[arm_name]
    print(f"{arm_name:<22} {r['a_washout']/n:>16.4f} {r['b_washout']/n:>12.4f} "
          f"{r['c_washout']/n:>12.4f} {r['b_nearest']/n:>12.4f}")

print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)

# Compare arms to isolate factors
c_b = results["C (control)"]["b_washout"] / n
a_b = results["A (block only)"]["b_washout"] / n
b_b = results["B (de-reinf only)"]["b_washout"] / n
ab_b = results["AB (both)"]["b_washout"] / n
ab_short_b = results["AB-short (dur=30)"]["b_washout"] / n
ab_nostdp_b = results["AB-noSTDP"]["b_washout"] / n
ab_private_b = results["AB-private-state"]["b_washout"] / n

print(f"\n  Factor isolation (B washout divergence):")
print(f"    Control:              {c_b:.4f}")
print(f"    Block only:            {a_b:.4f}  (blocking alone)")
print(f"    De-reinf only:         {b_b:.4f}  (de-reinforcement alone)")
print(f"    Both (block+de-reinf): {ab_b:.4f}  (interaction)")
print(f"    Both, dur=30:          {ab_short_b:.4f}  (duration effect)")
print(f"    Both, no shared STDP:  {ab_nostdp_b:.4f}  (STDP contribution)")
print(f"    Both, private state:   {ab_private_b:.4f}  (state sharing contribution)")

print(f"\n  What transports A -> B/C?")
if ab_private_b < 0.01 and ab_b > 0.01:
    print(f"    -> SHARED STATE is the primary transport.")
    print(f"       Private state kills the effect ({ab_private_b:.4f} vs {ab_b:.4f}).")
elif ab_nostdp_b < 0.01 and ab_b > 0.01:
    print(f"    -> SHARED STDP is the primary transport.")
    print(f"       No-STDP kills the effect ({ab_nostdp_b:.4f} vs {ab_b:.4f}).")
elif ab_private_b < ab_b * 0.5 and ab_nostdp_b < ab_b * 0.5:
    print(f"    -> BOTH shared state and STDP contribute.")
elif ab_b > 0.01:
    print(f"    -> The effect persists even with private state ({ab_private_b:.4f})")
    print(f"       and private STDP ({ab_nostdp_b:.4f}).")
    print(f"       Something else transports it (shared graph? shared k-NN?)")
else:
    print(f"    -> No significant B/C divergence in any arm.")
