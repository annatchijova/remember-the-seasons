# Exp54 provenance

- Raven source snapshot commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.
- Source snapshot directory: `sources/raven-memory/`; no files there were edited.
- Behavioral fixture and vectors: copied from Exp51's synthetic Raven assay.
- Prior counter-only state construction: reused from Exp53's isolated helper.
- All behavioral operations ran against temporary SQLite clones. No real
  memories, credentials, network calls, or model provider were used.
- The secondary-key graph selector is an Exp54-only SQL comparator. It does
  not modify Raven source or claim to be an upstream patch.
- `run_experiment()` serializes deterministic JSON. Its fixed engine clock is
  used for selected state-changing actions; recovery probes use the inherited
  Exp53 fixed `now` path.
- Behavioral scope and omitted runtime paths are listed in `PREREGISTRATION.md`
  and `REPORT.md`.
