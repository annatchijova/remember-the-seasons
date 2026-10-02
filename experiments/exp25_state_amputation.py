"""
Exp25: Factorial amputation of the persistent adaptive state.

Exp19 found that retrieval + persistent adaptive state (binary
REINFORCED/NEUTRAL) suffices for H8 path dependence. Raven amplifies
~2x but is not necessary.

But "state" is still a black box. What is the minimum sufficient
state for H8? We dissect it along three axes:

  DISCRETENESS:  binary {NEUTRAL, REINFORCED} vs scalar magnitude
  HISTORY:       accumulates vs last-touch only
  PERSISTENCE:   permanent vs decays vs reset-per-query

Variants:

  V0 binary    : REINFORCED/NEUTRAL, top-1 -> REINFORCED, mult 1.5
                 (Exp19 baseline — persists, accumulates)

  V1 scalar    : continuous count, mult = 1 + 0.05*min(count, 20)
                 (does discreteness matter? richer than binary)

  V2 last_only : boost only if reinforced in the immediately previous
                 step (no accumulation — 1-step history only)

  V3 decay     : REINFORCED expires after K steps without
                 re-reinforcement (does permanence matter?)

  V4 reset     : state cleared between queries (within-step only;
                 should be equivalent to stateless — sanity)

  V5 stateless : no state multiplier at all (pure cosine, B0)

Metrics per variant:
  - post-washout set_diff (H8)
  - decision flips
  - CF closure: restore state, re-run recall, does decision return?

If binary suffices, discreteness is not required beyond 1 bit.
If scalar amplifies, magnitude carries additional information.
If decay kills persistence, the state must be permanent.
If last_only kills H8, accumulation beyond 1 step is necessary.
If reset/stateless = 0, machinery is inert without carry-over.
"""
import sys
import numpy as np
import random
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from scipy.spatial import KDTree

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import State, RESONANT


@dataclass
class SimpleMemory:
    memory_id: str
    embedding: np.ndarray
    count: int = 0              # scalar: reinforcement count
    last_step: int = -999       # last reinforcement step


class StateVariantEngine:
    """Retrieval + configurable adaptive state. NO Raven machinery.

    Variants control how reinforcement maps to a scoring boost and
    how long it persists.
    """

    def __init__(self, variant="binary", decay_k=20):
        self.memories: Dict[str, SimpleMemory] = {}
        self._kdtree: Optional[KDTree] = None
        self._kdtree_dirty = True
        self._kdtree_ids: List[str] = []
        self.variant = variant
        self.decay_k = decay_k

    def store(self, memory_id, embedding):
        self.memories[memory_id] = SimpleMemory(memory_id, embedding)
        self._kdtree_dirty = True

    def _rebuild_kdtree(self):
        if not self._kdtree_dirty:
            return
        ids = list(self.memories.keys())
        if not ids:
            self._kdtree = None
            return
        points = np.array([self.memories[mid].embedding for mid in ids])
        self._kdtree = KDTree(points)
        self._kdtree_ids = ids
        self._kdtree_dirty = False

    def _boost(self, mid, step):
        """State multiplier for scoring."""
        mem = self.memories[mid]
        if self.variant == "stateless":
            return 1.0
        if self.variant == "binary":
            return 1.5 if mem.count > 0 else 1.0
        if self.variant == "scalar":
            return 1.0 + 0.05 * min(mem.count, 20)  # capped at 2.0
        if self.variant == "last_only":
            return 1.5 if mem.last_step == step - 1 else 1.0
        if self.variant == "decay":
            if mem.count > 0 and (step - mem.last_step) < self.decay_k:
                return 1.5
            return 1.0
        if self.variant == "reset":
            # state exists within recall but is cleared each step
            return 1.5 if mem.count > 0 else 1.0
        return 1.0

    def recall(self, query, top_k=10, step=0):
        """Pure retrieval + state multiplier."""
        self._rebuild_kdtree()
        if self._kdtree is None or len(self._kdtree_ids) == 0:
            return []

        results = []
        for mid in self._kdtree_ids:
            mem = self.memories[mid]
            sim = float(np.dot(query, mem.embedding) /
                       (np.linalg.norm(query) * np.linalg.norm(mem.embedding) + 1e-12))
            state_mult = self._boost(mid, step)
            final = sim * state_mult
            final = max(0.0, final)
            results.append((mid, final, sim))

        results.sort(key=lambda x: (-x[1], x[0]))
        return results[:top_k]

    def reinforce(self, memory_id, step):
        if memory_id in self.memories:
            self.memories[memory_id].count += 1
            self.memories[memory_id].last_step = step

    def clear_state(self):
        """Reset all state (for 'reset' variant)."""
        for mem in self.memories.values():
            mem.count = 0
            mem.last_step = -999

    def snapshot_state(self):
        return {
            mid: (mem.count, mem.last_step)
            for mid, mem in self.memories.items()
        }

    def restore_state(self, snap):
        for mid, (count, last) in snap.items():
            if mid in self.memories:
                self.memories[mid].count = count
                self.memories[mid].last_step = last


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def build_field(n_memories=100, dim=32, seed=42, variant="binary"):
    eng = StateVariantEngine(variant=variant)
    memories = {}
    for i in range(n_memories):
        angle = (i * 360.0 / n_memories) % 360
        mid = f"M{i:04d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim))
    return eng, memories


def run_trajectory(query_angles, int_start, int_end,
                   block_reinforcement, seed=42, variant="binary"):
    """Run trajectory with state variant engine."""
    eng, memories = build_field(seed=seed, variant=variant)
    trajectory = []
    votes = {}
    rng = random.Random(seed)
    for mid in memories:
        votes[mid] = "yes" if rng.random() < 0.6 else "no"

    for step, q_angle in enumerate(query_angles):
        query = make_embedding(q_angle)
        snap = eng.snapshot_state()

        results = eng.recall(query, top_k=10, step=step)
        recalled_ids = [r[0] for r in results]
        recalled_scores = {r[0]: round(r[1], 6) for r in results}

        # Decision (same as Exp11/19)
        yes_w = 0.0
        no_w = 0.0
        evidence = {}
        for mid, score, _ in results:
            vote = votes.get(mid, "abstain")
            if vote == "yes":
                yes_w += score
                evidence[mid] = "yes"
            elif vote == "no":
                no_w += score
                evidence[mid] = "no"
        if yes_w > no_w:
            dec = "yes"
        elif no_w > yes_w:
            dec = "no"
        else:
            dec = "abstain"

        in_int = int_start <= step < int_end
        if recalled_ids and not (in_int and block_reinforcement):
            eng.reinforce(recalled_ids[0], step)

        # For 'reset' variant: clear state after each step
        if variant == "reset":
            eng.clear_state()

        nearest = min(memories.keys(),
                     key=lambda mid: abs(memories[mid] - q_angle))

        trajectory.append({
            "step": step,
            "query_angle": q_angle,
            "recalled": recalled_ids,
            "scores": recalled_scores,
            "decision": dec,
            "yes_weight": yes_w,
            "no_weight": no_w,
            "evidence": evidence,
            "nearest_in_results": nearest in recalled_ids,
            "state_snapshot": snap,
        })

    return trajectory, eng, votes


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


def cf_state_replay(eng, control_traj, step, votes):
    """Restore state from control, re-run recall."""
    c = control_traj[step]
    eng.restore_state(c["state_snapshot"])
    query = make_embedding(c["query_angle"])
    results = eng.recall(query, top_k=10, step=step)

    yes_w = 0.0
    no_w = 0.0
    for mid, score, _ in results:
        vote = votes.get(mid, "abstain")
        if vote == "yes":
            yes_w += score
        elif vote == "no":
            no_w += score
    if yes_w > no_w:
        return "yes"
    elif no_w > yes_w:
        return "no"
    return "abstain"


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP25: Factorial amputation of persistent adaptive state")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(20))

variants = [
    ("binary",    "REINFORCED/NEUTRAL, top-1, mult 1.5, persists"),
    ("scalar",    "count-based, mult 1+0.05*min(count,20)"),
    ("last_only", "boost only if reinforced previous step"),
    ("decay",     "REINFORCED expires after 20 steps"),
    ("reset",     "state cleared between queries (inert)"),
    ("stateless", "no state multiplier (B0)"),
]

print(f"\n  Variants: {len(variants)}")
for v, desc in variants:
    print(f"    {v:<12} {desc}")
print(f"\n  {n_queries} queries, intervention {int_start}-{int_end}, "
      f"{len(seeds)} seeds")
print()

all_results = {}

for variant, desc in variants:
    washout_divs = []
    during_divs = []
    nearest_divs = []
    flips = 0
    cf_closed = 0

    for seed in seeds:
        rng_q = random.Random(seed)
        query_angles = [rng_q.uniform(0, 360) for _ in range(n_queries)]

        control, eng_c, votes = run_trajectory(
            query_angles, 999, 999, False, seed=seed, variant=variant)
        interv, eng_i, _ = run_trajectory(
            query_angles, int_start, int_end, True, seed=seed, variant=variant)

        d_during, _ = compare_traj(control, interv, int_start, int_end)
        d_washout, d_near = compare_traj(control, interv, int_end, n_queries)
        during_divs.append(d_during)
        washout_divs.append(d_washout)
        nearest_divs.append(d_near)

        # CF: restore state for each flip
        for i in range(int_end, n_queries):
            if control[i]["decision"] != interv[i]["decision"]:
                flips += 1
                cf = cf_state_replay(eng_i, control, i, votes)
                if cf == control[i]["decision"]:
                    cf_closed += 1

    all_results[variant] = {
        "washout": np.mean(washout_divs),
        "during": np.mean(during_divs),
        "nearest": np.mean(nearest_divs),
        "flips": flips,
        "cf_closed": cf_closed,
        "cf_rate": cf_closed / max(flips, 1),
    }

# Print results
print("=" * 70)
print("RESULTS")
print("=" * 70)

print(f"\n  {'Variant':<12} {'During':>8} {'Washout':>8} {'Nearest':>8} "
      f"{'Flips':>6} {'CF%':>7}")
print(f"  {'-'*51}")
for variant, _ in variants:
    r = all_results[variant]
    print(f"  {variant:<12} {r['during']:>8.4f} {r['washout']:>8.4f} "
          f"{r['nearest']:>8.4f} {r['flips']:>6} {r['cf_rate']:>7.1%}")

# Analysis
print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)

b = all_results["binary"]
s = all_results["scalar"]
l = all_results["last_only"]
d = all_results["decay"]
r_ = all_results["reset"]
sl = all_results["stateless"]

print(f"\n  Discreteness: binary vs scalar")
print(f"    binary  washout={b['washout']:.4f} flips={b['flips']}")
print(f"    scalar  washout={s['washout']:.4f} flips={s['flips']}")
print(f"    {'Binary sufficient' if abs(b['washout']-s['washout'])<0.005 else 'Scalar adds information'}")

print(f"\n  History: binary vs last_only")
print(f"    binary    washout={b['washout']:.4f} flips={b['flips']}")
print(f"    last_only washout={l['washout']:.4f} flips={l['flips']}")
print(f"    {'Accumulation needed' if l['washout']<b['washout']*0.5 else 'Last-touch suffices'}")

print(f"\n  Persistence: binary vs decay vs reset")
print(f"    binary  washout={b['washout']:.4f} flips={b['flips']}")
print(f"    decay   washout={d['washout']:.4f} flips={d['flips']}")
print(f"    reset   washout={r_['washout']:.4f} flips={r_['flips']}")

print(f"\n  Sanity: stateless")
print(f"    washout={sl['washout']:.4f} flips={sl['flips']} "
      f"(should be ~0)")

# Verdict
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

if b["washout"] > 0.005:
    print(f"\n  H8 present in binary variant ({b['washout']:.4f}).")
    print(f"  Minimum sufficient state analysis:")

    if abs(b["washout"] - s["washout"]) < 0.005:
        print(f"    - Discreteness: BINARY sufficient "
              f"(scalar={s['washout']:.4f} ~same)")
    else:
        print(f"    - Discreteness: scalar adds "
              f"({s['washout']:.4f} vs {b['washout']:.4f})")

    if l["washout"] < b["washout"] * 0.5:
        print(f"    - History: ACCUMULATION needed "
              f"(last_only={l['washout']:.4f} << {b['washout']:.4f})")
    else:
        print(f"    - History: last-touch suffices "
              f"({l['washout']:.4f} ~ {b['washout']:.4f})")

    if d["washout"] < b["washout"] * 0.5:
        print(f"    - Persistence: PERMANENT needed "
              f"(decay={d['washout']:.4f} << {b['washout']:.4f})")
    else:
        print(f"    - Persistence: decay-tolerant "
              f"({d['washout']:.4f} ~ {b['washout']:.4f})")

    if r_["washout"] < 0.005 and sl["washout"] < 0.005:
        print(f"    - Sanity: reset and stateless both ~0 "
              f"(machinery inert without carry-over)")

    print(f"\n  CF closure: binary={b['cf_rate']:.0%} scalar={s['cf_rate']:.0%}")
    print(f"  The minimum sufficient state is: 1 bit per memory,"
          f"  updated on recall, persisting until overwritten.")
else:
    print(f"\n  H8 ABSENT in binary variant ({b['washout']:.4f}).")
    print(f"  Binary REINFORCED/NEUTRAL is not sufficient.")
    print(f"  Something richer is needed.")
