#!/usr/bin/env python3
"""Independent verifier for counterfactual bundles (mneme-cf-bundle/v1).

Loads a bundle produced by seasons.trajectory.export_cf_bundle and
RECOMPUTES the cascade from the sealed evidence — it does not trust
the report's account of what would have been ungrounded.

Independence boundary: this file does not import seasons or
trajectory.py. It uses mneme.field.recall — the declared recall
protocol — on a world rebuilt from the bundle's evidence, and its own
replay implementation of the documented event semantics
(docs/CAUSAL_REWIND.md). What is under verification is the CASCADE
REASONING: given this evidence and this intervention, are the claimed
divergences, ungroundings and invalidations actually the ones that
follow?

Checks:
  CF0  bundle digest re-computes over canonical bytes.
  CF1  custody chains are internally linked (prev_hash → entry_hash).
  CF2  actual-world consistency: for every decision, replaying the
       chain prefixes at its timestamp and re-running recall serves
       exactly what the cited receipt claims — the "actual world" in
       the bundle must be self-consistent, or everything downstream
       of it is theatre.
  CF3  cf reconstruction: the cascade recomputed from evidence equals
       the report — divergent receipts, ungrounded decisions,
       invalidated events, propagation edges, cf states, and the
       report digest itself.

Usage: python3 verify_cf_offline.py bundle.json
Exit 0 = all checks hold. Exit 1 = any check fails.
"""

import hashlib
import json
import os
import sqlite3
import sys
from decimal import Decimal
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mneme import field                      # the declared protocol
from mneme.canonical import canonical_json

ALPHA = field.REINFORCEMENT_ALPHA
THRESH = field.PROMOTION_THRESHOLD


def replay(chain, dead, as_of=None):
    """Independent re-implementation of the documented event
    semantics: recompute, never trust recorded transitions. Mirrors
    docs/CAUSAL_REWIND.md's per-type rules."""
    status, fstate = "CLEAN", "NEUTRAL"
    conf = Fraction(1, 2)
    for ev in chain:
        if ev["seq"] in dead:
            continue
        if as_of is not None and ev["created_at"] >= as_of:
            continue
        et = ev["event_type"]
        if et == "QUARANTINED":
            status = "QUARANTINED"
        elif et == "SUPERSEDED_BY":
            status = "SUPERSEDED"
        elif et == "TAINT_FLAGGED":
            if status == "CLEAN":
                status = "TAINT_FLAGGED"
        elif et == "REHABILITATED":
            status = "CLEAN"
        elif et == "REINFORCED":
            conf = conf + ALPHA * (1 - conf)
        elif et == "STATE_CHANGED":
            p = json.loads(ev["payload_json"])
            to = p.get("to")
            if p.get("from") == "NEUTRAL" and to == "REINFORCED":
                if conf >= THRESH:
                    fstate = "REINFORCED"
            elif to is not None:
                fstate = to
    return status, fstate, conf


def main(path):
    b = json.load(open(path))
    checks = []

    def check(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}  {detail}")
        checks.append(cond)

    print("=" * 64)
    print("counterfactual bundle verification — mneme-cf-bundle/v1")
    print("=" * 64)

    # CF0 bundle integrity
    seal = b.pop("bundle_sha256", None)
    recomputed = hashlib.sha256(
        canonical_json(b).encode("utf-8")).hexdigest()
    check("CF0 bundle digest", seal == recomputed)

    # CF0.5 frozen semantics: refuse versions this verifier does not
    # implement — never apply new rules to old evidence.
    KNOWN = {"mneme-cf-bundle/v1", "cf-cascade/v1"}
    sem = b.get("semantics", {})
    known_sem = (
        sem.get("bundle_protocol") in KNOWN
        and sem.get("causal_rewind_protocol") in KNOWN)
    check("CF0.5 declared semantics are implemented here", known_sem,
          f"declared {sem}")

    ev = b["evidence"]
    chains = ev["chains"]
    intervention = b["intervention"]
    mid_i, seq_i = intervention["memory_id"], intervention["seq"]

    # CF1 chain integrity: recompute EVERY entry_hash from its
    # canonical envelope — linkage alone is not enough; a forged
    # event with borrowed hashes must die here.
    def envelope_hash(mid, e, prev):
        env = {"memory_id": mid, "seq": e["seq"],
               "event_type": e["event_type"], "actor_id": e["actor_id"],
               "reason": e["reason"], "created_at": e["created_at"],
               "payload": json.loads(e["payload_json"])}
        return hashlib.sha256(
            prev.encode("ascii")
            + canonical_json(env).encode("utf-8")).hexdigest()

    linked = True
    for mid, ch in chains.items():
        prev = hashlib.sha256(
            b"MNEME_CUSTODY_GENESIS:" + mid.encode()).hexdigest()
        for e in sorted(ch, key=lambda x: x["seq"]):
            if e["prev_hash"] != prev:
                linked = False
            if e["entry_hash"] != envelope_hash(mid, e, prev):
                linked = False
            prev = e["entry_hash"]
    check("CF1 entry_hash recomputed + linked", linked)

    # CF1.5 historically committed inputs: the decision's query
    # embedding must hash to the digest the RECEIPT recorded when the
    # recall happened — not merely be internally consistent.
    inputs_ok = all(
        d["query_embedding_sha256"] == field.embedding_sha256(
            [Decimal(x) for x in d["query_embedding"]])
        and ev["receipts"].get(d["receipt_sha256"], {})
        .get("query_sha256") == d["query_embedding_sha256"]
        for d in ev["decisions"])
    check("CF1.5 embeddings committed at recall time", inputs_ok)

    # Rebuild the world: in-memory sqlite with the evidence.
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE actors (actor_id TEXT PRIMARY KEY, display_name TEXT,
                         kind TEXT, status TEXT, created_at TEXT);
    CREATE TABLE memories (
        memory_id TEXT PRIMARY KEY, content TEXT, content_sha256 TEXT,
        embedding_json TEXT, embedding_model TEXT, topic TEXT,
        created_by TEXT, created_at TEXT,
        field_state TEXT, custody_status TEXT, confidence TEXT,
        superseded_by TEXT);
    CREATE TABLE custody_chain (
        memory_id TEXT, seq INTEGER, event_type TEXT, actor_id TEXT,
        reason TEXT, created_at TEXT, payload_json TEXT,
        prev_hash TEXT, entry_hash TEXT);
    CREATE TABLE cell_links (
        from_id TEXT, to_id TEXT, link_type TEXT, auto INTEGER);
    """)
    for a in ev["actors"]:
        cur.execute("INSERT INTO actors VALUES (?,?,?,?,?)",
                    (a["actor_id"], a["display_name"], a["kind"],
                     a["status"], a["created_at"]))
    for m in ev["memories"]:
        cur.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (m["memory_id"], m["content"], m["content_sha256"],
                     m["embedding_json"], m["embedding_model"],
                     m["topic"], m["created_by"], m["created_at"],
                     m["field_state"], m["custody_status"],
                     m["confidence"], m["superseded_by"]))
    for mid, ch in chains.items():
        for e in ch:
            cur.execute(
                "INSERT INTO custody_chain VALUES (?,?,?,?,?,?,?,?,?)",
                (mid, e["seq"], e["event_type"], e["actor_id"],
                 e["reason"], e["created_at"], e["payload_json"],
                 e["prev_hash"], e["entry_hash"]))
    for l in ev["cell_links"]:
        cur.execute("INSERT INTO cell_links VALUES (?,?,?,?)",
                    (l["from_id"], l["to_id"], l["link_type"], l["auto"]))
    conn.commit()

    t_i = next(e["created_at"] for e in chains[mid_i]
               if e["seq"] == seq_i)

    def world_recall(qemb, dead, as_of):
        """Recall in the world: chains truncated at as_of, dead events
        removed — recomputed states replace the rows under a
        savepoint; rolled back after."""
        cur.execute("SAVEPOINT cf_verify")
        try:
            for mid, ch in chains.items():
                st, fs, cf = replay(ch, dead.get(mid, set()), as_of)
                q = (Decimal(cf.numerator) /
                     Decimal(cf.denominator)).quantize(
                         Decimal("0.0000000001"))
                cur.execute(
                    "UPDATE memories SET custody_status=?,"
                    " field_state=?, confidence=? WHERE memory_id=?",
                    (st, fs, str(q), mid))
            hits, _ = field.recall(
                cur,
                query_embedding=[Decimal(str(x)) for x in qemb])
            return [h.memory_id for h in hits]
        finally:
            cur.execute("ROLLBACK TO cf_verify")
            cur.execute("RELEASE cf_verify")

    # CF2 actual-world consistency: every decision's cited receipt
    # must match what recall at t_d serves on the untampered evidence.
    consistent = True
    for d in ev["decisions"]:
        if d["created_at"] <= t_i:
            continue
        rec = ev["receipts"].get(d["receipt_sha256"])
        if rec is None:
            consistent = False
            continue
        served = world_recall(d["query_embedding"], {}, d["created_at"])
        if served != rec["served"]:
            consistent = False
    check("CF2 actual-world receipts self-consistent", consistent)

    # CF3 recompute the cascade and compare every claimed field.
    # Precedence rule (mirrors cf-cascade/v1): a decision is judged
    # against the world at t_d — events with created_at < t_d — and
    # its OWN consequences are excluded structurally (DECISION_USED
    # naming it + the adjacent REINFORCED), never by timestamp alone.
    def own_consequences(did):
        out = {}
        for mid, ch in chains.items():
            sch = sorted(ch, key=lambda x: x["seq"])
            for j, e in enumerate(sch):
                if (e["event_type"] == "DECISION_USED_MEMORY"
                        and json.loads(e["payload_json"]).get(
                            "decision_id") == did):
                    out.setdefault(mid, set()).add(e["seq"])
                    if (j + 1 < len(sch)
                            and sch[j + 1]["event_type"] == "REINFORCED"):
                        out[mid].add(sch[j + 1]["seq"])
        return out

    dead = {mid_i: {seq_i}}
    divergent, ungrounded, invalidated, propagation = [], [], [], []
    for d in sorted(ev["decisions"],
                    key=lambda x: (x["created_at"], x["decision_id"])):
        if d["created_at"] <= t_i:
            continue
        dead_eval = {mid: set(ds) for mid, ds in dead.items()}
        for mid, ds in own_consequences(d["decision_id"]).items():
            dead_eval.setdefault(mid, set()).update(ds)
        served_cf = world_recall(d["query_embedding"], dead_eval,
                                 d["created_at"])
        fallen = sorted(m for m in d["used"] if m not in served_cf)
        if not fallen:
            continue
        divergent.append(d["receipt_sha256"])
        kill = []
        for mid in sorted(d["used"]):
            sch = sorted(chains.get(mid, []), key=lambda x: x["seq"])
            for j, e in enumerate(sch):
                if (e["event_type"] == "DECISION_USED_MEMORY" and
                        json.loads(e["payload_json"]).get(
                            "decision_id") == d["decision_id"]):
                    dead.setdefault(mid, set()).add(e["seq"])
                    kill.append((mid, e["seq"], "DECISION_USED_MEMORY"))
                    if (j + 1 < len(sch)
                            and sch[j + 1]["event_type"] == "REINFORCED"):
                        dead[mid].add(sch[j + 1]["seq"])
                        kill.append((mid, sch[j + 1]["seq"], "REINFORCED"))
        ungrounded.append({"decision_id": d["decision_id"],
                           "used": d["used"], "fallen": fallen})
        invalidated.extend(kill)
        propagation.append({"decision_id": d["decision_id"],
                            "invalidated": [[m, s] for m, s, _ in kill]})

    rep = b["report"]
    check("CF3 divergent receipts recomputed",
          rep["divergent_receipts"] == divergent,
          f"claimed {len(rep['divergent_receipts'])},"
          f" recomputed {len(divergent)}")
    check("CF3 ungrounded decisions recomputed",
          rep["ungrounded_decisions"] == ungrounded)
    check("CF3 invalidated set recomputed",
          [list(x) for x in rep["invalidated"]]
          == [list(x) for x in invalidated],
          f"claimed {len(rep['invalidated'])},"
          f" recomputed {len(invalidated)}")
    check("CF3 propagation edges recomputed",
          rep["propagation"] == propagation)

    cf_states = {}
    for mid, ds in dead.items():
        st, fs, cf = replay(chains[mid], ds)
        cf_states[mid] = {"custody_status": st, "field_state": fs,
                          "confidence": str(cf)}
    check("CF3 counterfactual states recomputed",
          rep["counterfactual_states"] ==
          {m: cf_states[m] for m in sorted(cf_states)})

    rep_no_seal = {k: v for k, v in rep.items()
                   if k != "report_sha256"}
    check("CF3 report digest seals the recomputed result",
          rep["report_sha256"] == hashlib.sha256(
              canonical_json(rep_no_seal).encode("utf-8")).hexdigest())

    print()
    if all(checks):
        print("VERIFIED — the cascade recomputes from sealed evidence.")
        return 0
    print("REJECTED — the report does not follow from the evidence.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
