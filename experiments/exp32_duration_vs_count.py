"""
Exp32: Duration vs blocked-transition count — what actually drives
the Exp31 effect?

Exp31 showed washout divergence grows with hold length d. But the
hold conflates two things:

  lifetime of the asymmetry      (d elapsed steps)
  blocked re-flag transitions    (how many times reinforcement of
                                  the induced group was suppressed
                                  during those d steps)

An induced group that never becomes top-1 during its hold window
accumulates duration but ZERO blocked transitions. If washout still
grows with d there, duration per se matters — the asymmetry shifts
recall by its mere existence. If washout tracks the number of
suppressed re-flag events instead, the causal variable is
enforcement count, not elapsed time.

Arms (all on Exp31's 24 quiet seeds, same induced gid per seed):

  hold_d     — continuous suppression for d steps (Exp31 semantics)
  early_k    — suppress only the first k re-flag ATTEMPTS post-window
               (attempt = a step where the induced group's member
               lands top-1 while its flag is off)
  late_k     — allow re-flag at the first attempt (asymmetry dies),
               then at step 90 unflag again and suppress k attempts
               (same blocked count, later placement)

Measurements per (seed, arm):
  n_blocked — actual suppressed re-flag transitions
  washout divergence, mean top-1 diff

Comparisons:
  1. washout vs n_blocked across all hold_d arms — does divergence
     track count or elapsed duration?
  2. early_k vs late_k at equal k — does WHEN the asymmetry exists
     matter at equal enforcement count?
  3. In seeds where n_blocked saturates early (group stops hitting
     top-1), does washout still grow with d?

Predefined reading:
  - washout ~ n_blocked regardless of d  -> count, not duration
  - washout grows with d at n_blocked fixed -> duration per se
  - early_k > late_k at equal k -> asymmetry adjacent to the
    intervention boundary is special (early-position effect)
"""
import sys
import numpy as np
import random
from typing import Dict, List, Optional
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
            induce_gid=None, hold_d=0, early_k=None,
            late_k=None, late_start=90):
    """Induce arm with three suppression regimes.

    hold_d  : suppress induced-group re-flag for steps [int_end, int_end+hold_d)
    early_k : suppress the first early_k re-flag attempts post-window
    late_k  : allow normal re-flagging until late_start, then unflag
              induced_gid and suppress late_k attempts
    Returns (recalled_sets, top1s, n_blocked)
    """
    eng = build_field(n_groups=n_groups)
    recalled = []
    top1s = []
    n_blocked = 0
    attempts_suppressed = 0
    reflagged_once = False   # for late_k: did the flag come back?

    for step, qa in enumerate(query_angles):
        query = make_embedding(qa)
        in_int = int_start <= step < int_end
        post = step >= int_end

        if step == int_start and induce_gid is not None:
            eng.unflag(induce_gid)

        # late_k: re-arm the asymmetry at late_start
        if (late_k is not None and step == late_start
                and induce_gid is not None):
            eng.unflag(induce_gid)
            attempts_suppressed = 0

        top, _ = eng.recall(query)
        ids = [m for m, _ in top]
        recalled.append(ids)
        t1 = ids[0] if ids else None
        top1s.append(t1)

        if t1 and not in_int:
            g1 = eng.mem_to_group.get(t1)
            suppress = False
            if g1 == induce_gid:
                if hold_d and int_end <= step < int_end + hold_d:
                    suppress = True
                if early_k is not None and post \
                        and attempts_suppressed < early_k:
                    suppress = True
                if late_k is not None and step >= late_start \
                        and attempts_suppressed < late_k:
                    suppress = True
            if suppress:
                n_blocked += 1
                attempts_suppressed += 1
            else:
                eng.reinforce(t1)

    return recalled, top1s, n_blocked


def setdiff(a, b):
    return len(set(a) ^ set(b)) / 10.0


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP32: Duration vs blocked-transition count")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(30))
NG = 7

# Phase 1: classify seeds + induced gid per seed (same as Exp30/31)
print("\n  Phase 1: classify seeds, find induced groups")
seed_info = {}
for seed in seeds:
    rng_q = random.Random(seed)
    q = [rng_q.uniform(0, 360) for _ in range(n_queries)]
    c_recall, c_top1, _ = run_arm(q, 999, 999, NG)
    i_recall, _, _ = run_arm(q, int_start, int_end, NG)
    nat_wash = np.mean([setdiff(c_recall[i], i_recall[i])
                        for i in range(int_end, n_queries)])
    # most-reinforced group during window in control
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
                       "q": q, "c_recall": c_recall, "c_top1": c_top1}

quiet = [s for s in seeds if seed_info[s]["nat_wash"] <= 0.005]
print(f"  quiet seeds: {len(quiet)}")

# Phase 2: hold_d sweep WITH n_blocked logged
print(f"\n  Phase 2: hold duration sweep, logging blocked transitions")
print(f"  {'d':>4} {'P(div)':>7} {'mean wash':>10} {'mean nblk':>10}")

hold_rows = []   # (seed, d, n_blocked, wash)
for d in [0, 1, 4, 8, 16, 32, 50]:
    ndiv = 0
    washs, nblks = [], []
    for seed in quiet:
        info = seed_info[seed]
        i_recall, i_top1, nb = run_arm(
            info["q"], int_start, int_end, NG,
            induce_gid=info["gid"], hold_d=d)
        wash = np.mean([setdiff(info["c_recall"][i], i_recall[i])
                        for i in range(int_end, n_queries)])
        washs.append(wash); nblks.append(nb)
        hold_rows.append((seed, d, nb, wash))
        if wash > 0.005:
            ndiv += 1
    print(f"  {d:>4} {ndiv/len(quiet):>7.2f} {np.mean(washs):>10.4f} "
          f"{np.mean(nblks):>10.2f}")

# Phase 3: count-matched arms — suppress first k attempts only
print(f"\n  Phase 3: count arms — suppress first k attempts")
print(f"  {'k':>4} {'P(div)':>7} {'mean wash':>10} {'mean nblk':>10}")

early_rows = []
for k in [1, 2, 4, 8, 16]:
    ndiv = 0
    washs, nblks = [], []
    for seed in quiet:
        info = seed_info[seed]
        i_recall, _, nb = run_arm(
            info["q"], int_start, int_end, NG,
            induce_gid=info["gid"], early_k=k)
        wash = np.mean([setdiff(info["c_recall"][i], i_recall[i])
                        for i in range(int_end, n_queries)])
        washs.append(wash); nblks.append(nb)
        early_rows.append((seed, k, nb, wash))
        if wash > 0.005:
            ndiv += 1
    print(f"  {k:>4} {ndiv/len(quiet):>7.2f} {np.mean(washs):>10.4f} "
          f"{np.mean(nblks):>10.2f}")

# Phase 4: timing — same k blocked, placed late
print(f"\n  Phase 4: late_k — same blocked count, asymmetry starts "
      f"at step 90")
print(f"  {'k':>4} {'P(div)':>7} {'mean wash':>10} {'mean nblk':>10}")

late_rows = []
for k in [1, 2, 4, 8]:
    ndiv = 0
    washs, nblks = [], []
    for seed in quiet:
        info = seed_info[seed]
        i_recall, _, nb = run_arm(
            info["q"], int_start, int_end, NG,
            induce_gid=info["gid"], late_k=k, late_start=90)
        wash = np.mean([setdiff(info["c_recall"][i], i_recall[i])
                        for i in range(int_end, n_queries)])
        washs.append(wash); nblks.append(nb)
        late_rows.append((seed, k, nb, wash))
        if wash > 0.005:
            ndiv += 1
    print(f"  {k:>4} {ndiv/len(quiet):>7.2f} {np.mean(washs):>10.4f} "
          f"{np.mean(nblks):>10.2f}")

# ============================================================
# Analysis: duration vs count
# ============================================================
print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)

# For each d, correlate washout with n_blocked across seeds
print("\n  Per-duration correlation washout ~ n_blocked:")
for d in [0, 1, 4, 8, 16, 32, 50]:
    xs = np.array([r[2] for r in hold_rows if r[1] == d], float)
    ys = np.array([r[3] for r in hold_rows if r[1] == d], float)
    if xs.std() > 1e-9:
        r = np.corrcoef(xs, ys)[0, 1]
        print(f"    d={d:>2}: r={r:+.3f} (n_blocked range "
              f"{xs.min():.0f}-{xs.max():.0f})")
    else:
        print(f"    d={d:>2}: n_blocked constant ({xs.min():.0f}), "
              f"mean washout={ys.mean():.4f}")

# Compare hold_d vs early_k at matched counts:
# pick cells where n_blocked is equal, compare washout
print("\n  Matched-count comparison (washout | same n_blocked):")
print(f"  {'nblk':>5} {'hold mean':>10} {'early mean':>10} {'n hold':>7} "
      f"{'n early':>7}")
by_nb_hold = {}
by_nb_early = {}
for _, _, nb, w in hold_rows:
    by_nb_hold.setdefault(nb, []).append(w)
for _, _, nb, w in early_rows:
    by_nb_early.setdefault(nb, []).append(w)
for nb in sorted(set(by_nb_hold) & set(by_nb_early)):
    if nb <= 30:
        print(f"  {nb:>5} {np.mean(by_nb_hold[nb]):>10.4f} "
              f"{np.mean(by_nb_early[nb]):>10.4f} "
              f"{len(by_nb_hold[nb]):>7} {len(by_nb_early[nb]):>7}")

# early vs late at equal k
print("\n  Early vs late at equal suppressed count:")
for k in [1, 2, 4, 8]:
    e = [w for s, kk, nb, w in early_rows if kk == k]
    l = [w for s, kk, nb, w in late_rows if kk == k]
    if e and l:
        print(f"    k={k}: early wash={np.mean(e):.4f}  "
              f"late wash={np.mean(l):.4f}")

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

# Heuristic verdict
d0 = np.mean([r[3] for r in hold_rows if r[1] == 0])
d50 = np.mean([r[3] for r in hold_rows if r[1] == 50])
nb0 = np.mean([r[2] for r in hold_rows if r[1] == 0])
nb50 = np.mean([r[2] for r in hold_rows if r[1] == 50])

print(f"\n  hold_d=0:  wash={d0:.4f}, n_blocked={nb0:.2f}")
print(f"  hold_d=50: wash={d50:.4f}, n_blocked={nb50:.2f}")

# Do seeds exist where n_blocked saturates but washout grows?
saturated = []
for seed in quiet:
    nbs = [nb for s, d, nb, w in hold_rows if s == seed and d in (16, 50)]
    ws = [w for s, d, nb, w in hold_rows if s == seed and d in (16, 50)]
    if nbs[0] == nbs[1] and abs(ws[1] - ws[0]) > 0.01:
        saturated.append((seed, nbs[0], ws[0], ws[1]))

if saturated:
    print(f"\n  {len(saturated)} seeds where n_blocked is IDENTICAL at "
          f"d=16 and d=50 but washout differs:")
    for s, nb, w16, w50 in saturated[:8]:
        print(f"    seed {s}: n_blocked={nb}, wash16={w16:.4f} "
              f"wash50={w50:.4f}")
    print(f"  -> duration per se contributes: same suppressed count,")
    print(f"     different elapsed asymmetry, different outcome")
else:
    print(f"\n  No seeds show washout growth at constant n_blocked —")
    print(f"  the count of blocked transitions, not elapsed duration,")
    print(f"  is what scales the effect.")
