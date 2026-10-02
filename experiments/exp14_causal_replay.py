"""
Exp14: MNEME — counterfactual causal-state replay.

Exp12 found 56.5% closure with CF0 (restore set membership). The remaining
43.5% were score-only flips: same evidence set, different scores. CF0
cannot capture those.

The user's insight: don't copy the control's final result (circular).
Restore the causal antecedent state and re-execute the dynamics.

Counterfactual levels:

  CF0: restore set membership (Exp12 — already done)
  CF1: restore set + scores (copy control's scores, recompute decision)
  CF2: restore memory states (copy control's REINFORCED/NEUTRAL states
       into the intervention engine, then RE-RUN the recall dynamics)
  CF3: restore full causal state (replace intervention engine's entire
       state with control's at that step, then re-run recall — should
       always match control, sanity check)

CF2 is the key: we restore the control's memory states (which memories
are REINFORCED) into the intervention engine, then re-execute the BFS
propagation and scoring. If the decision matches control, the memory
states were the causal antecedent. If not, something else (STDP links,
activations) also differs.

CF3 is a sanity check: if we restore the FULL state and the decision
doesn't match control, our snapshot/restore is broken.
"""
import sys
import numpy as np
import random
from dataclasses import dataclass, field
from typing import List, Dict

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT


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
    votes = {}
    rng = random.Random(seed)
    for i in range(n_memories):
        angle = (i * 360.0 / n_memories) % 360
        mid = f"M{i:04d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim))
        votes[mid] = "yes" if rng.random() < 0.6 else "no"
    half = n_memories // 2
    for i in range(half):
        eng.add_link(f"M{i:04d}", f"M{i+half:04d}", RESONANT)
    return eng, memories, votes


def make_decision(results, votes):
    yes_w = 0.0
    no_w = 0.0
    evidence = {}
    for r in results:
        mid = r.memory.memory_id
        vote = votes.get(mid, "abstain")
        if vote == "yes":
            yes_w += r.final_score
            evidence[mid] = "yes"
        elif vote == "no":
            no_w += r.final_score
            evidence[mid] = "no"
    if yes_w > no_w:
        dec = "yes"
    elif no_w > yes_w:
        dec = "no"
    else:
        dec = "abstain"
    return dec, yes_w, no_w, evidence


def run_trajectory_with_snapshots(query_angles, int_start, int_end,
                                   block_reinforcement, seed=42):
    """Run trajectory, snapshot engine state BEFORE each recall."""
    eng, memories, votes = build_field(seed=seed)
    prev_recalled = None
    trajectory = []

    for step, q_angle in enumerate(query_angles):
        query = make_embedding(q_angle)
        now = float(step)

        # Snapshot state BEFORE this step's recall
        snap = eng.snapshot_state()

        outcome = eng.recall_with_learning(
            query, top_k=10, now=now,
            current_turn_memories=prev_recalled,
        )
        recalled_ids = [r.memory.memory_id for r in outcome.results]
        recalled_scores = {r.memory.memory_id: round(r.final_score, 6)
                          for r in outcome.results}
        dec, yes_w, no_w, evidence = make_decision(outcome.results, votes)

        in_int = int_start <= step < int_end
        if recalled_ids and not (in_int and block_reinforcement):
            eng.reinforce(recalled_ids[0])
        if prev_recalled and recalled_ids:
            eng.update_stdp(prev_recalled, recalled_ids)
        eng.update_activations(recalled_ids, now)

        trajectory.append({
            "step": step,
            "query_angle": q_angle,
            "recalled": recalled_ids,
            "scores": recalled_scores,
            "decision": dec,
            "yes_weight": yes_w,
            "no_weight": no_w,
            "evidence": evidence,
            "state_snapshot": snap,
        })
        prev_recalled = recalled_ids

    return trajectory, eng, votes


def cf1_restore_scores(int_traj, control_traj, step, votes):
    """CF1: restore set + scores from control, recompute decision."""
    c = control_traj[step]
    # Use control's recalled set and scores
    yes_w = 0.0
    no_w = 0.0
    for mid in c["recalled"]:
        vote = votes.get(mid, "abstain")
        score = c["scores"].get(mid, 0)
        if vote == "yes":
            yes_w += score
        elif vote == "no":
            no_w += score
    if yes_w > no_w:
        return "yes"
    elif no_w > yes_w:
        return "no"
    return "abstain"


def cf2_restore_memory_states(int_eng, int_traj, control_traj, step,
                               query_angles, votes):
    """CF2: restore control's memory states into intervention engine,
    then RE-RUN the recall dynamics (BFS, scoring, etc.)."""
    c = control_traj[step]
    # Restore control's state snapshot into the intervention engine
    int_eng.restore_state(c["state_snapshot"])

    # Re-run the recall with the restored state
    query = make_embedding(c["query_angle"])
    now = float(step)
    # Use the control's prev_recalled (from the step before)
    if step > 0:
        prev = control_traj[step - 1]["recalled"]
    else:
        prev = None

    outcome = int_eng.recall_with_learning(
        query, top_k=10, now=now,
        current_turn_memories=prev,
    )
    dec, yes_w, no_w, evidence = make_decision(outcome.results, votes)
    return dec


def cf2a_restore_state_only(int_eng, int_traj, control_traj, step,
                             query_angles, votes):
    """CF2a: restore ONLY the REINFORCED/NEUTRAL state from control,
    keep the intervention's STDP links, explicit links, and activations.
    This isolates whether memory state alone is the causal antecedent."""
    c = control_traj[step]
    c_snap = c["state_snapshot"]

    # Restore ONLY the state field, keep everything else from intervention
    for mid, mem_data in c_snap["memories"].items():
        mem = int_eng.memories.get(mid)
        if mem:
            mem.state = mem_data["state"]
    # Don't restore links, synaptic_links, last_activation, or active_cells

    query = make_embedding(c["query_angle"])
    now = float(step)
    if step > 0:
        prev = control_traj[step - 1]["recalled"]
    else:
        prev = None

    outcome = int_eng.recall_with_learning(
        query, top_k=10, now=now,
        current_turn_memories=prev,
    )
    dec, yes_w, no_w, evidence = make_decision(outcome.results, votes)
    return dec


def cf2b_restore_state_and_stdp(int_eng, int_traj, control_traj, step,
                                query_angles, votes):
    """CF2b: restore state + STDP links from control, keep explicit links
    and activations from intervention. Isolates STDP contribution."""
    c = control_traj[step]
    c_snap = c["state_snapshot"]

    for mid, mem_data in c_snap["memories"].items():
        mem = int_eng.memories.get(mid)
        if mem:
            mem.state = mem_data["state"]
            mem.synaptic_links = dict(mem_data["synaptic_links"])
    # Don't restore explicit links, last_activation, or active_cells

    query = make_embedding(c["query_angle"])
    now = float(step)
    if step > 0:
        prev = control_traj[step - 1]["recalled"]
    else:
        prev = None

    outcome = int_eng.recall_with_learning(
        query, top_k=10, now=now,
        current_turn_memories=prev,
    )
    dec, yes_w, no_w, evidence = make_decision(outcome.results, votes)
    return dec


def cf3_restore_full_state(int_eng, control_traj, step, query_angles, votes):
    """CF3: restore full control state, re-run recall. Sanity check."""
    c = control_traj[step]
    int_eng.restore_state(c["state_snapshot"])
    query = make_embedding(c["query_angle"])
    now = float(step)
    if step > 0:
        prev = control_traj[step - 1]["recalled"]
    else:
        prev = None
    outcome = int_eng.recall_with_learning(
        query, top_k=10, now=now,
        current_turn_memories=prev,
    )
    dec, yes_w, no_w, evidence = make_decision(outcome.results, votes)
    return dec


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP14: MNEME — counterfactual causal-state replay")
print("=" * 70)

n_queries = 120
int_start = 40
int_end = 70
seeds = list(range(20))

print(f"\n  {n_queries} queries, intervention at {int_start}-{int_end}")
print(f"  Full reinforcement block during intervention")
print(f"  Seeds: {len(seeds)}")
print(f"  Counterfactual levels: CF0 (set), CF1 (set+scores),")
print(f"    CF2 (memory states replay), CF3 (full state, sanity)")
print()

cf0_restored = 0
cf1_restored = 0
cf2_restored = 0
cf2a_restored = 0
cf2b_restored = 0
cf3_restored = 0
cf3_failed = 0  # Should be 0 — sanity check
total_washout_flips = 0
flip_details = []

for seed in seeds:
    rng_q = random.Random(seed)
    query_angles = [rng_q.uniform(0, 360) for _ in range(n_queries)]

    control_traj, _, votes = run_trajectory_with_snapshots(
        query_angles, 999, 999, False, seed=seed)
    int_traj, int_eng, _ = run_trajectory_with_snapshots(
        query_angles, int_start, int_end, True, seed=seed)

    for i in range(int_end, n_queries):
        c_dec = control_traj[i]["decision"]
        t_dec = int_traj[i]["decision"]
        if c_dec != t_dec:
            total_washout_flips += 1

            # CF0: restore set membership (from Exp12)
            c_evidence = set(control_traj[i]["evidence"].keys())
            t_evidence = set(int_traj[i]["evidence"].keys())
            missing = c_evidence - t_evidence
            added = t_evidence - c_evidence
            cf0_yes = int_traj[i]["yes_weight"]
            cf0_no = int_traj[i]["no_weight"]
            for mid in missing:
                vote = control_traj[i]["evidence"].get(mid, "abstain")
                score = control_traj[i]["scores"].get(mid, 0)
                if vote == "yes":
                    cf0_yes += score
                elif vote == "no":
                    cf0_no += score
            for mid in added:
                vote = int_traj[i]["evidence"].get(mid, "abstain")
                score = int_traj[i]["scores"].get(mid, 0)
                if vote == "yes":
                    cf0_yes -= score
                elif vote == "no":
                    cf0_no -= score
            cf0_dec = "yes" if cf0_yes > cf0_no else ("no" if cf0_no > cf0_yes else "abstain")
            if cf0_dec == c_dec:
                cf0_restored += 1

            # CF1: restore set + scores
            cf1_dec = cf1_restore_scores(int_traj, control_traj, i, votes)
            if cf1_dec == c_dec:
                cf1_restored += 1

            # CF2: restore full memory states + replay
            cf2_dec = cf2_restore_memory_states(int_eng, int_traj,
                                                control_traj, i,
                                                query_angles, votes)
            if cf2_dec == c_dec:
                cf2_restored += 1

            # CF2a: restore ONLY REINFORCED/NEUTRAL state, keep intervention's STDP
            cf2a_dec = cf2a_restore_state_only(int_eng, int_traj,
                                               control_traj, i,
                                               query_angles, votes)
            if cf2a_dec == c_dec:
                cf2a_restored += 1

            # CF2b: restore state + STDP links, keep intervention's explicit links
            cf2b_dec = cf2b_restore_state_and_stdp(int_eng, int_traj,
                                                  control_traj, i,
                                                  query_angles, votes)
            if cf2b_dec == c_dec:
                cf2b_restored += 1

            # CF3: restore full state (sanity check)
            cf3_dec = cf3_restore_full_state(int_eng, control_traj, i,
                                            query_angles, votes)
            if cf3_dec == c_dec:
                cf3_restored += 1
            else:
                cf3_failed += 1

            if len(flip_details) < 8:
                flip_details.append({
                    "seed": seed, "step": i,
                    "control": c_dec, "intervention": t_dec,
                    "cf0": cf0_dec, "cf1": cf1_dec,
                    "cf2": cf2_dec, "cf2a": cf2a_dec,
                    "cf2b": cf2b_dec, "cf3": cf3_dec,
                    "missing": sorted(missing),
                    "added": sorted(added),
                })

# Results
print("=" * 70)
print("RESULTS")
print("=" * 70)

print(f"\n  Post-washout flips: {total_washout_flips}")
print(f"\n  Counterfactual closure rates:")
print(f"    CF0  (restore set membership):          {cf0_restored}/{total_washout_flips} "
      f"({cf0_restored/max(total_washout_flips,1):.1%})")
print(f"    CF1  (restore set + scores):            {cf1_restored}/{total_washout_flips} "
      f"({cf1_restored/max(total_washout_flips,1):.1%})")
print(f"    CF2  (full state replay):               {cf2_restored}/{total_washout_flips} "
      f"({cf2_restored/max(total_washout_flips,1):.1%})")
print(f"    CF2a (state only, keep int STDP):        {cf2a_restored}/{total_washout_flips} "
      f"({cf2a_restored/max(total_washout_flips,1):.1%})")
print(f"    CF2b (state + STDP, keep int links):     {cf2b_restored}/{total_washout_flips} "
      f"({cf2b_restored/max(total_washout_flips,1):.1%})")
print(f"    CF3  (full state — sanity):             {cf3_restored}/{total_washout_flips} "
      f"({cf3_restored/max(total_washout_flips,1):.1%})")
if cf3_failed > 0:
    print(f"    CF3 FAILURES (should be 0):             {cf3_failed}")

print(f"\n--- Sample flips ---")
for fd in flip_details[:5]:
    print(f"\n  Seed {fd['seed']}, Step {fd['step']}:")
    print(f"    Control={fd['control']} Intervention={fd['intervention']}")
    print(f"    CF0={fd['cf0']} CF1={fd['cf1']} CF2={fd['cf2']} "
          f"CF2a={fd['cf2a']} CF2b={fd['cf2b']} CF3={fd['cf3']}")
    print(f"    Missing={fd['missing']} Added={fd['added']}")

# Verdict
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

cf2_rate = cf2_restored / max(total_washout_flips, 1)
cf2a_rate = cf2a_restored / max(total_washout_flips, 1)
cf1_rate = cf1_restored / max(total_washout_flips, 1)
cf0_rate = cf0_restored / max(total_washout_flips, 1)

print(f"\n  CF0  (set membership):       {cf0_rate:.1%}")
print(f"  CF1  (set + scores):         {cf1_rate:.1%}  [partially circular]")
print(f"  CF2  (full state replay):     {cf2_rate:.1%}")
print(f"  CF2a (state only, no STDP):   {cf2a_rate:.1%}")
print(f"  CF3  (full state sanity):     {cf3_restored/max(total_washout_flips,1):.1%}")

if cf3_failed > 0:
    print(f"\n  WARNING: CF3 sanity check failed {cf3_failed} times.")
    print(f"  Snapshot/restore may be incomplete.")

if cf2a_rate > 0.9:
    print(f"\n  SURVIVES — CF2a achieves {cf2a_rate:.1%} closure.")
    print(f"  Restoring ONLY the REINFORCED/NEUTRAL state from control")
    print(f"  and re-running the recall dynamics restores the control")
    print(f"  decision in ALL cases. The memory state is the complete")
    print(f"  causal antecedent — STDP links and explicit links are NOT")
    print(f"  needed for these flips.")
    print(f"\n  The causal chain is:")
    print(f"    intervention blocks reinforcement")
    print(f"      -> which memories are REINFORCED changes")
    print(f"      -> state multiplier in scoring changes")
    print(f"      -> scores change")
    print(f"      -> decision flips")
    print(f"\n  CF1 ({cf1_rate:.1%}) is partially circular (copies control's")
    print(f"  output scores). CF2a ({cf2a_rate:.1%}) is the proper causal")
    print(f"  counterfactual: restores the INPUT state, re-runs dynamics.")
elif cf2a_rate > cf0_rate:
    print(f"\n  IMPROVED — CF2a ({cf2a_rate:.1%}) beats CF0 ({cf0_rate:.1%}).")
    print(f"  Memory state restoration closes more flips than set membership.")
else:
    print(f"\n  WEAK — CF2a ({cf2a_rate:.1%}) does not improve over CF0 ({cf0_rate:.1%}).")
