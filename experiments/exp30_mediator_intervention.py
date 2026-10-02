"""
Exp30: Causal mediator intervention — does the late-flag -> top-1
-> reinforcement chain actually mediate divergence?

Exp27/29 described a correlational story: late flags exist, flag
diffs sometimes change top-1 (19.8%), divergence grows slowly.
This experiment manipulates each link directly.

Hypothesis chain:
  unflagged group at t=39 -> rank-1 susceptible ->
  top-1 differs -> different reinforcement -> persistent divergence

Arms (same partition, same queries, same state through t=39):

  natural      Exp27/29 baseline (blocked reinforcement 40-70)
  saturate     all group flags = True at t=39 in intervention arm
               -> kills flag asymmetry; divergence should collapse
  rescue       flag ONLY the groups control late-flags (40-70),
               at t=39 in intervention arm
               -> if specific late groups are the substrate,
               divergence collapses
  induce       on a NON-divergent seed: unflag one active group at
               t=39 in intervention arm
               -> if late-flag absence is sufficient, divergence
               appears
  top1_block   natural intervention until t=70; post-washout the
               intervention arm does NOT reinforce at all
               -> tests whether continued reinforcement is needed
               to sustain divergence
  top1_swap    natural intervention until t=70; post-washout the
               intervention arm reinforces CONTROL's top-1 instead
               of its own
               -> tests whether the reinforcement-target channel
               mediates amplification (flag sets should converge)

Predefined criteria:
  - Saturate/rescue collapsing divergence => late flags NECESSARY
  - Induce producing divergence => unset flag SUFFICIENT
  - top1_swap collapsing => reinforcement channel is the mediator
  - top1_block: if divergence freezes (doesn't grow) => continued
    reinforcement is the amplifier, not just the substrate
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
        if self._kdtree is None:
            return [], []
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
            mode="natural", ctrl_top1=None, rescue_groups=None,
            induce_gid=None):
    """Run one arm with optional manipulation.

    mode:
      natural    — normal reinforcement except blocked in window
      saturate   — all flags True at int_start
      rescue     — flag rescue_groups at int_start
      induce     — unflag induce_gid at int_start
      top1_block — post-washout: no reinforcement
      top1_swap  — post-washout: reinforce ctrl's top-1
    Returns (recalled_sets, top1s, flag_dists_vs_none)
    """
    eng = build_field(n_groups=n_groups)
    recalled = []
    top1s = []
    late_controlled = False

    for step, qa in enumerate(query_angles):
        query = make_embedding(qa)
        in_int = int_start <= step < int_end
        post = step >= int_end

        # Manipulations at the intervention boundary
        if step == int_start:
            if mode == "saturate":
                eng.group_flags = [True] * eng.n_groups
            elif mode == "rescue" and rescue_groups:
                for g in rescue_groups:
                    eng.group_flags[g] = True
            elif mode == "induce" and induce_gid is not None:
                eng.unflag(induce_gid)

        top, _ = eng.recall(query)
        ids = [m for m, _ in top]
        recalled.append(ids)
        t1 = ids[0] if ids else None
        top1s.append(t1)

        # Reinforcement policy per mode
        if mode == "top1_block" and post:
            pass  # no reinforcement post-washout
        elif mode == "top1_swap" and post and ctrl_top1:
            eng.reinforce(ctrl_top1[step])  # reinforce CTRL's choice
        elif not (in_int):
            if t1:
                eng.reinforce(t1)

    return recalled, top1s, eng


def setdiff(a, b):
    return len(set(a) ^ set(b)) / 10.0


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP30: Causal mediator intervention")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(30))
NG = 7

print(f"\n  n_groups={NG}, seeds={len(seeds)}, "
      f"intervention {int_start}-{int_end}")
print()

results = []

for seed in seeds:
    rng_q = random.Random(seed)
    q = [rng_q.uniform(0, 360) for _ in range(n_queries)]

    # Natural pair
    c_recall, c_top1, eng_c = run_arm(q, 999, 999, NG)
    i_recall, i_top1, eng_i = run_arm(q, int_start, int_end, NG)

    nat_wash = np.mean([setdiff(c_recall[i], i_recall[i])
                        for i in range(int_end, n_queries)])

    # Control's late flags (groups flagged during 40-70 window)
    # Rebuild control flag history
    eng_c2 = build_field(n_groups=NG)
    flags39 = eng_c2.flagset()
    late = set()
    for step, qa in enumerate(q):
        query = make_embedding(qa)
        top, _ = eng_c2.recall(query)
        if step == int_start:
            flags39 = eng_c2.flagset()
        if top:
            eng_c2.reinforce(top[0][0])
        if step == int_end - 1:
            late = eng_c2.flagset() - flags39

    row = {"seed": seed, "natural": nat_wash, "n_late": len(late)}

    if nat_wash > 0.005:
        # Divergent seed — run the manipulation arms
        # saturate: all flags on at step 40
        s_recall, _, _ = run_arm(q, int_start, int_end, NG,
                                 mode="saturate")
        row["saturate"] = np.mean([setdiff(c_recall[i], s_recall[i])
                                   for i in range(int_end, n_queries)])

        # rescue: flag only ctrl's late groups at step 40
        r_recall, _, _ = run_arm(q, int_start, int_end, NG,
                                 mode="rescue", rescue_groups=late)
        row["rescue"] = np.mean([setdiff(c_recall[i], r_recall[i])
                                 for i in range(int_end, n_queries)])

        # top1_block: no reinforcement post-washout
        b_recall, _, _ = run_arm(q, int_start, int_end, NG,
                                 mode="top1_block")
        row["top1_block"] = np.mean([setdiff(c_recall[i], b_recall[i])
                                     for i in range(int_end, n_queries)])

        # top1_swap: reinforce ctrl's top-1 post-washout
        w_recall, _, _ = run_arm(q, int_start, int_end, NG,
                                 mode="top1_swap", ctrl_top1=c_top1)
        row["top1_swap"] = np.mean([setdiff(c_recall[i], w_recall[i])
                                    for i in range(int_end, n_queries)])
        row["type"] = "DIVERGENT"
    else:
        # Non-divergent seed — induce: unflag an active group
        # Pick the group ctrl reinforced most during the window
        eng_c3 = build_field(n_groups=NG)
        reinforce_count = {}
        for step, qa in enumerate(q):
            query = make_embedding(qa)
            top, _ = eng_c3.recall(query)
            if top:
                eng_c3.reinforce(top[0][0])
                if int_start <= step < int_end:
                    g = eng_c3.mem_to_group[top[0][0]]
                    reinforce_count[g] = reinforce_count.get(g, 0) + 1
        induce_gid = (max(reinforce_count, key=reinforce_count.get)
                      if reinforce_count else 0)
        d_recall, _, _ = run_arm(q, int_start, int_end, NG,
                                 mode="induce", induce_gid=induce_gid)
        row["induce"] = np.mean([setdiff(c_recall[i], d_recall[i])
                                 for i in range(int_end, n_queries)])
        row["type"] = "quiet"

    results.append(row)

# ============================================================
# Results
# ============================================================
print("=" * 70)
print("RESULTS")
print("=" * 70)

div = [r for r in results if r["type"] == "DIVERGENT"]
quiet = [r for r in results if r["type"] == "quiet"]

print(f"\n  DIVERGENT seeds (natural > 0.005): {len(div)}")
print(f"  {'seed':>5} {'natural':>8} {'saturate':>9} {'rescue':>8} "
      f"{'t1block':>8} {'t1swap':>8} {'late':>5}")
print(f"  {'-'*55}")
for r in div:
    print(f"  {r['seed']:>5} {r['natural']:>8.4f} "
          f"{r.get('saturate',0):>9.4f} {r.get('rescue',0):>8.4f} "
          f"{r.get('top1_block',0):>8.4f} {r.get('top1_swap',0):>8.4f} "
          f"{r['n_late']:>5}")

if div:
    print(f"\n  Means: natural={np.mean([r['natural'] for r in div]):.4f} "
          f"saturate={np.mean([r.get('saturate',0) for r in div]):.4f} "
          f"rescue={np.mean([r.get('rescue',0) for r in div]):.4f} "
          f"t1block={np.mean([r.get('top1_block',0) for r in div]):.4f} "
          f"t1swap={np.mean([r.get('top1_swap',0) for r in div]):.4f}")

print(f"\n  QUIET seeds (natural <= 0.005): {len(quiet)}")
induced = [r for r in quiet if r.get("induce", 0) > 0.005]
print(f"  {'seed':>5} {'natural':>8} {'induce':>8} {'late':>5}")
print(f"  {'-'*30}")
for r in quiet:
    tag = " <== DIVERGED" if r.get("induce", 0) > 0.005 else ""
    print(f"  {r['seed']:>5} {r['natural']:>8.4f} "
          f"{r.get('induce',0):>8.4f} {r['n_late']:>5}{tag}")

print(f"\n  Induced divergence: {len(induced)}/{len(quiet)} quiet seeds")

# ============================================================
# Verdict
# ============================================================
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

if div:
    mn = np.mean([r["natural"] for r in div])
    ms = np.mean([r.get("saturate", 0) for r in div])
    mr = np.mean([r.get("rescue", 0) for r in div])
    mb = np.mean([r.get("top1_block", 0) for r in div])
    mw = np.mean([r.get("top1_swap", 0) for r in div])

    print(f"\n  Necessity tests (divergent seeds, n={len(div)}):")
    print(f"    natural={mn:.4f}")
    print(f"    saturate={ms:.4f} -> "
          f"{'NECESSARY (collapsed)' if ms < mn*0.3 else 'still diverges'}")
    print(f"    rescue={mr:.4f} -> "
          f"{'NECESSARY (collapsed)' if mr < mn*0.3 else 'still diverges'}")
    print(f"\n  Mediator tests:")
    print(f"    top1_block={mb:.4f} -> "
          f"{'amplifier needs reinforcement' if mb < mn*0.7 else 'divergence persists without reinforcement'}")
    print(f"    top1_swap={mw:.4f} -> "
          f"{'reinforcement channel mediates (converged)' if mw < mn*0.3 else 'flag divergence survives same-target'}")
    print(f"\n  Sufficiency test (quiet seeds, n={len(quiet)}):")
    print(f"    induced: {len(induced)}/{len(quiet)} "
          f"-> {'SUFFICIENT' if len(induced) > len(quiet)*0.3 else 'NOT sufficient'}")
