# Exp51 Preregistration Amendment 2

**Recorded after the first amended replay and before the final rerun.** The
first amended output was superseded and is not retained as a machine-readable
result. It exposed an operational confound: the preregistration gave
re-exposure and relearning the same availability time and the same reset
state, which made those arms identical by construction.

## Amended arm timing

- Re-exposure: make A available in a neutral, link-cleared state before
  experience step 5.
- Relearning: keep A absent during step 5, then make it available in the same
  neutral, link-cleared state before step 6. It receives one fewer common
  post-window learning experience.
- Other arms retain their preregistered step-5 restoration operations.

The initial A state is REINFORCED. Therefore neutral re-exposure is observably
different from restoring A's historical intrinsic row. Because complete
absence freezes A's intrinsic state, strict and complete restoration may
still coincide when the incident links also match; such equality is an
expected valid outcome, not a reason to add artificial changes.

All six arms continue to receive the same external query schedule. The
relearning arm's delayed availability is the declared treatment difference.
Only the final amended run is used for the research interpretation.
