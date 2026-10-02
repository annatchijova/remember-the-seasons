"""
Exp34: Event-indexed leverage — one REALIZED block per arm.

Exp33's pulse had a defect: supp_rate varied by position (0.71 at
t=72, 0.46 at t=112) because the block was conditional on the
group landing top-1 after the pulse. Arms were not delivering the
same realized intervention.

This arm works in EVENT space instead of wall-clock:

  1. For each quiet seed, run a baseline trajectory where the
     induced group is force-flagged at t=70 (kills the natural
     asymmetry; identical state at the boundary).
  2. Enumerate G-events: post-window steps where the induced
     group's member lands top-1 (on the baseline trajectory).
  3. Arm(j): at step tau_j (the j-th G-event), unflag the group
     just before recall, suppress that single reinforcement, then
     resume normal dynamics. The flag re-sets at the NEXT G-event
     (or never, if none remain).

  Every arm realizes exactly ONE denied transition. Position is
  the EVENT INDEX j, not a timestamp.

For each arm, record:
  - washout divergence vs control
  - remaining G-events after the block (downstream opportunities)
  - steps until flag re-set (asymmetry lifetime in steps)

Hypotheses under test:
  H_position: leverage = f(event index j)
  H_shadow:   leverage = f(downstream causal opportunities
                          remaining after the block)

If shadow: two blocks at the same j but different seeds with
different remaining-opportunity counts should differ; regress
washout on remaining-events controlling for j.
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


def setdiff(a, b):
    return len(set(a) ^ set(b)) / 10.0


def run_arm(query_angles, int_start, int_end, n_groups,
            force_flag_at=None, force_gid=None,
            block_event_idx=None, block_gid=None):
    """Intervention arm.

    force_flag_at/force_gid: at that step, set the group's flag
    (equalize state at window end for quiet seeds).

    block_event_idx/block_gid: at the block_event_idx-th post-window
    step where block_git's member lands top-1, unflag just before
    recall and suppress that reinforcement. Exactly one realized
    block. Flag re-sets at the next such event.

    Returns (recalled, top1s, info dict).
    """
    eng = build_field(n_groups=n_groups)
    recalled = []
    top1s = []
    g_event_count = 0
    blocked_at = None
    flag_restored_at = None
    unflagged_now = False

    for step, qa in enumerate(query_angles):
        query = make_embedding(qa)
        in_int = int_start <= step < int_end
        post = step >= int_end

        if (force_flag_at is not None and step == force_flag_at
                and force_gid is not None):
            eng.group_flags[force_gid] = True

        top, _ = eng.recall(query)
        ids = [m for m, _ in top]
        recalled.append(ids)
        t1 = ids[0] if ids else None
        top1s.append(t1)

        if t1 and not in_int:
            g1 = eng.mem_to_group.get(t1)
            is_g_event = post and g1 == block_gid

            if is_g_event:
                g_event_count += 1

            suppress = (is_g_event
                        and block_event_idx is not None
                        and g_event_count == block_event_idx
                        and blocked_at is None)

            if suppress:
                eng.unflag(block_gid)
                blocked_at = step
                unflagged_now = True
            else:
                eng.reinforce(t1)
                if unflagged_now and g1 == block_gid:
                    flag_restored_at = step
                    unflagged_now = False

    return recalled, top1s, {
        "blocked_at": blocked_at,
        "flag_restored_at": flag_restored_at,
        "g_events_total": g_event_count,
    }


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP34: Event-indexed leverage — one realized block per arm")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(30))
NG = 7

# Phase 1: classify seeds, induced gid, baseline G-event counts
print("\n  Phase 1: seeds + induced groups + natural G-events")
seed_info = {}
for seed in seeds:
    rng_q = random.Random(seed)
    q = [rng_q.uniform(0, 360) for _ in range(n_queries)]

    c_recall, c_top1, _ = run_arm(q, 999, 999, NG)
    i_recall, i_top1, _ = run_arm(q, int_start, int_end, NG)
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

    # baseline with force-flag at 70: enumerate natural G-events
    i_base, i_base_t1, base_meta = run_arm(
        q, int_start, int_end, NG,
        force_flag_at=int_end, force_gid=gid,
        block_gid=gid)
    n_g = base_meta["g_events_total"]
    base_wash = np.mean([setdiff(c_recall[i], i_base[i])
                         for i in range(int_end, n_queries)])

    seed_info[seed] = {"gid": gid, "nat_wash": nat_wash,
                       "q": q, "c_recall": c_recall,
                       "n_g": n_g, "base_wash": base_wash}

quiet = [s for s in seeds if seed_info[s]["nat_wash"] <= 0.005]
print(f"  quiet seeds: {len(quiet)}")
print(f"  G-events per seed (post-window top-1 in induced group):")
gdist = {}
for s in quiet:
    gdist[seed_info[s]["n_g"]] = gdist.get(seed_info[s]["n_g"], 0) + 1
print(f"    {dict(sorted(gdist.items()))}")

max_j = max(seed_info[s]["n_g"] for s in quiet)
max_j = min(max_j, 8)
print(f"  sweeping event index j in 1..{max_j}")

# Phase 2: one realized block at event index j
print(f"\n  Phase 2: block exactly the j-th G-event")
print(f"  {'j':>4} {'n arms':>7} {'realized':>8} {'mean wash':>10} "
      f"{'mean delta':>10}")

rows = []   # (seed, j, wash, delta, g_events, blocked_at, remaining)
for j in range(1, max_j + 1):
    washs, deltas, realized = [], [], 0
    for seed in quiet:
        info = seed_info[seed]
        if info["n_g"] < j:
            continue   # no j-th event exists — arm undefined
        i_recall, _, meta = run_arm(
            info["q"], int_start, int_end, NG,
            force_flag_at=int_end, force_gid=info["gid"],
            block_event_idx=j, block_gid=info["gid"])
        wash = np.mean([setdiff(info["c_recall"][i], i_recall[i])
                        for i in range(int_end, n_queries)])
        delta = wash - info["base_wash"]
        washs.append(wash); deltas.append(delta)
        remaining = info["n_g"] - j
        rows.append((seed, j, wash, delta, info["n_g"],
                     meta["blocked_at"], remaining,
                     meta["flag_restored_at"]))
        if meta["blocked_at"] is not None:
            realized += 1
    if washs:
        print(f"  {j:>4} {len(washs):>7} {realized:>8} "
              f"{np.mean(washs):>10.4f} {np.mean(deltas):>10.4f}")

# Phase 3: position vs shadow
print("\n  Phase 3: leverage ~ event index vs ~ remaining opportunities")
rs = [r for r in rows if r[5] is not None]  # realized blocks only
if rs:
    js = np.array([r[1] for r in rs], float)
    rem = np.array([r[6] for r in rs], float)
    dl = np.array([r[3] for r in rs], float)
    print(f"    n realized blocks: {len(rs)}")
    print(f"    corr(event index j, delta)     = "
          f"{np.corrcoef(js, dl)[0,1]:+.3f}")
    print(f"    corr(remaining events, delta)  = "
          f"{np.corrcoef(rem, dl)[0,1]:+.3f}")
    print(f"    corr(j, remaining)             = "
          f"{np.corrcoef(js, rem)[0,1]:+.3f}")

    # partial: control for j, does remaining still predict?
    # simple: residualize delta on j, correlate with remaining
    if js.std() > 0 and rem.std() > 0:
        bj = np.polyfit(js, dl, 1)
        resid_j = dl - np.polyval(bj, js)
        print(f"    corr(residual delta | j, remaining) = "
              f"{np.corrcoef(rem, resid_j)[0,1]:+.3f}")
        br = np.polyfit(rem, dl, 1)
        resid_r = dl - np.polyval(br, rem)
        print(f"    corr(residual delta | remaining, j) = "
              f"{np.corrcoef(js, resid_r)[0,1]:+.3f}")

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
print("""
  Interpretation guide (decided before looking at significance):
  - |corr(index)| dominant over |corr(remaining)| -> H_position
  - |corr(remaining)| dominant, survives controlling for j
    -> H_shadow (downstream opportunity count is the mechanism)
  - both weak -> single realized blocks are near-noise; leverage
    needs accumulation, not placement.
""")

if rs:
    ci = abs(np.corrcoef(js, dl)[0, 1])
    cr = abs(np.corrcoef(rem, dl)[0, 1])
    if cr > ci and cr > 0.25:
        print("  SHADOW WINS: remaining downstream opportunities predict")
        print("  leverage better than raw event index. 'Early' matters")
        print("  because more future is still reachable, not because")
        print("  earliness is magical.")
    elif ci > cr and ci > 0.25:
        print("  POSITION WINS: event index predicts leverage better")
        print("  than remaining-opportunity count. Ordinal position")
        print("  carries something beyond reachable-future count.")
    elif max(ci, cr) <= 0.25:
        print("  NEITHER: single realized blocks are too small to rank.")
        print("  Leverage is a property of accumulation over several")
        print("  denied transitions, not of any one transition.")
    else:
        print("  CONFUSED: both predictors comparable. Event index and")
        print("  shadow length are entangled in this trajectory class.")
