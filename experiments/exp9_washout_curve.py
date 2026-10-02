"""
Exp9: Washout curve — how long does divergence persist?

Run a long trajectory (200 steps) with intervention at steps 40-69.
Measure set_diff per step after washout (steps 70-199).

If divergence decays to 0, the effect is transient (eventually washes out).
If divergence persists indefinitely, the effect is permanent (true path dependence).
If divergence grows, the effect is cumulative (the system diverges further).

We also vary the washout length to see if longer washout reduces divergence.
"""
import sys
import numpy as np

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from sweep_infra import generate_queries, run_pair, run_trajectory, compare_trajectories

print("=" * 70)
print("EXP9: Washout curve — persistence of divergence")
print("=" * 70)

n_memories = 100
n_queries = 200  # long trajectory
intervention_start = 40
intervention_duration = 30
intervention_end = intervention_start + intervention_duration
intensity = 1.0  # full block
seeds = list(range(10))

print(f"\n  {n_queries} steps, intervention at {intervention_start}-{intervention_end}")
print(f"  Washout period: steps {intervention_end}-{n_queries-1} ({n_queries - intervention_end} steps)")
print(f"  Seeds: {len(seeds)}")
print()

# Collect per-step set_diff across seeds
all_per_step = []
for seed in seeds:
    query_angles = generate_queries(n_queries, "uniform", seed=seed)
    control = run_trajectory(
        query_angles, 999, 999,
        block_reinforcement_prob=0.0,
        n_memories=n_memories, n_resonant_links=n_memories // 2,
        dim=32, seed=seed,
    )
    intervention = run_trajectory(
        query_angles, intervention_start, intervention_end,
        block_reinforcement_prob=intensity,
        n_memories=n_memories, n_resonant_links=n_memories // 2,
        dim=32, seed=seed,
    )

    # Compute per-step set_diff for the entire trajectory
    per_step = []
    for i in range(min(len(control), len(intervention))):
        c_set = set(control[i]["recalled"])
        t_set = set(intervention[i]["recalled"])
        per_step.append(1 if c_set != t_set else 0)
    all_per_step.append(per_step)

# Average across seeds
per_step_mean = np.mean(all_per_step, axis=0)

# Print washout curve in bins
print("  Washout curve (set_diff fraction across seeds):")
print(f"  {'Phase':>12} {'Steps':>10} {'Mean set_diff':>14}")
print(f"  {'-'*40}")

# Baseline phase
baseline_mean = np.mean(per_step_mean[:intervention_start])
print(f"  {'baseline':>12} {'0-39':>10} {baseline_mean:>14.3f}")

# Intervention phase
intervention_mean = np.mean(per_step_mean[intervention_start:intervention_end])
print(f"  {'intervention':>12} {f'{intervention_start}-{intervention_end-1}':>10} {intervention_mean:>14.3f}")

# Washout phase in bins of 10
washout_start = intervention_end
bin_size = 10
for start in range(washout_start, n_queries, bin_size):
    end = min(start + bin_size, n_queries)
    bin_mean = np.mean(per_step_mean[start:end])
    label = f"{start}-{end-1}"
    print(f"  {'washout':>12} {label:>10} {bin_mean:>14.3f}")

# Trend analysis
washout_values = per_step_mean[washout_start:]
if len(washout_values) > 10:
    first_quarter = np.mean(washout_values[:len(washout_values)//4])
    last_quarter = np.mean(washout_values[-len(washout_values)//4:])
    print(f"\n  First quarter of washout: {first_quarter:.3f}")
    print(f"  Last quarter of washout:   {last_quarter:.3f}")

    if last_quarter < first_quarter * 0.5:
        print(f"\n  VERDICT: TRANSIENT — divergence decays over time.")
        print(f"  The effect washes out. Not permanent path dependence.")
    elif last_quarter > first_quarter * 1.2:
        print(f"\n  VERDICT: CUMULATIVE — divergence grows over time.")
        print(f"  The effect is self-amplifying. Strong path dependence.")
    else:
        print(f"\n  VERDICT: PERSISTENT — divergence is stable over time.")
        print(f"  The effect doesn't wash out. Permanent path dependence.")
else:
    print(f"\n  VERDICT: INCONCLUSIVE — not enough washout steps.")

# Also measure: does the reinf_gap persist?
print("\n  Reinforcement gap at end of trajectory:")
for seed in seeds[:3]:
    query_angles = generate_queries(n_queries, "uniform", seed=seed)
    control = run_trajectory(
        query_angles, 999, 999,
        block_reinforcement_prob=0.0,
        n_memories=n_memories, n_resonant_links=n_memories // 2,
        dim=32, seed=seed,
    )
    intervention = run_trajectory(
        query_angles, intervention_start, intervention_end,
        block_reinforcement_prob=intensity,
        n_memories=n_memories, n_resonant_links=n_memories // 2,
        dim=32, seed=seed,
    )
    c_reinf = control[-1]["reinforced_count"]
    t_reinf = intervention[-1]["reinforced_count"]
    print(f"    Seed {seed}: control={c_reinf}, intervention={t_reinf}, "
          f"gap={c_reinf - t_reinf}")
