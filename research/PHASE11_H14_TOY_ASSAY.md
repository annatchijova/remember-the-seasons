# Phase 11 — H14 Toy Assay: Independent Verification and Scope Review

Status: **OBSERVED — the supplied deterministic toy harness and its five
tests were executed and its JSON output was reproduced. H14 remains OPEN.**

This is a verification record for the three supplied artifacts. It does not
claim a Raven or MNEME experiment, a general result, or a biological analogue.

## 1. Artifact provenance

The source files were found under `/home/labestiadevigia/Downloads/` and copied
unchanged into `experiments/exp36_h14/`. The SHA-256 values below match at the
source and repository paths.

| Artifact | SHA-256 |
|---|---|
| `exp36_h14_restoration.py` | `e57a345df7e0d4c06d0b2581d41dc2f5becf970a6a0523e6b4164d39091aa245` |
| `test_exp36_h14_restoration.py` | `fe37e770c41c7fc0322bf13cb06298f573c8321185cb609ec277dbdd0fab90a1` |
| `h14_run.json` | `ae16d6d48a5ab39d55ee5f0ab05ac76b034bf935568457a7277706c28bc519b0` |

The result JSON's internal digest was independently recomputed from its
canonical compact, key-sorted payload after removing the `sha256` field. It
matches the embedded value `169d9ff3170cfd4b2d0594d73c4dcc1cb5a3a2f6def7d07d1d704c66dd9b5253`.

## 2. Verification performed

Static review found only Python standard-library imports in the harness and
test. No filesystem writes, subprocess launches, or network calls are present
in the reviewed code paths. The harness prints JSON to stdout.

Commands run from `experiments/exp36_h14/`:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_exp36_h14_restoration.py
PYTHONDONTWRITEBYTECODE=1 python3 exp36_h14_restoration.py
```

The five tests pass:

1. Measurement neutralization is read-only and blocks paths through A.
2. Absence does not update A's intrinsic strength; A and its incident links
   remain recorded.
3. The four state/link restoration combinations have the asserted values.
4. The run is deterministic and includes six arm names.
5. Repeated measurement does not mutate the world.

The harness was rerun with stdout captured outside the repository. `diff -u`
against the supplied `h14_run.json` produced no differences. The rerun therefore
reproduces the supplied default-parameter result exactly.

## 3. Observed toy result

The assay uses four hand-authored queries, two actions, four memories, exact
`Fraction` arithmetic, one-step directed propagation, a hand-coded
reinforcement rule, co-recall links, and incident-link aging. It has no random
sampling or repeated seeds.

The reported influence vector has four binary entries: for each query, `1`
means the selected action changes when A is neutralized and `0` means it does
not. At the final measurement, the vectors and Hamming distances to the
no-absence arm are:

| Arm | Final flip-indicator vector | Hamming distance from no-absence |
|---|---:|---:|
| No absence | `[1, 1, 1, 1]` | 0 |
| Re-exposure | `[0, 0, 1, 1]` | 2 |
| Strict restoration | `[1, 1, 1, 1]` | 0 |
| Links only | `[1, 0, 1, 0]` | 2 |
| State and links | `[1, 1, 1, 1]` | 0 |
| Relearning | `[1, 0, 1, 1]` | 1 |

At the initial post-absence measurement, no-absence is `[1, 1, 1, 1]`, while
strict restoration and state-plus-links are `[1, 0, 1, 1]`. Both therefore
differ by one indicator immediately after restoration, then match the
no-absence indicator vector after 12 follow-up updates.

**INFERRED, scoped to this harness:** the selected four-query flip pattern for
strict restoration and state-plus-links converges to the no-absence pattern
during the declared follow-up. The run does not establish general equivalence
or that causal influence was fully restored.

## 4. Protocol-alignment findings

### The untouched-rest condition

**OBSERVED:** `reinstate` changes A's availability and intrinsic strength and,
only in the relevant factorial arms, incident links. It does not assign the
strengths of B, C, or D, nor links not incident to A (`exp36_h14_restoration.py`
lines 134–148). The absent and no-absence worlds evolve independently during
the absence window; restoration arms branch from the absent world
(lines 150–177). This implements the rule that restoration branches do not
rewind the rest of the agent.

The tests directly assert preservation of B's strength in the factorial
test, but do not assert every non-A state field or every non-incident edge.
The broader claim above is also supported by inspection of the complete
`reinstate` body, not by a comprehensive invariant test.

### Deviations and limits

1. **Incident links age during functional absence.** The run multiplies each
   edge incident to A by `7/8` on every absence step
   (`exp36_h14_restoration.py` lines 113–121, 159–165). This is an explicit
   background mechanism in the harness, but it differs from the current
   protocol's primary operationalization, which freezes incident links during
   absence (`docs/REINTRODUCTION_RESTORATION.md` lines 92–96). Thus the
   links-only contrast includes this designed aging process; it is not an
   isolated test of naturally evolving shared state.
2. **Restoration uses the pre-absence snapshot.** Both the intrinsic state and
   restored incident links are taken from `before`, not from the later state
   reached by the no-absence branch (`exp36_h14_restoration.py` lines 150–177).
   The assay tests restoration of historical state, not restoration of the
   state A would have reached had absence never occurred.
3. **The outcome is a lossy influence summary.** `influence_vector` stores
   only whether neutralizing A changes the chosen action
   (`exp36_h14_restoration.py` lines 79–86). The paired action identities are
   available through `signature` but are not included in the JSON. Equal
   vectors therefore mean equal flip/no-flip indicators for four probes, not
   equal causal effects in direction or magnitude.
4. **The relearning dose is hand-coded.** Four follow-up steps add fixed
   increments to A's strength and may add an association
   (`exp36_h14_restoration.py` lines 124–131, 181–186). The arm also undergoes
   the ordinary `learn` update. This is a declared toy rule, not an
   independently validated or exposure-matched model of learning.
5. **Five passing tests are invariant checks, not an H14 verdict.** They
   establish the listed properties of this harness. They do not test a
   preregistered equivalence margin, statistical power, robustness across
   configurations, Raven behavior, or MNEME counterfactual verification.

## 5. Disposition

**OBSERVED:** The six requested arms execute, the five supplied tests pass, the
provided JSON reproduces exactly, and its embedded digest is valid.

**UNKNOWN:** Whether restoration recovers A's influence in Raven, MNEME, or
another agent; whether equality persists under richer decision outcomes,
different queries, or additional seeds; and which other-memory state explains
any residual from a no-absence counterfactual.

**H14 verdict: OPEN.** Treat this as a reproducible toy assay and a concrete
source of testable follow-up discrepancies, not as evidence that H14 survived
or was falsified. The files are preserved as supplied; this review does not
silently patch the experimental mechanism or replace the submitted JSON.
