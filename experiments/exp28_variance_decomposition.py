"""
Exp28: Variance decomposition — does the memory-context change
exceed the LLM's own stochasticity?

Exp24 showed: sham (same context twice) flips 1/15 positions at a
cost of 1cp; intervention (control vs divergent context) flips
6/45 with mean |regret diff| 129cp. But sham had only 15 pairs vs
45 for intervention — not a fair noise baseline.

This experiment decomposes variance:

  within-condition stochasticity:
    D(C,C) — C reps vs C reps (same context)
    D(I,I) — I reps vs I reps (same context)
  between-condition effect:
    D(C,I) — C reps vs I reps

Question: does D(C,I) exceed max(D(C,C), D(I,I))?

  - If D(C,I) ~ within noise: the six Exp24 flips are LLM
    nondeterminism, not a memory effect.
  - If D(C,I) > within noise: the memory context change causally
    affects move choice beyond stochasticity.

Design (preregistered):
  - Uses Exp24's calibration: seeds {2,7,11} (mem_diff >= 0.02),
    15 fixed FENs (seed 77777)
  - For each (seed, position): n_reps calls with control context
    and n_reps calls with intervention context
  - Metrics: move disagreement rate + |regret diff|
  - Compare D(C,I) vs max(D(C,C), D(I,I)) on both metrics
"""
import sys
import os
import json
import random
import time
import numpy as np
import chess
import subprocess
import urllib.request
from itertools import combinations
from typing import Dict, List, Optional

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, RESONANT

STOCKFISH_PATH = "/tmp/stockfish/stockfish-ubuntu-x86-64-avx2"
OLLAMA_MODEL = "hermes3:8b"
STOCKFISH_DEPTH = 15

SELECTED_SEEDS = [2, 7, 11]  # from Exp24 calibration
N_POSITIONS = 15
POSITION_SEED = 77777
N_REPS = 4
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
    mems = []
    for ta in test_angles:
        tq = make_embedding(float(ta))
        outcome = eng.recall(tq, top_k=top_k)
        for r in outcome.results:
            mems.append((r.memory.memory_id,
                         mem_angles[r.memory.memory_id],
                         round(r.final_score, 4)))
    return mems


def fmt_memories(mems):
    return "\n".join(f"  - Memory {mid}: angle {ang:.1f} degrees"
                     for mid, ang, sc in mems)


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
    return best_score - (-after)


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
    except Exception:
        return None


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


# ============================================================
# MAIN
# ============================================================
print("=" * 70)
print("EXP28: Variance decomposition — does C vs I exceed noise?")
print("=" * 70)
print(f"\n  Seeds: {SELECTED_SEEDS} (from Exp24 calibration)")
print(f"  Positions: {N_POSITIONS} (fixed, seed {POSITION_SEED})")
print(f"  Reps per condition: {N_REPS}")
print(f"  LLM calls: {len(SELECTED_SEEDS)} seeds x {N_POSITIONS} pos "
      f"x {N_REPS} reps x 2 cond = "
      f"{len(SELECTED_SEEDS)*N_POSITIONS*N_REPS*2}")
print()

positions = generate_chess_positions(N_POSITIONS, POSITION_SEED)
print(f"  {len(positions)} positions generated")

# Precompute best scores
best_scores = {}
for fen in positions:
    best_scores[fen] = stockfish_evaluate(fen)
print(f"  Stockfish baselines computed")

# Build contexts per seed
contexts = {}
for seed in SELECTED_SEEDS:
    rng_q = random.Random(seed)
    q = [rng_q.uniform(0, 360) for _ in range(N_QUERIES)]

    eng_c, mem_c = build_field(seed=seed)
    run_memory_trajectory(eng_c, q, 999, 999, False)
    eng_i, _ = build_field(seed=seed)
    run_memory_trajectory(eng_i, q, INT_START, INT_END, True)

    test_angles = q[INT_END:INT_END + 8]
    c_mems = memory_context(eng_c, test_angles, mem_c)
    i_mems = memory_context(eng_i, test_angles, mem_c)
    contexts[seed] = {"C": fmt_memories(c_mems), "I": fmt_memories(i_mems)}
    print(f"  Seed {seed}: contexts built")

# Run repeated measurements
print(f"\n  Running {N_REPS} reps per condition per position...")

within_cc_disagree = 0   # C rep vs C rep
within_ii_disagree = 0   # I rep vs I rep
between_ci_disagree = 0  # C rep vs I rep
within_cc_pairs = 0
within_ii_pairs = 0
between_ci_pairs = 0

within_cc_regret = []
within_ii_regret = []
between_ci_regret = []

per_pos_detail = []

for seed in SELECTED_SEEDS:
    print(f"\n  Seed {seed}:")
    c_lines = contexts[seed]["C"]
    i_lines = contexts[seed]["I"]

    for pi, fen in enumerate(positions):
        # Collect moves per condition
        c_moves = [llm_pick_move(OLLAMA_MODEL, fen, c_lines)
                   for _ in range(N_REPS)]
        i_moves = [llm_pick_move(OLLAMA_MODEL, fen, i_lines)
                   for _ in range(N_REPS)]

        # Regrets
        c_regrets = [move_regret(fen, m, best_scores[fen])
                     for m in c_moves]
        i_regrets = [move_regret(fen, m, best_scores[fen])
                     for m in i_moves]

        # Within C disagreement
        cc_d = 0
        cc_n = 0
        for a, b in combinations(range(N_REPS), 2):
            cc_n += 1
            if c_moves[a] != c_moves[b]:
                cc_d += 1
            if c_regrets[a] is not None and c_regrets[b] is not None:
                within_cc_regret.append(abs(c_regrets[a] - c_regrets[b]))
        within_cc_disagree += cc_d
        within_cc_pairs += cc_n

        # Within I disagreement
        ii_d = 0
        ii_n = 0
        for a, b in combinations(range(N_REPS), 2):
            ii_n += 1
            if i_moves[a] != i_moves[b]:
                ii_d += 1
            if i_regrets[a] is not None and i_regrets[b] is not None:
                within_ii_regret.append(abs(i_regrets[a] - i_regrets[b]))
        within_ii_disagree += ii_d
        within_ii_pairs += ii_n

        # Between C-I disagreement
        ci_d = 0
        ci_n = 0
        for a in range(N_REPS):
            for b in range(N_REPS):
                ci_n += 1
                if c_moves[a] != i_moves[b]:
                    ci_d += 1
                if c_regrets[a] is not None and i_regrets[b] is not None:
                    between_ci_regret.append(
                        abs(c_regrets[a] - i_regrets[b]))
        between_ci_disagree += ci_d
        between_ci_pairs += ci_n

        pos_tag = ""
        if cc_d or ii_d or ci_d:
            pos_tag = f"  cc={cc_d}/{cc_n} ii={ii_d}/{ii_n} ci={ci_d}/{ci_n}"
        print(f"    pos {pi+1:>2}: C={c_moves} I={i_moves}{pos_tag}")

# ============================================================
# Results
# ============================================================
print("\n" + "=" * 70)
print("VARIANCE DECOMPOSITION")
print("=" * 70)

r_cc = within_cc_disagree / max(within_cc_pairs, 1)
r_ii = within_ii_disagree / max(within_ii_pairs, 1)
r_ci = between_ci_disagree / max(between_ci_pairs, 1)
r_within = max(r_cc, r_ii)

print(f"\n  Move disagreement rates:")
print(f"    D(C,C) = {within_cc_disagree}/{within_cc_pairs} = {r_cc:.3f}")
print(f"    D(I,I) = {within_ii_disagree}/{within_ii_pairs} = {r_ii:.3f}")
print(f"    D(C,I) = {between_ci_disagree}/{between_ci_pairs} = {r_ci:.3f}")
print(f"    max within = {r_within:.3f}")

w_cc = np.array(within_cc_regret) if within_cc_regret else np.array([0.0])
w_ii = np.array(within_ii_regret) if within_ii_regret else np.array([0.0])
w_ci = np.array(between_ci_regret) if between_ci_regret else np.array([0.0])

print(f"\n  |regret diff| distributions:")
print(f"    within C:  mean={w_cc.mean():.1f}  max={w_cc.max():.0f}  "
      f"n={len(w_cc)}")
print(f"    within I:  mean={w_ii.mean():.1f}  max={w_ii.max():.0f}  "
      f"n={len(w_ii)}")
print(f"    between:   mean={w_ci.mean():.1f}  max={w_ci.max():.0f}  "
      f"n={len(w_ci)}")

# Ratio
ratio = r_ci / max(r_within, 0.001)
print(f"\n  D(C,I) / max(D(C,C), D(I,I)) = {ratio:.2f}")

# ============================================================
# Verdict
# ============================================================
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

if r_ci > r_within * 2 and r_ci > 0.05:
    print(f"\n  SIGNAL BEYOND NOISE: D(C,I)={r_ci:.3f} exceeds")
    print(f"  within-condition noise (max={r_within:.3f}) by {ratio:.1f}x.")
    print(f"  The memory-context change causally affects move choice")
    print(f"  beyond LLM stochasticity.")
    print(f"\n  This does NOT mean the effect is large — it means it")
    print(f"  exists. Equivalence is still untested at the effect")
    print(f"  magnitude level.")
elif r_ci > r_within * 1.2 and r_ci > 0.03:
    print(f"\n  MARGINAL SIGNAL: D(C,I)={r_ci:.3f} exceeds within-noise")
    print(f"  ({r_within:.3f}) by {ratio:.1f}x — some evidence of a")
    print(f"  context effect but near the noise boundary.")
elif abs(r_ci - r_within) < 0.02:
    print(f"\n  NO SIGNAL: D(C,I)={r_ci:.3f} ~ within-noise")
    print(f"  ({r_within:.3f}). The observed flips are LLM")
    print(f"  nondeterminism, not a memory-context effect.")
    print(f"  Supports H11 specificity: changing memory context does")
    print(f"  not change chess behavior beyond noise.")
else:
    print(f"\n  AMBIGUOUS: D(C,I)={r_ci:.3f}, within={r_within:.3f}.")
    print(f"  Ratio {ratio:.2f} is near 1 — cannot cleanly separate.")

# Regret comparison
w_max = max(w_cc.mean(), w_ii.mean())
if w_ci.mean() > w_max * 2 and w_ci.mean() > 5:
    print(f"\n  Regret diffs: between ({w_ci.mean():.1f}cp) >> within")
    print(f"  ({w_max:.1f}cp) — when moves differ, the consequences")
    print(f"  are large, not just marginal flips.")
elif w_ci.mean() <= w_max * 1.5:
    print(f"\n  Regret diffs: between ({w_ci.mean():.1f}cp) ~ within")
    print(f"  ({w_max:.1f}cp) — magnitudes are noise-consistent.")
