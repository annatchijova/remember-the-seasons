"""
Exp8: Dose-response curve.

Vary intervention intensity from 0.0 to 1.0 in steps of 0.2.
For each dose, run N seeds and measure washout divergence.

If divergence increases monotonically with dose, the intervention has
a clean dose-response relationship (like a real drug).
If divergence is non-monotonic or flat, the relationship is more complex.
"""
import sys
import numpy as np

sys.path.insert(0, "/home/labestiadevigia/remember-the-seasons/experiments")
from sweep_infra import generate_queries, run_pair

print("=" * 70)
print("EXP8: Dose-response curve")
print("=" * 70)

doses = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
seeds = list(range(20))  # 20 seeds per dose for statistical power
n_memories = 100
n_queries = 120
intervention_start = 40
intervention_duration = 30
intervention_end = intervention_start + intervention_duration
distribution = "uniform"

print(f"\nDoses: {doses}")
print(f"Seeds per dose: {len(seeds)}")
print(f"Field: {n_memories} memories, {n_queries} queries")
print(f"Intervention: steps {intervention_start}-{intervention_end}")
print()

results_by_dose = {}

for dose in doses:
    washout_set_diffs = []
    washout_score_diffs = []
    during_set_diffs = []
    nearest_diffs = []
    reinf_gaps = []

    for seed in seeds:
        query_angles = generate_queries(n_queries, distribution, seed=seed)
        metrics = run_pair(
            query_angles=query_angles,
            intervention_start=intervention_start,
            intervention_end=intervention_end,
            block_reinforcement_prob=dose,
            stdp_scale=1.0,
            n_memories=n_memories,
            n_resonant_links=n_memories // 2,
            dim=32,
            seed=seed,
        )
        washout_set_diffs.append(metrics["washout_set_diff"])
        washout_score_diffs.append(metrics["washout_score_diff"])
        during_set_diffs.append(metrics["during_set_diff"])
        nearest_diffs.append(metrics["washout_nearest_diff"])
        reinf_gaps.append(metrics["reinf_gap"])

    wsd = np.array(washout_set_diffs)
    wscd = np.array(washout_score_diffs)
    dsd = np.array(during_set_diffs)
    nd = np.array(nearest_diffs)
    rg = np.array(reinf_gaps)

    results_by_dose[dose] = {
        "washout_set_mean": float(np.mean(wsd)),
        "washout_set_std": float(np.std(wsd)),
        "washout_set_frac_nonzero": float(np.mean(wsd > 0)),
        "washout_score_mean": float(np.mean(wscd)),
        "during_set_mean": float(np.mean(dsd)),
        "nearest_mean": float(np.mean(nd)),
        "reinf_gap_mean": float(np.mean(rg)),
    }

    print(f"  Dose {dose:.1f}: washout_set={np.mean(wsd):.3f}±{np.std(wsd):.3f} "
          f"frac>0={np.mean(wsd > 0):.2f} "
          f"during={np.mean(dsd):.3f} "
          f"nearest={np.mean(nd):.3f} "
          f"reinf_gap={np.mean(rg):.1f}")

# Print dose-response table
print("\n" + "=" * 70)
print("DOSE-RESPONSE TABLE")
print("=" * 70)
print(f"  {'Dose':>6} {'Washout_set':>14} {'Washout_score':>14} "
      f"{'During_set':>12} {'Frac>0':>8} {'Nearest':>8} {'Reinf_gap':>10}")
for dose in doses:
    r = results_by_dose[dose]
    print(f"  {dose:>6.1f} {r['washout_set_mean']:>10.3f}±{r['washout_set_std']:>3.3f} "
          f"{r['washout_score_mean']:>14.3f} {r['during_set_mean']:>12.3f} "
          f"{r['washout_set_frac_nonzero']:>8.2f} {r['nearest_mean']:>8.3f} "
          f"{r['reinf_gap_mean']:>10.1f}")

# Check monotonicity
washout_means = [results_by_dose[d]["washout_set_mean"] for d in doses]
is_monotone = all(washout_means[i] <= washout_means[i+1] + 0.01
                  for i in range(len(washout_means)-1))

print(f"\n  Monotone increasing: {is_monotone}")
print(f"  Dose 0.0 (control): washout_set={results_by_dose[0.0]['washout_set_mean']:.3f}")
print(f"  Dose 1.0 (full block): washout_set={results_by_dose[1.0]['washout_set_mean']:.3f}")

if is_monotone and washout_means[-1] > washout_means[0]:
    print(f"\n  VERDICT: SURVIVES — clean dose-response relationship.")
    print(f"  Higher dose -> more divergence. The intervention behaves")
    print(f"  like a drug with a dose-response curve.")
elif washout_means[-1] > washout_means[0]:
    print(f"\n  VERDICT: SURVIVES — dose-response present but non-monotone.")
else:
    print(f"\n  VERDICT: FALSIFIED — no dose-response relationship.")

# Negative control
all_nearest = [results_by_dose[d]["nearest_mean"] for d in doses]
print(f"\n  Negative control: mean nearest_diff={np.mean(all_nearest):.4f} "
      f"(should be ~0)")
if np.mean(all_nearest) < 0.05:
    print(f"  PASS: intervention is memory-specific at all doses.")
else:
    print(f"  WARNING: intervention degrades general recall at some doses.")
