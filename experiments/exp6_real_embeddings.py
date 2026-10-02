"""
Exp6: Real embeddings generalization — does the Exp1b result hold outside
the unit circle?

We can't add sentence-transformers (no new deps authorized). Instead we
use a deterministic bag-of-words + random projection approach that
produces more realistic embeddings: non-unit-norm, non-uniform, with
semantic clusters.

Each memory gets a "text" (a set of keywords). The embedding is a
bag-of-words vector projected to 32 dimensions via a fixed random
matrix. This produces:
- Non-unit-norm vectors (realistic)
- Semantic clustering (memories with shared keywords are closer)
- Non-trivial geometry (not a perfect circle)

We test: does B4 (full dynamics) still bring in a memory that B0/B1/B2'
miss, when the embeddings are realistic rather than unit-circle?

We also test with a second approach: random Gaussian embeddings
(non-unit-norm, no structure) to check if the result is an artifact of
the bag-of-words structure.
"""
import sys
import numpy as np
import random

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT, INHIBITORY


# ============================================================
# Embedding approach 1: bag-of-words + random projection
# ============================================================
def make_bow_embedding(text_keywords, vocab, proj_matrix, dim=32):
    """Bag-of-words embedding: count keywords, project to dim dimensions."""
    vec = np.zeros(len(vocab), dtype=np.float64)
    for kw in text_keywords:
        if kw in vocab:
            vec[vocab[kw]] += 1.0
    # L2 normalize the BoW vector
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    # Project to lower dimension
    projected = proj_matrix @ vec
    return projected


def build_bow_field():
    """Build a field with bag-of-words embeddings.

    X is a memory about "cooking" that shares no keywords with the query
    about "programming". But X has RESONANT links from memories about
    "programming" that also mention "cooking" (cross-domain memories).
    """
    # Vocabulary
    vocab_words = [
        "python", "code", "function", "debug", "algorithm", "data",
        "cook", "recipe", "ingredient", "kitchen", "taste", "food",
        "music", "guitar", "melody", "rhythm", "note", "chord",
        "travel", "city", "map", "road", "hotel", "trip",
        "science", "physics", "quantum", "energy", "force", "mass",
        "art", "paint", "color", "canvas", "brush", "design",
    ]
    vocab = {w: i for i, w in enumerate(vocab_words)}

    # Fixed random projection matrix
    rng = np.random.RandomState(42)
    proj = rng.randn(32, len(vocab_words)) / np.sqrt(32)

    # Define memories
    # Query: "python code function algorithm data"
    query_keywords = ["python", "code", "function", "algorithm", "data"]

    # Anchors: programming memories near the query
    anchors = {
        "A0": ["python", "code", "function", "debug"],
        "A1": ["python", "algorithm", "data", "function"],
        "A2": ["code", "debug", "function", "python"],
        "A3": ["python", "data", "algorithm", "code"],
        "A4": ["function", "code", "data", "debug"],
    }

    # X: cooking memory that shares ONE keyword with query (positive but low cosine)
    # In a real system, this would be a cross-domain memory that shares
    # one concept with the query domain.
    X_keywords = ["cook", "recipe", "ingredient", "kitchen", "taste", "data"]

    # Noise: 56 memories with various keyword combinations
    noise = {}
    rng_noise = random.Random(42)
    for i in range(56):
        # Pick 3-5 random keywords
        n_kw = rng_noise.randint(3, 6)
        kws = rng_noise.sample(vocab_words, n_kw)
        noise[f"N{i:02d}"] = kws

    # Build the field
    eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                       recency_on=False, rescue_on=True,
                       auto_contradiction=False, k_neighbors=6)
    query_emb = make_bow_embedding(query_keywords, vocab, proj)

    for mid, kws in anchors.items():
        emb = make_bow_embedding(kws, vocab, proj)
        eng.store(mid, emb)

    x_emb = make_bow_embedding(X_keywords, vocab, proj)
    eng.store("X", x_emb, state=State.REINFORCED)

    for mid, kws in noise.items():
        emb = make_bow_embedding(kws, vocab, proj)
        eng.store(mid, emb)

    # RESONANT links: each anchor -> X
    for anchor_id in anchors:
        eng.add_link(anchor_id, "X", RESONANT)

    return eng, query_emb, vocab, proj


# ============================================================
# Embedding approach 2: random Gaussian (no structure)
# ============================================================
def build_gaussian_field():
    """Build a field with random Gaussian embeddings (non-unit-norm)."""
    rng = np.random.RandomState(42)

    # Query: random Gaussian vector
    query_emb = rng.randn(32)

    # Anchors: close to query (query + small noise)
    anchors = {}
    for i in range(5):
        anchors[f"A{i}"] = query_emb + 0.3 * rng.randn(32)

    # X: far from query (orthogonal direction + REINFORCED)
    x_direction = rng.randn(32)
    # Make X roughly orthogonal to query
    x_direction -= np.dot(x_direction, query_emb) / np.dot(query_emb, query_emb) * query_emb
    x_emb = x_direction + 0.5 * rng.randn(32)

    # Noise: 56 random Gaussian vectors
    noise = {}
    for i in range(56):
        noise[f"N{i:02d}"] = rng.randn(32)

    eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                       recency_on=False, rescue_on=True,
                       auto_contradiction=False, k_neighbors=6)

    for mid, emb in anchors.items():
        eng.store(mid, emb.copy())
    eng.store("X", x_emb.copy(), state=State.REINFORCED)
    for mid, emb in noise.items():
        eng.store(mid, emb.copy())

    for anchor_id in anchors:
        eng.add_link(anchor_id, "X", RESONANT)

    return eng, query_emb


# ============================================================
# Test function
# ============================================================
def test_field(eng, query_emb, label, top_k=10):
    """Run B0, B1, B4, and B2' on a field and check if B4 gets X."""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    # B0: flat top-k (cosine to ALL, no state, no recency)
    b0_results = eng.recall_flat_topk(query_emb, top_k=top_k, state_on=False, recency_on=False)
    set_b0 = {r.memory.memory_id for r in b0_results}

    # B1: top-k + state + recency
    b1_results = eng.recall_flat_topk(query_emb, top_k=top_k, state_on=True, recency_on=True)
    set_b1 = {r.memory.memory_id for r in b1_results}

    # B4: full dynamics
    out_b4 = eng.recall(query_emb, top_k=top_k)
    set_b4 = {r.memory.memory_id for r in out_b4.results}

    # B2': two-stage (ALL by cosine -> B1 reranking -> top-k)
    all_candidates = eng.recall_flat_topk(query_emb, top_k=9999, state_on=False, recency_on=False)
    reranked = []
    for r in all_candidates:
        mem = r.memory
        sim = eng._cosine_sim(query_emb, mem.embedding)
        state_boost = mem.state.value
        final = max(0.0, sim * state_boost)
        reranked.append((mem.memory_id, final))
    reranked.sort(key=lambda x: (-x[1], x[0]))
    set_b2prime = {mid for mid, _ in reranked[:top_k]}

    # X's cosine rank
    all_sims = []
    for mid, mem in eng.memories.items():
        sim = eng._cosine_sim(query_emb, mem.embedding)
        all_sims.append((mid, sim))
    all_sims.sort(key=lambda x: (-x[1], x[0]))
    x_cosine_rank = next((i+1 for i, (mid, _) in enumerate(all_sims) if mid == "X"), None)
    x_cosine_sim = next((sim for mid, sim in all_sims if mid == "X"), None)

    # X's B4 score
    x_b4_score = None
    x_b4_source = None
    for r in out_b4.results:
        if r.memory.memory_id == "X":
            x_b4_score = r.final_score
            x_b4_source = r.source
            break

    print(f"  X cosine sim:  {x_cosine_sim:.4f} (rank {x_cosine_rank}/{len(eng.memories)})")
    print(f"  X in B0:       {'X' in set_b0}")
    print(f"  X in B1:       {'X' in set_b1}")
    print(f"  X in B2':      {'X' in set_b2prime}")
    print(f"  X in B4:       {'X' in set_b4}")
    if x_b4_score is not None:
        print(f"  X B4 score:    {x_b4_score:.4f} (source={x_b4_source})")
    print(f"  B0 set:        {sorted(set_b0)}")
    print(f"  B1 set:        {sorted(set_b1)}")
    print(f"  B4 set:        {sorted(set_b4)}")

    if "X" in set_b4 and "X" not in set_b0 and "X" not in set_b1 and "X" not in set_b2prime:
        print(f"\n  VERDICT: SURVIVES — B4 gets X, no retrieval-only variant does.")
        return "SURVIVES"
    elif "X" in set_b4 and ("X" in set_b0 or "X" in set_b1 or "X" in set_b2prime):
        print(f"\n  VERDICT: FALSIFIED — some retrieval-only variant also gets X.")
        return "FALSIFIED"
    elif "X" not in set_b4:
        print(f"\n  VERDICT: FALSIFIED — B4 doesn't get X either.")
        return "FALSIFIED"
    else:
        print(f"\n  VERDICT: INCONCLUSIVE")
        return "INCONCLUSIVE"


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP6: Real embeddings generalization")
print("=" * 70)

# Test 1: bag-of-words + random projection
eng_bow, query_bow, vocab, proj = build_bow_field()
v1 = test_field(eng_bow, query_bow, "Bag-of-words + random projection")

# Test 2: random Gaussian (no structure)
eng_gauss, query_gauss = build_gaussian_field()
v2 = test_field(eng_gauss, query_gauss, "Random Gaussian (no structure)")

print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
print(f"  Bag-of-words + projection: {v1}")
print(f"  Random Gaussian:            {v2}")
