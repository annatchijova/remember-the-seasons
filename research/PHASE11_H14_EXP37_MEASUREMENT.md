# Phase 11 — Exp37: H14 Causal Measurement Instrument

Status: **OBSERVED — six arms ran in a deterministic synthetic harness; six
tests pass; the sign mutation was detected. H14 remains OPEN.**

Exp37 is a new assay, not a replacement for Exp36. Exp36 and its original
result remain intact as historical evidence. Exp37 addresses two limitations
identified in the Exp36 audit: it freezes A-incident links during functional
absence and preserves signed action-score contributions instead of reducing
the result to choice flips.

## 1. Question and falsifier

**PROPOSED — instrument question:** Can the assay retain measurable effects of
A on both action scores when neutralizing A does not change the selected
action?

**Simpler alternative:** Choice-level measurements are sufficient for the
tested system; the additional score measurements add no distinguishable
information.

**Falsifier for the instrument claim:** A constructed case with nonzero,
equal contributions to both action scores is reported as zero effect merely
because the selected action is unchanged. The exact-value test
`test_signed_effect_retains_magnitude_when_choice_does_not_flip` rejects that
failure mode.

This is an instrument check, not a verdict for H14. It does not establish that
score differences are behaviorally meaningful in Raven, MNEME, or a deployed
agent.

## 2. Provenance and execution

Exp37 is an independent implementation of the bounded toy assay in
`experiments/exp37_h14_measurement/`; it does not import or modify Exp36. It
uses the same declared four-memory, four-query synthetic setup and six arm
labels, with exact rational arithmetic and no external dependencies.

Files:

- `experiments/exp37_h14_measurement/exp37_h14_causal_measurement.py`
- `experiments/exp37_h14_measurement/test_exp37_h14_causal_measurement.py`
- `experiments/exp37_h14_measurement/h14_exp37_run.json`

SHA-256:

| File | SHA-256 |
|---|---|
| `exp37_h14_causal_measurement.py` | `762d16d65268091426fe56787102440694905231ba2755ce486fd269898faefc` |
| `test_exp37_h14_causal_measurement.py` | `edec48b8aaedf65d6d40e25af2b448611abfc9c6bdbb9590433c1bf363d24eaa` |
| `h14_exp37_run.json` | `f48eb432f99f9f9fd79e75828c45387533a92518a497a9c968e94057ca256236` |

Commands, run from the Exp37 directory:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_exp37_h14_causal_measurement.py
PYTHONDONTWRITEBYTECODE=1 python3 exp37_h14_causal_measurement.py --output h14_exp37_run.json
```

**OBSERVED:** All six tests pass. Repeated calls to `run()` return equal
objects. The six arms are `no_absence`, `reexposure`, `strict`, `links_only`,
`state_and_links`, and `relearning`.

## 3. Measurement definition

For each branch and fixed query, the instrument records exact rational action
scores with A available and in a controlled copy with A neutralized. It
retains:

1. The X and Y scores in both conditions.
2. The signed per-action effect `score_with_A - score_neutralized_A`.
3. The signed change in the X-minus-Y margin.
4. The selected action in both conditions.

Neutralization blocks A's direct score and propagation through A while
retaining the rest of the branch state. The measurement function does not
mutate that state. This is a controlled intervention in this toy model; it
does not prove that all possible causal pathways in a real agent have been
captured.

**OBSERVED — constructed control:** With A contributing `+1` to X and an
A-to-B edge contributing `+1` to Y, the measured effects are
`delta_X = 1`, `delta_Y = 1`, and `delta_margin = 0`. The selected action is
the same with and without A. A flip-only metric would report no change, while
Exp37 retains the two score contributions and the zero net margin effect.

This does not mean the score scale is calibrated or comparable across
different models. It establishes only that this harness preserves the
declared exact score quantities rather than collapsing them to an argmax
indicator.

## 4. Absence and restoration behavior

**OBSERVED:** Exp37 freezes every edge incident to A at its pre-absence value
during the absence window. Learning can still update eligible memory strength
and non-A edges. The harness asserts that the A-incident edge map is unchanged
through the window. This corrects Exp36's explicit `7/8` aging behavior for
this assay.

Restoration branches fork from the absent branch. `reinstate` changes A's
availability and intrinsic strength, and changes A-incident links only in
arms whose declared condition calls for that operation. It does not restore
the rest of the agent from the no-absence branch.

**OBSERVED — one synthetic run:** Immediately after reintroduction, the strict
arm and no-absence arm choose the same action with A and the same action with
A neutralized for query 0. Their measured effects still differ:

| Quantity, query 0 | No absence | Strict restoration |
|---|---:|---:|
| `delta_X` | `139/60` | `29/12` |
| `delta_Y` | `8/15` | `8/15` |
| `delta_margin_X_minus_Y` | `107/60` | `113/60` |

The initial full measurements do not exactly match for any recovery arm on
all four queries. At the final measurement, after 12 updates, they still do
not exactly match the no-absence arm on all four queries. These are descriptive
results for one hand-authored configuration, not estimates of a general
effect.

## 5. Test integrity

- **Exact-value oracle:** The constructed equal-contribution case asserts exact
  rational values, including identical choices with nonzero per-action
  effects.
- **Negative control:** In a temporary copy, the sign in the delta formula
  was deliberately inverted. Two tests failed with negative values where
  positive values were specified. The working source was not mutated.
- **Invariants:** Link-freeze behavior, read-only measurement, target
  availability validation, six-arm shape, and deterministic output are
  asserted.
- **Known blind spots:** Tests do not establish model validity, broad input
  coverage, statistical power, an equivalence margin, adequate query
  coverage, robust causal identification under a different propagation rule,
  or Raven/MNEME behavior. No stochastic variance is estimated.

## 6. Disposition

**OBSERVED:** The richer instrument detects nonzero action-score effects even
when choices do not flip, and it does not mutate state during measurement.
The absence-link freeze invariant holds in the executed assay.

**INFERRED, scoped to this harness:** In this setup, two branches can agree on
the paired choices while differing in the magnitudes of A's action-score
effects. The query-0 strict-restoration and no-absence rows demonstrate that
case directly.

**UNKNOWN:** Whether these score effects correspond to a useful causal
quantity in Raven or MNEME; whether the six operations differ beyond this
synthetic configuration; whether results survive broader probe sets,
alternative scoring rules, repeated seeds, or a preregistered equivalence
test.

**H14 verdict: OPEN.** Exp37 fixes specified instrument defects. It does not
validate the toy dynamics or complete the preregistered research package.
