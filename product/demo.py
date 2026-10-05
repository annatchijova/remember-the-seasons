#!/usr/bin/env python3
"""Remember the Seasons — skeleton demo.

The product claim in one script: the same question asked at different
points in the field's history returns different retrievals, and the
difference is explainable from sealed evidence — not asserted.

    python3 demo.py                          # offline, deterministic
    NEBIUS_API_KEY=... python3 demo.py       # real model via Nebius
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seasons import agent, trajectory


def section(t):
    print(f"\n{'=' * 70}\n{t}\n{'=' * 70}")


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f+00:00")


DEMO_KEY_SEED = "dd" * 32  # fixed test-only Ed25519 seed


def main():
    a = agent.SeasonsAgent(key_seed=DEMO_KEY_SEED)
    live = bool(os.environ.get("NEBIUS_API_KEY"))
    path_desc = ("Nebius Token Factory — Nemotron-3-Nano (chat) + "
                 "Qwen3-Embedding-8B" if live else
                 "offline deterministic stub (no NEBIUS_API_KEY)")
    print(f"inference path: {path_desc}")

    section("1. Season 1 — the field learns")
    a.remember("The deploy gate requires staging to pass.",
               topic="deploy-policy")
    a.remember("Rollbacks run via `ops rollback <release>`.")
    q = "What do I need before deploying?"
    r1 = a.ask(q)
    print(f"ask: {q!r}")
    print(f"answer: {r1['answer']}")
    print(f"served:    {r1['served']}  <- what retrieval offered")
    print(f"used:      {r1['used']}     <- the model's claim")
    print(f"reinforced:{r1['reinforced']}  <- what the deterministic "
          f"engine honored")
    print("  the model may declare; it cannot manufacture authority —")
    print("  only corroborated use changes the field")
    print(f"receipt: {r1['receipt'][:24]}…")
    t1 = now()   # the cut between seasons

    section("2. Season 2 — history happens")
    a.remember("Policy change: staging gate is now mandatory for ALL "
               "deploys, including hotfixes.", topic="deploy-policy")
    a.ask("Can I skip staging for a hotfix?")
    r2 = a.ask(q)
    print(f"same question asked again:")
    print(f"answer: {r2['answer']}")
    print(f"served: {r2['served']}")
    changed = r1["receipt"] != r2["receipt"]
    print(f"different receipt than season 1: {changed}")

    section("3. Remember the season — replay the past")
    s = a.season(q, as_of=t1)
    print(f"query {q!r} at as_of={t1[:23]}…")
    print("what the field would have served THEN:")
    for i, (mid, content, score) in enumerate(s["hits"]):
        print(f"  #{i+1}  {mid}  {content!r}")
    print(f"receipt {s['receipt'][:24]}… — computed from chains truncated")
    print("at t1, not from any stored snapshot.")

    section("4. Why did it change? — the chain answers")
    for mid in set(r2["served"]) - set(r1["served"]):
        print(f"{mid} entered season 2; its chain:")
        for seq, et, actor, reason, ts in a.chain(mid):
            print(f"  {seq:>2} {et:<22} by {actor:<16} {reason[:40]}")
    if r1["served"]:
        rep = a.impact(r1["served"][0])
        print(f"impact({r1['served'][0]}): DIRECT receipts "
              f"{len(rep.direct_receipts)}, decisions "
              f"{len(rep.direct_decisions)}")

    section("5. Trajectory counterfactual — what if it hadn't happened?")
    # scenario where the promotion itself decides the ranking:
    # a reinforced memory outranks a fresher, higher-similarity rival
    b = agent.SeasonsAgent()
    b.remember("staging gate deployment")          # lower raw sim
    for _ in range(3):
        b.ask("deploy gate staging")               # promotes mem-0000
    b.remember("deploy gate staging pass")         # higher sim, NEUTRAL
    # mem-0000's chain: promotion lives at seq 7
    rep = b.what_if_transition("deploy gate staging", "mem-0000",
                               excise_seq=7)
    print("excised mem-0000 seq 7 (STATE_CHANGED promotion):")
    print(f"  counterfactual state: {rep['counterfactual_state']}")
    print(f"  actual served:        {rep['actual']['served']}")
    print(f"  counterfactual served:{rep['counterfactual']['served']}")
    d = rep["delta"]
    print(f"  delta: removed={d['removed']} entered={d['entered']} "
          f"rank_changed={d['rank_changed']}")
    print(f"  report {rep['report_sha256'][:24]}… "
          f"(hypothetical={rep['hypothetical']})")
    print("  one excised transition flipped the top-1 — the answer in")
    print("  that world would have been different, and the report seals")
    print("  exactly which transition did it.")

    # decision counterfactual: would a recorded decision's evidence
    # base survive without that transition?
    rep_d = b.decision_what_if("dec-0002", "mem-0000", excise_seq=7)
    d = rep_d["decision"]
    print(f"  decision {d['decision_id']} used {d['used_memory_ids']}:")
    print(f"    in the excised world, served={rep_d['counterfactual']['served']}")
    print(f"    survived={d['survived']}  fallen={d['fallen']}  "
          f"intact={d['evidence_base_intact']}")

    section("6. Provenance by levels — one facade, bounded depth")
    for d in ["summary", "direct", "counterfactual"]:
        p = b.request_provenance("mem-0000", depth=d)
        extras = [k for k in p if k not in (
            "trace_id", "depth", "anchor", "memories",
            "projection_sha256")]
        line = f"  depth={d}: anchor={p['anchor']['kind']}"
        if "excisable" in p:
            line += f"  excisable={p['excisable']['mem-0000']}"
        elif extras:
            line += f"  +{extras}"
        print(line)

    section("7. Bundle — sealed evidence for a distrusting auditor")
    bj = a.export_bundle()
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                     delete=False) as f:
        f.write(bj)
        path = f.name
    r = subprocess.run([sys.executable, "verify_offline.py", path],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    os.unlink(path)

    section("8. Attribution — every write signed by its actor's key")
    n_events = a.cur.execute(
        "SELECT COUNT(*) FROM custody_chain").fetchone()[0]
    n_sigs = a.cur.execute(
        "SELECT COUNT(*) FROM event_sigs").fetchone()[0]
    print(f"agent keyid: {a.keyid}")
    print(f"custody events: {n_events}   event signatures: {n_sigs}")
    row = a.cur.execute(
        "SELECT seq, sig FROM event_sigs WHERE memory_id='mem-0000' "
        "ORDER BY seq DESC LIMIT 1").fetchone()
    vk_hex = a.cur.execute(
        "SELECT verify_key_hex FROM actor_keys WHERE actor_id=?",
        (a.actor,)).fetchone()[0]
    last = trajectory.load_chain(a.cur, "mem-0000")[-1]
    from nacl.signing import VerifyKey
    ok = VerifyKey(bytes.fromhex(vk_hex)).verify(
        last["entry_hash"].encode("ascii"),
        bytes.fromhex(row[1])) is not None
    print(f"latest entry on mem-0000 verifies under the agent's key:"
          f" {ok}")
    print("  'who wrote this' is a cryptographic answer — CF1.8 in the"
          " verifiers enforces it on exported bundles too")


if __name__ == "__main__":
    main()
