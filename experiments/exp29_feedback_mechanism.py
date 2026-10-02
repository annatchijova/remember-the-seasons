"""
Exp29: When does flag divergence self-amplify vs die out?

Exp27 found the mechanism: a group unflagged at step 39 gets
flagged in control but not intervention -> recall differs ->
feedback (different groups get reinforced -> flag sets diverge
further). But this only fires in ~20% of seeds at ng=7.

Question: what determines whether the initial flag difference
self-amplifies (feedback loop) or dies out (intervention arm
re-flags the group and converges)?

Hypothesis: the loop feeds only when a flag difference changes the
TOP-1 of a recall, because top-1 is what gets reinforced next, and
the reinforced memory's group is the next flag set. If a flag boost
only lifts members into ranks 2-10, the set changes but the
reinforcement target doesn't -> no feedback. If it flips rank-1 ->
a different group gets flagged -> flag sets diverge.

Testable prediction: divergent seeds are exactly those where the
late-flagged group contains memories that would reach rank-1 for
post-washout queries. Non-divergent seeds: late flags exist but
the group never reaches rank-1, so the arm re-flags it and
converges.

Instrumentation per (n_groups, seed):
  - flag-set Hamming distance between arms per step (post-washout)
  - per step: does the differing flag change rank-1 or only set?
  - growth vs decay of flag distance over time
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
    """Retrieval + group-level binary flags (index-contiguous)."""

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

    def _rank(self, query):
        """Full ranking: list of (mid, score) sorted desc."""
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
        return results

    def recall(self, query, top_k=10):
        return self._rank(query)[:top_k]

    def reinforce(self, memory_id):
        if memory_id in self.memories and self.n_groups > 0:
            self.group_flags[self.mem_to_group[memory_id]] = True

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
        angle = (i * 360.0 / n_memories) % 360
        eng.store(f"M{i:04d}", make_embedding(angle, dim))
    eng.finalize_groups()
    return eng


# ============================================================
# Paired trajectory with flag-distance logging
# ============================================================
def run_pair(query_angles, int_start, int_end, n_groups, seed):
    """Run control + intervention, log flag distance + top1 changes."""
    eng_c = build_field(n_groups=n_groups)
    eng_i = build_field(n_groups=n_groups)

    log = {
        "flag_dist": [],        # Hamming distance between flag sets
        "top1_same": [],        # same top-1 memory this step?
        "top1_group_same": [],  # same top-1 GROUP this step?
        "set_diff": [],
        "late_flags": None,
        "top1_changed_by_flagdiff": 0,
        "top1_same_despite_flagdiff": 0,
    }

    for step, qa in enumerate(query_angles):
        query = make_embedding(qa)
        in_int = int_start <= step < int_end

        # Before recall, snapshot flags
        fc = eng_c.flagset()
        fi = eng_i.flagset()
        log["flag_dist"].append(len(fc ^ fi))

        if step == int_start - 1:
            log["flags39"] = fc
        if step == int_end:
            log["late_flags"] = fc - log.get("flags39", fc)

        rc = eng_c.recall(query)
        ri = eng_i.recall(query)

        c_set = set(m for m, _ in rc)
        i_set = set(m for m, _ in ri)
        log["set_diff"].append(len(c_set ^ i_set) / 10.0)

        c_top1 = rc[0][0] if rc else None
        i_top1 = ri[0][0] if ri else None
        log["top1_same"].append(c_top1 == i_top1)

        if c_top1 and i_top1:
            c_g = eng_c.mem_to_group[c_top1]
            i_g = eng_i.mem_to_group[i_top1]
            log["top1_group_same"].append(c_g == i_g)
            # Did the flag difference change the top-1?
            if fc != fi:
                if c_top1 != i_top1:
                    log["top1_changed_by_flagdiff"] += 1
                else:
                    log["top1_same_despite_flagdiff"] += 1

        # Reinforce top-1 (blocked during intervention for int arm)
        if c_top1:
            eng_c.reinforce(c_top1)
        if i_top1 and not (in_int):
            eng_i.reinforce(i_top1)

    return log


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP29: When does flag divergence self-amplify vs die out?")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(30))
n_groups_list = [6, 7, 8, 11, 25]

print(f"\n  n_groups: {n_groups_list}, seeds: {len(seeds)}")
print(f"  Intervention {int_start}-{int_end}, washout {int_end}-{n_queries}")
print()

all_results = {}

for ng in n_groups_list:
    cfg = {
        "div_seeds": 0,
        "top1_changed": 0,
        "top1_same": 0,
        "flag_dist_traj": [],
        "converged": 0,
        "diverged": 0,
    }

    for seed in seeds:
        rng_q = random.Random(seed)
        q = [rng_q.uniform(0, 360) for _ in range(n_queries)]
        log = run_pair(q, int_start, int_end, ng, seed)

        washout = np.mean(log["set_diff"][int_end:])
        cfg["top1_changed"] += log["top1_changed_by_flagdiff"]
        cfg["top1_same"] += log["top1_same_despite_flagdiff"]

        # Trajectory of flag distance post-washout
        fd = log["flag_dist"][int_end:]
        cfg["flag_dist_traj"].append(fd)

        # Did it converge or diverge?
        early = np.mean(fd[:10]) if len(fd) >= 10 else np.mean(fd)
        late = np.mean(fd[-10:]) if len(fd) >= 10 else np.mean(fd)
        if washout > 0.005:
            cfg["div_seeds"] += 1
            if late > early * 1.2:
                cfg["diverged"] += 1
            elif late < early * 0.8:
                cfg["converged"] += 1

    all_results[ng] = cfg

# Results
print("=" * 70)
print("RESULTS")
print("=" * 70)

print(f"\n  {'ng':>4} {'div seeds':>10} {'converged':>10} {'diverged':>9} "
      f"{'top1 chg':>9} {'top1 same':>10}")
print(f"  {'-'*56}")
for ng in n_groups_list:
    c = all_results[ng]
    print(f"  {ng:>4} {c['div_seeds']:>10} {c['converged']:>10} "
          f"{c['diverged']:>9} {c['top1_changed']:>9} {c['top1_same']:>10}")

# Feedback mechanism: when flags differ, does top-1 change?
print(f"\n  Feedback mechanism across all configs:")
tot_chg = sum(c["top1_changed"] for c in all_results.values())
tot_same = sum(c["top1_same"] for c in all_results.values())
print(f"    Steps where flags differ AND top-1 changed: {tot_chg}")
print(f"    Steps where flags differ but top-1 same:    {tot_same}")
if tot_chg + tot_same:
    frac = tot_chg / (tot_chg + tot_same)
    print(f"    Flag-diff -> top-1-change rate: {frac:.1%}")

# Flag distance trajectory: does it grow or shrink post-washout?
print(f"\n  Flag distance trajectory (post-washout), ng=7:")
trajs = all_results[7]["flag_dist_traj"]
nz_trajs = [t for t, s in zip(trajs, seeds)
            if all_results[7]["flag_dist_traj"] and np.mean(t) > 0]
if nz_trajs:
    avg_traj = np.mean([t for t in nz_trajs], axis=0)
    print(f"    Mean flag distance over post-washout steps "
          f"(divergent seeds only, n={len(nz_trajs)}):")
    for i in range(0, len(avg_traj), 10):
        chunk = avg_traj[i:i+10]
        print(f"      steps {int_end+i:>3}-{int_end+min(i+9,len(avg_traj)-1):>3}: "
              f"{np.mean(chunk):.2f}")

# Verdict
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

if tot_chg + tot_same > 0:
    frac = tot_chg / (tot_chg + tot_same)
    if frac > 0.5:
        print(f"\n  FEEDBACK CONFIRMED: when flag sets differ, top-1 changes")
        print(f"  {frac:.0%} of the time. The loop feeds: flag diff ->")
        print(f"  top-1 change -> different group reinforced -> more")
        print(f"  flag diff. The amplifier is the rank-1 flip.")
    elif frac > 0.2:
        print(f"\n  PARTIAL FEEDBACK: flag diff changes top-1 only")
        print(f"  {frac:.0%} of steps. The loop fires but weakly —")
        print(f"  most flag differences affect the tail of top-k, not")
        print(f"  the reinforcement target.")
    else:
        print(f"\n  WEAK FEEDBACK: flag diff changes top-1 only")
        print(f"  {frac:.0%} of steps. Divergence is mostly set-level,")
        print(f"  not reinforcement-level. The feedback loop barely")
        print(f"  feeds itself.")

for ng in n_groups_list:
    c = all_results[ng]
    if c["div_seeds"]:
        print(f"\n  ng={ng}: {c['div_seeds']}/30 seeds diverged, "
              f"{c['diverged']} grew, {c['converged']} shrank")
