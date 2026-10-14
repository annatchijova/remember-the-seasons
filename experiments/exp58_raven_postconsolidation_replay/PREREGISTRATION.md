# Exp58: Post-Consolidation Longitudinal Replay

## Status and scope

**PROPOSED — preregistered before implementation and execution.** This assay
extends Exp57's two copied-Raven branches using independent disposable SQLite
clones. It will not edit `sources/`, upstream Raven, product code, or add
dependencies.

Pinned source commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

## Question and rival

Exp57 found that opposite allocations of recent activation to C or D changed
pre-consolidation retrieval, while its consolidation run produced matching
merged embeddings and fixed-query traces. Exp58 asks:

> After that consolidation, do the initially different audit histories cause
> any divergence in outputs or persistent memory state under the same sequence
> of real recall operations?

The simple alternative is that audit history has no path into the retrieval
transition: if all scoring state is equal after consolidation, identical
inputs and times should produce identical outputs and memory updates. The rival
is that some operation reads the divergent history and causes later branch
divergence. This is **PROPOSED**; no outcome is assumed.

## Branches and input sequence

Build T1 and T2 exactly as preregistered in Exp57, including their opposite
14-day activation schedules, and run the same non-dry-run consolidation.
Before the longitudinal probe, require:

- same consolidated memory rows and cell links;
- differing audit-history digests;
- same consolidation counts and merged embedding bytes.

Then execute the same eight actual `recall()` calls in both branches, with
`current_turn_memories=None`, `top_k=4`, `hops=0`, and no layer filter. The
query-key sequence is `C, D, D, C, D, C, C, D`; call i uses timestamp
`NOW + i * 21600` seconds and identical query text in both branches. Require
each call to return the same ordered memory IDs and exact score components in
both branches.

After every call, compare the complete logical `memories` and `cell_links`
tables. Audit-log rows are intentionally excluded from state equality because
the branches start with different valid audit histories. At the end, require
both chains to pass Raven's audit-chain linkage and hash-integrity verifier,
while retaining different audit digests.

## Falsifiers and controls

- **Primary falsifier:** any per-step returned-ID, score-component, memory-row,
  or cell-link mismatch falsifies the prediction that the existing audit
  divergence is behaviorally inert under this sequence.
- **Initial-state gate:** if memory rows or cell links differ before the first
  recall, the run is invalid; the experiment must not attribute that mismatch
  to the audit history.
- **History distinction gate:** if the audit digests are equal, the two
  histories were not actually distinct and the assay is invalid.
- **Chain-integrity control:** both audit chains must remain valid after the
  calls. A broken chain invalidates the run rather than counting as causal
  evidence.
- **Mutation control:** after the unmodified run, shift T2's merged node
  `last_activation` by 3600 seconds on a fresh clone. The next fixed recall
  must produce a different recency component. This confirms the longitudinal
  measurement can detect a real state-mediated score change.
- **Replay:** rebuild both branches and the full sequence from fresh clones;
  canonical JSON outputs must match exactly.

## Measurements and limits

Record each step's query, timestamp, returned memories, all score components,
memory and link state digests, and audit-chain validity. Record audit digests
separately to show whether operational histories remain distinguishable.

Any conclusion applies only to the pinned copied snapshot, this synthetic
four-memory fixture, the declared sequence and fixed clock schedule, and the
selected engine recall operation. Equality does not prove congruence under all
Raven operations or arbitrary future inputs. It does not establish behavior in
a deployed Raven service, MNEME, Stigmergy, or downstream agents.
