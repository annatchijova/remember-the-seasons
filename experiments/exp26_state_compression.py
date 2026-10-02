"""
Exp26: State compression — how much persistent information is
required for H8?

Exp25 found that a persistent accumulating binary flag per memory
suffices for H8. But "1 bit per memory" with 100 memories is still
100 bits of history. The question now: how much persistent
information is actually required?

We compress the state vector by sharing flags across groups of
memories:

  100 bits: 1 flag per memory          (Exp25 binary — reference)
   50 bits: 1 flag per pair
   25 bits: 1 flag per group of 4
   10 bits: 1 flag per group of 10
    5 bits: 1 flag per group of 20
    1 bit : 1 global flag              (all memories share)
    0 bits: stateless                  (sanity)

When ANY memory in a group is reinforced (top-1), the group's flag
is set. The boost applies to ALL memories in the group.

Three outcome possibilities:
  A. H8 scales smoothly with bits — path dependence doesn't need
     fine-grained memory identity
  B. There's a threshold — below k bits the phenomenon collapses
  C. Even 1 global bit preserves H8 — another organ dies

Also: same bit budget, different assignment:
  - contiguous: adjacent memories (by angle) share a flag
  - hash: memories assigned to groups by hash (random)

This distinguishes AMOUNT of information from LOCATION of
information relative to each memory.
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


class GroupedStateEngine:
    """Retrieval + group-level binary state. NO Raven machinery.

    n_groups flags shared across groups of memories. When ANY memory
    in a group is reinforced, the group's flag is set. The boost
    applies to all memories in the group.
    """

    def __init__(self, n_groups=100, assignment="contiguous"):
        self.memories: Dict[str, SimpleMemory] = {}
        self._kdtree: Optional[KDTree] = None
        self._kdtree_dirty = True
        self._kdtree_ids: List[str] = []
        self.n_groups = n_groups
        self.assignment = assignment
        self.group_flags = [False] * n_groups
        self.mem_to_group: Dict[str, int] = {}
        self._n_stored = 0

    def store(self, memory_id, embedding, total_memories=100):
        self.memories[memory_id] = SimpleMemory(memory_id, embedding)
        idx = self._n_stored
        self._n_stored += 1
        if self.assignment == "contiguous" and self.n_groups > 0:
            gid = idx * self.n_groups // total_memories
            self.mem_to_group[memory_id] = min(gid, self.n_groups - 1)
        elif self.assignment == "hash" and self.n_groups > 0:
            h = hash(memory_id) & 0x7fffffff
            self.mem_to_group[memory_id] = h % self.n_groups
        else:
            self.mem_to_group[memory_id] = 0
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

    def recall(self, query, top_k=10, step=0):
        self._rebuild_kdtree()
        if self._kdtree is None or len(self._kdtree_ids) == 0:
            return []

        results = []
        for mid in self._kdtree_ids:
            mem = self.memories[mid]
            sim = float(np.dot(query, mem.embedding) /
                       (np.linalg.norm(query) * np.linalg.norm(mem.embedding) + 1e-12))
            gid = self.mem_to_group.get(mid, 0)
            state_mult = 1.5 if (self.n_groups > 0 and
                                 self.group_flags[gid]) else 1.0
            final = max(0.0, sim * state_mult)
            results.append((mid, final, sim))

        results.sort(key=lambda x: (-x[1], x[0]))
        return results[:top_k]

    def reinforce(self, memory_id, step):
        if memory_id in self.memories and self.n_groups > 0:
            gid = self.mem_to_group[memory_id]
            self.group_flags[gid] = True

    def snapshot_state(self):
        return list(self.group_flags)

    def restore_state(self, snap):
        self.group_flags = list(snap)


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def build_field(n_memories=100, dim=32, seed=42, n_groups=100,
                assignment="contiguous"):
    eng = GroupedStateEngine(n_groups=n_groups, assignment=assignment)
    memories = {}
    for i in range(n_memories):
        angle = (i * 360.0 / n_memories) % 360
        mid = f"M{i:04d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim))
    return eng, memories


def run_trajectory(query_angles, int_start, int_end,
                   block_reinforcement, seed=42, n_groups=100,
                   assignment="contiguous"):
    eng, memories = build_field(seed=seed, n_groups=n_groups,
                                 assignment=assignment)
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

        yes_w = 0.0
        no_w = 0.0
        for mid, score, _ in results:
            vote = votes.get(mid, "abstain")
            if vote == "yes":
                yes_w += score
            elif vote == "no":
                no_w += score
        dec = "yes" if yes_w > no_w else ("no" if no_w > yes_w else "abstain")

        in_int = int_start <= step < int_end
        if recalled_ids and not (in_int and block_reinforcement):
            eng.reinforce(recalled_ids[0], step)

        nearest = min(memories.keys(),
                     key=lambda mid: abs(memories[mid] - q_angle))

        trajectory.append({
            "step": step, "recalled": recalled_ids, "decision": dec,
            "nearest_in_results": nearest in recalled_ids,
            "state_snapshot": snap,
        })

    return trajectory, eng, votes


def compare_traj(ta, tb, start, end):
    set_diffs = []
    for i in range(start, min(end, len(ta), len(tb))):
        a_set = set(ta[i]["recalled"])
        b_set = set(tb[i]["recalled"])
        set_diffs.append(len(a_set.symmetric_difference(b_set)) / 10.0)
    return sum(set_diffs) / len(set_diffs) if set_diffs else 0.0


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP26: State compression — how many bits does H8 need?")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(20))

# Bit budget sweep (contiguous assignment)
bit_levels = [
    (100, "contiguous"),  # 1 flag/memory = Exp25 binary
    (50, "contiguous"),   # 1 flag/pair
    (25, "contiguous"),   # 1 flag/group of 4
    (10, "contiguous"),   # 1 flag/group of 10
    (5, "contiguous"),    # 1 flag/group of 20
    (2, "contiguous"),    # 1 flag/group of 50
    (1, "contiguous"),    # 1 global flag
    (0, "contiguous"),    # stateless
]

# Assignment comparison at same bit budget
assignment_levels = [
    (10, "contiguous"),
    (10, "hash"),
    (25, "contiguous"),
    (25, "hash"),
    (50, "contiguous"),
    (50, "hash"),
]

print(f"\n  Bit sweep: {[b for b, _ in bit_levels]} groups")
print(f"  Assignment comparison: {[a for _, a in assignment_levels]}")
print(f"  {n_queries} queries, intervention {int_start}-{int_end}, "
      f"{len(seeds)} seeds")
print()

# Bit sweep
print("=" * 70)
print("BIT SWEEP (contiguous assignment)")
print("=" * 70)

sweep_results = {}
for n_groups, assignment in bit_levels:
    washout_divs = []
    during_divs = []
    flips = 0

    for seed in seeds:
        rng_q = random.Random(seed)
        query_angles = [rng_q.uniform(0, 360) for _ in range(n_queries)]

        control, _, _ = run_trajectory(
            query_angles, 999, 999, False, seed=seed,
            n_groups=n_groups, assignment=assignment)
        interv, _, _ = run_trajectory(
            query_angles, int_start, int_end, True, seed=seed,
            n_groups=n_groups, assignment=assignment)

        d_during = compare_traj(control, interv, int_start, int_end)
        d_washout = compare_traj(control, interv, int_end, n_queries)
        during_divs.append(d_during)
        washout_divs.append(d_washout)

        for i in range(int_end, n_queries):
            if control[i]["decision"] != interv[i]["decision"]:
                flips += 1

    sweep_results[n_groups] = {
        "during": np.mean(during_divs),
        "washout": np.mean(washout_divs),
        "flips": flips,
    }

print(f"\n  {'Groups':>8} {'Bits':>6} {'During':>8} {'Washout':>8} {'Flips':>6}")
print(f"  {'-'*38}")
for n_groups, _ in bit_levels:
    r = sweep_results[n_groups]
    print(f"  {n_groups:>8} {n_groups:>6} {r['during']:>8.4f} "
          f"{r['washout']:>8.4f} {r['flips']:>6}")

# Assignment comparison
print("\n" + "=" * 70)
print("ASSIGNMENT COMPARISON (same bits, different grouping)")
print("=" * 70)

assign_results = {}
for n_groups, assignment in assignment_levels:
    key = f"{n_groups}_{assignment}"
    washout_divs = []
    flips = 0

    for seed in seeds:
        rng_q = random.Random(seed)
        query_angles = [rng_q.uniform(0, 360) for _ in range(n_queries)]

        control, _, _ = run_trajectory(
            query_angles, 999, 999, False, seed=seed,
            n_groups=n_groups, assignment=assignment)
        interv, _, _ = run_trajectory(
            query_angles, int_start, int_end, True, seed=seed,
            n_groups=n_groups, assignment=assignment)

        d_washout = compare_traj(control, interv, int_end, n_queries)
        washout_divs.append(d_washout)

        for i in range(int_end, n_queries):
            if control[i]["decision"] != interv[i]["decision"]:
                flips += 1

    assign_results[key] = {
        "washout": np.mean(washout_divs),
        "flips": flips,
    }

print(f"\n  {'Groups':>8} {'Assignment':>12} {'Washout':>8} {'Flips':>6}")
print(f"  {'-'*36}")
for n_groups, assignment in assignment_levels:
    key = f"{n_groups}_{assignment}"
    r = assign_results[key]
    print(f"  {n_groups:>8} {assignment:>12} {r['washout']:>8.4f} "
          f"{r['flips']:>6}")

# Analysis
print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)

# Check scaling shape
vals = [(g, sweep_results[g]["washout"]) for g, _ in bit_levels]
print(f"\n  Washout divergence vs bit budget:")
for g, w in vals:
    bar = "#" * int(w * 200)
    print(f"    {g:>4} groups ({g:>3} bits): {w:.4f} {bar}")

# Check for threshold vs smooth scaling
nz = [(g, w) for g, w in vals if w > 0.005]
if nz:
    lowest_nz = min(g for g, w in nz)
    print(f"\n  Lowest bit budget with divergence > 0.005: {lowest_nz}")
    if lowest_nz == 1:
        print(f"  Even 1 global bit produces H8.")
    elif lowest_nz <= 10:
        print(f"  Threshold around {lowest_nz} groups.")
    else:
        print(f"  No clear threshold; smooth scaling.")

# Assignment comparison
print(f"\n  Assignment effect:")
for n_groups in [10, 25, 50]:
    c = assign_results[f"{n_groups}_contiguous"]
    h = assign_results[f"{n_groups}_hash"]
    ratio = c["washout"] / h["washout"] if h["washout"] > 0.001 else 999
    print(f"    {n_groups} groups: contiguous={c['washout']:.4f} "
          f"hash={h['washout']:.4f} (ratio={ratio:.2f})")

# Verdict
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

w100 = sweep_results[100]["washout"]
w1 = sweep_results[1]["washout"]
w0 = sweep_results[0]["washout"]

if w1 > 0.005:
    print(f"\n  1 GLOBAL BIT SUFFICES — even a single shared flag")
    print(f"  produces H8 ({w1:.4f}). The state does not need to be")
    print(f"  associated with individual memories at all.")
elif w0 > 0.001:
    print(f"\n  UNEXPECTED: stateless shows nonzero divergence ({w0:.4f}).")
    print(f"  Bug or noise?")
elif all(w > 0.005 for _, w in vals[1:5]):
    print(f"\n  SMOOTH SCALING — divergence decreases smoothly with")
    print(f"  bit budget. No sharp threshold. H8 needs SOME persistent")
    print(f"  state but the amount matters more than the structure.")
elif sweep_results[10]["washout"] > 0.005 and sweep_results[5]["washout"] < 0.005:
    print(f"\n  THRESHOLD — divergence drops sharply between")
    print(f"  10 and 5 groups. There's a minimum information budget")
    print(f"  for H8 to exist.")
else:
    print(f"\n  NONTRIVIAL PROFILE — the scaling curve is neither")
    print(f"  smooth nor threshold-like. Examine the numbers above.")
