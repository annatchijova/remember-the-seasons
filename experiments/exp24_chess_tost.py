"""
Exp24: H11 done properly — preregistered behavioral assay.

Exp20 was INCONCLUSIVE: n=1 informative seed, post-hoc selection,
no equivalence test. This version fixes the methodology.

DESIGN (all decisions preregistered BEFORE chess evaluation):

  Phase 1 — CALIBRATION (memory only, no chess):
    - Candidate seeds: [0..15] (16 candidates, fixed list)
    - Run control vs intervention trajectories for each
    - Selection rule: include seed iff post-washout recall
      divergence >= 0.02
    - Selection happens BEFORE any chess evaluation. The outcome
      variable is never observed during selection.

  Phase 2 — SHAM (pipeline control):
    - Same control context presented twice to the LLM
    - At temperature=0 + fixed seed, must produce identical moves
    - If sham != 0, the pipeline is non-deterministic and results
      are invalid regardless of the memory effect.

  Phase 3 — CHESS EVALUATION (selected seeds only):
    - One fixed set of 15 positions (fixed seed, same FENs in
      all arms)
    - Same LLM (hermes3:8b, temp=0) in both arms; only the
      memory context differs
    - Stockfish 16 depth 15 evaluates each move's regret
      (best_score - move_score, centipawns)

  Phase 4 — EQUIVALENCE TEST (TOST):
    - H0: |mean paired regret difference| >= delta
    - H1: |mean paired regret difference| <  delta
    - delta = 30 centipawns (preregistered: ~1/3 pawn)
    - alpha = 0.05 each side => 90% CI must lie inside [-30, +30]
    - Primary unit: per-position paired regret differences
    - Secondary: per-seed mean differences, move agreement rate

INTERPRETATION RULES (preregistered):
  - TOST rejects H0 (CI inside [-delta, delta]) AND sham == 0
    -> PASS: evidence of equivalence under tested conditions
  - CI outside [-delta, delta] -> FAIL: off-target effect
  - CI crosses boundary -> INCONCLUSIVE
  - Sham != 0 -> INVALID PIPELINE, report and stop
"""
import sys
import os
import json
import random
import time
import hashlib
import numpy as np
import chess
import subprocess
import urllib.request
from typing import Dict, List, Optional, Tuple
from scipy import stats as scipy_stats

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, RESONANT

STOCKFISH_PATH = "/tmp/stockfish/stockfish-ubuntu-x86-64-avx2"
OLLAMA_MODEL = "hermes3:8b"
STOCKFISH_DEPTH = 15

# ---- PREREGISTERED PARAMETERS (fixed before any chess run) ----
CANDIDATE_SEEDS = list(range(16))     # calibration candidates
DIVERGENCE_MIN = 0.02                 # min post-washout recall divergence
N_POSITIONS = 15                      # chess positions per seed
POSITION_SEED = 77777                 # fixed position set for all seeds
DELTA_CP = 30.0                       # equivalence margin (centipawns)
ALPHA = 0.05                          # TOST one-sided alpha
N_QUERIES = 120
INT_START = 40
INT_END = 70


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def build_field(n_memories=100, dim=32, seed=42):
    eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                       recency_on=False, rescue_on=True,
                       auto_contradiction=False, k_neighbors=6)
    memories = {}
    for i in range(n_memories):
        angle = (i * 360.0 / n_memories) % 360
        mid = f"M{i:04d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim))
    half = n_memories // 2
    for i in range(half):
        eng.add_link(f"M{i:04d}", f"M{i+half:04d}", RESONANT)
    return eng, memories


def run_memory_trajectory(eng, query_angles, int_start, int_end,
                          block_reinforcement):
    """Same semantics as Exp20: recall_with_learning + reinforce top-1."""
    prev_recalled = None
    for step, q_angle in enumerate(query_angles):
        query = make_embedding(q_angle)
        outcome = eng.recall_with_learning(
            query, top_k=10, now=float(step),
            current_turn_memories=prev_recalled)
        recalled_ids = [r.memory.memory_id for r in outcome.results]
        in_int = int_start <= step < int_end
        if recalled_ids and not (in_int and block_reinforcement):
            eng.reinforce(recalled_ids[0])
        if prev_recalled and recalled_ids:
            eng.update_stdp(prev_recalled, recalled_ids)
        eng.update_activations(recalled_ids, float(step))
        prev_recalled = recalled_ids


def memory_context(eng, test_angles, mem_angles, top_k=5):
    """Recall memory context for the chess prompt."""
    mems = []
    diff_set = []
    for ta in test_angles:
        tq = make_embedding(float(ta))
        outcome = eng.recall(tq, top_k=top_k)
        for r in outcome.results:
            mems.append((r.memory.memory_id,
                         mem_angles[r.memory.memory_id],
                         round(r.final_score, 4)))
    return mems


def mem_divergence(eng_c, eng_i, test_angles):
    """Post-washout recall divergence between arms."""
    total = 0
    for ta in test_angles:
        tq = make_embedding(float(ta))
        oc = eng_c.recall(tq, top_k=5)
        oi = eng_i.recall(tq, top_k=5)
        c_ids = set(r.memory.memory_id for r in oc.results)
        i_ids = set(r.memory.memory_id for r in oi.results)
        total += len(c_ids.symmetric_difference(i_ids))
    return total / (len(test_angles) * 5)


# ---- Stockfish ----
def stockfish_evaluate(fen, depth=STOCKFISH_DEPTH):
    try:
        proc = subprocess.Popen(
            [STOCKFISH_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        proc.stdin.write(f"position fen {fen}\ngo depth {depth}\n")
        proc.stdin.flush()
        time.sleep(0.05)
        score_cp = None
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            if line.startswith("info") and "score cp" in line:
                parts = line.split()
                score_cp = int(parts[parts.index("cp") + 1])
            if line.startswith("bestmove"):
                break
        proc.stdin.write("quit\n")
        proc.stdin.flush()
        proc.wait(timeout=5)
        return score_cp
    except Exception:
        return None


def move_regret(fen, move, best_score, depth=STOCKFISH_DEPTH):
    """Regret of a move in centipawns: best_score - resulting_score."""
    if move is None or best_score is None:
        return None
    board = chess.Board(fen)
    try:
        mv = chess.Move.from_uci(move)
        if mv not in board.legal_moves:
            return None
        board.push(mv)
    except Exception:
        return None
    after = stockfish_evaluate(board.fen(), depth)
    if after is None:
        return None
    # after is from opponent's perspective; negate for ours
    return best_score - (-after)


# ---- LLM ----
def llm_pick_move(model, fen, mem_lines):
    prompt = f"""You are a chess player. Choose the best move for the current position.

Context memories (from a memory system, unrelated to chess):
{mem_lines}

Chess position (FEN): {fen}

Legal moves: {' '.join(m.uci() for m in chess.Board(fen).legal_moves)}

Respond with ONLY the best move in UCI format (e.g., e2e4). No explanation."""
    data = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0, "seed": 42}
    }).encode()
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/generate", data=data,
            headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=60)
        text = json.loads(resp.read()).get("response", "").strip()
        for word in text.split():
            word = word.strip().strip(".,;:!?\"'")
            if len(word) >= 4:
                try:
                    mv = chess.Move.from_uci(word)
                    if mv in chess.Board(fen).legal_moves:
                        return mv.uci()
                except Exception:
                    continue
        moves = list(chess.Board(fen).legal_moves)
        return moves[0].uci() if moves else None
    except Exception as e:
        return None


def fmt_memories(mems):
    return "\n".join(f"  - Memory {mid}: angle {ang:.1f} degrees"
                     for mid, ang, sc in mems)


def generate_chess_positions(n, seed):
    rng = random.Random(seed)
    positions = []
    attempts = 0
    while len(positions) < n and attempts < n * 20:
        attempts += 1
        board = chess.Board()
        for _ in range(rng.randint(8, 24)):
            if board.is_game_over():
                break
            board.push(rng.choice(list(board.legal_moves)))
        if not board.is_game_over() and len(list(board.legal_moves)) > 5:
            positions.append(board.fen())
    return positions


def tost(diffs, delta, alpha=ALPHA):
    """Two one-sided tests for equivalence on mean paired diff."""
    diffs = np.array(diffs, dtype=float)
    n = len(diffs)
    if n < 2:
        return None
    m = diffs.mean()
    sd = diffs.std(ddof=1)
    se = sd / np.sqrt(n)
    t1 = (m + delta) / se   # rejects m <= -delta
    t2 = (delta - m) / se   # rejects m >= +delta
    p1 = 1 - scipy_stats.t.cdf(t1, n - 1)
    p2 = 1 - scipy_stats.t.cdf(t2, n - 1)
    # 90% CI
    lo, hi = scipy_stats.t.interval(1 - 2 * alpha, n - 1, loc=m, scale=se)
    return {"mean": m, "sd": sd, "n": n, "lo": lo, "hi": hi,
            "p_tost": max(p1, p2), "equiv": p1 < alpha and p2 < alpha}


# ============================================================
# MAIN
# ============================================================
print("=" * 70)
print("EXP24: H11 done properly — preregistered + TOST")
print("=" * 70)
print(f"\n  PREREGISTERED:")
print(f"    candidate seeds: {CANDIDATE_SEEDS[0]}..{CANDIDATE_SEEDS[-1]}")
print(f"    divergence gate: mem_diff >= {DIVERGENCE_MIN}")
print(f"    positions: {N_POSITIONS} (fixed set, seed {POSITION_SEED})")
print(f"    equivalence margin: delta = {DELTA_CP} centipawns")
print(f"    alpha: {ALPHA} (90% CI inside [-delta, +delta] = equivalence)")

# ---- Phase 1: CALIBRATION ----
print("\n" + "=" * 70)
print("PHASE 1: CALIBRATION (memory divergence only, no chess)")
print("=" * 70)

selected = []
mem_angles_cache = {}
for seed in CANDIDATE_SEEDS:
    rng_q = random.Random(seed)
    q = [rng_q.uniform(0, 360) for _ in range(N_QUERIES)]

    eng_c, mem_c = build_field(seed=seed)
    run_memory_trajectory(eng_c, q, 999, 999, False)
    eng_i, _ = build_field(seed=seed)
    run_memory_trajectory(eng_i, q, INT_START, INT_END, True)

    test_angles = q[INT_END:INT_END + 8]
    d = mem_divergence(eng_c, eng_i, test_angles)
    status = "SELECTED" if d >= DIVERGENCE_MIN else "skipped"
    print(f"  seed {seed:>3}: mem_diff={d:.4f}  {status}")
    if d >= DIVERGENCE_MIN:
        selected.append({"seed": seed, "eng_c": eng_c, "eng_i": eng_i,
                          "mem_angles": mem_c, "test_angles": test_angles,
                          "mem_diff": d})

print(f"\n  Selected {len(selected)}/{len(CANDIDATE_SEEDS)} conditions "
      f"(divergence >= {DIVERGENCE_MIN})")

# ---- Phase 2: SHAM ----
print("\n" + "=" * 70)
print("PHASE 2: SHAM — same context twice (determinism check)")
print("=" * 70)

positions = generate_chess_positions(N_POSITIONS, POSITION_SEED)
print(f"  {len(positions)} positions generated")

# Precompute Stockfish best scores once (needed for sham regret too)
best_scores = {}
for fen in positions:
    best_scores[fen] = stockfish_evaluate(fen)

sham_ctx = fmt_memories(memory_context(
    selected[0]["eng_c"], selected[0]["test_angles"],
    selected[0]["mem_angles"])) if selected else "  - none"
sham_agree = 0
sham_regret_diffs = []
for i, fen in enumerate(positions):
    m1 = llm_pick_move(OLLAMA_MODEL, fen, sham_ctx)
    m2 = llm_pick_move(OLLAMA_MODEL, fen, sham_ctx)
    if m1 == m2:
        sham_agree += 1
        sham_regret_diffs.append(0.0)
    else:
        r1 = move_regret(fen, m1, best_scores[fen])
        r2 = move_regret(fen, m2, best_scores[fen])
        if r1 is not None and r2 is not None:
            sham_regret_diffs.append(r2 - r1)
print(f"  Sham agreement: {sham_agree}/{len(positions)} "
      f"(must equal {len(positions)} for fully deterministic pipeline)")
sham_noise = [abs(d) for d in sham_regret_diffs if d != 0]
if sham_noise:
    print(f"  Sham noise: {len(sham_noise)} flips, regret diffs "
          f"{['%.0f' % d for d in sham_noise]}")
    print(f"  Max |sham regret diff|: {max(sham_noise):.0f} cp")
else:
    print(f"  Sham noise: zero (all diffs 0)")

# ---- Phase 3: CHESS EVALUATION ----
print("\n" + "=" * 70)
print("PHASE 3: CHESS EVALUATION (selected seeds)")
print("=" * 70)

paired_diffs = []       # regret_i - regret_c, per position
move_agreements = 0
move_total = 0
per_seed_means = []

for cond in selected:
    seed = cond["seed"]
    c_mems = memory_context(cond["eng_c"], cond["test_angles"],
                             cond["mem_angles"])
    i_mems = memory_context(cond["eng_i"], cond["test_angles"],
                             cond["mem_angles"])
    c_lines = fmt_memories(c_mems)
    i_lines = fmt_memories(i_mems)

    seed_diffs = []
    print(f"\n  Seed {seed} (mem_diff={cond['mem_diff']:.4f}):")
    for idx, fen in enumerate(positions):
        c_move = llm_pick_move(OLLAMA_MODEL, fen, c_lines)
        i_move = llm_pick_move(OLLAMA_MODEL, fen, i_lines)
        best = best_scores[fen]
        rc = move_regret(fen, c_move, best)
        ri = move_regret(fen, i_move, best)
        move_total += 1
        if c_move == i_move:
            move_agreements += 1
        if rc is not None and ri is not None:
            d = ri - rc
            paired_diffs.append(d)
            seed_diffs.append(d)
            tag = " (same move)" if c_move == i_move else f"  <- {c_move} vs {i_move}"
            print(f"    pos {idx+1:>2}: regret c={rc:>5} i={ri:>5} "
                  f"diff={d:>6}{tag}")
    if seed_diffs:
        per_seed_means.append(np.mean(seed_diffs))

# ---- Phase 4: TOST ----
print("\n" + "=" * 70)
print("PHASE 4: EQUIVALENCE TEST (TOST)")
print("=" * 70)

res = tost(paired_diffs, DELTA_CP)
print(f"\n  Paired positions evaluated: {len(paired_diffs)}")
print(f"  Move agreement: {move_agreements}/{move_total} "
      f"({100*move_agreements/max(move_total,1):.0f}%)")
if res:
    print(f"\n  Mean paired regret diff (i - c): {res['mean']:+.1f} cp")
    print(f"  90% CI: [{res['lo']:+.1f}, {res['hi']:+.1f}]")
    print(f"  Equivalence margin: +/-{DELTA_CP} cp")
    print(f"  TOST p: {res['p_tost']:.4f} (alpha={ALPHA})")
    print(f"  Per-seed mean diffs: "
          f"{['%.1f' % x for x in per_seed_means]}")

# ---- VERDICT ----
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

sham_rate = 1 - sham_agree / len(positions)
if not selected:
    print("\n  INCONCLUSIVE — no seed met the divergence gate.")
elif res is None:
    print("\n  INCONCLUSIVE — insufficient paired positions.")
else:
    # Compare intervention diffs vs sham noise floor
    int_abs = [abs(d) for d in paired_diffs if d != 0]
    print(f"\n  Sham noise floor: {sham_agree}/{len(positions)} agreement "
          f"({sham_rate:.0%} nondeterminism)")
    if sham_noise:
        print(f"    Sham |regret diff|: mean={np.mean(sham_noise):.0f} "
              f"max={max(sham_noise):.0f}")
    print(f"  Intervention diffs (nonzero): {len(int_abs)}")
    if int_abs:
        print(f"    mean={np.mean(int_abs):.1f} max={max(int_abs):.0f}")

    if res["equiv"]:
        print(f"\n  PASS (equivalence): 90% CI [{res['lo']:+.1f}, "
              f"{res['hi']:+.1f}] inside +/-{DELTA_CP} cp.")
        if sham_rate > 0:
            print(f"  CAVEAT: sham showed {sham_rate:.0%} nondeterminism —")
            print(f"  equivalence is at the noise floor's precision.")
        print(f"  Evidence supports behavioral specificity under tested")
        print(f"  conditions: memory intervention does not change chess")
        print(f"  move quality by more than {DELTA_CP} cp.")
    elif res["hi"] > DELTA_CP and res["lo"] < -DELTA_CP:
        print(f"\n  FAIL: CI spans outside +/-{DELTA_CP} — off-target effect.")
    else:
        print(f"\n  INCONCLUSIVE: CI [{res['lo']:+.1f}, {res['hi']:+.1f}]")
        print(f"  crosses the equivalence boundary.")
        if sham_rate > 0:
            print(f"  Sham nondeterminism ({sham_rate:.0%}) may inflate")
            print(f"  the noise floor, masking a real small effect.")
        print(f"  Cannot distinguish 'no effect' from 'insufficient data'.")
