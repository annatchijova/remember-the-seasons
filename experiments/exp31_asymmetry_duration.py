"""
Exp31: Does asymmetry duration causally predict divergence?

Exp30's induce arm produced three natural negative controls:
seeds 3, 10, 11 — the unflagged group was re-flagged at the first
post-window reinforcement, so the asymmetry died before affecting
recall. The refined hypothesis:

    unflagged bit -> persistent asymmetry -> asymmetry survives
    long enough to affect ranking -> top-1 diff -> reinforcement
    diff -> future divergence

This experiment manipulates asymmetry DURATION directly:

  induce arm: unflag the active group at t=40 (as Exp30)
  duration arm: same, but the induced group is held unflagged
                for d extra post-window steps — reinforcement of
                that group is suppressed for t in [70, 70+d)

  d in {0, 1, 2, 4, 8, 16, 32, 50}

  At d=0 the arm equals Exp30's induce (group can re-flag
  immediately — the failure mode). As d grows, the asymmetry
  persists longer, giving it more chances to alter a top-1 and
  enter the feedback loop.

Measure per (seed, d):
  P(top-1 differs at some post-window step)
  mean washout set-diff
  whether divergence appears at all (washout > 0.005)

Prediction: P(divergence) rises with d — the longer the state
asymmetry stays available, the more likely it lands on a ranking
boundary and enters the loop. If the curve is flat, duration is
not the causal variable and the failure mode has another cause.

Unit of analysis: (seed, d) cells — 24 quiet seeds x 8 durations.
"""
import sys
import numpy as np
import random
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from scipy.spatial import KDTree

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")


@dataclass
class SimpleMemory:
    memory_id: str
    embedding: np.ndarray


class GroupedEngine:
    def __init__(self, n_groups):
        self.memories: Dict[str, SimpleMemory] = {}
        self._kdtree: Optional[KDTree] = None
        self._kdtree_dirty = True
        self._kdtree_ids: List[str] = []
        self.n_groups = n_groups
        self.group_flags = [False] * max(n_groups, 1)
        self.mem_to_group: Dict[str, int] = {}
        self._order: List[str] = []

    def store(self, memory_id, embedding):
        self.memories[memory_id] = SimpleMemory(memory_id, embedding)
        self._order.append(memory_id)
        self._kdtree_dirty = True

    def finalize_groups(self):
        for i, mid in enumerate(self._order):
            gid = i * self.n_groups // len(self._order)
            self.mem_to_group[mid] = min(gid, self.n_groups - 1)

    def _rebuild_kdtree(self):
        if not self._kdtree_dirty:
            return
        ids = list(self.memories.keys())
        if not ids:
            self._kdtree = None
            return
        pts = np.array([self.memories[mid].embedding for mid in ids])
        self._kdtree = KDTree(pts)
        self._kdtree_ids = ids
        self._kdtree_dirty = False

    def recall(self, query, top_k=10):
        self._rebuild_kdtree()
        results = []
        for mid in self._kdtree_ids:
            mem = self.memories[mid]
            sim = float(np.dot(query, mem.embedding) /
                       (np.linalg.norm(query) * np.linalg.norm(mem.embedding) + 1e-12))
            gid = self.mem_to_group.get(mid, 0)
            mult = 1.5 if (self.n_groups > 0 and
                           self.group_flags[gid]) else 1.0
            results.append((mid, max(0.0, sim * mult)))
        results.sort(key=lambda x: (-x[1], x[0]))
        return results[:top_k], results

    def reinforce(self, memory_id):
        if memory_id in self.memories and self.n_groups > 0:
            self.group_flags[self.mem_to_group[memory_id]] = True

    def unflag(self, gid):
        self.group_flags[gid] = False

    def flagset(self):
        return frozenset(g for g, f in enumerate(self.group_flags) if f)


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def build_field(n_memories=100, dim=32, n_groups=8):
    eng = GroupedEngine(n_groups)
    for i in range(n_memories):
        eng.store(f"M{i:04d}",
                  make_embedding((i * 360.0 / n_memories) % 360, dim))
    eng.finalize_groups()
    return eng


def run_arm(query_angles, int_start, int_end, n_groups,
            induce_gid=None, hold_d=0):
    """Intervention arm: blocked during [int_start, int_end).
    induce_gid unflagged at int_start; held unflagged (reinforcement
    suppressed for that group) during [int_end, int_end+hold_d)."""
    eng = build_field(n_groups=n_groups)
    recalled = []
    top1s = []
    top1_diff_flags = []   # filled post-hoc vs control

    for step, qa in enumerate(query_angles):
        query = make_embedding(qa)
        in_int = int_start <= step < int_end
        in_hold = int_end <= step < int_end + hold_d

        if step == int_start and induce_gid is not None:
            eng.unflag(induce_gid)

        top, _ = eng.recall(query)
        ids = [m for m, _ in top]
        recalled.append(ids)
        t1 = ids[0] if ids else None
        top1s.append(t1)

        if t1 and not in_int:
            # during hold: reinforce everything EXCEPT induced group
            if in_hold and eng.mem_to_group.get(t1) == induce_gid:
                # suppress: reinforce nothing — flag can't come back
                pass
            else:
                eng.reinforce(t1)

    return recalled, top1s, eng


def setdiff(a, b):
    return len(set(a) ^ set(b)) / 10.0


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP31: Does asymmetry duration causally predict divergence?")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(30))
NG = 7
DURATIONS = [0, 1, 2, 4, 8, 16, 32, 50]

print(f"\n  n_groups={NG}, seeds={len(seeds)}, durations={DURATIONS}")
print(f"  hold window: suppress re-flag of induced group for d steps "
      f"post-window")
print()

# First: classify seeds as divergent/quiet under natural induce (d=0)
# to compare against Exp30
print("  Phase 1: classify seeds (natural induce, d=0)...")

seed_info = {}   # seed -> dict(induce_gid, natural_wash, is_div)
for seed in seeds:
    rng_q = random.Random(seed)
    q = [rng_q.uniform(0, 360) for _ in range(n_queries)]

    # control
    c_recall, c_top1, _ = run_arm(q, 999, 999, NG)
    # natural intervention (blocked 40-70)
    i_recall, i_top1, _ = run_arm(q, int_start, int_end, NG)
    nat_wash = np.mean([setdiff(c_recall[i], i_recall[i])
                        for i in range(int_end, n_queries)])

    # find ctrl's most-reinforced group during window
    eng_c = build_field(n_groups=NG)
    rc = {}
    for st, qa in enumerate(q):
        top, _ = eng_c.recall(make_embedding(qa))
        if top:
            eng_c.reinforce(top[0][0])
            if int_start <= st < int_end:
                g = eng_c.mem_to_group[top[0][0]]
                rc[g] = rc.get(g, 0) + 1
    gid = max(rc, key=rc.get) if rc else 0

    seed_info[seed] = {"gid": gid, "nat_wash": nat_wash,
                       "div": nat_wash > 0.005}

div_seeds = [s for s in seeds if seed_info[s]["div"]]
quiet_seeds = [s for s in seeds if not seed_info[s]["div"]]
print(f"  divergent: {len(div_seeds)} {div_seeds}")
print(f"  quiet:     {len(quiet_seeds)}")

# Phase 2: duration sweep on QUIET seeds (where induce is the only
# asymmetry source)
print(f"\n  Phase 2: duration sweep on {len(quiet_seeds)} quiet seeds")
print(f"  {'d':>4} {'P(div)':>8} {'mean wash':>10} {'mean t1diff':>12}")

sweep = {}
for d in DURATIONS:
    n_div = 0
    wash_list = []
    t1diff_list = []

    for seed in quiet_seeds:
        rng_q = random.Random(seed)
        q = [rng_q.uniform(0, 360) for _ in range(n_queries)]
        gid = seed_info[seed]["gid"]

        c_recall, c_top1, _ = run_arm(q, 999, 999, NG)
        i_recall, i_top1, _ = run_arm(
            q, int_start, int_end, NG,
            induce_gid=gid, hold_d=d)

        wash = np.mean([setdiff(c_recall[i], i_recall[i])
                        for i in range(int_end, n_queries)])
        t1d = np.mean([1.0 if c_top1[i] != i_top1[i] else 0.0
                       for i in range(int_end, n_queries)])

        wash_list.append(wash)
        t1diff_list.append(t1d)
        if wash > 0.005:
            n_div += 1

    p_div = n_div / len(quiet_seeds)
    sweep[d] = {"p_div": p_div,
                "mean_wash": np.mean(wash_list),
                "mean_t1d": np.mean(t1diff_list)}
    print(f"  {d:>4} {p_div:>8.2f} {np.mean(wash_list):>10.4f} "
          f"{np.mean(t1diff_list):>12.4f}")

# Phase 3: same sweep on DIVERGENT seeds — does duration modulate
# the natural effect?
print(f"\n  Phase 3: duration sweep on {len(div_seeds)} divergent seeds "
      f"(baseline + induced unflag of their late group)")
print(f"  {'d':>4} {'P(div)':>8} {'mean wash':>10} {'mean t1d':>9}")

for d in [0, 4, 16, 50]:
    n_div = 0
    wash_list = []
    for seed in div_seeds:
        rng_q = random.Random(seed)
        q = [rng_q.uniform(0, 360) for _ in range(n_queries)]
        gid = seed_info[seed]["gid"]
        c_recall, _, _ = run_arm(q, 999, 999, NG)
        i_recall, i_top1, _ = run_arm(
            q, int_start, int_end, NG,
            induce_gid=gid, hold_d=d)
        wash = np.mean([setdiff(c_recall[i], i_recall[i])
                        for i in range(int_end, n_queries)])
        wash_list.append(wash)
        if wash > 0.005:
            n_div += 1
    print(f"  {d:>4} {n_div/len(div_seeds):>8.2f} "
          f"{np.mean(wash_list):>10.4f}")

# ============================================================
# Verdict
# ============================================================
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

ds = DURATIONS
p0 = sweep[0]["p_div"]
p_max = max(sweep[d]["p_div"] for d in ds)
monotonic = all(sweep[ds[i]]["p_div"] <= sweep[ds[i+1]]["p_div"] + 0.05
                for i in range(len(ds) - 1))

print(f"\n  P(div) at d=0:  {p0:.2f}")
print(f"  P(div) at d=50: {sweep[50]['p_div']:.2f}")
print(f"  Monotonic-ish:  {monotonic}")

if p_max > p0 + 0.15 and monotonic:
    print(f"\n  DURATION IS CAUSAL: divergence probability rises with")
    print(f"  asymmetry lifetime. The longer a state difference stays")
    print(f"  available, the more likely it lands on a ranking boundary")
    print(f"  and enters the reinforcement loop.")
elif p_max > p0 + 0.10:
    print(f"\n  PARTIAL: duration matters but the relation is noisy.")
    print(f"  Asymmetry persistence is one factor among several.")
elif p0 > 0.7:
    print(f"\n  d=0 already sufficient for most seeds — duration is not")
    print(f"  the binding constraint; the failures are idiosyncratic.")
else:
    print(f"\n  NO DURATION EFFECT: extending the hold does not rescue")
    print(f"  the quiet seeds. The failure mode has another cause.")
