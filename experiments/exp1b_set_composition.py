"""
Exp1b: Set composition with a configuration designed to give propagation
its BEST chance to change the result set.

If propagation STILL can't change the set here, the hypothesis is dead.
If it CAN, we've found the boundary condition.
"""
import sys
import numpy as np

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT, INHIBITORY


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def result_ids(results):
    if hasattr(results, 'results'):
        return {r.memory.memory_id for r in results.results}
    return {r.memory.memory_id for r in results}


def result_scores(results):
    if hasattr(results, 'results'):
        return {r.memory.memory_id: round(r.final_score, 6) for r in results.results}
    return {r.memory.memory_id: round(r.final_score, 6) for r in results}


query = make_embedding(0, dim=32)

# 60 memories spread around the circle. K_NEIGHBORS=6 means each cell
# has ~6 k-NN neighbors. After 2 hops, BFS reaches ~6^2=36 cells (with
# overlaps, fewer unique). With 60 cells, some are unreachable by k-NN
# alone but reachable through RESONANT links.

# X: far from query (78 degrees, cos ≈ 0.208), REINFORCED
# At 78°, X is NOT in flat top-k (too far) but has positive cosine
# so RESONANT boost helps rather than hurts.
X_angle = 78

# 5 anchors near query, all with RESONANT links to X
anchors = {"A0": 3, "A1": 7, "A2": 12, "A3": 16, "A4": 20}

# Noise: 56 memories spread around the circle, avoiding 0-15 and 115-125
import random
rng = random.Random(42)
noise = {}
used = set(anchors.values()) | {X_angle}
for i in range(56):
    while True:
        a = rng.uniform(0, 360)
        # avoid near query and near X
        if min(abs(a - 0), abs(a - 360)) > 22 and abs(a - X_angle) > 8:
            if a not in used:
                used.add(a)
                noise[f"N{i}"] = a
                break

print(f"Field: {len(anchors) + 1 + len(noise)} memories")
print(f"X at {X_angle}deg, REINFORCED, with RESONANT links from {list(anchors.keys())}")

# B0: flat top-k
b0 = MinimalRaven(hops=0, links_on=False, state_on=False,
                   recency_on=False, rescue_on=False,
                   auto_contradiction=False, k_neighbors=6)
for mid, ang in anchors.items():
    b0.store(mid, make_embedding(ang, 32))
b0.store("X", make_embedding(X_angle, 32), state=State.REINFORCED)
for mid, ang in noise.items():
    b0.store(mid, make_embedding(ang, 32))

# B1: flat top-k + state + recency
b1 = MinimalRaven(hops=0, links_on=False, state_on=True,
                   recency_on=True, rescue_on=False,
                   auto_contradiction=False, k_neighbors=6)
for mid, ang in anchors.items():
    b1.store(mid, make_embedding(ang, 32))
b1.store("X", make_embedding(X_angle, 32), state=State.REINFORCED)
for mid, ang in noise.items():
    b1.store(mid, make_embedding(ang, 32))

# B4: full raven with RESONANT links to X
b4 = MinimalRaven(hops=2, links_on=True, state_on=True,
                  recency_on=False, rescue_on=True,
                  auto_contradiction=False, k_neighbors=6)
for mid, ang in anchors.items():
    b4.store(mid, make_embedding(ang, 32))
b4.store("X", make_embedding(X_angle, 32), state=State.REINFORCED)
for mid, ang in noise.items():
    b4.store(mid, make_embedding(ang, 32))
# RESONANT links: each anchor -> X
for anchor_id in anchors:
    b4.add_link(anchor_id, "X", RESONANT)

top_k = 10
out_b0 = b0.recall_flat_topk(query, top_k=top_k, state_on=False, recency_on=False)
out_b1 = b1.recall_flat_topk(query, top_k=top_k, state_on=True, recency_on=True)
out_b4 = b4.recall(query, top_k=top_k)

set_b0 = result_ids(out_b0)
set_b1 = result_ids(out_b1)
set_b4 = result_ids(out_b4)

print(f"\nB0 (flat top-k):     {sorted(set_b0)}")
print(f"  X in B0:           {'X' in set_b0}")
print(f"B1 (top-k + meta):   {sorted(set_b1)}")
print(f"  X in B1:           {'X' in set_b1}")
print(f"B4 (full dynamics):  {sorted(set_b4)}")
print(f"  X in B4:           {'X' in set_b4}")

# B4 source detail for X
for r in out_b4.results:
    if r.memory.memory_id == "X":
        print(f"  X in B4: source={r.source}, hop={r.hop_distance}, score={r.final_score:.6f}")
        break

only_b4 = set_b4 - set_b0
only_b4_vs_b1 = set_b4 - set_b1
print(f"\nIn B4 but NOT B0:    {sorted(only_b4)}")
print(f"In B4 but NOT B1:    {sorted(only_b4_vs_b1)}")

# Also check: is X reachable by k-NN at all?
b4._ensure_kdtree()
x_cell = b4.memories["X"].cell_id
x_neighbors = b4.cell_neighbors.get(x_cell, set())
print(f"\nX k-NN neighbors: {len(x_neighbors)} cells")
# Are any of X's k-NN neighbors near the query?
near_query = set()
for n_cell in x_neighbors:
    n_id = b4._cell_to_memory.get(n_cell, "")
    if n_id in anchors:
        near_query.add(n_id)
print(f"X k-NN neighbors that are anchors: {near_query}")

if "X" in set_b4 and "X" not in set_b0:
    print(f"\nVERDICT: SURVIVES — propagation brought X into the result set")
    print(f"which flat top-k missed. Set composition differs.")
    # Check if B1 (with state multiplier) also gets X
    if "X" in set_b1:
        print(f"  BUT: B1 (metadata rerank) ALSO gets X via state multiplier.")
        print(f"  So dynamics don't add anything that state-as-multiplier doesn't.")
        print(f"  The discriminating question is whether B4 gets X via PROPAGATION")
        print(f"  (RESONANT links) or just via the state multiplier.")
else:
    if "X" in set_b0:
        print(f"\nVERDICT: FALSIFIED — X is in flat top-k anyway (too close).")
    elif "X" not in set_b4:
        print(f"\nVERDICT: FALSIFIED — X not in B4 either. Propagation couldn't")
        print(f"  boost X enough to enter top-k even with 3 RESONANT links + REINFORCED.")
        # Diagnose: what was X's score in B4?
        all_b4_results = b4.recall(query, top_k=100)
        for r in all_b4_results.results:
            if r.memory.memory_id == "X":
                print(f"  X score in B4: {r.final_score:.6f} (source={r.source}, hop={r.hop_distance})")
                break
        # What was the k-th score?
        if out_b4.results:
            kth = out_b4.results[-1]
            print(f"  k-th score in B4: {kth.final_score:.6f} ({kth.memory.memory_id})")
        # What was X's flat cosine score?
        from minimal_raven import MinimalRaven as MR
        x_sim = b4._cosine_sim(query, b4.memories["X"].embedding)
        print(f"  X cosine sim to query: {x_sim:.6f}")
        print(f"  X state_boost: {b4.memories['X'].state.value}")
        # Check if X was even reached by BFS
        print(f"  X in activated_cells: {x_cell in all_b4_results.activated_cells}")
        print(f"  X in inhibited_cells: {x_cell in all_b4_results.inhibited_cells}")
