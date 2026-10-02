"""
Exp20: REAL behavioral off-target assay — LLM agent + Stockfish ground truth.

Exp18 was a pipeline check (independent task, same seed -> identical by
construction). This is the real thing:

  same LLM model (Ollama, fixed model)
  same prompt
  same FEN
  same inference config (temperature=0)

  CONTROL MEMORY ─┐
                  ├─> LLM ─> chess move ─> Stockfish (fixed depth)
  DRUGGED MEMORY ─┘

The LLM receives recalled memories + chess position in its context.
The memories are about angles (irrelevant to chess). If the memory
intervention changes which memories are recalled, that changes the
LLM's context, which MIGHT change its chess move.

If chess quality differs between control and intervention:
  -> the memory intervention has an off-target behavioral effect
  -> Frankenstein is hanging the queen

If chess quality is preserved:
  -> the intervention is behaviorally memory-specific
  -> Frankenstein's chess is unaffected by memory changes

Ground truth: Stockfish 16 at fixed depth (not material+mobility).
The LLM's move is scored by Stockfish's evaluation of the resulting
position, normalized against the best move.

The probe (chess) does NOT write back to memory.
"""
import sys
import os
import json
import random
import time
import numpy as np
import chess
import subprocess
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT

STOCKFISH_PATH = "/tmp/stockfish/stockfish-ubuntu-x86-64-avx2"
OLLAMA_MODEL = "hermes3:8b"
STOCKFISH_DEPTH = 15


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
    """Run memory trajectory. Returns the engine with post-washout state."""
    prev_recalled = None
    for step, q_angle in enumerate(query_angles):
        query = make_embedding(q_angle)
        now = float(step)
        in_int = int_start <= step < int_end

        outcome = eng.recall_with_learning(query, top_k=10, now=now,
                                           current_turn_memories=prev_recalled)
        recalled_ids = [r.memory.memory_id for r in outcome.results]

        if recalled_ids and not (in_int and block_reinforcement):
            eng.reinforce(recalled_ids[0])
        if prev_recalled and recalled_ids:
            eng.update_stdp(prev_recalled, recalled_ids)
        eng.update_activations(recalled_ids, now)
        prev_recalled = recalled_ids


def recall_memories_for_chess(eng, n_memories=5):
    """Recall memories using a neutral query (angle=0) to provide
    context for the chess task. These memories are about angles,
    completely irrelevant to chess."""
    query = make_embedding(0.0)
    outcome = eng.recall(query, top_k=n_memories)
    return [(r.memory.memory_id, round(r.final_score, 4))
            for r in outcome.results]


def stockfish_evaluate(fen, depth=STOCKFISH_DEPTH):
    """Evaluate a position with Stockfish at fixed depth."""
    try:
        proc = subprocess.Popen(
            [STOCKFISH_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True
        )
        proc.stdin.write(f"position fen {fen}\n")
        proc.stdin.write(f"go depth {depth}\n")
        proc.stdin.flush()
        time.sleep(0.1)

        best_move = None
        best_score = None
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            if line.startswith("bestmove"):
                best_move = line.split()[1]
                break

        # Get evaluation
        proc.stdin.write(f"position fen {fen}\n")
        proc.stdin.write(f"go depth {depth}\n")
        proc.stdin.flush()
        time.sleep(0.1)

        score_cp = None
        for _ in range(100):
            line = proc.stdout.readline()
            if not line:
                break
            if line.startswith("info") and "score cp" in line:
                parts = line.split()
                idx = parts.index("cp") + 1
                score_cp = int(parts[idx])
            if line.startswith("bestmove"):
                break

        proc.stdin.write("quit\n")
        proc.stdin.flush()
        proc.wait(timeout=5)
        return best_move, score_cp
    except Exception as e:
        return None, None


def stockfish_score_move(fen, move, depth=STOCKFISH_DEPTH):
    """Score a move by evaluating the resulting position with Stockfish."""
    if move is None:
        return -1.0, None

    board = chess.Board(fen)
    try:
        move_obj = chess.Move.from_uci(move)
        if move_obj not in board.legal_moves:
            return -1.0, None
        board.push(move_obj)
    except Exception:
        return -1.0, None

    # Evaluate the resulting position from the opponent's perspective
    result_fen = board.fen()
    _, score = stockfish_evaluate(result_fen, depth)

    if score is None:
        return -1.0, None

    # Score is from the perspective of the side to move (opponent after our move)
    # Negate to get our perspective
    our_score = -score
    return our_score, score


def stockfish_best_score(fen, depth=STOCKFISH_DEPTH):
    """Get the best possible score for the position."""
    _, score = stockfish_evaluate(fen, depth)
    return score


def llm_pick_move(model, fen, memories):
    """Ask the LLM to pick a chess move, with memories in context."""
    import urllib.request

    mem_text = "\n".join(f"  - Memory {mid}: angle {angle:.1f} degrees"
                        for mid, angle, score in memories)

    prompt = f"""You are a chess player. Choose the best move for the current position.

Context memories (from a memory system, unrelated to chess):
{mem_text}

Chess position (FEN): {fen}

Legal moves: {' '.join(m.uci() for m in chess.Board(fen).legal_moves)}

Respond with ONLY the best move in UCI format (e.g., e2e4). No explanation."""

    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "seed": 42}
    }).encode()

    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        text = result.get("response", "").strip()
        # Extract UCI move from response
        for word in text.split():
            word = word.strip().strip(".,;:!?")
            if len(word) >= 4 and word[:1].isalpha() and word[1:2].isdigit():
                try:
                    move = chess.Move.from_uci(word)
                    if move in chess.Board(fen).legal_moves:
                        return move.uci()
                except Exception:
                    continue
        # Fallback: random move
        moves = list(chess.Board(fen).legal_moves)
        return random.choice(moves).uci() if moves else None
    except Exception as e:
        print(f"    LLM error: {e}")
        moves = list(chess.Board(fen).legal_moves)
        return random.choice(moves).uci() if moves else None


def generate_chess_positions(n, seed=42):
    """Generate n random legal chess positions."""
    rng = random.Random(seed)
    positions = []
    for _ in range(n):
        board = chess.Board()
        for _ in range(rng.randint(5, 20)):
            if board.is_game_over():
                break
            moves = list(board.legal_moves)
            board.push(rng.choice(moves))
        if not board.is_game_over():
            positions.append(board.fen())
    return positions


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP20: REAL behavioral off-target assay — LLM + Stockfish")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
n_chess = 20  # Keep LLM calls manageable
seeds = [42, 7, 13, 99, 3]  # Try multiple seeds to find divergent ones

print(f"\n  LLM: {OLLAMA_MODEL} (temperature=0)")
print(f"  Ground truth: Stockfish 16, depth {STOCKFISH_DEPTH}")
print(f"  Memory: 100 memories (angles), intervention at {int_start}-{int_end}")
print(f"  Chess positions: {n_chess}")
print(f"  Seeds: {len(seeds)} (LLM calls are slow)")
print()

all_results = []

for seed in seeds:
    print(f"  Seed {seed}:")

    # Generate queries and chess positions
    rng_q = random.Random(seed)
    query_angles = [rng_q.uniform(0, 360) for _ in range(n_queries)]
    chess_positions = generate_chess_positions(n_chess, seed=seed * 13)

    # Run memory trajectories
    print(f"    Running control memory trajectory...")
    eng_c, mem_c = build_field(seed=seed)
    run_memory_trajectory(eng_c, query_angles, 999, 999, False)

    print(f"    Running intervention memory trajectory...")
    eng_i, mem_i = build_field(seed=seed)
    run_memory_trajectory(eng_i, query_angles, int_start, int_end, True)

    # Recall memories for chess context using POST-WASHOUT queries
    # from the trajectory itself (these should produce divergent results
    # because the memory state diverged during the trajectory)
    post_washout_queries = query_angles[int_end:]  # steps 70-120
    test_angles = post_washout_queries[:8]  # use first 8 post-washout queries
    c_mems = []
    i_mems = []
    total_mem_diff = 0
    mem_angles = {mid: angle for mid, angle in mem_c.items()}

    for ta in test_angles:
        tq = make_embedding(float(ta))
        oc = eng_c.recall(tq, top_k=5)
        oi = eng_i.recall(tq, top_k=5)
        c_ids = set(r.memory.memory_id for r in oc.results)
        i_ids = set(r.memory.memory_id for r in oi.results)
        total_mem_diff += len(c_ids.symmetric_difference(i_ids))
        for r in oc.results:
            c_mems.append((r.memory.memory_id, mem_angles[r.memory.memory_id],
                          round(r.final_score, 4)))
        for r in oi.results:
            i_mems.append((r.memory.memory_id, mem_angles[r.memory.memory_id],
                          round(r.final_score, 4)))

    mem_diff = total_mem_diff / (len(test_angles) * 5)
    print(f"    Memory divergence (post-washout queries): {mem_diff:.4f}")
    c_set = set(m[0] for m in c_mems)
    i_set = set(m[0] for m in i_mems)
    print(f"    Unique control: {len(c_set)}, unique intervention: {len(i_set)}")
    print(f"    Set difference: {len(c_set.symmetric_difference(i_set))}")

    if mem_diff < 0.01:
        print(f"    WARNING: memory divergence is near zero.")
        print(f"    Chess quality difference will not be meaningful.")
        print(f"    Skipping chess evaluation for this seed.")
        all_results.append({
            "seed": seed,
            "mem_diff": mem_diff,
            "chess_c": -1,
            "chess_i": -1,
            "chess_diff": -1,
        })
        continue

    # Evaluate chess with each memory state
    print(f"    Evaluating chess positions with LLM...")
    c_scores = []
    i_scores = []
    c_best_scores = []
    i_best_scores = []

    for idx, fen in enumerate(chess_positions):
        print(f"      Position {idx+1}/{n_chess}...", end="", flush=True)

        # Control
        c_move = llm_pick_move(OLLAMA_MODEL, fen, c_mems)
        c_score, _ = stockfish_score_move(fen, c_move)
        best_score = stockfish_best_score(fen)
        c_scores.append(c_score)
        c_best_scores.append(best_score)

        # Intervention
        i_move = llm_pick_move(OLLAMA_MODEL, fen, i_mems)
        i_score, _ = stockfish_score_move(fen, i_move)
        i_scores.append(i_score)
        i_best_scores.append(best_score)

        print(f" c={c_score} i={i_score} best={best_score}")

    # Normalize: how close is each move to the best?
    c_normalized = []
    i_normalized = []
    for cs, ibs, is_, in zip(c_scores, c_best_scores, i_scores):
        if ibs is not None and ibs != 0:
            c_norm = max(0.0, min(1.0, (cs - ibs + 300) / 300))
            i_norm = max(0.0, min(1.0, (is_ - ibs + 300) / 300))
        else:
            c_norm = 1.0 if cs == 0 else 0.5
            i_norm = 1.0 if is_ == 0 else 0.5
        c_normalized.append(c_norm)
        i_normalized.append(i_norm)

    avg_c = np.mean(c_normalized)
    avg_i = np.mean(i_normalized)
    diff = abs(avg_c - avg_i)

    print(f"\n    Chess quality (control):     {avg_c:.4f}")
    print(f"    Chess quality (intervention): {avg_i:.4f}")
    print(f"    Difference:                   {diff:.4f}")
    print(f"    Memory divergence:            {mem_diff:.4f}")

    all_results.append({
        "seed": seed,
        "mem_diff": mem_diff,
        "chess_c": avg_c,
        "chess_i": avg_i,
        "chess_diff": diff,
    })

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

valid_results = [r for r in all_results if r["chess_diff"] >= 0]

if not valid_results:
    print(f"\n  No seeds produced sufficient memory divergence.")
    print(f"  Chess evaluation skipped for all seeds.")
    print(f"  Need to investigate why memory divergence is near zero")
    print(f"  for all tested seeds.")
else:
    avg_mem = np.mean([r["mem_diff"] for r in valid_results])
    avg_chess_c = np.mean([r["chess_c"] for r in valid_results])
    avg_chess_i = np.mean([r["chess_i"] for r in valid_results])
    avg_diff = np.mean([r["chess_diff"] for r in valid_results])

    print(f"\n  Seeds with sufficient divergence: {len(valid_results)}/{len(all_results)}")
    print(f"  Memory divergence:     {avg_mem:.4f}")
    print(f"  Chess quality (ctrl):  {avg_chess_c:.4f}")
    print(f"  Chess quality (int):   {avg_chess_i:.4f}")
    print(f"  Chess difference:      {avg_diff:.4f}")

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

if not valid_results:
    print(f"\n  INCONCLUSIVE — no seeds produced sufficient memory divergence.")
    print(f"  The memory intervention did not produce divergent recall at")
    print(f"  the post-washout queries for any tested seed.")
    print(f"  This may mean the intervention is too weak for this setup,")
    print(f"  or the test queries don't hit the affected memories.")
elif avg_diff < 0.02:
    print(f"\n  PASS — chess quality is preserved (diff={avg_diff:.4f}).")
    print(f"  The memory intervention does NOT degrade chess performance.")
    print(f"  Frankenstein does not hang the queen.")
    print(f"\n  The intervention is behaviorally memory-specific: it changes")
    print(f"  memory recall but does not affect orthogonal reasoning")
    print(f"  (chess move quality) when an LLM agent uses the memory.")
elif avg_diff < 0.05:
    print(f"\n  MARGINAL — small chess quality difference ({avg_diff:.4f}).")
    print(f"  May be noise. More seeds needed to confirm.")
else:
    print(f"\n  FAIL — chess quality degraded by {avg_diff:.4f}.")
    print(f"  The memory intervention has an off-target behavioral effect.")
    print(f"  Frankenstein IS hanging the queen.")
    print(f"  Different memory context (from the intervention) changes")
    print(f"  the LLM's chess reasoning, even though the memories are")
    print(f"  irrelevant to chess.")
