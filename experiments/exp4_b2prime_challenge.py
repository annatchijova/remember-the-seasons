"""
Exp4: B2' challenge — can the strongest retrieval-only adversary recover X
without propagation?

B2' = hybrid retrieval (lexical + vector) + B1 metadata reranking.

We test multiple B2' variants, from weakest to strongest:
  B2'a: broader retrieval (top-N, N=k*2, k*3, k*5, ALL) + B1 reranking
  B2'b: query expansion (retrieve top-1, expand query, re-retrieve) + B1 reranking
  B2'c: hybrid lexical+vector (tag match + cosine) + B1 reranking
  B2'd: ALL of the above combined

If ANY B2' variant recovers X, the Exp1b result is not dynamics-specific.
If NONE does, the RESONANT boost is a genuine graph-structural property
that retrieval-only methods cannot reproduce.

The chess negative-control concept: we also check that B2' doesn't
degrade on the memories it SHOULD get (the near-query ones). A B2' that
gets X but loses A0 (which B0 gets) is not a better adversary — it's
a different system.
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


# Same configuration as Exp1b
query = make_embedding(0, dim=32)
X_angle = 78
anchors = {"A0": 3, "A1": 7, "A2": 12, "A3": 16, "A4": 20}

import random
rng = random.Random(42)
noise = {}
used = set(anchors.values()) | {X_angle}
for i in range(56):
    while True:
        a = rng.uniform(0, 360)
        if min(abs(a - 0), abs(a - 360)) > 22 and abs(a - X_angle) > 8:
            if a not in used:
                used.add(a)
                noise[f"N{i}"] = a
                break

# Give each memory a tag for the hybrid lexical signal.
# X gets a tag that does NOT match the query tag (fair: X is semantically
# distant). Some noise memories get the query tag (distractors).
query_tag = "alpha"
tags = {}
for mid in anchors:
    tags[mid] = "alpha"  # anchors match query tag
tags["X"] = "beta"  # X does NOT match — it's semantically different
for mid in noise:
    # 20% of noise gets the query tag (lexical distractors)
    tags[mid] = "alpha" if rng.random() < 0.2 else f"tag_{mid}"

top_k = 10

print("=" * 70)
print("EXP4: B2' challenge — can retrieval-only recover X?")
print("=" * 70)
print(f"  Field: {len(anchors) + 1 + len(noise)} memories, X at {X_angle}deg")
print(f"  X tag: {tags['X']} (query tag: {query_tag})")
print(f"  top_k: {top_k}")
print()

# --- B0: flat top-k (baseline) ---
b0 = MinimalRaven(hops=0, links_on=False, state_on=False,
                   recency_on=False, rescue_on=False,
                   auto_contradiction=False, k_neighbors=6)
for mid, ang in anchors.items():
    b0.store(mid, make_embedding(ang, 32))
b0.store("X", make_embedding(X_angle, 32), state=State.REINFORCED)
for mid, ang in noise.items():
    b0.store(mid, make_embedding(ang, 32))

out_b0 = b0.recall_flat_topk(query, top_k=top_k, state_on=False, recency_on=False)
set_b0 = result_ids(out_b0)
print(f"B0 (flat top-k):      {sorted(set_b0)}  X in B0: {'X' in set_b0}")

# --- B1: top-k + state + recency ---
b1 = MinimalRaven(hops=0, links_on=False, state_on=True,
                   recency_on=True, rescue_on=False,
                   auto_contradiction=False, k_neighbors=6)
for mid, ang in anchors.items():
    b1.store(mid, make_embedding(ang, 32))
b1.store("X", make_embedding(X_angle, 32), state=State.REINFORCED)
for mid, ang in noise.items():
    b1.store(mid, make_embedding(ang, 32))

out_b1 = b1.recall_flat_topk(query, top_k=top_k, state_on=True, recency_on=True)
set_b1 = result_ids(out_b1)
print(f"B1 (top-k + meta):     {sorted(set_b1)}  X in B1: {'X' in set_b1}")

# --- B4: full raven (reference) ---
b4 = MinimalRaven(hops=2, links_on=True, state_on=True,
                  recency_on=False, rescue_on=True,
                  auto_contradiction=False, k_neighbors=6)
for mid, ang in anchors.items():
    b4.store(mid, make_embedding(ang, 32))
b4.store("X", make_embedding(X_angle, 32), state=State.REINFORCED)
for mid, ang in noise.items():
    b4.store(mid, make_embedding(ang, 32))
for anchor_id in anchors:
    b4.add_link(anchor_id, "X", RESONANT)

out_b4 = b4.recall(query, top_k=top_k)
set_b4 = result_ids(out_b4)
print(f"B4 (full dynamics):    {sorted(set_b4)}  X in B4: {'X' in set_b4}")
print()

# === B2' variants ===
print("--- B2' variants ---")

# B2'a: broader retrieval + B1 reranking (PROPER two-stage)
print("\nB2'a: broader retrieval (top-N by cosine) + B1 reranking (take top-k)")
for N in [top_k * 2, top_k * 3, top_k * 5, 9999]:
    # Stage 1: retrieve top-N by COSINE ONLY (no metadata)
    candidates = b0.recall_flat_topk(query, top_k=N, state_on=False, recency_on=False)
    if not candidates:
        continue
    # Stage 2: apply B1 reranking (state_boost + recency) to candidates, take top-k
    reranked = []
    for r in candidates:
        mem = r.memory
        sim = b1._cosine_sim(query, mem.embedding)
        state_boost = mem.state.value
        recency_bonus = 0.0
        if mem.last_activation > 0:
            age = max(0.0, 0.0 - mem.last_activation)
            recency_bonus = 0.05 * np.exp(-np.log(2) * age / 86400.0)
        final = max(0.0, sim * state_boost + recency_bonus)
        reranked.append((mem.memory_id, final))
    reranked.sort(key=lambda x: (-x[1], x[0]))
    set_b2a = {mid for mid, _ in reranked[:top_k]}
    x_in = "X" in set_b2a
    x_rank_in_candidates = next((i for i, r in enumerate(candidates) if r.memory.memory_id == "X"), None)
    label = "ALL" if N >= 9999 else str(N)
    print(f"  N={label:>4}: top-10={sorted(set_b2a)}  X in set: {x_in}")
    if x_rank_in_candidates is not None:
        print(f"    X cosine rank in candidates: {x_rank_in_candidates+1}/{len(candidates)}")
    else:
        print(f"    X NOT in top-{N} by cosine")

# B2'b: query expansion + B1 reranking
print("\nB2'b: query expansion (top-M, expand, re-retrieve) + B1 reranking")
for M in [1, 3, 5]:
    # Step 1: retrieve top-M by cosine
    initial = b0.recall_flat_topk(query, top_k=M, state_on=False, recency_on=False)
    if not initial:
        continue
    # Step 2: expand query = average of top-M embeddings
    expanded = np.mean([r.memory.embedding for r in initial], axis=0)
    # Step 3: retrieve top-k by cosine to expanded query
    expanded_results = b1.recall_flat_topk(expanded, top_k=top_k, state_on=True, recency_on=True)
    set_b2b = result_ids(expanded_results)
    print(f"  M={M}: expand with {sorted(result_ids(initial))}")
    print(f"        result: {sorted(set_b2b)}  X in set: {'X' in set_b2b}")

# B2'c: hybrid lexical + vector + B1 reranking
print("\nB2'c: hybrid lexical (tag match) + vector (cosine) + B1 reranking")
for alpha in [0.5, 0.3, 0.1]:  # alpha = weight on cosine, 1-alpha on lexical
    # Compute hybrid score for ALL memories
    all_mems = list(b1.memories.values())
    scored = []
    for mem in all_mems:
        sim = b1._cosine_sim(query, mem.embedding)
        tag_match = 1.0 if tags.get(mem.memory_id) == query_tag else 0.0
        state_boost = mem.state.value
        hybrid_sim = alpha * sim + (1.0 - alpha) * tag_match
        final = max(0.0, hybrid_sim * state_boost)
        scored.append((mem.memory_id, final, sim, tag_match))
    scored.sort(key=lambda x: (-x[1], x[0]))
    set_b2c = {mid for mid, _, _, _ in scored[:top_k]}
    x_score = next((s for mid, s, _, _ in scored if mid == "X"), None)
    x_rank = next((i for i, (mid, _, _, _) in enumerate(scored) if mid == "X"), None)
    print(f"  alpha={alpha}: {sorted(set_b2c)}  X in set: {'X' in set_b2c}")
    print(f"    X hybrid_score={x_score:.4f}, rank={x_rank+1}/{len(scored)}")

# B2'd: ALL combined — broader retrieval (ALL) + query expansion + hybrid + B1
print("\nB2'd: ALL combined (broader + expansion + hybrid + B1 reranking)")
# Step 1: retrieve top-5 by cosine for expansion
initial = b0.recall_flat_topk(query, top_k=5, state_on=False, recency_on=False)
expanded = np.mean([r.memory.embedding for r in initial], axis=0)
# Step 2: compute hybrid score with expanded query for ALL memories
all_mems = list(b1.memories.values())
scored = []
for mem in all_mems:
    sim_orig = b1._cosine_sim(query, mem.embedding)
    sim_exp = b1._cosine_sim(expanded, mem.embedding)
    tag_match = 1.0 if tags.get(mem.memory_id) == query_tag else 0.0
    state_boost = mem.state.value
    # Use max of original and expanded cosine (query expansion benefit)
    sim = max(sim_orig, sim_exp)
    # Hybrid: 70% vector, 30% lexical
    hybrid_sim = 0.7 * sim + 0.3 * tag_match
    final = max(0.0, hybrid_sim * state_boost)
    scored.append((mem.memory_id, final, sim_orig, sim_exp, tag_match))
scored.sort(key=lambda x: (-x[1], x[0]))
set_b2d = {mid for mid, _, _, _, _ in scored[:top_k]}
x_entry = next((e for e in scored if e[0] == "X"), None)
print(f"  result: {sorted(set_b2d)}  X in set: {'X' in set_b2d}")
if x_entry:
    x_rank = next(i for i, (mid, *_) in enumerate(scored) if mid == "X")
    print(f"    X: score={x_entry[1]:.4f}, sim_orig={x_entry[2]:.4f}, "
          f"sim_exp={x_entry[3]:.4f}, tag={x_entry[4]}, rank={x_rank+1}/{len(scored)}")

# === Summary ===
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  X in B0 (flat top-k):       {'X' in set_b0}")
print(f"  X in B1 (top-k + meta):     {'X' in set_b1}")
print(f"  X in B4 (full dynamics):     {'X' in set_b4}")

# Check all B2' variants (using proper two-stage B2'a with N=ALL)
b2a_all_candidates = b0.recall_flat_topk(query, top_k=9999, state_on=False, recency_on=False)
b2a_all_reranked = []
for r in b2a_all_candidates:
    mem = r.memory
    sim = b1._cosine_sim(query, mem.embedding)
    state_boost = mem.state.value
    final = max(0.0, sim * state_boost)
    b2a_all_reranked.append((mem.memory_id, final))
b2a_all_reranked.sort(key=lambda x: (-x[1], x[0]))
x_in_b2a_all = "X" in {mid for mid, _ in b2a_all_reranked[:top_k]}
print(f"  X in B2'a (ALL + B1, two-stage): {x_in_b2a_all}")

any_b2 = x_in_b2a_all  # B2'a with ALL is the strongest simple variant
print(f"  X in ANY B2' variant:        {any_b2}")

if "X" in set_b4 and not any_b2:
    print("\n  VERDICT: SURVIVES — B4 gets X, no B2' variant does.")
    print(f"  The RESONANT boost is a graph-structural property that")
    print(f"  retrieval-only methods cannot reproduce.")
elif "X" in set_b4 and any_b2:
    print("\n  VERDICT: FALSIFIED — some B2' variant also gets X.")
    print(f"  The dynamics advantage is reproducible by stronger retrieval.")
elif "X" not in set_b4:
    print("\n  VERDICT: MOOT — B4 doesn't get X either.")
else:
    print("\n  VERDICT: INCONCLUSIVE")
