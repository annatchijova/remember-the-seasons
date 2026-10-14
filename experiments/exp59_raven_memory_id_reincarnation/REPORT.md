# Exp59: Recall History Across Memory-ID Reuse

## Verdict

**OBSERVED, copied Raven snapshot and synthetic fixture:** two branches had
identical current memory and link rows before consolidation, but different
historical recall distributions for C and D. Replacing each row with new
content under the same ID preserved those old audit events. The next
consolidation used weights C=5/D=4 versus C=4/D=5 and produced different
merged embeddings in the predicted directions. The old audit content hashes
did not match the new current-row hashes.

The fresh-ID control produced zero historical counts for `C_reborn` and
`D_reborn` and identical merged embeddings across histories. A temporary
generation-aware mutation that ignored audit entries whose content hash did
not match the current row also produced zero counts and equal embeddings.
Five tests passed, including canonical full-run replay.

This establishes an ID-linked historical effect in the copied storage and
consolidation paths. Whether that is a defect depends on the identity contract:
if `memory_id` deliberately denotes one continuing logical memory despite
content replacement, carrying its history may be intended. The experiment
does not show that a deployed API permits an attacker to trigger this sequence
or that an agent decision changes.

## Results

| Branch | Reused-ID audit counts | Merge weights | Result |
|---|---:|---:|---|
| R54, same IDs | C=5, D=4 | 5:4 | Embedding closer to C |
| R45, same IDs | C=4, D=5 | 4:5 | Embedding closer to D |
| R54, fresh IDs | C_reborn=0, D_reborn=0 | 1:1 floor | Equal to R45 fresh-ID embedding |
| R45, fresh IDs | C_reborn=0, D_reborn=0 | 1:1 floor | Equal to R54 fresh-ID embedding |
| Same-ID generation-aware mutant | C=0, D=0 in both | 1:1 floor | Equal embeddings |

Before the second consolidation, all current memory and cell-link rows in each
paired comparison matched exactly. The paired audit histories differed. For
same-ID branches, the audit entries contained the old C/D content hashes while
the current C/D rows contained the new hashes.

## Epistemic assessment

- **OBSERVED:** the pinned `get_recall_counts()` reads IDs from historical
  `memories_retrieved` entries, and `merge_group()` uses these counts as
  embedding weights. See
  [`sleep_consolidator.py:79–95`](../../sources/raven-memory/raven/sleep_consolidator.py#L79)
  and [`sleep_consolidator.py:170–183`](../../sources/raven-memory/raven/sleep_consolidator.py#L170).
- **OBSERVED:** `MemoryStore.store_memory()` replaces rows by ID without
  clearing the audit table. See
  [`memory_engine.py:856–875`](../../sources/raven-memory/raven/memory_engine.py#L856).
- **INFERRED:** the different new-node vectors arise because history is
  attached by reused ID despite the changed content incarnation. A different
  result under a second fixture or another count source would weaken that
  inference.
- **UNKNOWN:** whether the behavior violates Raven's intended identifier
  semantics, whether a public operation can produce the full sequence, and
  whether downstream choices are affected.

## Reproduction

```sh
python3 -m unittest -v experiments/exp59_raven_memory_id_reincarnation/test_exp59_raven_memory_id_reincarnation.py
python3 experiments/exp59_raven_memory_id_reincarnation/exp59_raven_memory_id_reincarnation.py
```

All branches use disposable SQLite clones, fixed vectors, and a fixed clock.
The runner verifies source-copy hashes, current-state equality, historical
versus current content hashes, exact counts and merge groups, a fresh-ID
control, a generation-aware mutation, and deterministic replay.
