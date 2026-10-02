"""
Exp33: What determines a transition's causal leverage?

Exp32 showed count explains the duration gradient but is not a
sufficient statistic: early_k > late_k at equal count, and
within-duration correlations are weak. The question shifts from
"how many" to "which, when, and in what system state".

Design: ONE blocked transition, variable position.

Because flags are monotone (once set, a re-flag is a no-op), a
single-event intervention must be a PULSE: at chosen step t_p,
unflag the induced group and suppress the next attempt where it
would land top-1, then resume normal dynamics. Every arm has
exactly ONE denied self-correction; only its position varies.

Baseline arm: same trajectory, no pulse (0 blocked transitions).
washout(pulse at t_p) - washout(baseline) isolates the leverage
of one transition at position t_p.

Per pulse position, log the margin between the induced group's
best member and the actual top-1 at that step — the hypothesis
is that leverage concentrates where the group sits near the
rank-1 boundary (a denied transition near a boundary changes
reinforcement; one far from it changes nothing observable).

Positions: t_p in {72,80,88,96,104,112} (post-window).
Seeds: the 24 quiet seeds from Exp30/31/32. ng=7.
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
            pulse_at=None, pulse_gid=None):
    """Intervention arm with an optional single-transition pulse.

    At step pulse_at: unflag pulse_gid. The NEXT step where that
    group's member lands top-1 has its reinforcement suppressed
    (one denied transition); all others pass through normally.
    Returns (recalled_sets, top1s, pulse_info).
    """
    eng = build_field(n_groups=n_groups)
    recalled = []
    top1s = []
    pulse_active = False   # flag is off, waiting for next attempt
    suppressed_step = None
    margin_at_pulse = None
    gid_top1_gap_at_pulse = None

    for step, qa in enumerate(query_angles):
        query = make_embedding(qa)
        in_int = int_start <= step < int_end
        post = step >= int_end

        if step == pulse_at and pulse_gid is not None:
            eng.unflag(pulse_gid)
            pulse_active = True

        top, full = eng.recall(query)
        ids = [m for m, _ in top]
        recalled.append(ids)
        t1 = ids[0] if ids else None
        top1s.append(t1)

        # measure how close the induced group is to top-1 this step
        if post and pulse_gid is not None:
            full_d = dict(full)
            gid_scores = [s for m, s in full
                          if eng.mem_to_group.get(m) == pulse_gid]
            if gid_scores and full:
                gid_best = max(gid_scores)
                t1_score = full[0][1]
                if step == pulse_at:
                    gid_top1_gap_at_pulse = t1_score - gid_best

        if t1 and not in_int:
            g1 = eng.mem_to_group.get(t1)
            if (pulse_active and g1 == pulse_gid
                    and suppressed_step is None):
                # suppress this one transition
                suppressed_step = step
                pulse_active = False
            else:
                eng.reinforce(t1)

    return recalled, top1s, {
        "suppressed_step": suppressed_step,
        "gap_at_pulse": gid_top1_gap_at_pulse,
    }


def setdiff(a, b):
    return len(set(a) ^ set(b)) / 10.0


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP33: What determines a transition's causal leverage?")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(30))
NG = 7
POSITIONS = [72, 80, 88, 96, 104, 112]

print(f"\n  ng={NG}, {len(seeds)} seeds, pulse positions {POSITIONS}")
print(f"  one denied transition per arm\n")

# Phase 1: classify + induced gid
seed_info = {}
for seed in seeds:
    rng_q = random.Random(seed)
    q = [rng_q.uniform(0, 360) for _ in range(n_queries)]
    c_recall, c_top1, _ = run_arm(q, 999, 999, NG)
    i_recall, _, _ = run_arm(q, int_start, int_end, NG)
    nat_wash = np.mean([setdiff(c_recall[i], i_recall[i])
                        for i in range(int_end, n_queries)])
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
                       "q": q, "c_recall": c_recall}

quiet = [s for s in seeds if seed_info[s]["nat_wash"] <= 0.005]
print(f"  quiet seeds: {len(quiet)}\n")

# Phase 2: baseline (no pulse) + pulse at each position
base_wash = {}
for seed in quiet:
    info = seed_info[seed]
    i_recall, _, _ = run_arm(info["q"], int_start, int_end, NG)
    base_wash[seed] = np.mean([setdiff(info["c_recall"][i],
                                      i_recall[i])
                               for i in range(int_end, n_queries)])

print(f"  Baseline (0 blocked transitions): "
      f"mean wash={np.mean(list(base_wash.values())):.4f}\n")

print(f"  {'t_p':>5} {'mean wash':>10} {'delta':>8} {'P(div)':>7} "
      f"{'mean gap':>9} {'supp_rate':>9}")

pulse_data = []   # (seed, t_p, wash, gap, suppressed_or_not)
for tp in POSITIONS:
    washs, gaps, supp = [], [], 0
    ndiv = 0
    for seed in quiet:
        info = seed_info[seed]
        i_recall, _, meta = run_arm(
            info["q"], int_start, int_end, NG,
            pulse_at=tp, pulse_gid=info["gid"])
        wash = np.mean([setdiff(info["c_recall"][i], i_recall[i])
                        for i in range(int_end, n_queries)])
        washs.append(wash)
        if meta["gap_at_pulse"] is not None:
            gaps.append(meta["gap_at_pulse"])
        if meta["suppressed_step"] is not None:
            supp += 1
        if wash > 0.005:
            ndiv += 1
        pulse_data.append((seed, tp, wash,
                           meta["gap_at_pulse"],
                           meta["suppressed_step"] is not None))
    mean_w = np.mean(washs)
    delta = mean_w - np.mean(list(base_wash.values()))
    print(f"  {tp:>5} {mean_w:>10.4f} {delta:>8.4f} "
          f"{ndiv/len(quiet):>7.2f} {np.mean(gaps) if gaps else float('nan'):>9.4f} "
          f"{supp/len(quiet):>9.2f}")

# Per-pulse leverage vs gap-to-top1 at pulse time
print("\n  Leverage vs rank-1 proximity at pulse time:")
with_gap = [(w, g) for s, tp, w, g, sup in pulse_data
            if g is not None]
if with_gap:
    gs = np.array([g for _, g in with_gap])
    ws = np.array([w for w, _ in with_gap])
    r = np.corrcoef(gs, ws)[0, 1]
    print(f"    corr(gap_at_pulse, washout) = {r:+.3f} "
          f"(n={len(with_gap)})")
    # binned
    lo = [w for w, g in with_gap if g < np.median(gs)]
    hi = [w for w, g in with_gap if g >= np.median(gs)]
    print(f"    small gap (near boundary): mean wash "
          f"{np.mean(lo):.4f} (n={len(lo)})")
    print(f"    large gap (far from it):   mean wash "
          f"{np.mean(hi):.4f} (n={len(hi)})")

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

# which position had the largest delta?
best = max(POSITIONS,
           key=lambda p: np.mean([w for s, t, w, g, sp in pulse_data
                                  if t == p]))
mean_by_pos = {p: np.mean([w for s, t, w, g, sp in pulse_data
                           if t == p]) for p in POSITIONS}
base = np.mean(list(base_wash.values()))

print(f"\n  baseline wash (no pulse): {base:.4f}")
print(f"  best pulse position: t={best} "
      f"(wash={mean_by_pos[best]:.4f})")
spread = max(mean_by_pos.values()) - min(mean_by_pos.values())
print(f"  position spread: {spread:.4f}")

if spread > 0.05:
    print(f"\n  POSITION MATTERS: one identical blocked transition")
    print(f"  produces different divergence depending on WHERE in the")
    print(f"  trajectory it lands. Leverage is positional/contextual,")
    print(f"  not merely countable.")
elif with_gap and abs(r) > 0.3:
    print(f"\n  PROXIMITY MATTERS: leverage tracks how close the group")
    print(f"  was to rank-1 at pulse time (r={r:+.3f}), more than the")
    print(f"  position itself.")
else:
    print(f"\n  SINGLE TRANSITIONS are weak: one pulse barely moves")
    print(f"  the outcome regardless of position. Leverage is mostly")
    print(f"  a property of accumulation, not individual events.")
