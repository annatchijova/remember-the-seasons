"""
Exp16: STIGMERGY — per-agent reinforcement provenance.

Exp13/15's de-reinforcement sets mem.state = NEUTRAL globally, which
erases B/C's contributions too. The user's critique:

  "A nos da permiso para neutralizar globalmente una memoria compartida."

This is potentially tautological. The fix: track reinforcement
contributions PER AGENT. The intervention modifies ONLY A's
contribution. If B/C diverge after that, it's genuine stigmergic
transmission.

Model: instead of a single mem.state, each memory has:

  reinforcement_contributions = {
    A: fraction,
    B: fraction,
    C: fraction,
  }

The effective state multiplier is a function of all contributions.
The intervention zeroes A's contribution only. B/C's contributions
are untouched.

If B/C still diverge, the mechanism is:
  A's contribution removed -> effective state changes -> B encounters
  altered environment -> B reinforces something different -> B's
  own trajectory changes -> remove intervention -> B still differs

That is genuine stigmergic transmission.
"""
import sys
import numpy as np
import random
from typing import Dict, Set, List
from dataclasses import dataclass, field

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT, K_NEIGHBORS


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


class ProvenanceEngine:
    """Engine with per-agent reinforcement provenance.

    Each memory tracks which agents reinforced it and how much.
    The effective state multiplier is the SUM of contributions, capped
    at the REINFORCED multiplier (1.5).

    Intervention on agent A zeroes A's contributions only.
    """

    def __init__(self, n_memories=100, dim=32, seed=42):
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

    def init_agent(self, agent_id):
        self.agents.append(agent_id)

    def get_effective_state(self, mid):
        """Compute effective state from contributions.
        0 contributions -> NEUTRAL (1.0)
        1+ contributions -> REINFORCED (1.5)
        """
        total = sum(self.contributions[mid].values())
        if total > 0:
            return State.REINFORCED
        return State.NEUTRAL

    def reinforce(self, agent, mid):
        """Agent reinforces a memory. Adds to that agent's contribution."""
        self.contributions[mid][agent] = self.contributions[mid].get(agent, 0) + 1
        # Update the engine's state to the effective state
        self.eng.memories[mid].state = self.get_effective_state(mid)

    def de_reinforce_agent(self, agent):
        """Zero ALL of this agent's contributions. Does NOT touch
        other agents' contributions."""
        for mid in self.contributions:
            if agent in self.contributions[mid]:
                self.contributions[mid][agent] = 0
            # Update effective state
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


def run_provenance_arm(query_streams, intervention_agent, int_start, int_end,
                        de_reinforce_agent_only=True, seed=42):
    """Run with per-agent provenance. During intervention, zero ONLY
    the intervened agent's contributions."""
    pe = ProvenanceEngine(seed=seed)
    for agent in query_streams:
        pe.init_agent(agent)

    n_steps = max(len(qs) for qs in query_streams.values())
    prev_recalled = {a: None for a in query_streams}
    trajectories = {a: [] for a in query_streams}

    for step in range(n_steps):
        now = float(step)
        in_int = int_start <= step < int_end

        # De-reinforce ONLY the intervened agent's contributions
        if in_int and de_reinforce_agent_only and intervention_agent is not None:
            pe.de_reinforce_agent(intervention_agent)

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

            # Reinforcement: all agents reinforce normally
            # (the intervention only de-reinforces, doesn't block new ones)
            if recalled_ids:
                if in_int and agent == intervention_agent:
                    # Intervened agent still reinforces (but its past
                    # contributions are being zeroed each step)
                    pe.reinforce(agent, recalled_ids[0])
                else:
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
print("EXP16: STIGMERGY — per-agent reinforcement provenance")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 80
seeds = list(range(10))

print(f"\n  3 agents (A intervened, B/C non-intervened)")
print(f"  Per-agent reinforcement contributions (not global state)")
print(f"  Intervention: zero A's contributions only (B/C untouched)")
print(f"  {n_queries} queries per agent, {len(seeds)} seeds")
print(f"  Intervention: steps {int_start}-{int_end}")
print()

total_a = 0
total_b = 0
total_c = 0
total_b_near = 0
total_c_near = 0

for seed in seeds:
    rng_a = random.Random(seed * 3)
    rng_b = random.Random(seed * 3 + 1)
    rng_c = random.Random(seed * 3 + 2)
    query_streams = {
        "A": [rng_a.uniform(0, 360) for _ in range(n_queries)],
        "B": [rng_b.uniform(0, 360) for _ in range(n_queries)],
        "C": [rng_c.uniform(0, 360) for _ in range(n_queries)],
    }

    # Control
    control = run_provenance_arm(query_streams, None, 999, 999, seed=seed)

    # Intervention: zero A's contributions only
    interv = run_provenance_arm(query_streams, "A", int_start, int_end, seed=seed)

    a_d, _ = compare_traj(control["A"], interv["A"], int_end, n_queries)
    b_d, b_n = compare_traj(control["B"], interv["B"], int_end, n_queries)
    c_d, c_n = compare_traj(control["C"], interv["C"], int_end, n_queries)

    total_a += a_d
    total_b += b_d
    total_c += c_d
    total_b_near += b_n
    total_c_near += c_n

n = len(seeds)

print("=" * 70)
print("RESULTS")
print("=" * 70)

print(f"\n  Agent A (intervened, contributions zeroed):")
print(f"    Post-washout set_diff: {total_a/n:.4f}")

print(f"\n  Agent B (non-intervened, contributions untouched):")
print(f"    Post-washout set_diff: {total_b/n:.4f}, nearest_diff: {total_b_near/n:.4f}")

print(f"\n  Agent C (non-intervened, contributions untouched):")
print(f"    Post-washout set_diff: {total_c/n:.4f}, nearest_diff: {total_c_near/n:.4f}")

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

b_rate = total_b / n
c_rate = total_c / n

if b_rate > 0.02 or c_rate > 0.02:
    print(f"\n  SURVIVES — genuine stigmergic transmission.")
    print(f"  Zeroing ONLY A's reinforcement contributions (B/C's")
    print(f"  contributions untouched) still causes B and C to diverge.")
    print(f"  B washout: {b_rate:.4f}, C washout: {c_rate:.4f}")
    print(f"\n  This is NOT tautological. The intervention modified only")
    print(f"  A's causal contribution. B/C diverge because A's altered")
    print(f"  contributions changed the shared effective state, which")
    print(f"  changed B/C's recall, which changed what B/C reinforced,")
    print(f"  which changed B/C's subsequent trajectory.")
elif b_rate > 0.005 or c_rate > 0.005:
    print(f"\n  WEAK — small stigmergic effect.")
    print(f"  B washout: {b_rate:.4f}, C washout: {c_rate:.4f}")
else:
    print(f"\n  FALSIFIED — no stigmergic transmission with per-agent provenance.")
    print(f"  B washout: {b_rate:.4f}, C washout: {c_rate:.4f}")
    print(f"  When we zero ONLY A's contributions (not B/C's), the")
    print(f"  collective effect disappears. The Exp13/15 effect was")
    print(f"  tautological: de-reinforcement erased B/C's contributions too.")
