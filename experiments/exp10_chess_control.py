"""
Exp10: Orthogonal behavioral control — the real chess test.

The nearest-memory probe (Exp5) was a weak negative control. Here we
implement a REAL orthogonal behavioral control:

Design: TWO independent domains in the same field.
  - Domain A: memories at angles 0-180 (the "memory" domain)
  - Domain B: memories at angles 180-360 (the "chess" domain)
  - The intervention blocks reinforcement ONLY for domain A memories
  - Domain B reinforcement proceeds normally

The "chess" test: after the intervention + washout, does domain B recall
still work correctly? If the intervention (which only touched domain A)
degraded domain B, it's a general poison leaking across domains.

But our intervention is global (blocks ALL reinforcement). So we also
test a DOMAIN-SPECIFIC intervention: block reinforcement only for
memories whose angle is in [0, 180).

If domain-specific intervention:
  - degrades domain A recall (expected — that's the target)
  - does NOT degrade domain B recall (the chess test)
  -> the intervention is truly memory-specific

If global intervention:
  - degrades both domains
  -> the intervention is a general poison (expected for global block)

This tells us whether the path dependence is a property of the memory
dynamics (domain-specific) or a general system-wide degradation.
"""
import sys
import numpy as np
import random

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from minimal_raven import MinimalRaven, State, RESONANT, INHIBITORY, SYNAPTIC_SCORE_WEIGHT


def make_embedding(angle_deg, dim=32):
    rad = np.radians(angle_deg)
    v = np.zeros(dim, dtype=np.float64)
    v[0] = np.cos(rad)
    v[1] = np.sin(rad)
    return v


def build_two_domain_field(n_per_domain=50, dim=32, seed=42):
    """Build a field with two domains: A (0-180) and B (180-360)."""
    eng = MinimalRaven(hops=2, links_on=True, state_on=True,
                       recency_on=False, rescue_on=True,
                       auto_contradiction=False, k_neighbors=6)
    memories = {}

    # Domain A: 0-180 degrees
    for i in range(n_per_domain):
        angle = (i * 180.0 / n_per_domain)
        mid = f"A{i:03d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim))

    # Domain B: 180-360 degrees
    for i in range(n_per_domain):
        angle = 180 + (i * 180.0 / n_per_domain)
        mid = f"B{i:03d}"
        memories[mid] = angle
        eng.store(mid, make_embedding(angle, dim))

    # RESONANT links within each domain
    for i in range(n_per_domain // 2):
        eng.add_link(f"A{i:03d}", f"A{i + n_per_domain//2:03d}", RESONANT)
        eng.add_link(f"B{i:03d}", f"B{i + n_per_domain//2:03d}", RESONANT)

    return eng, memories


def run_two_domain_trajectory(query_angles, query_domains,
                               intervention_start, intervention_end,
                               block_domain="A",  # "A", "B", "both", or "none"
                               n_per_domain=50, dim=32, seed=42):
    """Run a trajectory with two domains. During intervention, actively
    de-reinforce (set to NEUTRAL) memories in the blocked domain.

    This is a stronger intervention than merely blocking new reinforcement:
    it actively reverses prior consolidation."""
    eng, memories = build_two_domain_field(n_per_domain, dim, seed)
    prev_recalled = None
    trajectory = []
    rng = random.Random(seed * 7 + 1)

    for step, (q_angle, q_domain) in enumerate(zip(query_angles, query_domains)):
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

        # Active de-reinforcement during intervention
        if in_intervention and block_domain != "none":
            for mid, mem in eng.memories.items():
                mem_domain = mid[0]  # "A" or "B"
                if block_domain == "both" or block_domain == mem_domain:
                    if mem.state == State.REINFORCED:
                        mem.state = State.NEUTRAL

        # Normal reinforcement (outside intervention)
        if recalled_ids and not in_intervention:
            eng.reinforce(recalled_ids[0])

        # STDP
        if prev_recalled and recalled_ids:
            eng.update_stdp(prev_recalled, recalled_ids)

        eng.update_activations(recalled_ids, now)

        # Nearest memory in the SAME domain as the query
        same_domain_mems = {mid: ang for mid, ang in memories.items()
                           if mid[0] == q_domain}
        nearest = min(same_domain_mems.keys(),
                      key=lambda mid: abs(same_domain_mems[mid] - q_angle))

        trajectory.append({
            "step": step,
            "query_angle": q_angle,
            "query_domain": q_domain,
            "recalled": recalled_ids,
            "scores": recalled_scores,
            "in_intervention": in_intervention,
            "nearest_in_results": nearest in recalled_ids,
            "reinforced_a": sum(1 for m in eng.memories.values()
                               if m.state == State.REINFORCED and m.memory_id[0] == "A"),
            "reinforced_b": sum(1 for m in eng.memories.values()
                               if m.state == State.REINFORCED and m.memory_id[0] == "B"),
        })
        prev_recalled = recalled_ids

    return trajectory


def compare_domain_trajectories(control, intervention, domain, start, end):
    """Compare trajectories for a specific domain only."""
    set_diffs = 0
    nearest_diffs = 0
    total = 0

    for i in range(start, min(end, len(control), len(intervention))):
        c = control[i]
        t = intervention[i]
        if c["query_domain"] != domain:
            continue
        total += 1
        if set(c["recalled"]) != set(t["recalled"]):
            set_diffs += 1
        if c["nearest_in_results"] != t["nearest_in_results"]:
            nearest_diffs += 1

    return {
        "set_diff_frac": set_diffs / total if total > 0 else 0.0,
        "nearest_diff_frac": nearest_diffs / total if total > 0 else 0.0,
        "total": total,
    }


# ============================================================
# Main
# ============================================================
print("=" * 70)
print("EXP10: Orthogonal behavioral control (chess test)")
print("=" * 70)

n_queries = 120
intervention_start = 40
intervention_duration = 30
intervention_end = intervention_start + intervention_duration

# Generate queries: ALL intervention-window queries are domain A.
# This maximizes the intervention's effect on domain A.
# Washout queries alternate between domains.
rng_q = random.Random(123)
query_angles = []
query_domains = []
for i in range(n_queries):
    if intervention_start <= i < intervention_end:
        # During intervention: all domain A queries
        query_angles.append(rng_q.uniform(0, 180))
        query_domains.append("A")
    else:
        # Outside intervention: alternate domains
        if rng_q.random() < 0.5:
            query_angles.append(rng_q.uniform(0, 180))
            query_domains.append("A")
        else:
            query_angles.append(rng_q.uniform(180, 360))
            query_domains.append("B")

# Use smaller fields so each reinforcement matters more
n_per_domain = 25

print(f"  Two domains: A (0-180) and B (180-360), {n_per_domain} memories each")
print(f"  {n_queries} queries, ALL intervention queries in domain A")
print(f"  Intervention: steps {intervention_start}-{intervention_end}")
print(f"  Block domain A only (full block, not probabilistic)")
print()

# Run control (no intervention)
print("Running control...")
control = run_two_domain_trajectory(
    query_angles, query_domains,
    999, 999, block_domain="none",
    n_per_domain=n_per_domain,
    seed=42,
)

# Run domain-specific intervention (block A only)
print("Running domain-specific intervention (block A)...")
intA = run_two_domain_trajectory(
    query_angles, query_domains,
    intervention_start, intervention_end, block_domain="A",
    n_per_domain=n_per_domain,
    seed=42,
)

# Run global intervention (block both)
print("Running global intervention (block both)...")
intBoth = run_two_domain_trajectory(
    query_angles, query_domains,
    intervention_start, intervention_end, block_domain="both",
    n_per_domain=n_per_domain,
    seed=42,
)

# Compare domain A (target domain)
print("\n" + "=" * 70)
print("DOMAIN A (target domain)")
print("=" * 70)

a_during_ctrl_vs_intA = compare_domain_trajectories(control, intA, "A",
    intervention_start, intervention_end)
a_washout_ctrl_vs_intA = compare_domain_trajectories(control, intA, "A",
    intervention_end, n_queries)

print(f"  Domain-specific intervention (block A):")
print(f"    During:  set_diff={a_during_ctrl_vs_intA['set_diff_frac']:.3f}, "
      f"nearest_diff={a_during_ctrl_vs_intA['nearest_diff_frac']:.3f}")
print(f"    Washout: set_diff={a_washout_ctrl_vs_intA['set_diff_frac']:.3f}, "
      f"nearest_diff={a_washout_ctrl_vs_intA['nearest_diff_frac']:.3f}")

a_during_ctrl_vs_both = compare_domain_trajectories(control, intBoth, "A",
    intervention_start, intervention_end)
a_washout_ctrl_vs_both = compare_domain_trajectories(control, intBoth, "A",
    intervention_end, n_queries)

print(f"  Global intervention (block both):")
print(f"    During:  set_diff={a_during_ctrl_vs_both['set_diff_frac']:.3f}, "
      f"nearest_diff={a_during_ctrl_vs_both['nearest_diff_frac']:.3f}")
print(f"    Washout: set_diff={a_washout_ctrl_vs_both['set_diff_frac']:.3f}, "
      f"nearest_diff={a_washout_ctrl_vs_both['nearest_diff_frac']:.3f}")

# Compare domain B (chess domain — should be unaffected by domain-specific)
print("\n" + "=" * 70)
print("DOMAIN B (chess domain — orthogonal control)")
print("=" * 70)

b_during_ctrl_vs_intA = compare_domain_trajectories(control, intA, "B",
    intervention_start, intervention_end)
b_washout_ctrl_vs_intA = compare_domain_trajectories(control, intA, "B",
    intervention_end, n_queries)

print(f"  Domain-specific intervention (block A):")
print(f"    During:  set_diff={b_during_ctrl_vs_intA['set_diff_frac']:.3f}, "
      f"nearest_diff={b_during_ctrl_vs_intA['nearest_diff_frac']:.3f}")
print(f"    Washout: set_diff={b_washout_ctrl_vs_intA['set_diff_frac']:.3f}, "
      f"nearest_diff={b_washout_ctrl_vs_intA['nearest_diff_frac']:.3f}")

b_during_ctrl_vs_both = compare_domain_trajectories(control, intBoth, "B",
    intervention_start, intervention_end)
b_washout_ctrl_vs_both = compare_domain_trajectories(control, intBoth, "B",
    intervention_end, n_queries)

print(f"  Global intervention (block both):")
print(f"    During:  set_diff={b_during_ctrl_vs_both['set_diff_frac']:.3f}, "
      f"nearest_diff={b_during_ctrl_vs_both['nearest_diff_frac']:.3f}")
print(f"    Washout: set_diff={b_washout_ctrl_vs_both['set_diff_frac']:.3f}, "
      f"nearest_diff={b_washout_ctrl_vs_both['nearest_diff_frac']:.3f}")

# State summary
print("\n" + "=" * 70)
print("STATE SUMMARY")
print("=" * 70)
for label, traj in [("Control", control), ("Block A", intA), ("Block both", intBoth)]:
    final = traj[-1]
    print(f"  {label:>12}: REINF_A={final['reinforced_a']:>3} "
          f"REINF_B={final['reinforced_b']:>3}")

# Verdict
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

print(f"\n  Domain A (target):")
if a_washout_ctrl_vs_intA["set_diff_frac"] > 0:
    print(f"    SURVIVES: path dependence in target domain")
else:
    print(f"    No path dependence in target domain")

print(f"\n  Domain B (chess, orthogonal control):")
if b_washout_ctrl_vs_intA["set_diff_frac"] < 0.05:
    print(f"    PASS: chess domain unaffected by domain-specific intervention")
    print(f"    The intervention is truly memory-specific.")
    if b_washout_ctrl_vs_both["set_diff_frac"] > 0:
        print(f"    (Global intervention DOES affect domain B, as expected)")
else:
    print(f"    FAIL: chess domain affected by domain-specific intervention")
    print(f"    The intervention leaks across domains — general poison.")

if (a_washout_ctrl_vs_intA["set_diff_frac"] > 0 and
    b_washout_ctrl_vs_intA["set_diff_frac"] < 0.05):
    print(f"\n  OVERALL: SURVIVES — path dependence is domain-specific.")
    print(f"  The intervention affects the target domain's trajectory")
    print(f"  without degrading the orthogonal domain's capability.")
    print(f"  This is the chess test: Frankenstein remembers the seasons")
    print(f"  but doesn't start hanging the queen.")
elif a_washout_ctrl_vs_intA["set_diff_frac"] > 0:
    print(f"\n  OVERALL: WEAK — path dependence exists but leaks across domains.")
else:
    print(f"\n  OVERALL: FALSIFIED — no path dependence.")
