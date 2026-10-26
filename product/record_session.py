#!/usr/bin/env python3
"""Record a Remember the Seasons session as a replayable sealed artifact.

    python3 record_session.py                      # offline stub
    NEBIUS_API_KEY=... python3 record_session.py   # real Nebius run

Why this exists
---------------
A judge should not have to take our word that the model ran, nor
install anything to check. This script runs a real session — against
Nebius Token Factory when a key is present — and emits ONE file that
carries both halves of the claim:

  - the narration: every turn, the question, the model's answer, and
    the served / used / reinforced triad it produced;
  - the seal: the unmodified `mneme-cf-bundle/v1` DSSE envelope the
    product already exports, verbatim.

The narration sits BESIDE the seal, never inside it (CLAUDE.md 5.1):
the inner envelope is byte-identical to what `export_cf_bundle_signed`
produces, so `verify_cf_offline.py` and the clean-room Go verifier
still accept it without knowing this format exists. The recording adds
its own digest over its own body, and the web viewer cross-checks that
every receipt the narration cites is actually present in the sealed
evidence — a transcript that cites a receipt the seal does not contain
is a forged transcript, and says so.

Honest scope: the model's reply is recorded as the parsed answer text
plus its declaration. The raw completion is deliberately NOT recorded,
because it carries the Kassandra session nonce.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mneme import protocol
from mneme.canonical import canonical_json
from seasons import agent, embed, llm, signing, trajectory

RECORDING_PROTOCOL = "rts-session-recording/v1"

# Fixed test-only Ed25519 seed. Public on purpose: the signature
# proves the bundle was produced by this published pipeline, not that
# a secret was held. The real trust anchor is the repo and its CI.
DEMO_KEY_SEED = "dd" * 32

QUESTION = "What do I need before deploying?"


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f+00:00")


class Recorder:
    """Collects typed turns. Every turn is a dict with a `kind`."""

    def __init__(self) -> None:
        self.turns: list[dict] = []

    def add(self, kind: str, **fields) -> dict:
        turn = {"kind": kind, "n": len(self.turns), "at": now()}
        turn.update(fields)
        self.turns.append(turn)
        return turn


def _timed(fn, *a, **kw):
    """Run fn, return (result, elapsed_ms as int). No floats reach the
    recording: milliseconds are counted, never averaged."""
    t0 = time.monotonic_ns()
    out = fn(*a, **kw)
    return out, (time.monotonic_ns() - t0) // 1_000_000


def record(out_path: str) -> dict:
    live = bool(os.environ.get("NEBIUS_API_KEY"))
    started = now()

    a = agent.SeasonsAgent(key_seed=DEMO_KEY_SEED)
    rec = Recorder()

    # ---- season 1: the field learns -------------------------------
    for content, topic in [
            ("The deploy gate requires staging to pass.",
             "deploy-policy"),
            ("Rollbacks run via `ops rollback <release>`.", None)]:
        mid = a.remember(content, topic=topic) if topic \
            else a.remember(content)
        rec.add("remember", memory_id=mid, content=content,
                topic=topic, season=1)

    r1, ms1 = _timed(a.ask, QUESTION)
    rec.add("ask", season=1, question=QUESTION, latency_ms=ms1,
            answer=r1["answer"], served=r1["served"], used=r1["used"],
            reinforced=r1["reinforced"], receipt=r1["receipt"],
            decision=r1["decision"],
            integrity_violation=r1["integrity_violation"],
            withheld=r1["withheld"])

    t1 = now()   # the cut between seasons
    rec.add("season_boundary", as_of=t1,
            note="everything after this point is season 2")

    # ---- season 2: history happens --------------------------------
    mid3 = a.remember("Policy change: staging gate is now mandatory "
                      "for ALL deploys, including hotfixes.",
                      topic="deploy-policy")
    rec.add("remember", memory_id=mid3, season=2,
            content="Policy change: staging gate is now mandatory for "
                    "ALL deploys, including hotfixes.",
            topic="deploy-policy")

    rh, msh = _timed(a.ask, "Can I skip staging for a hotfix?")
    rec.add("ask", season=2, question="Can I skip staging for a hotfix?",
            latency_ms=msh, answer=rh["answer"], served=rh["served"],
            used=rh["used"], reinforced=rh["reinforced"],
            receipt=rh["receipt"], decision=rh["decision"],
            integrity_violation=rh["integrity_violation"],
            withheld=rh["withheld"])

    r2, ms2 = _timed(a.ask, QUESTION)
    rec.add("ask", season=2, question=QUESTION, latency_ms=ms2,
            answer=r2["answer"], served=r2["served"], used=r2["used"],
            reinforced=r2["reinforced"], receipt=r2["receipt"],
            decision=r2["decision"],
            integrity_violation=r2["integrity_violation"],
            withheld=r2["withheld"],
            same_question_as_turn=1,
            receipt_changed=r1["receipt"] != r2["receipt"])

    # ---- the past, recomputed (not a snapshot) --------------------
    s = a.season(QUESTION, as_of=t1)
    rec.add("season_replay", question=QUESTION, as_of=t1,
            served=[h[0] for h in s["hits"]],
            hits=[{"memory_id": h[0], "content": h[1], "score": h[2]}
                  for h in s["hits"]],
            receipt=s["receipt"],
            now_served=r2["served"])

    # ---- why it changed: the chain --------------------------------
    for mid in sorted(set(r2["served"]) - set(r1["served"])):
        rec.add("chain", memory_id=mid, entered_in_season=2,
                events=[{"seq": seq, "event_type": et, "actor_id": ac,
                         "reason": rs, "created_at": ts}
                        for seq, et, ac, rs, ts in a.chain(mid)])

    if r1["served"]:
        anchor = r1["served"][0]
        imp = a.impact(anchor)
        rec.add("impact", memory_id=anchor,
                direct_receipts=len(imp.direct_receipts),
                direct_decisions=len(imp.direct_decisions))

    # ---- the counterfactual: do(T_i = none) -----------------------
    # Every excisable transition on every served memory is replayed, so
    # the static page is explorable: the judge picks a transition and
    # sees the sealed result, with no backend to call. An excision that
    # changes NOTHING is recorded too — "this transition did not matter"
    # is a real answer, and hiding it would be cherry-picking.
    anchor_mid = r1["served"][0]
    cf_runs = []
    for mid in sorted(set(r1["served"]) | set(r2["served"])):
        prov = a.request_provenance(mid, depth="counterfactual")
        for e in prov["excisable"].get(mid, []):
            cf = a.what_if_transition(QUESTION, mid, excise_seq=e["seq"])
            actual, counter = cf["actual"]["served"], \
                cf["counterfactual"]["served"]
            cf_runs.append({
                "memory_id": mid, "seq": e["seq"],
                "event_type": e["event_type"],
                "actual_served": actual,
                "counterfactual_served": counter,
                "delta": cf["delta"],
                "counterfactual_state": cf["counterfactual_state"],
                "report_sha256": cf["report_sha256"],
                "hypothetical": cf["hypothetical"],
                "flipped_top1": actual[:1] != counter[:1],
                "changed_anything": bool(cf["delta"]["removed"]
                                         or cf["delta"]["entered"]
                                         or cf["delta"]["rank_changed"]),
            })
    target = next((c for c in cf_runs if c["flipped_top1"]),
                  next((c for c in cf_runs if c["changed_anything"]),
                       cf_runs[0]))
    rec.add("counterfactual", question=QUESTION,
            default_memory_id=target["memory_id"],
            default_seq=target["seq"],
            any_flip=any(c["flipped_top1"] for c in cf_runs),
            any_change=any(c["changed_anything"] for c in cf_runs),
            runs=cf_runs)

    # ---- the seal: unmodified cf-bundle DSSE envelope --------------
    envelope = trajectory.export_cf_bundle_signed(
        a.cur, memory_id=target["memory_id"], excise_seq=target["seq"],
        sign_seed_hex=DEMO_KEY_SEED, keyid=a.keyid)

    body = {
        "protocol": RECORDING_PROTOCOL,
        "run": {
            "live": live,
            "backend": ("Nebius Token Factory" if live
                        else "offline deterministic stub"),
            "endpoint": (os.environ.get(
                "NEBIUS_BASE_URL",
                "https://api.tokenfactory.nebius.com/v1") if live
                else None),
            "chat_model": (llm.DEFAULT_MODEL if live else None),
            "embedding_model": (embed.DEFAULT_MODEL if live else
                                "local-token-hash-64"),
            "started_at": started,
            "finished_at": now(),
            "python": platform.python_version(),
            "signed": signing.available(),
            "semantics": dict(protocol.CURRENT_PROTOCOLS),
        },
        "agent": {"actor_id": a.actor, "keyid": a.keyid,
                  "verify_key_hex": signing.verify_key_hex(DEMO_KEY_SEED)},
        "turns": rec.turns,
        "bundle": envelope,
    }
    body["recording_sha256"] = hashlib.sha256(
        canonical_json(body).encode("utf-8")).hexdigest()

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(body, fh, indent=1, sort_keys=True)
    return body


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    default_out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "web", "session.recording.json")
    p.add_argument("--out", default=os.path.normpath(default_out))
    args = p.parse_args()

    body = record(args.out)
    run = body["run"]
    print(f"inference path: {run['backend']}"
          + (f" — {run['chat_model']} + {run['embedding_model']}"
             if run["live"] else ""))
    print(f"turns recorded: {len(body['turns'])}")
    print(f"signed:         {run['signed']} (keyid {body['agent']['keyid']})")
    print(f"recording:      {body['recording_sha256'][:24]}…")
    print(f"written to:     {args.out}")
    if not run["live"]:
        print("\nNOTE: this is the offline stub recording. Re-run with "
              "NEBIUS_API_KEY set\n      to capture a real "
              "Nemotron + Qwen3 session before recording the video.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
