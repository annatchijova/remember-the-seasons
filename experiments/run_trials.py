"""
Three discriminating experiments for the Remember the Seasons pre-clinical trials.

Exp1: Set composition — does propagation change the SET of memories returned,
      or just the order? (B0/B1 vs B4)
Exp2: Rescue vs post-hoc filter — A (raven rescue) vs B (no rescue) vs C
      (no rescue + post-scoring filter). Are A and C identical?
Exp3: Intervention vs removal — does suppress Δ == remove-from-corpus Δ?

Each experiment reports a verdict: SURVIVES / FALSIFIED / INCONCLUSIVE.
"""

import sys
import copy
import numpy as np

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT, INHIBITORY


def make_embedding(angle_deg: float, dim: int = 16) -> np.ndarray:
    """Deterministic embedding on a unit circle in the first 2 dims, zero elsewhere."""
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def result_ids(outcome) -> set:
    return {r.memory.memory_id for r in outcome.results}


def result_order(outcome) -> list:
    return [r.memory.memory_id for r in outcome.results]


def result_scores(outcome) -> dict:
    return {r.memory.memory_id: round(r.final_score, 6) for r in outcome.results}


# ============================================================
# EXP1: Set composition — does propagation change the SET?
# ============================================================
def exp1_set_composition():
    """
    H1 test: does BFS propagation bring in memories that flat top-k misses?

    Design:
    - Place memories on a circle. Query at angle 0.
    - Memory A at 5deg (close to query — top-k gets it)
    - Memory B at 30deg (medium — top-k might get it)
    - Memory C at 80deg (far — top-k misses it)
    - Memory D at 85deg (far — top-k misses it)
    - Add RESONANT link A -> D, so D should be reachable via propagation
    - Add RESONANT link B -> C, so C should be reachable via propagation
    - Fill with noise memories at various angles

    B0 (hops=0, no links, no state, no recency): flat top-k. Should miss C and D.
    B1 (hops=0, no links, state, recency): same SET as B0 (links are off).
    B4 (hops=2, links, state, recency): should reach C via B->C and D via A->D.

    Verdict:
    - If B4's result SET differs from B0/B1's SET (C or D appears in B4 but
      not B0/B1): propagation changes set composition -> H1 SURVIVES.
    - If B4's SET == B0/B1's SET: propagation only reorders -> H1 FALSIFIED
      for set composition.
    """
    print("=" * 70)
    print("EXP1: Set composition — does propagation change the SET?")
    print("=" * 70)

    # Build the field
    angles = {
        "A": 5,   # close to query
        "B": 30,  # medium
        "C": 80,  # far — top-k should miss
        "D": 85,  # far — top-k should miss
    }
    # Noise memories
    noise_angles = {f"N{i}": a for i, a in enumerate(
        [120, 150, 200, 250, 300, 340, 10, 20, 45, 60, 95, 110]
    )}

    query = make_embedding(0)

    def build_field():
        eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                           recency_on=True, rescue_on=True,
                           auto_contradiction=False)
        for mid, ang in angles.items():
            eng.store(mid, make_embedding(ang))
        for mid, ang in noise_angles.items():
            eng.store(mid, make_embedding(ang))
        # RESONANT links: A->D, B->C
        eng.add_link("A", "D", RESONANT)
        eng.add_link("B", "C", RESONANT)
        return eng

    # B0: flat top-k (cosine to ALL memories, no state, no recency)
    b0 = MinimalRaven(hops=0, links_on=False, state_on=False,
                      recency_on=False, rescue_on=False,
                      auto_contradiction=False)
    for mid, ang in {**angles, **noise_angles}.items():
        b0.store(mid, make_embedding(ang))

    # B1: top-k + state + recency (cosine to ALL, state multiplier, recency)
    b1 = MinimalRaven(hops=0, links_on=False, state_on=True,
                      recency_on=True, rescue_on=False,
                      auto_contradiction=False)
    for mid, ang in {**angles, **noise_angles}.items():
        b1.store(mid, make_embedding(ang))

    # B4: full raven
    b4 = build_field()

    top_k = 5
    out_b0_results = b0.recall_flat_topk(query, top_k=top_k, state_on=False, recency_on=False)
    out_b1_results = b1.recall_flat_topk(query, top_k=top_k, state_on=True, recency_on=True)
    out_b4 = b4.recall(query, top_k=top_k)

    set_b0 = {r.memory.memory_id for r in out_b0_results}
    set_b1 = {r.memory.memory_id for r in out_b1_results}
    set_b4 = result_ids(out_b4)

    print(f"  B0 (flat top-k):     {sorted(set_b0)}")
    print(f"  B1 (top-k + meta):   {sorted(set_b1)}")
    print(f"  B4 (full dynamics):  {sorted(set_b4)}")
    print(f"  B4 sources:          {[(r.memory.memory_id, r.source, r.hop_distance) for r in out_b4.results]}")

    # Check: does B4 contain memories NOT in B0/B1?
    only_b4 = set_b4 - set_b0
    only_b4_vs_b1 = set_b4 - set_b1

    print(f"\n  In B4 but NOT B0:    {sorted(only_b4)}")
    print(f"  In B4 but NOT B1:    {sorted(only_b4_vs_b1)}")

    if only_b4:
        print(f"\n  VERDICT: SURVIVES — propagation brought in {sorted(only_b4)}")
        print(f"  which flat top-k missed. Set composition differs.")
        return "SURVIVES"
    else:
        print(f"\n  VERDICT: FALSIFIED — B4 set == B0 set. Propagation only reorders.")
        return "FALSIFIED"


# ============================================================
# EXP2: Rescue vs post-hoc filter
# ============================================================
def exp2_rescue_vs_posthoc():
    """
    H7 test: is the rescue rule a post-hoc filter in disguise?

    Design:
    - Memory V (REINFORCED) and memory W (NEUTRAL) with same topic,
      different claims -> auto INHIBITORY link.
    - Query lands near W. W inhibits V during BFS.
    - A: rescue ON (raven actual) — V is rescued, appears in results.
    - B: rescue OFF — V is inhibited, excluded.
    - C: rescue OFF + post-hoc filter — V is inhibited, then added back
      after scoring because REINFORCED.

    Compare A vs C: identical result set + ranking -> rescue is a post-hoc
    filter (H7 FALSIFIED). Different -> rescue has a propagation effect
    (H7 SURVIVES).

    We also test with multiple contradictions and different field sizes to
    check for edge cases.
    """
    print("\n" + "=" * 70)
    print("EXP2: Rescue vs post-hoc filter — A == C?")
    print("=" * 70)

    query = make_embedding(0)

    def build_field():
        eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                           recency_on=False, rescue_on=True,
                           auto_contradiction=True)
        # V: REINFORCED, close to query
        eng.store("V", make_embedding(10), state=State.REINFORCED,
                  topic="T", claim="X")
        # W: NEUTRAL, close to query, contradicts V
        eng.store("W", make_embedding(5), state=State.NEUTRAL,
                  topic="T", claim="Y")
        # Noise
        for i, a in enumerate([60, 100, 150, 200, 250, 300]):
            eng.store(f"N{i}", make_embedding(a))
        return eng

    # A: rescue ON (actual raven)
    eng_a = build_field()
    out_a = eng_a.recall(query, top_k=10)
    set_a = result_ids(out_a)
    order_a = result_order(out_a)
    scores_a = result_scores(out_a)

    # B: rescue OFF (no rescue at all)
    eng_b = build_field()
    eng_b.rescue_on = False
    out_b = eng_b.recall(query, top_k=10)
    set_b = result_ids(out_b)

    # C: rescue OFF + post-hoc filter
    eng_c = build_field()
    eng_c.rescue_on = False
    out_c = eng_c.recall_post_hoc_rescue(query, top_k=10)
    set_c = result_ids(out_c)
    order_c = result_order(out_c)
    scores_c = result_scores(out_c)

    print(f"  A (rescue ON):       {order_a}")
    print(f"  A scores:            {scores_a}")
    print(f"  B (rescue OFF):      {sorted(set_b)}")
    print(f"  B has V:             {'V' in set_b}")
    print(f"  C (post-hoc filter): {order_c}")
    print(f"  C scores:            {scores_c}")

    print(f"\n  A == C (set):        {set_a == set_c}")
    print(f"  A == C (order):      {order_a == order_c}")
    print(f"  A == C (scores):     {scores_a == scores_c}")

    # Detailed comparison
    if set_a == set_c and order_a == order_c and scores_a == scores_c:
        print(f"\n  VERDICT: FALSIFIED — A == C. Rescue is a post-hoc filter.")
        print(f"  The rescue rule provides no property beyond what a metadata")
        print(f"  filter (\"if REINFORCED and inhibited -> add back\") does.")
        return "FALSIFIED"
    else:
        print(f"\n  VERDICT: SURVIVES — A != C. Rescue has a propagation effect.")
        if set_a != set_c:
            print(f"  Set difference: A-only={set_a - set_c}, C-only={set_c - set_a}")
        if order_a != order_c:
            print(f"  Order difference: A={order_a}, C={order_c}")
        if scores_a != scores_c:
            for mid in set_a & set_c:
                if scores_a[mid] != scores_c.get(mid):
                    print(f"  Score diff for {mid}: A={scores_a[mid]} C={scores_c.get(mid)}")
        return "SURVIVES"


# ============================================================
# EXP3: Intervention vs removal
# ============================================================
def exp3_intervention_vs_removal():
    """
    H2 test: is suppression equivalent to removing the target from the corpus?

    Design:
    - Build a field with memories at various angles.
    - Pick a target memory T that is in the result set.
    - Run intervention: suppress T, measure Δ = R(q) vs R(q|do(T=0)).
    - Run removal: physically remove T from corpus, re-run recall,
      measure Δ' = R(q) vs R(q without T).
    - Compare Δ and Δ'.

    If Δ == Δ': suppression is equivalent to removal — the intervention is
    a retrieval operation ("retrieve without this memory"), not a distinct
    causal probe (H2 FALSIFIED).

    If Δ != Δ': suppression has a propagation-specific effect (the target's
    links are inert but the graph topology differs) — H2 SURVIVES.

    We test with multiple targets to check robustness.
    """
    print("\n" + "=" * 70)
    print("EXP3: Intervention vs removal — suppress Δ == remove Δ?")
    print("=" * 70)

    query = make_embedding(0)

    def build_field():
        eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                           recency_on=False, rescue_on=True,
                           auto_contradiction=False)
        memories = {
            "M0": 5, "M1": 15, "M2": 25, "M3": 35,
            "M4": 45, "M5": 55, "M6": 65, "M7": 75,
            "M8": 85, "M9": 95, "M10": 105, "M11": 200,
        }
        for mid, ang in memories.items():
            eng.store(mid, make_embedding(ang))
        # Some RESONANT links to create propagation paths
        eng.add_link("M0", "M8", RESONANT)
        eng.add_link("M1", "M9", RESONANT)
        eng.add_link("M2", "M11", RESONANT)
        return eng, memories

    # Baseline recall
    eng_base, memories = build_field()
    out_base = eng_base.recall(query, top_k=10)
    base_ids = result_ids(out_base)
    base_order = result_order(out_base)
    base_scores = result_scores(out_base)

    print(f"  Baseline result set: {sorted(base_ids)}")

    # Identify the seed cell (nearest to query)
    eng_base._ensure_kdtree()
    _, seed_idx = eng_base._kdtree.query(query.reshape(1, -1))
    seed_cell = eng_base._kdtree_idx_to_cell[int(seed_idx[0])]
    seed_id = eng_base._cell_to_memory[seed_cell]
    print(f"  Seed cell: {seed_id}")

    # Test each target that's in the baseline, EXCLUDING the seed
    # (suppressing the seed is degenerate: BFS has no starting point)
    targets_to_test = sorted(base_ids - {seed_id})[:5]
    all_match = True
    details = []

    for target_id in targets_to_test:
        target_cell = eng_base.memories[target_id].cell_id

        # Intervention: suppress target
        eng_int = build_field()[0]
        out_int = eng_int.recall(query, top_k=10, suppressed={target_cell})
        int_ids = result_ids(out_int)
        int_order = result_order(out_int)
        int_scores = result_scores(out_int)

        # Removal: physically remove target from corpus
        eng_rem = build_field()[0]
        eng_rem.remove_memory(target_id)
        out_rem = eng_rem.recall(query, top_k=10)
        rem_ids = result_ids(out_rem)
        rem_order = result_order(out_rem)
        rem_scores = result_scores(out_rem)

        # Compare
        set_match = int_ids == rem_ids
        order_match = int_order == rem_order
        scores_match = int_scores == rem_scores

        match = set_match and order_match and scores_match
        if not match:
            all_match = False

        details.append({
            "target": target_id,
            "set_match": set_match,
            "order_match": order_match,
            "scores_match": scores_match,
            "int_set": sorted(int_ids),
            "rem_set": sorted(rem_ids),
            "int_order": int_order,
            "rem_order": rem_order,
            "int_scores": int_scores,
            "rem_scores": rem_scores,
        })

        print(f"\n  Target: {target_id}")
        print(f"    suppress set:  {sorted(int_ids)}")
        print(f"    remove set:    {sorted(rem_ids)}")
        print(f"    set match:     {set_match}")
        print(f"    order match:   {order_match}")
        print(f"    scores match:  {scores_match}")
        if not scores_match:
            for mid in sorted(set(int_scores.keys()) | set(rem_scores.keys())):
                si = int_scores.get(mid)
                sr = rem_scores.get(mid)
                if si != sr:
                    print(f"      {mid}: suppress={si}  remove={sr}")

    # Also test the degenerate seed case separately
    print(f"\n  --- Degenerate case: suppress the seed ({seed_id}) ---")
    eng_seed = build_field()[0]
    out_seed_sup = eng_seed.recall(query, top_k=10, suppressed={seed_cell})
    eng_seed2 = build_field()[0]
    eng_seed2.remove_memory(seed_id)
    out_seed_rem = eng_seed2.recall(query, top_k=10)
    print(f"    suppress set:  {sorted(result_ids(out_seed_sup))}")
    print(f"    remove set:    {sorted(result_ids(out_seed_rem))}")
    print(f"    (degenerate: suppressing the seed kills BFS entirely because")
    print(f"     the seed is still in the KDTree but skipped — a known edge case)")

    print(f"\n  All non-seed targets match: {all_match}")

    if all_match:
        print(f"\n  VERDICT: FALSIFIED — suppress Δ == remove Δ for all targets.")
        print(f"  Intervention is equivalent to retrieval without the target.")
        print(f"  The 'optogenetic' probe is 'delete a row in a lab coat'.")
        return "FALSIFIED"
    else:
        print(f"\n  VERDICT: SURVIVES — suppress Δ != remove Δ for some targets.")
        print(f"  Intervention has a propagation-specific effect distinct from removal.")
        mismatches = [d for d in details if not d["set_match"] or not d["order_match"]]
        for d in mismatches:
            print(f"    {d['target']}: set_match={d['set_match']}, order_match={d['order_match']}")
            if not d["set_match"]:
                print(f"      suppress: {d['int_set']}")
                print(f"      remove:   {d['rem_set']}")
        return "SURVIVES"


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("Remember the Seasons — Pre-clinical trials")
    print("Three discriminating experiments")
    print()

    v1 = exp1_set_composition()
    v2 = exp2_rescue_vs_posthoc()
    v3 = exp3_intervention_vs_removal()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Exp1 (set composition):     {v1}")
    print(f"  Exp2 (rescue vs post-hoc):   {v2}")
    print(f"  Exp3 (intervention vs removal): {v3}")
    print()

    survived = sum(1 for v in [v1, v2, v3] if v == "SURVIVES")
    falsified = sum(1 for v in [v1, v2, v3] if v == "FALSIFIED")
    print(f"  SURVIVES: {survived}/3  FALSIFIED: {falsified}/3")
