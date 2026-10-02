"""
Exp27: Why does 7 groups produce H8 and 8 does not?

Exp26b showed a noisy, non-monotonic divergence curve:
  5->NO, 6->YES, 7->YES (0.0805, 24 flips), 8->NO (0.0049, 3 flips),
  9->NO, 10->NO, 11->YES, 12->NO, 15->YES, 20->NO, 25->YES...

Two almost-identical capacities differ by ~16x in divergence. The
hypothesis: the difference is NOT the bit count — it is which
specific groups remain unflagged at the intervention boundary and
how much leverage their flags have on the recall boundary.

Mechanism under test (feedback hypothesis):
  recall -> reinforce group -> flag boost changes ranking ->
  different recall -> different group reinforced -> ...

If flag divergence changes WHICH groups get reinforced next, the
flag sets diverge further — a feedback loop. The observed
post-washout divergence should then exceed what the initial
late-flag difference alone predicts.

Instrumentation per (n_groups, seed), control and intervention:

  - flags set by step 39 (identical in both arms)
  - "late flags": groups flagged in control during 40-70
    (blocked in intervention) — the direct causal substrate
  - flag sets at step 70 in each arm
  - post-washout: per-step recalled-set difference, and for each
    differing memory, whether its group flag differed at that step
  - boundary leverage: per group, how many members sit at
    ranks 11-20 (marginal, boostable into top-10)
  - feedback events: post-70 steps where the intervention arm flags
    a group control never flags, or vice versa (flag-set divergence)
  - per-seed contribution to divergence (is 7-vs-8 driven by a few
    seeds?)

Predefined criterion: the 7-vs-8 difference is "explained" if
(a) the set of post-washout differing recalls is almost entirely
composed of members of groups whose flag state differs at that step
    (state explanation), OR
(b) a substantial fraction differs even when flag states match
    (feedback explanation).
"""
import sys
import numpy as np
import random
import hashlib
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from scipy.spatial import KDTree

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")


@dataclass
class SimpleMemory:
    memory_id: str
    embedding: np.ndarray
    angle: float


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
        self._storage_order: List[str] = []

    def store(self, memory_id, embedding, angle):
        self.memories[memory_id] = SimpleMemory(memory_id, embedding, angle)
        self._storage_order.append(memory_id)
        self._kdtree_dirty = True

    def finalize_groups(self):
        ids = self._storage_order
        n = len(ids)
        for i, mid in enumerate(ids):
            gid = i * self.n_groups // n
            self.mem_to_group[mid] = min(gid, self.n_groups - 1)

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

    def recall(self, query, top_k=10):
        self._rebuild_kdtree()
        if self._kdtree is None or len(self._kdtree_ids) == 0:
            return []
        results = []
        for mid in self._kdtree_ids:
            mem = self.memories[mid]
            sim = float(np.dot(query, mem.embedding) /
                       (np.linalg.norm(query) * np.linalg.norm(mem.embedding) + 1e-12))
            gid = self.mem_to_group.get(mid, 0)
            mult = 1.5 if (self.n_groups > 0 and
                           gid < len(self.group_flags) and
                           self.group_flags[gid]) else 1.0
            results.append((mid, max(0.0, sim * mult), sim))
        results.sort(key=lambda x: (-x[1], x[0]))
        return results[:top_k], results  # top_k + full ranking

    def reinforce(self, memory_id):
        if memory_id in self.memories and self.n_groups > 0:
            self.group_flags[self.mem_to_group[memory_id]] = True


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def build_field(n_memories=100, dim=32, n_groups=8):
    eng = GroupedEngine(n_groups)
    memories = {}
    for i in range(n_memories):
        angle = (i * 360.0 / n_memories) % 360
        mid = f"M{i:04d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim), angle)
    eng.finalize_groups()
    return eng, memories


def run_logged(query_angles, int_start, int_end, block, n_groups, seed):
    """Run trajectory with full per-step logging."""
    eng, memories = build_field(n_groups=n_groups)
    votes = {}
    rng = random.Random(seed)
    for mid in memories:
        votes[mid] = "yes" if rng.random() < 0.6 else "no"

    log = {
        "flags": [],        # frozenset of flagged gids BEFORE this step
        "recalled": [],
        "top1": [],
        "decisions": [],
        "boundary": [],     # (score rank 10, score rank 11)
        "margin": [],       # gids with members at ranks 11-20
    }

    for step, q_angle in enumerate(query_angles):
        query = make_embedding(q_angle)
        flags_before = frozenset(g for g, f in enumerate(eng.group_flags) if f)

        top, full = eng.recall(query, top_k=10)
        recalled = [r[0] for r in top]

        yes_w = 0.0
        no_w = 0.0
        for mid, score, _ in top:
            v = votes.get(mid, "abstain")
            if v == "yes":
                yes_w += score
            elif v == "no":
                no_w += score
        dec = "yes" if yes_w > no_w else ("no" if no_w > yes_w else "abstain")

        cutoff = full[9][1] if len(full) > 9 else 0.0
        next_s = full[10][1] if len(full) > 10 else 0.0
        margin_gids = set(eng.mem_to_group[r[0]] for r in full[10:20])

        in_int = int_start <= step < int_end
        top1 = recalled[0] if recalled else None
        if top1 and not (in_int and block):
            eng.reinforce(top1)

        log["flags"].append(flags_before)
        log["recalled"].append(recalled)
        log["top1"].append(top1)
        log["decisions"].append(dec)
        log["boundary"].append((cutoff, next_s))
        log["margin"].append(margin_gids)

    return log, eng, votes


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP27: Why does 7 groups produce H8 and 8 does not?")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(30))

print(f"\n  n_groups in {{7, 8}}, {len(seeds)} seeds, "
      f"intervention {int_start}-{int_end}")
print(f"  Full per-step logging: flags, recalls, boundary, margin")
print()

per_cfg = {}

for ng in (7, 8):
    cfg = {
        "late_flag_counts": [],       # # of late-flagged groups per seed
        "per_seed_washout": [],
        "per_seed_flips": [],
        "state_explained": 0,         # diff recalls explained by flag diff
        "unexplained_diff": 0,        # diff recalls with same flag state
        "feedback_events": 0,         # int arm flags group ctrl doesn't
        "total_diff_events": 0,
    }

    for seed in seeds:
        rng_q = random.Random(seed)
        q = [rng_q.uniform(0, 360) for _ in range(n_queries)]

        ctrl_log, ctrl_eng, _ = run_logged(q, 999, 999, False, ng, seed)
        int_log, int_eng, _ = run_logged(q, int_start, int_end, True, ng, seed)

        # Flags at step 39 (identical in both arms)
        f39 = ctrl_log["flags"][int_start - 1]
        # Control flags at step 70 = all flags set by end of window
        f70c = ctrl_log["flags"][int_end - 1]
        # Intervention flags at step 70 = same as step 39 (blocked)
        f70i = int_log["flags"][int_end - 1]

        late_flags = f70c - f39      # set during intervention in control
        cfg["late_flag_counts"].append(len(late_flags))

        # Post-washout divergence + per-event attribution
        diffs = []
        seed_flips = 0
        for i in range(int_end, n_queries):
            cset = set(ctrl_log["recalled"][i])
            iset = set(int_log["recalled"][i])
            diffs.append(len(cset ^ iset) / 10.0)

            if ctrl_log["decisions"][i] != int_log["decisions"][i]:
                seed_flips += 1

            # Attribution of differing members
            cflags = ctrl_log["flags"][i]
            iflags = int_log["flags"][i]
            for mid in cset ^ iset:
                gid = ctrl_eng.mem_to_group[mid]
                cfg["total_diff_events"] += 1
                if (gid in cflags) != (gid in iflags):
                    cfg["state_explained"] += 1
                else:
                    cfg["unexplained_diff"] += 1

            # Feedback: intervention flagged a group control hasn't
            if len(iflags - cflags) > 0 or len(cflags - iflags) > len(late_flags - iflags):
                pass  # measured below

        # Feedback events: flag sets that appear in int arm that ctrl
        # never had at same step (beyond the late-flag deficit)
        fb = 0
        for i in range(int_end, n_queries):
            extra_in_int = int_log["flags"][i] - ctrl_log["flags"][i]
            if extra_in_int:
                fb += 1
        cfg["feedback_events"] += fb

        cfg["per_seed_washout"].append(np.mean(diffs))
        cfg["per_seed_flips"].append(seed_flips)

    per_cfg[ng] = cfg

# ============================================================
# Results
# ============================================================
print("=" * 70)
print("RESULTS")
print("=" * 70)

for ng in (7, 8):
    c = per_cfg[ng]
    w = np.array(c["per_seed_washout"])
    f = np.array(c["per_seed_flips"])
    lf = np.array(c["late_flag_counts"])
    print(f"\n  n_groups={ng}:")
    print(f"    washout set_diff:   mean={w.mean():.4f} "
          f"median={np.median(w):.4f} max={w.max():.4f}")
    print(f"    flips:              total={f.sum()} "
          f"median/seed={np.median(f):.0f} max={f.max()}")
    print(f"    late flags (ctrl, 40-70): mean={lf.mean():.2f} "
          f"dist={np.bincount(lf)[1:] if len(lf)>0 else []}")
    tot = c["total_diff_events"]
    if tot:
        print(f"    diff recall events: {tot}")
        print(f"      state-explained (flag diff): {c['state_explained']} "
              f"({100*c['state_explained']/tot:.1f}%)")
        print(f"      unexplained (same flags):    {c['unexplained_diff']} "
              f"({100*c['unexplained_diff']/tot:.1f}%)")
    print(f"    feedback steps (int flags group ctrl lacks): "
          f"{c['feedback_events']}")

    # Per-seed distribution
    nz = [(s, c['per_seed_washout'][s], c['per_seed_flips'][s])
          for s in range(len(seeds)) if c['per_seed_washout'][s] > 0.001]
    print(f"    seeds with washout>0.001: {len(nz)}/{len(seeds)}")
    for s, wv, fv in sorted(nz, key=lambda x: -x[1])[:8]:
        print(f"      seed={seeds[s]:>3} washout={wv:.4f} flips={fv}")

# Direct comparison
print("\n" + "=" * 70)
print("7 vs 8 COMPARISON")
print("=" * 70)

w7 = np.array(per_cfg[7]["per_seed_washout"])
w8 = np.array(per_cfg[8]["per_seed_washout"])
lf7 = np.array(per_cfg[7]["late_flag_counts"])
lf8 = np.array(per_cfg[8]["late_flag_counts"])

print(f"\n  {'Metric':<40} {'ng=7':>10} {'ng=8':>10}")
print(f"  {'-'*62}")
print(f"  {'mean washout':<40} {w7.mean():>10.4f} {w8.mean():>10.4f}")
print(f"  {'total flips':<40} {per_cfg[7]['per_seed_flips'] and sum(per_cfg[7]['per_seed_flips']) or 0:>10} "
      f"{sum(per_cfg[8]['per_seed_flips']):>10}")
print(f"  {'mean late flags':<40} {lf7.mean():>10.2f} {lf8.mean():>10.2f}")
print(f"  {'seeds with divergence>0.001':<40} "
      f"{(w7>0.001).sum():>10} {(w8>0.001).sum():>10}")
print(f"  {'state-explained diff events':<40} "
      f"{per_cfg[7]['state_explained']:>10} {per_cfg[8]['state_explained']:>10}")
print(f"  {'unexplained diff events':<40} "
      f"{per_cfg[7]['unexplained_diff']:>10} {per_cfg[8]['unexplained_diff']:>10}")
print(f"  {'feedback events':<40} "
      f"{per_cfg[7]['feedback_events']:>10} {per_cfg[8]['feedback_events']:>10}")

# Is the difference driven by a few seeds?
print(f"\n  Per-seed washout (7):  "
      f"{['%.3f'%x for x in sorted(w7, reverse=True)[:10]]}")
print(f"  Per-seed washout (8):  "
      f"{['%.3f'%x for x in sorted(w8, reverse=True)[:10]]}")

# ============================================================
# Verdict
# ============================================================
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

tot7 = per_cfg[7]["total_diff_events"]
tot8 = per_cfg[8]["total_diff_events"]
se7 = per_cfg[7]["state_explained"] / max(tot7, 1)
se8 = per_cfg[8]["state_explained"] / max(tot8, 1)
fb7 = per_cfg[7]["feedback_events"]
fb8 = per_cfg[8]["feedback_events"]

print(f"\n  State-explained fraction: 7g={se7:.1%}  8g={se8:.1%}")
print(f"  Feedback events:          7g={fb7}      8g={fb8}")

if se7 > 0.9 and se8 > 0.9:
    print(f"\n  Post-washout recall differences are ~fully explained by")
    print(f"  contemporaneous flag-state differences. The mechanism is")
    print(f"  direct: a flag difference at step t changes recall at t.")
    if lf7.mean() > lf8.mean() * 1.5:
        print(f"  7 groups has more late-flagged groups "
              f"({lf7.mean():.1f} vs {lf8.mean():.1f}) — the")
        print(f"  partition leaves more groups unflagged at step 39,")
        print(f"  creating more causal substrate for the intervention.")
    else:
        print(f"  Similar late-flag counts ({lf7.mean():.1f} vs "
              f"{lf8.mean():.1f}) — the difference is in WHICH")
        print(f"  groups are late-flagged (boundary leverage), not how many.")
elif fb7 > 10 or fb8 > 10:
    print(f"\n  FEEDBACK DETECTED: intervention arms flag groups that")
    print(f"  control never flags. Flag-set divergence compounds")
    print(f"  post-washout — recall differences breed flag differences.")
else:
    print(f"\n  Mixed: partial state explanation, partial feedback.")
    print(f"  Examine per-seed breakdown.")
