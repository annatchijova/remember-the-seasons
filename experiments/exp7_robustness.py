"""
Exp7: Statistical robustness of washout.

Sweep: seeds × field sizes × intervention durations × intensities ×
query distributions.

For each configuration, run N seeds and compute:
  - mean washout_set_diff (the key metric: does divergence persist?)
  - std washout_set_diff
  - fraction of seeds where washout_set_diff > 0 (any divergence)
  - mean nearest_diff (negative control: should be ~0)
  - mean reinf_gap

If washout_set_diff is consistently > 0 across seeds/sizes/durations,
the path dependence effect is robust, not an artifact of one seed.
"""
import sys
import numpy as np
import random

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from sweep_infra import generate_queries, run_pair

print("=" * 70)
print("EXP7: Statistical robustness of washout")
print("=" * 70)

# Sweep parameters
seeds = list(range(10))  # 10 seeds per config
field_sizes = [50, 100, 200]
durations = [10, 20, 40]  # intervention duration in steps
intensities = [0.5, 0.8, 1.0]  # block_reinforcement_prob
distributions = ["uniform", "clustered", "biased"]

# Total queries per trajectory
n_queries = 120
# Intervention starts at step 40
intervention_start = 40

results = []

print(f"\nSweep: {len(seeds)} seeds × {len(field_sizes)} sizes × "
      f"{len(durations)} durations × {len(intensities)} intensities × "
      f"{len(distributions)} distributions")
print(f"Total configs: {len(field_sizes) * len(durations) * len(intensities) * len(distributions)}")
print(f"Total runs: {len(field_sizes) * len(durations) * len(intensities) * len(distributions) * len(seeds)}")
print()

# Run sweep
config_idx = 0
total_configs = len(field_sizes) * len(durations) * len(intensities) * len(distributions)

for field_size in field_sizes:
    for duration in durations:
        for intensity in intensities:
            for dist in distributions:
                config_idx += 1
                intervention_end = intervention_start + duration

                washout_set_diffs = []
                washout_score_diffs = []
                nearest_diffs = []
                reinf_gaps = []

                for seed in seeds:
                    query_angles = generate_queries(
                        n_queries, dist, seed=seed
                    )
                    metrics = run_pair(
                        query_angles=query_angles,
                        intervention_start=intervention_start,
                        intervention_end=intervention_end,
                        block_reinforcement_prob=intensity,
                        stdp_scale=1.0,
                        n_memories=field_size,
                        n_resonant_links=field_size // 2,
                        dim=32,
                        seed=seed,
                    )
                    washout_set_diffs.append(metrics["washout_set_diff"])
                    washout_score_diffs.append(metrics["washout_score_diff"])
                    nearest_diffs.append(metrics["washout_nearest_diff"])
                    reinf_gaps.append(metrics["reinf_gap"])

                wsd = np.array(washout_set_diffs)
                wscd = np.array(washout_score_diffs)
                nd = np.array(nearest_diffs)
                rg = np.array(reinf_gaps)

                results.append({
                    "field_size": field_size,
                    "duration": duration,
                    "intensity": intensity,
                    "distribution": dist,
                    "washout_set_diff_mean": float(np.mean(wsd)),
                    "washout_set_diff_std": float(np.std(wsd)),
                    "washout_set_diff_frac_nonzero": float(np.mean(wsd > 0)),
                    "washout_score_diff_mean": float(np.mean(wscd)),
                    "nearest_diff_mean": float(np.mean(nd)),
                    "reinf_gap_mean": float(np.mean(rg)),
                })

                if config_idx % 5 == 0 or config_idx == total_configs:
                    print(f"  Config {config_idx}/{total_configs}: "
                          f"size={field_size} dur={duration} int={intensity} "
                          f"dist={dist} -> "
                          f"washout_set={np.mean(wsd):.3f}±{np.std(wsd):.3f} "
                          f"frac>0={np.mean(wsd > 0):.2f}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

# Aggregate by each dimension
print("\n--- By field size ---")
for fs in field_sizes:
    subset = [r for r in results if r["field_size"] == fs]
    mean_wsd = np.mean([r["washout_set_diff_mean"] for r in subset])
    mean_frac = np.mean([r["washout_set_diff_frac_nonzero"] for r in subset])
    print(f"  size={fs:>3}: washout_set_diff={mean_wsd:.3f}, "
          f"frac seeds with divergence={mean_frac:.2f}")

print("\n--- By intervention duration ---")
for dur in durations:
    subset = [r for r in results if r["duration"] == dur]
    mean_wsd = np.mean([r["washout_set_diff_mean"] for r in subset])
    mean_frac = np.mean([r["washout_set_diff_frac_nonzero"] for r in subset])
    print(f"  dur={dur:>2}: washout_set_diff={mean_wsd:.3f}, "
          f"frac seeds with divergence={mean_frac:.2f}")

print("\n--- By intervention intensity ---")
for inten in intensities:
    subset = [r for r in results if r["intensity"] == inten]
    mean_wsd = np.mean([r["washout_set_diff_mean"] for r in subset])
    mean_frac = np.mean([r["washout_set_diff_frac_nonzero"] for r in subset])
    print(f"  int={inten:.1f}: washout_set_diff={mean_wsd:.3f}, "
          f"frac seeds with divergence={mean_frac:.2f}")

print("\n--- By query distribution ---")
for dist in distributions:
    subset = [r for r in results if r["distribution"] == dist]
    mean_wsd = np.mean([r["washout_set_diff_mean"] for r in subset])
    mean_frac = np.mean([r["washout_set_diff_frac_nonzero"] for r in subset])
    print(f"  dist={dist:>10}: washout_set_diff={mean_wsd:.3f}, "
          f"frac seeds with divergence={mean_frac:.2f}")

print("\n--- Negative control (nearest-memory probe) ---")
all_nearest = [r["nearest_diff_mean"] for r in results]
print(f"  Mean nearest_diff across all configs: {np.mean(all_nearest):.4f}")
print(f"  Max nearest_diff across all configs: {np.max(all_nearest):.4f}")

# Overall verdict
all_wsd = [r["washout_set_diff_mean"] for r in results]
all_frac = [r["washout_set_diff_frac_nonzero"] for r in results]
print(f"\n--- Overall ---")
print(f"  Mean washout_set_diff: {np.mean(all_wsd):.4f}")
print(f"  Mean frac seeds with divergence: {np.mean(all_frac):.2f}")
print(f"  Configs with >50% seeds showing divergence: "
      f"{sum(1 for f in all_frac if f > 0.5)}/{len(all_frac)}")

if np.mean(all_frac) > 0.5:
    print(f"\n  VERDICT: SURVIVES — path dependence is robust across seeds,")
    print(f"  sizes, durations, intensities, and distributions.")
elif np.mean(all_frac) > 0.2:
    print(f"\n  VERDICT: WEAK SURVIVES — path dependence appears in some")
    print(f"  configurations but not consistently.")
else:
    print(f"\n  VERDICT: FALSIFIED — path dependence is not robust.")

if np.mean(all_nearest) < 0.05:
    print(f"  Negative control: PASS (nearest-memory unaffected)")
else:
    print(f"  Negative control: FAIL (intervention degrades general recall)")
