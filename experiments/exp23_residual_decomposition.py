"""
Exp23: Residual decomposition — what explains F_obs \\ F_pred?

Exp22 found that step-40 contributor topology predicts threshold
position (8/9) and most flips (91% precision, 71% recall). But it
misses ~29% of observed flips and underestimates divergence by
30-70%.

KEY STRUCTURAL FACT: in this model, a memory with
|C_m(40) \\ I| >= T can NEVER flip — non-intervened contributions
are never removed. Therefore every false negative (F_obs \\ F_pred)
must be a "late bloomer": c_m(40) < T, which crossed the threshold
during the intervention window in control but not in intervention.

Two sub-mechanisms for late bloomers:
  A1 (direct): the memory needed INTERVENED agents' contributions
     to reach T. Those are zeroed every step.
  A2 (cascade): the memory needed NON-INTERVENED agents'
     contributions that never came — because those agents' recalls
     diverged during intervention and they reinforced different
     memories.

A2 is the interesting one: it's the channel where an intervention
on A changes B's behavior, which changes what gets reinforced —
a behavioral cascade through the shared field.

Gate (per user's spec):
  - If residual is explained by observable trajectory state
    (contributor counts + reinforcement logs), H10a is DERIVABLE
    DYNAMICALLY. No emergence.
  - If partially explained, identify the remaining mechanism.
  - If unexplained after full trajectory reconstruction, then
    (and only then) a new hypothesis is warranted.
"""
import sys
import numpy as np
import random
from typing import Dict, Set, List, Tuple
from collections import defaultdict

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT
from exp16_provenance import make_embedding, compare_traj


class LoggedEngine:
    """ThresholdEngine with full per-step logging."""

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

        # Logs
        self.log_contributors: List[Dict[str, Set[str]]] = []
        self.log_states: List[Dict[str, State]] = []
        self.log_reinforce: List[Tuple[str, str]] = []  # (agent, mid)
        self.log_recall_top1: List[Tuple[str, str]] = []  # (agent, top1 mid)
        self.log_recall_sets: List[Dict[str, Set[str]]] = []  # agent -> top10 set

    def init_agent(self, agent_id):
        self.agents.append(agent_id)

    def n_contributors(self, mid):
        return sum(1 for c in self.contributions[mid].values() if c > 0)

    def get_effective_state(self, mid):
        return (State.REINFORCED if self.n_contributors(mid) >= self.threshold
                else State.NEUTRAL)

    def reinforce(self, agent, mid):
        self.contributions[mid][agent] = self.contributions[mid].get(agent, 0) + 1
        self.eng.memories[mid].state = self.get_effective_state(mid)
        self.log_reinforce.append((agent, mid))

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

    def snapshot_step(self):
        """Log contributor sets and states at this step."""
        self.log_contributors.append(
            {mid: {a for a, c in contrib.items() if c > 0}
             for mid, contrib in self.contributions.items()})
        self.log_states.append(
            {mid: mem.state for mid, mem in self.eng.memories.items()})


def run_arm(query_streams, intervened_agents, int_start, int_end,
            seed=42, threshold=1):
    """Run with full per-step logging."""
    pe = LoggedEngine(seed=seed, threshold=threshold)
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

        step_recalls = {}
        for agent, queries in query_streams.items():
            if step >= len(queries):
                continue
            q_angle = queries[step]
            query = make_embedding(q_angle, dim=32)

            outcome = pe.recall(agent, query, top_k=10, now=now,
                               prev_recalled=prev_recalled[agent])
            recalled_ids = [r.memory.memory_id for r in outcome.results]
            step_recalls[agent] = set(recalled_ids)

            if recalled_ids:
                pe.reinforce(agent, recalled_ids[0])
                pe.log_recall_top1.append((agent, recalled_ids[0]))

            if prev_recalled[agent] and recalled_ids:
                pe.update_stdp(prev_recalled[agent], recalled_ids)

            pe.update_activations(recalled_ids, now)

            nearest = min(pe.memories.keys(),
                         key=lambda mid: abs(pe.memories[mid] - q_angle))
            trajectories[agent].append({
                "step": step, "recalled": recalled_ids,
                "top1": recalled_ids[0] if recalled_ids else None,
                "nearest_in_results": nearest in recalled_ids,
            })
            prev_recalled[agent] = recalled_ids

        pe.log_recall_sets.append(step_recalls)
        pe.snapshot_step()

    return trajectories, pe


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP23: Residual decomposition — what explains F_obs \\ F_pred?")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 80
seeds = list(range(5))

# Focus on T=3 mismatch cases from Exp21, plus T=1 controls
test_cases = [
    (3, 3, 1), (3, 3, 2),   # T=3, N=3
    (3, 5, 1), (3, 5, 2),   # T=3, N=5
    (3, 8, 4), (3, 8, 5),   # T=3, N=8
    (1, 5, 4),               # T=1 control
    (2, 5, 3),               # T=2 control
]

print(f"\n  Decomposing F_obs \\ F_pred for T=3 mismatch cases")
print(f"  Plus T=1, T=2 controls")
print(f"  {n_queries} queries, {len(seeds)} seeds")
print()

all_fn_analysis = []

for T, n_agents, k_int in test_cases:
    for seed in seeds:
        query_streams = {}
        for a in range(n_agents):
            rng = random.Random(seed * 100 + a)
            query_streams[f"A{a}"] = [rng.uniform(0, 360)
                                      for _ in range(n_queries)]

        intervened = {f"A{i}" for i in range(k_int)}

        # Control arm
        ctrl_traj, ctrl_pe = run_arm(query_streams, [], 999, 999,
                                     seed=seed, threshold=T)
        # Intervention arm
        int_traj, int_pe = run_arm(query_streams, list(intervened),
                                   int_start, int_end,
                                   seed=seed, threshold=T)

        # Contributor sets at step 39 (BEFORE intervention starts)
        # Step 40's de_reinforce already changes recalls, so step-40
        # snapshot includes divergent reinforcements
        C39 = {mid: ctrl_pe.log_contributors[int_start - 1][mid]
               for mid in ctrl_pe.log_contributors[int_start - 1]}
        # Contributor sets at step 80
        C80_ctrl = {mid: ctrl_pe.log_contributors[int_end][mid]
                    for mid in ctrl_pe.log_contributors[int_end]}
        C80_int = {mid: int_pe.log_contributors[int_end][mid]
                   for mid in int_pe.log_contributors[int_end]}

        # F_pred: memories REINFORCED at step 39 that would flip
        # when intervened agents' contributions are removed
        F_pred = set()
        for mid, contrib in C39.items():
            if len(contrib) >= T:
                remaining = len(contrib - intervened)
                if remaining < T:
                    F_pred.add(mid)

        # F_obs: REINFORCED in ctrl@80, NEUTRAL in int@80
        F_obs = set()
        for mid in C80_ctrl:
            ctrl_reinf = len(C80_ctrl[mid]) >= T
            int_reinf = len(C80_int[mid]) >= T
            if ctrl_reinf and not int_reinf:
                F_obs.add(mid)

        FN = F_obs - F_pred

        # For each FN memory, classify the mechanism
        for mid in FN:
            c39 = len(C39[mid])
            c80_ctrl = len(C80_ctrl[mid])
            c80_int = len(C80_int[mid])

            # Which agents contributed in control by step 80 but
            # not in intervention?
            gained_ctrl = C80_ctrl[mid] - C39[mid]  # new contributors 39->80
            missing_int = C80_ctrl[mid] - C80_int[mid]  # in ctrl, not int

            # Split missing into intervened vs non-intervened
            missing_intervened = missing_int & intervened
            missing_nonint = missing_int - intervened

            # For missing non-intervened contributors: did their
            # recall diverge during intervention?
            cascade_evidence = []
            for agent in missing_nonint:
                # Find steps where this agent reinforced m in control
                # but the top-1 differed in intervention
                for step in range(int_start, int_end):
                    ctrl_top1 = ctrl_traj[agent][step]["top1"]
                    int_top1 = int_traj[agent][step]["top1"]
                    if ctrl_top1 == mid and int_top1 != mid:
                        cascade_evidence.append((agent, step, ctrl_top1, int_top1))

            all_fn_analysis.append({
                "T": T, "N": n_agents, "k": k_int, "seed": seed,
                "mid": mid,
                "c39": c39, "c80_ctrl": c80_ctrl, "c80_int": c80_int,
                "C39": C39[mid],
                "C80_ctrl": C80_ctrl[mid],
                "C80_int": C80_int[mid],
                "intervened": intervened,
                "gained_ctrl": gained_ctrl,
                "missing_int": missing_int,
                "missing_intervened": missing_intervened,
                "missing_nonint": missing_nonint,
                "cascade_evidence": cascade_evidence,
                "was_neutral_at_39": c39 < T,
            })

# Analysis
print("=" * 70)
print("RESULTS")
print("=" * 70)

print(f"\n  Total false negatives (F_obs \\ F_pred): {len(all_fn_analysis)}")
if not all_fn_analysis:
    print(f"  No false negatives to analyze.")
else:
    # Verify: all FN should be late bloomers (c39 < T)
    late_bloomers = [f for f in all_fn_analysis if f["was_neutral_at_39"]]
    print(f"  Late bloomers (c39 < T): {len(late_bloomers)}/{len(all_fn_analysis)}")

    # Classify mechanisms
    a1_only = [f for f in late_bloomers
               if f["missing_intervened"] and not f["missing_nonint"]]
    a2_only = [f for f in late_bloomers
               if f["missing_nonint"] and not f["missing_intervened"]]
    both = [f for f in late_bloomers
            if f["missing_intervened"] and f["missing_nonint"]]
    neither = [f for f in late_bloomers
               if not f["missing_intervened"] and not f["missing_nonint"]]

    print(f"\n  Mechanism classification:")
    print(f"    A1 only (lost intervened contributors):     {len(a1_only)}")
    print(f"    A2 only (lost non-intervened via cascade):  {len(a2_only)}")
    print(f"    Both A1+A2:                                {len(both)}")
    print(f"    Neither (unexplained):                     {len(neither)}")

    # Cascade evidence
    with_cascade = [f for f in late_bloomers if f["cascade_evidence"]]
    print(f"\n  With cascade evidence (non-intervened agent's")
    print(f"  top-1 diverged during intervention):          {len(with_cascade)}")

    # Detailed breakdown
    print(f"\n  Detailed false negatives (first 20):")
    for f in all_fn_analysis[:20]:  # first 20
        print(f"    T={f['T']} N={f['N']} k={f['k']} seed={f['seed']} "
              f"{f['mid']}: c39={f['c39']} c80c={f['c80_ctrl']} "
              f"c80i={f['c80_int']} miss_int={sorted(f['missing_intervened'])} "
              f"miss_non={sorted(f['missing_nonint'])} "
              f"cascade={len(f['cascade_evidence'])}")

    # Show non-late-bloomers (c39 >= T) — these shouldn't exist
    non_late = [f for f in all_fn_analysis if not f["was_neutral_at_39"]]
    if non_late:
        print(f"\n  NON-LATE-BLOOMERS (c39 >= T, should not flip):")
        for f in non_late:
            print(f"    T={f['T']} N={f['N']} k={f['k']} seed={f['seed']} "
                  f"{f['mid']}:")
            print(f"      C39={sorted(f['C39'])} "
                  f"(|C39|={f['c39']}, "
                  f"|C39\\I|={len(f['C39']-f['intervened'])})")
            print(f"      C80_ctrl={sorted(f['C80_ctrl'])}")
            print(f"      C80_int={sorted(f['C80_int'])}")
            print(f"      missing_int={sorted(f['missing_intervened'])}")
            print(f"      missing_nonint={sorted(f['missing_nonint'])}")

# Overall verdict
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

if all_fn_analysis:
    n_explained = len(a1_only) + len(a2_only) + len(both)
    total = len(all_fn_analysis)
    pct_explained = n_explained / total * 100

    print(f"\n  Residual decomposition:")
    print(f"    Total false negatives: {total}")
    print(f"    Explained by contributor loss (A1+A2): {n_explained} "
          f"({pct_explained:.0f}%)")
    print(f"    Unexplained: {len(neither)}")

    if len(neither) == 0:
        print(f"\n  DERIVABLE DYNAMICALLY — every unexplained flip from")
        print(f"  Exp22's static topology prediction is a 'late bloomer':")
        print(f"  a memory that was NEUTRAL at step 40, crossed the")
        print(f"  threshold during the intervention window in control,")
        print(f"  but didn't in intervention because contributors were")
        print(f"  lost (either intervened agents' zeroed contributions")
        print(f"  or non-intervened agents' divergent reinforcement).")
        print(f"\n  No emergent mechanism needed. The residual is")
        print(f"  fully explained by observable trajectory state.")
    elif pct_explained > 80:
        print(f"\n  MOSTLY DERIVABLE — {pct_explained:.0f}% of residual")
        print(f"  flips are late bloomers explained by contributor loss.")
        print(f"  {len(neither)} memories remain unexplained.")
    else:
        print(f"\n  PARTIALLY DERIVABLE — {pct_explained:.0f}% explained.")
        print(f"  {len(neither)} memories unexplained. Needs further")
        print(f"  investigation.")
else:
    print(f"\n  No false negatives — topology fully predicts flips.")
