"""
Exp35: Dose x Position factorial — what actually drives leverage?

Exp34 left two questions confounded across designs: whether
accumulation (k) and position (early/mid/late) contribute
independently, and whether they interact. This experiment runs a
single factorial inside one protocol.

Design:
  For each quiet seed (24), enumerate the induced group's natural
  post-window G-events (steps where a member lands top-1) on a
  force-flagged-at-70 baseline.

  Arms: k in {0,1,2,3,4} realized blocks at three positions:

    EARLY : suppress re-flag at event ordinals 1..k
    MID   : suppress at event ordinals 4..(3+k)
    LATE  : suppress at ordinals (N-k+1)..N  (last k of baseline)

  k=0 = baseline (no blocks).

  Event ordinals are counted within each arm's own trajectory;
  because suppression only acts at/after the first suppressed
  event, pre-treatment ordinals coincide with baseline's.

Model: washout ~ k + position + k:position (OLS on realized cells).
Unit of analysis: (seed, k, position) cells — no pseudoreplication
beyond the seed level clustering which is reported descriptively.

Predefined reading:
  beta_k    > 0 clearly   -> dose matters
  beta_pos  nonzero       -> position matters at equal dose
  beta_int  nonzero       -> dose and position interact
  all ~ 0               -> noise dominates; leverage is not
                           well-described by dose x position at all
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
            block_gid=None, block_ordinals=None):
    """Intervention arm with ordinal event blocking.

    force_flag_at/force_gid: set flag at that step (equalize at
    window end for quiet seeds).

    block_gid/block_ordinals: set of event ordinals at which to
    suppress. At the j-th post-window step where block_gid's member
    lands top-1, if j is in block_ordinals: unflag the group and
    suppress that reinforcement. Counted in the arm's own
    trajectory.

    Returns (recalled, top1s, info).
    """
    eng = build_field(n_groups=n_groups)
    recalled = []
    top1s = []
    g_event_count = 0
    n_realized_blocks = 0
    unflagged_now = False

    block_ordinals = block_ordinals or set()

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
                        and g_event_count in block_ordinals)

            if suppress:
                eng.unflag(block_gid)
                n_realized_blocks += 1
                unflagged_now = True
            else:
                eng.reinforce(t1)
                if unflagged_now and g1 == block_gid:
                    unflagged_now = False

    return recalled, top1s, {
        "n_realized_blocks": n_realized_blocks,
        "g_events_total": g_event_count,
    }


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP35: Dose x Position factorial")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(30))
NG = 7
K_VALUES = [0, 1, 2, 3, 4]
POSITIONS = ["early", "mid", "late"]

print(f"\n  ng={NG}, {len(seeds)} seeds")
print(f"  k in {K_VALUES}, positions {POSITIONS}")
print()

# Phase 1: classify + induced gid + baseline G-event count
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

    i_base, _, base_meta = run_arm(
        q, int_start, int_end, NG,
        force_flag_at=int_end, force_gid=gid, block_gid=gid)
    n_g = base_meta["g_events_total"]
    base_wash = np.mean([setdiff(c_recall[i], i_base[i])
                         for i in range(int_end, n_queries)])
    seed_info[seed] = {"gid": gid, "nat_wash": nat_wash, "q": q,
                       "c_recall": c_recall, "n_g": n_g,
                       "base_wash": base_wash}

quiet = [s for s in seeds if seed_info[s]["nat_wash"] <= 0.005]
print(f"  quiet seeds: {len(quiet)}\n")

# Phase 2: factorial sweep
cells = []   # (seed, k, position, n_realized, wash, delta)

for seed in quiet:
    info = seed_info[seed]
    N = info["n_g"]
    for k in K_VALUES:
        for pos in POSITIONS:
            if k == 0:
                ords = set()
            elif pos == "early":
                ords = set(range(1, k + 1))
            elif pos == "mid":
                ords = set(range(4, 4 + k))
            else:  # late
                ords = set(range(N - k + 1, N + 1))
            if pos == "late" and N - k + 1 < 1:
                continue  # not enough events for this cell
            i_recall, _, meta = run_arm(
                info["q"], int_start, int_end, NG,
                force_flag_at=int_end, force_gid=info["gid"],
                block_gid=info["gid"], block_ordinals=ords)
            wash = np.mean([setdiff(info["c_recall"][i], i_recall[i])
                            for i in range(int_end, n_queries)])
            cells.append({"seed": seed, "k": k, "pos": pos,
                          "n_realized": meta["n_realized_blocks"],
                          "wash": wash,
                          "delta": wash - info["base_wash"],
                          "n_g": N})

# Report factorial table
print(f"  Factorial table (mean delta over seeds):")
print(f"  {'k':>3} {'early':>8} {'mid':>8} {'late':>8}   "
      f"{'realized k (early/mid/late)':>30}")
for k in K_VALUES:
    row = {}
    nre = {}
    for pos in POSITIONS:
        cs = [c for c in cells if c["k"] == k and c["pos"] == pos]
        row[pos] = np.mean([c["delta"] for c in cs]) if cs else float("nan")
        nre[pos] = np.mean([c["n_realized"] for c in cs]) if cs else float("nan")
    print(f"  {k:>3} {row['early']:>8.4f} {row['mid']:>8.4f} "
          f"{row['late']:>8.4f}   "
          f"{nre['early']:>6.2f} {nre['mid']:>6.2f} {nre['late']:>6.2f}")

# Fit OLS: delta ~ k + pos_mid + pos_late + k*pos_mid + k*pos_late
print("\n" + "=" * 70)
print("OLS: delta ~ k + position + k:position")
print("=" * 70)

treated = [c for c in cells if c["k"] > 0]
if len(treated) > 10:
    X = []
    y = []
    for c in treated:
        pm = 1.0 if c["pos"] == "mid" else 0.0
        pl = 1.0 if c["pos"] == "late" else 0.0
        X.append([1.0, c["k"], pm, pl,
                  c["k"] * pm, c["k"] * pl])
        y.append(c["delta"])
    X = np.array(X); y = np.array(y)
    beta, res, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    n, p = X.shape
    sigma2 = ss_res / max(n - p, 1)
    cov = sigma2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))

    names = ["const", "k", "mid", "late", "k:mid", "k:late"]
    print(f"\n  n={n} treated cells, R2={r2:.3f}")
    print(f"  {'term':>8} {'beta':>9} {'se':>8} {'t':>7}")
    for name, b, s in zip(names, beta, se):
        t = b / s if s > 0 else float("nan")
        print(f"  {name:>8} {b:>9.4f} {s:>8.4f} {t:>7.2f}")

# Descriptive: per-seed paired comparison early vs late at k=4
print("\n  Paired seed-level check (early vs late, k=4):")
pairs = []
for seed in quiet:
    e = [c for c in cells if c["seed"] == seed and c["k"] == 4
         and c["pos"] == "early"]
    l = [c for c in cells if c["seed"] == seed and c["k"] == 4
         and c["pos"] == "late"]
    if e and l:
        pairs.append((e[0]["delta"], l[0]["delta"],
                      e[0]["n_realized"], l[0]["n_realized"]))
if pairs:
    d = np.array([a - b for a, b, _, _ in pairs])
    rd = np.array([re - rl for _, _, re, rl in pairs])
    print(f"    n={len(pairs)}  mean(early-late)={d.mean():.4f} "
          f" sd={d.std():.4f}  share early>late: "
          f"{np.mean(d > 0):.2f}")
    print(f"    realized-k diff (early-late): mean={rd.mean():.2f}")
    # how much of the early>late gap remains at matched realized dose?
    same_dose = [a - b for a, b, re, rl in pairs if re == rl]
    if same_dose:
        print(f"    at EQUAL realized dose (n={len(same_dose)}): "
              f"mean(early-late)={np.mean(same_dose):.4f}")
    # regression: delta_diff ~ realized_diff
    if rd.std() > 1e-9:
        b = np.polyfit(rd, d, 1)
        resid = d - np.polyval(b, rd)
        print(f"    after removing realized-dose effect: "
              f"mean resid={resid.mean():.4f}")

# Reanalysis on REALIZED dose, not programmed dose
print("\n" + "=" * 70)
print("REANALYSIS: delta ~ realized_k + position + realized_k:position")
print("=" * 70)

treated_r = [c for c in cells if c["n_realized"] > 0]
if len(treated_r) > 10:
    X = []
    y = []
    for c in treated_r:
        pm = 1.0 if c["pos"] == "mid" else 0.0
        pl = 1.0 if c["pos"] == "late" else 0.0
        X.append([1.0, c["n_realized"], pm, pl,
                  c["n_realized"] * pm, c["n_realized"] * pl])
        y.append(c["delta"])
    X = np.array(X); y = np.array(y)
    beta, res, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    n, p = X.shape
    sigma2 = ss_res / max(n - p, 1)
    cov = sigma2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))

    names = ["const", "k_real", "mid", "late", "k:mid", "k:late"]
    print(f"\n  n={n} realized-treated cells, R2={r2:.3f}")
    print(f"  {'term':>8} {'beta':>9} {'se':>8} {'t':>7}")
    for name, b, s in zip(names, beta, se):
        t = b / s if s > 0 else float("nan")
        print(f"  {name:>8} {b:>9.4f} {s:>8.4f} {t:>7.2f}")
    print("\n  NOTE: cells from the same seed share a trajectory —")
    print("  treat t-values descriptively, not as strong inference.")

# TRUE within estimator: de-mean y AND the FULL regressor vector
# per seed (equivalent to seed fixed effects). Previous version
# de-meaned only y and k_realized — wrong.
print("\n  Within estimator (all regressors de-meaned per seed):")
import collections
by_seed = collections.defaultdict(list)
for c in treated_r:
    by_seed[c["seed"]].append(c)

def build_X(c):
    pm = 1.0 if c["pos"] == "mid" else 0.0
    pl = 1.0 if c["pos"] == "late" else 0.0
    r = c["n_realized"]
    return np.array([r, pm, pl, r * pm, r * pl])

dm_X, dm_y = [], []
for seed, cs in by_seed.items():
    if len(cs) < 2:
        continue
    Xs = np.array([build_X(c) for c in cs])
    Xbar = Xs.mean(axis=0)
    ybar = np.mean([c["delta"] for c in cs])
    for c, x in zip(cs, Xs):
        dm_X.append(x - Xbar)
        dm_y.append(c["delta"] - ybar)
dm_X = np.array(dm_X); dm_y = np.array(dm_y)
if len(dm_y) > 10:
    b2, *_ = np.linalg.lstsq(dm_X, dm_y, rcond=None)
    yhat = dm_X @ b2
    ss_res = float(((dm_y - yhat) ** 2).sum())
    ss_tot = float((dm_y ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    names = ["k_real", "mid", "late", "k:mid", "k:late"]
    print(f"    n={len(dm_y)} cells, within R2={r2:.3f}")
    for name, b in zip(names, b2):
        print(f"    beta_{name:>8} = {b:+.4f}")
    print("    (descriptive within-seed associations; realized_k is")
    print("     post-treatment/trajectory-dependent — not exogenous dose)")

# Cleanest descriptive contrast: k=1 arms realize exactly 1 block
print("\n  Cleanest contrast — k=1, exactly one realized block each:")
for pos in POSITIONS:
    cs = [c for c in cells if c["k"] == 1 and c["pos"] == pos]
    if cs:
        print(f"    {pos:>5}: mean delta={np.mean([c['delta'] for c in cs]):.4f} "
              f"(realized={np.mean([c['n_realized'] for c in cs]):.2f}, "
              f"n={len(cs)})")

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
print("""
  Reading (decided before running):
   beta_k large & significant      -> dose confirmed causal
   position terms ~0               -> position dead at equal dose
   interaction terms nonzero       -> dose value depends on place
   R2 low                          -> neither factor explains much;
                                      trajectory particulars dominate
""")
