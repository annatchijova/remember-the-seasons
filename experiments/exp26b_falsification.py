"""
Exp26b: Falsification of Exp26's two claims.

Exp26 claimed: (a) a minimum information budget exists (~10 bits);
(b) contiguous partition > hash partition, implying semantic
coherence matters.

Problems with Exp26:
1. "contiguous" groups are by INSERTION INDEX, not verified
   embedding-space coherence. We never measured whether contiguous
   groups are actually coherent.
2. hash() builtin is not deterministic across processes (no
   PYTHONHASHSEED guarantee) — the "hash" assignment isn't stable.
3. The threshold was only tested at coarse grain (5 vs 10).

This experiment tries to falsify both claims.

PREDEFINED CRITERIA (before running):
  H8 present iff mean post-washout set_diff > 0.005 AND at least 3
  decision flips across all seeds. Below that = absent.

Claim 1 (budget threshold): if the apparent 5->10 cliff is real,
  it should persist at fine grain (5,6,...,12) across 30 seeds.
  If it's noise/artifact, the curve smooths out or moves.

Claim 2 (location matters): we separate "index adjacency" from
  "embedding coherence" by storing memories in permuted order.
  - index_contiguous on ORDERED field = coherent by construction
  - index_contiguous on SHUFFLED field = same index grouping but
    geometrically scattered — falsification arm
  - angular_cluster = groups by angle regardless of index order
  - sha256 = deterministic scatter (replaces unstable hash())
  - stride = deterministic scatter (i * stride % n_groups)

If "coherence matters" is real: index_contiguous on SHUFFLED should
behave like sha256 (low divergence), while angular_cluster should
reproduce the threshold. If index_contiguous on shuffled still
produces divergence, the effect is index-driven (artifact), not
geometry-driven.
"""
import sys
import numpy as np
import random
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass
from scipy.spatial import KDTree
from scipy import stats as scipy_stats

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")


@dataclass
class SimpleMemory:
    memory_id: str
    embedding: np.ndarray
    angle: float


class FalsificationEngine:
    """Retrieval + group-level binary state, with explicit assignment
    strategies and field ordering."""

    def __init__(self, n_groups=100, assignment="index",
                 field_order="ordered"):
        self.memories: Dict[str, SimpleMemory] = {}
        self._kdtree: Optional[KDTree] = None
        self._kdtree_dirty = True
        self._kdtree_ids: List[str] = []
        self.n_groups = n_groups
        self.assignment = assignment
        self.field_order = field_order
        self.group_flags = [False] * max(n_groups, 1)
        self.mem_to_group: Dict[str, int] = {}
        self._storage_order: List[str] = []

    def store(self, memory_id, embedding, angle):
        self.memories[memory_id] = SimpleMemory(memory_id, embedding, angle)
        self._storage_order.append(memory_id)
        self._kdtree_dirty = True

    def finalize_groups(self):
        """Assign groups after all memories are stored."""
        ids = self._storage_order
        n = len(ids)

        if self.assignment == "index":
            for i, mid in enumerate(ids):
                gid = i * self.n_groups // n
                self.mem_to_group[mid] = min(gid, self.n_groups - 1)

        elif self.assignment == "angular":
            # Sort by angle, assign contiguous arcs
            sorted_mids = sorted(ids, key=lambda m: self.memories[m].angle)
            for i, mid in enumerate(sorted_mids):
                gid = i * self.n_groups // n
                self.mem_to_group[mid] = min(gid, self.n_groups - 1)

        elif self.assignment == "sha256":
            for mid in ids:
                h = int(hashlib.sha256(mid.encode()).hexdigest(), 16)
                self.mem_to_group[mid] = h % self.n_groups

        elif self.assignment == "stride":
            for i, mid in enumerate(ids):
                self.mem_to_group[mid] = (i * 37) % self.n_groups

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

    def coherence(self):
        """Measure within-group vs between-group cosine similarity."""
        if self.n_groups <= 0:
            return 0.0, 0.0, 0.0

        group_members = {}
        for mid, gid in self.mem_to_group.items():
            group_members.setdefault(gid, []).append(mid)

        within_sims = []
        between_sims = []

        all_mids = list(self.memories.keys())
        for mid_a in all_mids:
            emb_a = self.memories[mid_a].embedding
            gid_a = self.mem_to_group[mid_a]
            for mid_b in all_mids:
                if mid_a >= mid_b:
                    continue
                emb_b = self.memories[mid_b].embedding
                gid_b = self.mem_to_group[mid_b]
                sim = float(np.dot(emb_a, emb_b) /
                           (np.linalg.norm(emb_a) * np.linalg.norm(emb_b) + 1e-12))
                if gid_a == gid_b:
                    within_sims.append(sim)
                else:
                    between_sims.append(sim)

        w = np.mean(within_sims) if within_sims else 0.0
        b = np.mean(between_sims) if between_sims else 0.0
        return w, b, w - b

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
                                 gid < len(self.group_flags) and
                                 self.group_flags[gid]) else 1.0
            final = max(0.0, sim * state_mult)
            results.append((mid, final, sim))

        results.sort(key=lambda x: (-x[1], x[0]))
        return results[:top_k]

    def reinforce(self, memory_id, step):
        if memory_id in self.memories and self.n_groups > 0:
            gid = self.mem_to_group[memory_id]
            if gid < len(self.group_flags):
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
                assignment="index", field_order="ordered"):
    eng = FalsificationEngine(n_groups=n_groups, assignment=assignment,
                               field_order=field_order)
    memories = {}

    # Generate memory positions
    order = list(range(n_memories))
    if field_order == "shuffled":
        rng = random.Random(seed * 7919)
        rng.shuffle(order)

    for i in order:
        angle = (i * 360.0 / n_memories) % 360
        mid = f"M{i:04d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim), angle)

    eng.finalize_groups()
    return eng, memories


def run_trajectory(query_angles, int_start, int_end,
                   block_reinforcement, seed=42, n_groups=100,
                   assignment="index", field_order="ordered"):
    eng, memories = build_field(seed=seed, n_groups=n_groups,
                                 assignment=assignment,
                                 field_order=field_order)
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
        })

    return trajectory, eng, votes


def compare_traj(ta, tb, start, end):
    set_diffs = []
    for i in range(start, min(end, len(ta), len(tb))):
        a_set = set(ta[i]["recalled"])
        b_set = set(tb[i]["recalled"])
        set_diffs.append(len(a_set.symmetric_difference(b_set)) / 10.0)
    return set_diffs


def mean_ci(vals, confidence=0.95):
    """Mean and CI."""
    a = np.array(vals)
    m = np.mean(a)
    if len(a) > 1:
        sem = np.std(a, ddof=1) / np.sqrt(len(a))
        ci = scipy_stats.t.interval(confidence, len(a)-1, loc=m, scale=sem)
        return m, ci
    return m, (m, m)


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP26b: Falsification — is the threshold real? Does location matter?")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(30))  # more seeds for tighter CI

# PREDEFINED CRITERIA (before running):
H8_THRESHOLD = 0.005
H8_MIN_FLIPS = 3
print(f"\n  PREDEFINED CRITERIA:")
print(f"    H8 present iff mean washout set_diff > {H8_THRESHOLD}")
print(f"    AND >= {H8_MIN_FLIPS} decision flips across all seeds")
print(f"\n  {n_queries} queries, intervention {int_start}-{int_end}, "
      f"{len(seeds)} seeds")
print()

# ============================================================
# PART A: Fine-grained threshold localization
# ============================================================
print("=" * 70)
print("PART A: Fine-grained threshold (contiguous, ordered field)")
print("=" * 70)

fine_groups = [5, 6, 7, 8, 9, 10, 11, 12, 15, 20, 25, 50, 100]
fine_results = {}

for ng in fine_groups:
    washout_vals = []
    flips = 0
    for seed in seeds:
        rng_q = random.Random(seed)
        query_angles = [rng_q.uniform(0, 360) for _ in range(n_queries)]

        control, _, _ = run_trajectory(
            query_angles, 999, 999, False, seed=seed,
            n_groups=ng, assignment="index", field_order="ordered")
        interv, _, _ = run_trajectory(
            query_angles, int_start, int_end, True, seed=seed,
            n_groups=ng, assignment="index", field_order="ordered")

        diffs = compare_traj(control, interv, int_end, n_queries)
        washout_vals.extend(diffs)

        for i in range(int_end, n_queries):
            if control[i]["decision"] != interv[i]["decision"]:
                flips += 1

    m, (lo, hi) = mean_ci(washout_vals)
    fine_results[ng] = {"mean": m, "lo": lo, "hi": hi, "flips": flips,
                        "h8": m > H8_THRESHOLD and flips >= H8_MIN_FLIPS}

print(f"\n  {'Groups':>8} {'Mean':>8} {'95% CI':>18} {'Flips':>6} {'H8?':>5}")
print(f"  {'-'*47}")
for ng in fine_groups:
    r = fine_results[ng]
    print(f"  {ng:>8} {r['mean']:>8.4f} [{r['lo']:.4f},{r['hi']:.4f}] "
          f"{r['flips']:>6} {'YES' if r['h8'] else 'NO':>5}")

# ============================================================
# PART B: Assignment falsification — separate index from geometry
# ============================================================
print("\n" + "=" * 70)
print("PART B: Assignment falsification")
print("=" * 70)

# Measure coherence for each assignment
print(f"\n  Within-group vs between-group coherence (n_groups=10):")
print(f"    {'Assignment':>20} {'Within':>8} {'Between':>8} {'Diff':>8}")
print(f"    {'-'*46}")

for assign in ["index", "angular", "sha256", "stride"]:
    for fo in ["ordered", "shuffled"]:
        eng, _ = build_field(n_groups=10, assignment=assign,
                             field_order=fo, seed=42)
        w, b, d = eng.coherence()
        print(f"    {assign:>20} ({fo:>8}): {w:>8.4f} {b:>8.4f} {d:>8.4f}")

# Run divergence for each assignment x field_order combo at key budgets
print(f"\n  Divergence at n_groups=10 (the Exp26 threshold):")

assign_configs = [
    ("index",    "ordered",   "Exp26 baseline (index = angle)"),
    ("index",    "shuffled",  "FALSIFICATION: index grouping, scattered geometry"),
    ("angular",  "ordered",   "Coherent by angle"),
    ("angular",  "shuffled",  "Coherent by angle (shuffled storage)"),
    ("sha256",   "ordered",   "Deterministic scatter"),
    ("stride",   "ordered",   "Deterministic scatter (stride)"),
]

assign_results = {}
for assign, fo, desc in assign_configs:
    key = f"{assign}_{fo}"
    washout_vals = []
    flips = 0
    for seed in seeds:
        rng_q = random.Random(seed)
        query_angles = [rng_q.uniform(0, 360) for _ in range(n_queries)]

        control, _, _ = run_trajectory(
            query_angles, 999, 999, False, seed=seed,
            n_groups=10, assignment=assign, field_order=fo)
        interv, _, _ = run_trajectory(
            query_angles, int_start, int_end, True, seed=seed,
            n_groups=10, assignment=assign, field_order=fo)

        diffs = compare_traj(control, interv, int_end, n_queries)
        washout_vals.extend(diffs)

        for i in range(int_end, n_queries):
            if control[i]["decision"] != interv[i]["decision"]:
                flips += 1

    m, (lo, hi) = mean_ci(washout_vals)
    assign_results[key] = {"mean": m, "lo": lo, "hi": hi, "flips": flips,
                            "desc": desc,
                            "h8": m > H8_THRESHOLD and flips >= H8_MIN_FLIPS}

print(f"\n  {'Assignment':>20} {'Field':>10} {'Mean':>8} {'95% CI':>18} "
      f"{'Flips':>6} {'H8?':>5}")
print(f"  {'-'*70}")
for key, r in assign_results.items():
    print(f"  {key:>20} {'':>10} {r['mean']:>8.4f} [{r['lo']:.4f},{r['hi']:.4f}] "
          f"{r['flips']:>6} {'YES' if r['h8'] else 'NO':>5}")
    print(f"    {'':>20} {r['desc']}")

# Same at n_groups=25
print(f"\n  Divergence at n_groups=25:")
assign_results_25 = {}
for assign, fo, desc in assign_configs:
    key = f"{assign}_{fo}"
    washout_vals = []
    flips = 0
    for seed in seeds:
        rng_q = random.Random(seed)
        query_angles = [rng_q.uniform(0, 360) for _ in range(n_queries)]

        control, _, _ = run_trajectory(
            query_angles, 999, 999, False, seed=seed,
            n_groups=25, assignment=assign, field_order=fo)
        interv, _, _ = run_trajectory(
            query_angles, int_start, int_end, True, seed=seed,
            n_groups=25, assignment=assign, field_order=fo)

        diffs = compare_traj(control, interv, int_end, n_queries)
        washout_vals.extend(diffs)

        for i in range(int_end, n_queries):
            if control[i]["decision"] != interv[i]["decision"]:
                flips += 1

    m, (lo, hi) = mean_ci(washout_vals)
    assign_results_25[key] = {"mean": m, "lo": lo, "hi": hi,
                               "flips": flips, "desc": desc,
                               "h8": m > H8_THRESHOLD and flips >= H8_MIN_FLIPS}

print(f"\n  {'Assignment':>20} {'Mean':>8} {'95% CI':>18} "
      f"{'Flips':>6} {'H8?':>5}")
print(f"  {'-'*60}")
for key, r in assign_results_25.items():
    print(f"  {key:>20} {r['mean']:>8.4f} [{r['lo']:.4f},{r['hi']:.4f}] "
          f"{r['flips']:>6} {'YES' if r['h8'] else 'NO':>5}")

# ============================================================
# VERDICT
# ============================================================
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

# Claim 1: does a threshold exist?
fine_h8 = [(g, r["h8"]) for g, r in fine_results.items()]
present = [g for g, h in fine_h8 if h]
absent = [g for g, h in fine_h8 if not h]

print(f"\n  CLAIM 1: Minimum information budget exists")
print(f"  H8 present at: {sorted(present)}")
print(f"  H8 absent at:  {sorted(absent)}")
if present and absent:
    max_absent = max(absent)
    min_present = min(present)
    if min_present > max_absent:
        print(f"  Threshold confirmed: absent below {min_present}, "
              f"present at {min_present}+")
    else:
        print(f"  NO CLEAN THRESHOLD: present at {min_present}, "
              f"absent at {max_absent} — overlapping.")
elif not absent:
    print(f"  H8 present at ALL levels tested — no threshold.")
elif not present:
    print(f"  H8 absent at ALL levels — threshold above tested range.")

# Claim 2: does location matter?
print(f"\n  CLAIM 2: Location (partition alignment) matters")

idx_ord = assign_results.get("index_ordered", {})
idx_shuf = assign_results.get("index_shuffled", {})
ang_ord = assign_results.get("angular_ordered", {})
sha_ord = assign_results.get("sha256_ordered", {})

if idx_ord and idx_shuf:
    ratio = idx_shuf["mean"] / max(idx_ord["mean"], 0.0001)
    print(f"  index_ordered:   {idx_ord['mean']:.4f} "
          f"({idx_ord['flips']} flips)")
    print(f"  index_shuffled:  {idx_shuf['mean']:.4f} "
          f"({idx_shuf['flips']} flips)")
    print(f"  Ratio:           {ratio:.2f}")
    if ratio < 0.5:
        print(f"  -> Shuffling storage DESTROYS the effect despite same")
        print(f"     index grouping. Location (geometry) matters, not")
        print(f"     just index adjacency.")
    elif ratio > 2.0:
        print(f"  -> Shuffling INCREASES divergence. The effect is")
        print(f"     index-driven, not geometry-driven. Exp26's claim")
        print(f"     about 'semantic coherence' is FALSIFIED.")
    else:
        print(f"  -> Shuffling has moderate effect ({ratio:.2f}).")

if ang_ord and sha_ord:
    ratio2 = ang_ord["mean"] / max(sha_ord["mean"], 0.0001)
    print(f"\n  angular_ordered: {ang_ord['mean']:.4f} "
          f"({ang_ord['flips']} flips)")
    print(f"  sha256_ordered:  {sha_ord['mean']:.4f} "
          f"({sha_ord['flips']} flips)")
    print(f"  Ratio:           {ratio2:.2f}")
    if ratio2 > 2.0:
        print(f"  -> Angular (coherent) >> sha256 (scattered).")
        print(f"     Confirms location matters.")
    elif ratio2 < 0.5:
        print(f"  -> Sha256 >> angular. Location does NOT matter.")
    else:
        print(f"  -> Moderate difference. Location partially matters.")

# Final assessment
print(f"\n  FINAL:")
h10 = fine_results.get(10, {})
h5 = fine_results.get(5, {})
if h10.get("h8") and not h5.get("h8"):
    print(f"  Budget threshold: CONFIRMED at ~10 groups")
elif not h10.get("h8"):
    print(f"  Budget threshold: NOT confirmed (10 groups fails)")
else:
    print(f"  Budget threshold: UNCLEAR")

if idx_shuf and idx_shuf.get("mean", 0) < idx_ord.get("mean", 0) * 0.5:
    print(f"  Location matters: CONFIRMED (shuffling kills it)")
elif ang_ord and ang_ord.get("mean", 0) > sha_ord.get("mean", 0) * 2:
    print(f"  Location matters: CONFIRMED (angular >> sha256)")
else:
    print(f"  Location matters: NOT confirmed")
