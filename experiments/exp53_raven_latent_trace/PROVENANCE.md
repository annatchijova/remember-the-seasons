# Exp53 Provenance

## Source snapshot

- **OBSERVED:** upstream source snapshot: `sources/raven-memory/`.
- **OBSERVED:** source commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.
- **OBSERVED:** snapshot digest:
  `4eee9af6a22ec8311b0bf3d289bce166cb7d6a7b83c99687d004a490dcd302f4`.
- **OBSERVED:** Exp53 uses the copied package in
  `experiments/exp51_raven_h14_longitudinal/vendor/raven/` and does not modify
  either that copy or `sources/`.
- **OBSERVED:** copied `memory_engine.py`, `sleep_consolidator.py`, and
  `portability.py` SHA-256 values match their files in the source snapshot:
  `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0`,
  `9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39`, and
  `2747a81180612ca775e25353278533bd4196d4a3fb280c1b66f4cb5a0a2e6869`.

## Runtime and artifact

- **OBSERVED:** Python 3.12, NumPy 1.26.4, SciPy 1.11.4; exact KDTree backend.
- **OBSERVED:** four synthetic fixture rows, fixed query vectors, fixed time,
  temporary SQLite copies, and no personal data, model, network, credentials,
  or external service.
- **OBSERVED:** run artifact SHA-256:
  `d8b045f9fe215450839b8422639bcfdabd8fbb7ddf68b0761ece1146cbfc6823`.
- **OBSERVED:** the sleep consolidator was imported from the same copied
  Raven package namespace to avoid initializing a second package copy.

## Source locations

- Retrieval score formula and fields read:
  `sources/raven-memory/raven/memory_engine.py:1795-1831`.
- Increment on activation:
  `sources/raven-memory/raven/memory_engine.py:1031-1047`.
- Stats aggregation:
  `sources/raven-memory/raven/memory_engine.py:962-1006`.
- Truncated export ordering and node output:
  `sources/raven-memory/raven/memory_engine.py:952-960`,
  `2257-2286`.
- API inspection output:
  `sources/raven-memory/api_server.py:431-472`.
- Consolidator's audit-derived counts:
  `sources/raven-memory/raven/sleep_consolidator.py:56-95`, `416-436`.
- Portability column list:
  `sources/raven-memory/raven/portability.py:40-44`.
