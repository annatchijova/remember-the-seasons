# Exp52 Provenance

## Source snapshot

- **OBSERVED:** Exp52 imports the copied Raven implementation in
  `../exp51_raven_h14_longitudinal/vendor/raven/`.
- **OBSERVED:** that copy was taken from `sources/raven-memory/`, commit
  `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.
- **OBSERVED:** source snapshot digest:
  `4eee9af6a22ec8311b0bf3d289bce166cb7d6a7b83c99687d004a490dcd302f4`.
- **OBSERVED:** Exp52 does not edit the read-only source snapshot or the Exp51
  vendor copy. Its fixture and protocol driver are local to this experiment.

## Runtime and fixture

- **OBSERVED:** Python 3.12, NumPy 1.26.4, SciPy 1.11.4; exact KDTree selected
  with `RAVEN_ANN_BACKEND=kdtree`.
- **OBSERVED:** synthetic IDs A/B/C/D and fixed 8-dimensional vectors are
  inherited from Exp51's seed builder.
- **OBSERVED:** no model, embedding provider, network, credentials, personal
  memories, or external service used.
- **OBSERVED:** deterministic artifact SHA-256:
  `32400cae533cb7bca021e339aa0081b1ee38121342b787dc902eb38fe1039e75`.

## Mechanism references

- Suppression contract in copied upstream source:
  `sources/raven-memory/raven/memory_engine.py:1635-1639`.
- Synaptic source iteration and target filtering:
  `sources/raven-memory/raven/memory_engine.py:1857-1888`.
- Public recall's STDP and activation writes:
  `sources/raven-memory/raven/memory_engine.py:1979-1982`.
- Exp51 seed, vectors, and source hashes:
  `../exp51_raven_h14_longitudinal/exp51_raven_h14_longitudinal.py` and
  `../exp51_raven_h14_longitudinal/PROVENANCE.md`.
