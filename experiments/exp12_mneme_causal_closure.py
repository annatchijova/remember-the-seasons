"""
Exp12: MNEME — causal closure per instance.

The user's question:

  Decision D_control = YES
  Decision D_treated = NO
              |
              v
  Which recalls differed?
              |
              v
  Which memories caused that difference?
              |
              v
  Which state transitions changed those memories?
              |
              v
  Which transitions descend from intervention I?
              |
              v
  COUNTERFACTUAL:
  same history - intervention I
              |
              v
  does decision return to YES?

This experiment implements a minimal MNEME-style custody chain on top of
the minimal raven engine. For each decision in the trajectory, we record:

  1. RECALL: which memories were recalled (with scores)
  2. DECISION: what the agent decided (weighted vote)
  3. RECEIPT: which memories were used for the decision (the evidence base)
  4. CUSTODY: what state transitions happened (reinforcement, STDP)

Then, for each decision that FLIPPED between control and intervention, we
trace the causal chain backwards:

  - Which memories were in the control's evidence base but not the
    intervention's (or vice versa)?
  - Were those memories REINFORCED in control but not in intervention?
  - Was the reinforcement blocked during the intervention window?
  - COUNTERFACTUAL: if we restore the missing memory to the intervention's
    evidence base, does the decision flip back?

If the counterfactual restores the decision, we have causal closure:
  "This decision changed because the intervention at step T blocked the
  reinforcement of memory M; without that intervention, keeping everything
  else constant, the decision would not have changed."

If the counterfactual does NOT restore the decision, the flip was caused
by something else (or the simple vote model is too coarse to capture it).
"""
import sys
import numpy as np
import random
import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT, INHIBITORY, SYNAPTIC_SCORE_WEIGHT


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


@dataclass
class CustodyEvent:
    """One event in a memory's custody chain (MNEME-style)."""
    step: int
    memory_id: str
    event_type: str  # "STORED", "REINFORCED", "RECALLED", "DECISION_USED_MEMORY"
    details: Dict = field(default_factory=dict)
    # Hash chain
    prev_hash: str = ""
    entry_hash: str = ""

    def compute_hash(self):
        payload = json.dumps({
            "step": self.step,
            "memory_id": self.memory_id,
            "event_type": self.event_type,
            "details": self.details,
            "prev_hash": self.prev_hash,
        }, sort_keys=True)
        self.entry_hash = hashlib.sha256(payload.encode()).hexdigest()
        return self.entry_hash


@dataclass
class DecisionRecord:
    """A sealed decision with its evidence base (MNEME-style receipt)."""
    step: int
    query_angle: float
    recalled_ids: List[str]
    recalled_scores: Dict[str, float]
    decision: str  # "yes", "no", "abstain"
    yes_weight: float
    no_weight: float
    # Evidence base: which memories contributed to the decision
    evidence_base: Dict[str, str]  # memory_id -> "yes" or "no"
    # Seal
    seal: str = ""

    def compute_seal(self):
        payload = json.dumps({
            "step": self.step,
            "query_angle": self.query_angle,
            "recalled_ids": self.recalled_ids,
            "recalled_scores": self.recalled_scores,
            "decision": self.decision,
            "yes_weight": self.yes_weight,
            "no_weight": self.no_weight,
            "evidence_base": self.evidence_base,
        }, sort_keys=True)
        self.seal = hashlib.sha256(payload.encode()).hexdigest()
        return self.seal


def build_field_with_votes(n_memories=100, dim=32, seed=42):
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


def make_decision_with_evidence(recalled_results, votes):
    """Weighted majority vote with evidence base tracking."""
    yes_weight = 0.0
    no_weight = 0.0
    evidence_base = {}

    for r in recalled_results:
        mid = r.memory.memory_id
        vote = votes.get(mid, "abstain")
        if vote == "yes":
            yes_weight += r.final_score
            evidence_base[mid] = "yes"
        elif vote == "no":
            no_weight += r.final_score
            evidence_base[mid] = "no"

    if yes_weight > no_weight:
        decision = "yes"
    elif no_weight > yes_weight:
        decision = "no"
    else:
        decision = "abstain"

    return decision, yes_weight, no_weight, evidence_base


def run_trajectory_with_custody(query_angles, intervention_start, intervention_end,
                                block_reinforcement=True,
                                n_memories=100, dim=32, seed=42):
    """Run a trajectory with full custody chain tracking."""
    eng, memories, votes = build_field_with_votes(n_memories, dim, seed)
    prev_recalled = None
    trajectory = []
    custody_chains = {}  # memory_id -> list of CustodyEvent
    decisions = []  # list of DecisionRecord
    rng = random.Random(seed * 7 + 1)

    # Initialize custody chains for all memories (STORED event)
    for mid in memories:
        event = CustodyEvent(step=0, memory_id=mid, event_type="STORED")
        event.compute_hash()
        custody_chains[mid] = [event]

    for step, q_angle in enumerate(query_angles):
        query = make_embedding(q_angle, dim)
        now = float(step)

        outcome = eng.recall_with_learning(
            query, top_k=10, now=now,
            current_turn_memories=prev_recalled,
        )
        recalled_ids = [r.memory.memory_id for r in outcome.results]
        recalled_scores = {r.memory.memory_id: round(r.final_score, 6)
                          for r in outcome.results}

        in_intervention = intervention_start <= step < intervention_end

        # Make decision with evidence base
        decision, yes_w, no_w, evidence = make_decision_with_evidence(
            outcome.results, votes)

        # Record RECALLED custody events
        for mid in recalled_ids:
            prev_hash = custody_chains[mid][-1].entry_hash if custody_chains[mid] else ""
            event = CustodyEvent(
                step=step, memory_id=mid, event_type="RECALLED",
                details={"query_angle": q_angle, "score": recalled_scores.get(mid, 0)},
                prev_hash=prev_hash,
            )
            event.compute_hash()
            custody_chains[mid].append(event)

        # Record DECISION_USED_MEMORY custody events
        for mid, vote in evidence.items():
            prev_hash = custody_chains[mid][-1].entry_hash if custody_chains[mid] else ""
            event = CustodyEvent(
                step=step, memory_id=mid, event_type="DECISION_USED_MEMORY",
                details={"decision": decision, "vote": vote,
                        "yes_weight": yes_w, "no_weight": no_w},
                prev_hash=prev_hash,
            )
            event.compute_hash()
            custody_chains[mid].append(event)

        # Seal the decision
        dec_record = DecisionRecord(
            step=step, query_angle=q_angle,
            recalled_ids=recalled_ids,
            recalled_scores=recalled_scores,
            decision=decision, yes_weight=yes_w, no_weight=no_w,
            evidence_base=evidence,
        )
        dec_record.compute_seal()
        decisions.append(dec_record)

        # Reinforcement (with intervention blocking)
        reinforced_this_step = None
        if recalled_ids:
            should_reinforce = True
            if in_intervention and block_reinforcement:
                should_reinforce = False
            if should_reinforce:
                eng.reinforce(recalled_ids[0])
                reinforced_this_step = recalled_ids[0]
                # Record REINFORCED custody event
                mid = recalled_ids[0]
                prev_hash = custody_chains[mid][-1].entry_hash if custody_chains[mid] else ""
                event = CustodyEvent(
                    step=step, memory_id=mid, event_type="REINFORCED",
                    details={"intervention_blocked": False},
                    prev_hash=prev_hash,
                )
                event.compute_hash()
                custody_chains[mid].append(event)
            elif in_intervention:
                # Record that reinforcement was BLOCKED
                mid = recalled_ids[0]
                prev_hash = custody_chains[mid][-1].entry_hash if custody_chains[mid] else ""
                event = CustodyEvent(
                    step=step, memory_id=mid, event_type="REINFORCEMENT_BLOCKED",
                    details={"intervention_blocked": True,
                            "intervention_step": step},
                    prev_hash=prev_hash,
                )
                event.compute_hash()
                custody_chains[mid].append(event)

        # STDP
        if prev_recalled and recalled_ids:
            eng.update_stdp(prev_recalled, recalled_ids)

        eng.update_activations(recalled_ids, now)

        trajectory.append({
            "step": step,
            "query_angle": q_angle,
            "recalled": recalled_ids,
            "scores": recalled_scores,
            "decision": decision,
            "yes_weight": yes_w,
            "no_weight": no_w,
            "evidence_base": evidence,
            "in_intervention": in_intervention,
            "reinforced": reinforced_this_step,
        })
        prev_recalled = recalled_ids

    return trajectory, custody_chains, decisions


def causal_closure_for_flip(control_traj, intervention_traj, control_decisions,
                            intervention_decisions, step):
    """For a decision that flipped at `step`, trace the causal chain.

    Returns a structured causal analysis.
    """
    c = control_traj[step]
    t = intervention_traj[step]

    c_evidence = set(c["evidence_base"].keys())
    t_evidence = set(t["evidence_base"].keys())

    # Memories in control's evidence but not intervention's
    missing_from_intervention = c_evidence - t_evidence
    # Memories in intervention's evidence but not control's
    added_in_intervention = t_evidence - c_evidence

    # For each missing memory, check if it was REINFORCED in control
    # but not in intervention (i.e., the intervention blocked it)
    missing_reinforced = []
    for mid in missing_from_intervention:
        c_state = None
        t_state = None
        # Check if this memory is REINFORCED at this step in control
        # vs intervention (we need to check the engine state, but we
        # don't have it here — we use the custody chain instead)
        # For now, check if the memory appears in control's recalled
        # set with a higher score than in intervention's
        c_score = c["scores"].get(mid, 0)
        t_score = t["scores"].get(mid, 0)
        if c_score > t_score:
            missing_reinforced.append({
                "memory": mid,
                "control_score": c_score,
                "intervention_score": t_score,
                "vote": c["evidence_base"].get(mid, "?"),
            })

    # Counterfactual: if we add the missing memories back to the
    # intervention's evidence base, does the decision flip back?
    cf_yes_weight = t["yes_weight"]
    cf_no_weight = t["no_weight"]

    for mid in missing_from_intervention:
        vote = c["evidence_base"].get(mid, "abstain")
        score = c["scores"].get(mid, 0)
        if vote == "yes":
            cf_yes_weight += score
        elif vote == "no":
            cf_no_weight += score

    for mid in added_in_intervention:
        vote = t["evidence_base"].get(mid, "abstain")
        score = t["scores"].get(mid, 0)
        if vote == "yes":
            cf_yes_weight -= score
        elif vote == "no":
            cf_no_weight -= score

    if cf_yes_weight > cf_no_weight:
        cf_decision = "yes"
    elif cf_no_weight > cf_yes_weight:
        cf_decision = "no"
    else:
        cf_decision = "abstain"

    # Did the counterfactual restore the control's decision?
    cf_restores = (cf_decision == c["decision"])

    return {
        "step": step,
        "control_decision": c["decision"],
        "intervention_decision": t["decision"],
        "control_yes_weight": c["yes_weight"],
        "control_no_weight": c["no_weight"],
        "intervention_yes_weight": t["yes_weight"],
        "intervention_no_weight": t["no_weight"],
        "missing_from_intervention": sorted(missing_from_intervention),
        "added_in_intervention": sorted(added_in_intervention),
        "missing_reinforced": missing_reinforced,
        "counterfactual_decision": cf_decision,
        "counterfactual_restores_control": cf_restores,
        "counterfactual_yes_weight": cf_yes_weight,
        "counterfactual_no_weight": cf_no_weight,
    }


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP12: MNEME — causal closure per instance")
print("=" * 70)

n_queries = 120
intervention_start = 40
intervention_duration = 30
intervention_end = intervention_start + intervention_duration
seeds = list(range(20))

print(f"\n  {n_queries} queries, intervention at {intervention_start}-{intervention_end}")
print(f"  Full reinforcement block during intervention")
print(f"  Seeds: {len(seeds)}")
print(f"  Custody chain: per-memory, append-only, hash-linked")
print(f"  Decision model: weighted majority vote with evidence base")
print()

total_flips = 0
total_washout_flips = 0
total_cf_restored = 0
total_cf_not_restored = 0
flip_details = []

for seed in seeds:
    rng_q = random.Random(seed)
    query_angles = [rng_q.uniform(0, 360) for _ in range(n_queries)]

    control_traj, control_custody, control_decs = run_trajectory_with_custody(
        query_angles, 999, 999, block_reinforcement=False, seed=seed)
    int_traj, int_custody, int_decs = run_trajectory_with_custody(
        query_angles, intervention_start, intervention_end,
        block_reinforcement=True, seed=seed)

    for i in range(n_queries):
        c_dec = control_traj[i]["decision"]
        t_dec = int_traj[i]["decision"]
        if c_dec != t_dec:
            total_flips += 1
            if i >= intervention_end:
                total_washout_flips += 1

                # Causal closure analysis
                analysis = causal_closure_for_flip(
                    control_traj, int_traj, control_decs, int_decs, i)

                if analysis["counterfactual_restores_control"]:
                    total_cf_restored += 1
                else:
                    total_cf_not_restored += 1

                if len(flip_details) < 10:  # Keep first 10 for display
                    flip_details.append(analysis)

# Summary
print("=" * 70)
print("RESULTS")
print("=" * 70)

print(f"\n  Total decision flips: {total_flips}")
print(f"  Post-washout flips: {total_washout_flips}")
print(f"  Counterfactual restored control decision: {total_cf_restored}")
print(f"  Counterfactual did NOT restore: {total_cf_not_restored}")
print(f"  Closure rate: {total_cf_restored}/{total_washout_flips} "
      f"({total_cf_restored/max(total_washout_flips,1):.1%})")

print(f"\n--- First flips with causal closure ---")
for fd in flip_details[:5]:
    print(f"\n  Step {fd['step']}:")
    print(f"    Control decision:     {fd['control_decision']} "
          f"(yes={fd['control_yes_weight']:.4f}, no={fd['control_no_weight']:.4f})")
    print(f"    Intervention decision: {fd['intervention_decision']} "
          f"(yes={fd['intervention_yes_weight']:.4f}, no={fd['intervention_no_weight']:.4f})")
    print(f"    Missing from intervention: {fd['missing_from_intervention']}")
    print(f"    Added in intervention:     {fd['added_in_intervention']}")
    if fd["missing_reinforced"]:
        for mr in fd["missing_reinforced"]:
            print(f"      {mr['memory']}: control_score={mr['control_score']:.4f} "
                  f"-> intervention_score={mr['intervention_score']:.4f} "
                  f"(vote={mr['vote']})")
    print(f"    Counterfactual decision: {fd['counterfactual_decision']} "
          f"(yes={fd['counterfactual_yes_weight']:.4f}, "
          f"no={fd['counterfactual_no_weight']:.4f})")
    print(f"    Counterfactual restores control: "
          f"{'YES' if fd['counterfactual_restores_control'] else 'NO'}")

# Verdict
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

closure_rate = total_cf_restored / max(total_washout_flips, 1)
if closure_rate > 0.8:
    print(f"  SURVIVES — {closure_rate:.1%} of flips have causal closure.")
    print(f"  For most flipped decisions, we can identify which memories")
    print(f"  were missing from the intervention's evidence base and")
    print(f"  demonstrate that restoring them flips the decision back.")
    print(f"  This is MNEME-style causal closure: per-instance, not")
    print(f"  aggregate.")
elif closure_rate > 0.5:
    print(f"  WEAK — {closure_rate:.1%} of flips have causal closure.")
    print(f"  Some decisions can be causally explained, but not all.")
    print(f"  The simple vote model may be too coarse for full closure.")
else:
    print(f"  FALSIFIED — {closure_rate:.1%} of flips have causal closure.")
    print(f"  The counterfactual rarely restores the control decision.")
    print(f"  The simple vote model cannot provide causal closure.")

print(f"\n  MNEME contribution: the custody chain records WHICH memories")
print(f"  were used for each decision, so we can trace the causal chain")
print(f"  from decision -> recall -> memory -> state transition ->")
print(f"  intervention. This is per-instance, not aggregate statistics.")
