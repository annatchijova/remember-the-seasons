# Provenance — stigmergy

This directory is a READ-ONLY research snapshot of an external repository.
It is NOT the source of truth and MUST NOT be edited. Experiment on copies,
never here.

- source_repo_path: /home/labestiadevigia/stigmergy
- remote: https://github.com/annatchijova/stigmergy.git
- head_commit: b80a7f9cf259d7b0965b659d410daca81167bf37
- branch: main
- export_method: `git archive HEAD` piped to tar, then removed heavy assets
- exclusions: visual/screens/assets/fotos/deck image directories; binary/media
  extensions (.png .jpg .jpeg .gif .zip .mp4 .wav .pkl .npy .npz .wasm .bin)
- excluded_note: .env and secrets are gitignored in the source repo and were
  never tracked, so they are absent from this snapshot by construction.
- snapshot_file_count: 81
- snapshot_content_sha256: e97849d95ce50dc832db10509afacf97af75e46c4a8233eed4047741c2a98144
- exported_on: 2026-10-02
- exported_by: Devin research session (Remember the Seasons, Phase 0)

## Source working-tree state at export

- raven-memory: clean (no uncommitted changes)
- mneme: clean
- stigmergy: one untracked dir `.aws-sam/` (not exported; git archive only
  emits tracked files)

## Integrity check

Re-derive `snapshot_content_sha256` from this directory and compare to the
value above. A mismatch means the snapshot was modified after export.
