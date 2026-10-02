# AGENTS.md — Discipline for the Remember the Seasons research workspace

This file governs any agent (or human) working inside this experimental
workspace. It is deliberately stricter than a normal repo because the whole
point is to inspect before claiming, and to falsify before building.

## 0. Working agreement

- Conversation with the maintainer is in Rioplatense Spanish (voseo).
- Everything written into the repo (code, docs, comments, commit messages) is
  in English.
- No emojis anywhere in the repo or in generated output.
- You do not know the state of anything until you have read it. Verify, then
  claim.

## 1. Git authority

- `git init` is authorized. The repo is initialized.
- **Commit and push are NOT authorized unless the maintainer explicitly says
  so.** Do not commit, tag, or push on your own initiative.
- Forbidden operations (always): rebase, interactive rebase, squash,
  `push --force` / `--force-with-lease`. Forward-only operations only.
- Before reporting repo state, run `git status --short` and `git log --oneline`
  and report what they actually say.

## 2. sources/ is read-only research material

- `sources/<name>/` are snapshots of external repositories. Each has a
  `PROVENANCE.md` with the exact source commit and a content hash.
- **Never edit files under `sources/`.** They are evidence. If you need to
  experiment on a mechanism, copy the relevant code into `experiments/` and
  record where it came from.
- Never modify the original working trees of raven-memory, mneme, or
  stigmergy outside this workspace.
- A claim about a mechanism MUST point to a file/line in `sources/` (or in the
  original repo with its commit). Orientation descriptions in READMEs are not
  evidence.

## 3. Epistemic labelling — mandatory

Every non-trivial claim in research output must be labelled with its epistemic
level. Do not silently promote an inference into a fact.

- **OBSERVED** — directly read from code/tests/docs in `sources/`. Cite the
  file/line.
- **INFERRED** — derived from observation but not directly stated. State the
  reasoning and what would confirm/refute it.
- **PROPOSED** — a design or hypothesis we put forward. Not yet tested.
- **UNKNOWN** — we do not have the evidence to say. Say so.

## 4. Hypothesis discipline — falsify, do not confirm

The research hypothesis is "retrieval is not necessarily sufficient as a model
of persistent agent memory." The job of this phase is to try to **refute** it.

- Before acting on a hypothesis, formulate the simpler/benign alternative
  ("retrieval already handles this") and test it against the evidence.
- A refuted hypothesis is a valid, valuable result.
- Do not fall in love with the hypothesis. Possible valid conclusions include
  "RAG is sufficient", "only one mechanism matters", "the premise is
  unsupported". Any of these is a successful research result if backed by
  evidence.

## 5. Do not build the product

- Do not implement Remember the Seasons.
- Do not design the final architecture merely because research looks promising.
- Do not integrate the three systems because they seem compatible.
- Do not add frameworks/dependencies/external repos on your own initiative.
- Do not do frontend. Do not optimize for a demo.
- Commodity infrastructure (HTTP servers, DB drivers, tokenizers, vector math,
  model serving) stays a dependency; do not reimplement it unless the
  implementation itself is the hypothesis.

## 6. Transition gate

After the research package is complete: STOP. Report findings to the
maintainer. Do not proceed to implementation without explicit approval.
