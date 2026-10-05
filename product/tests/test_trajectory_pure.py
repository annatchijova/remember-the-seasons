#!/usr/bin/env python3
"""Invariant tests for seasons/trajectory.py — the counterfactual the
research identified. Standalone (same style as mneme's suite):
exit 0 on pass, 1 on fail.

Invariants under test:

  I1  excising a state-neutral event (DECISION_USED_MEMORY) changes
      nothing — same state, empty delta.
  I2  excising the REINFORCED that made promotion due leaves the
      counterfactual NEUTRAL — the promotion event still on the chain
      does NOT fire in the excised world (arithmetically due, recomputed
      not trusted).
  I3  excising the promotion STATE_CHANGED itself leaves NEUTRAL at
      full confidence.
  I4  NOTHING IS WRITTEN — memories row and custody chains identical
      before/after; the receipts table stays empty.
  I5  the report is deterministic: two runs, one digest.
  I6  WIDENING GATE: excising a QUARANTINED event without a
      COUNTERFACTUAL-holding actor refuses.
  I7  excising STORED (seq 0) refuses — 'never existed' is a different
      question.
  I8  the report is marked hypothetical — it can never pass as
      evidence about the actual field.
  I9  unknown memory / unknown seq refuse loudly.
"""

import os
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seasons import agent, actors, trajectory
from mneme import custody, field, trust

FAIL = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}  {detail}")
    if not cond:
        FAIL.append(name)


def build_promoted():
    """mem-0000 promoted via three asks; mem-0001 stored after, NEUTRAL."""
    a = agent.SeasonsAgent()
    a.remember("staging gate deployment")
    for _ in range(3):
        a.ask("deploy gate staging")
    a.remember("deploy gate staging pass")
    return a


def snapshot(cur):
    cur.execute("SELECT memory_id, custody_status, field_state, "
                "confidence FROM memories ORDER BY memory_id")
    mem = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM custody_chain")
    nch = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM recall_receipts")
    nrc = cur.fetchone()[0]
    return mem, nch, nrc


print("=" * 60)
print("trajectory.py invariant tests")
print("=" * 60)

a = build_promoted()
q = field.quantize_embedding(__import__("seasons.embed", fromlist=["embed"])
                             .embed("deploy gate staging"))

# I3 / I8: promotion excision, hypothetical flag, determinism (I5)
rep = trajectory.what_if_transition(
    a.cur, query_embedding=q, memory_id="mem-0000", excise_seq=7)
check("I3 promotion excised -> NEUTRAL",
      rep["counterfactual_state"]["field_state"] == "NEUTRAL",
      rep["counterfactual_state"])
check("I3 rank flipped", rep["delta"]["rank_changed"] != [],
      rep["delta"])
check("I8 hypothetical flag", rep["hypothetical"] is True)
rep2 = trajectory.what_if_transition(
    a.cur, query_embedding=q, memory_id="mem-0000", excise_seq=7)
check("I5 deterministic digest",
      rep["report_sha256"] == rep2["report_sha256"])

# I4: nothing written
before = snapshot(a.cur)
trajectory.what_if_transition(
    a.cur, query_embedding=q, memory_id="mem-0000", excise_seq=7)
check("I4 no state change", snapshot(a.cur) == before)

# I2: excising enabling REINFORCED (seq 4) -> promotion not due
rep4 = trajectory.what_if_transition(
    a.cur, query_embedding=q, memory_id="mem-0000", excise_seq=4)
check("I2 excise enabling REINFORCED -> NEUTRAL",
      rep4["counterfactual_state"]["field_state"] == "NEUTRAL",
      rep4["counterfactual_state"])

# I1: DECISION_USED_MEMORY changes nothing
rep_d = trajectory.what_if_transition(
    a.cur, query_embedding=q, memory_id="mem-0000", excise_seq=1)
check("I1 evidence-event excision -> no delta",
      rep_d["delta"] == {"removed": [], "entered": [],
                         "rank_changed": []} and
      rep_d["actual"]["served"] == rep_d["counterfactual"]["served"])

# I7: STORED refused
try:
    trajectory.what_if_transition(
        a.cur, query_embedding=q, memory_id="mem-0000", excise_seq=0)
    check("I7 STORED excision refused", False)
except ValueError:
    check("I7 STORED excision refused", True)

# I9: unknown inputs refuse
for mid, seq in [("nope", 1), ("mem-0000", 999)]:
    try:
        trajectory.what_if_transition(
            a.cur, query_embedding=q, memory_id=mid, excise_seq=seq)
        check(f"I9 refuses {mid}:{seq}", False)
    except ValueError:
        check(f"I9 refuses {mid}:{seq}", True)

# I6: widening gate — quarantine mem-0000, then excise QUARANTINED
trust.quarantine_memory(
    a.cur, memory_id="mem-0000", actor_id=actors.OPERATOR,
    reason="test quarantine")
a.conn.commit()
qseq = max(e[0] for e in a.chain("mem-0000"))
try:
    trajectory.what_if_transition(
        a.cur, query_embedding=q, memory_id="mem-0000",
        excise_seq=qseq)   # no actor_id -> must refuse widening
    check("I6 widening refused without COUNTERFACTUAL", False)
except ValueError:
    check("I6 widening refused without COUNTERFACTUAL", True)

# I10: decision counterfactual — does the evidence base survive?
rep_dec = trajectory.decision_what_if(
    a.cur, decision_id="dec-0000", memory_id="mem-0000", excise_seq=7)
check("I10 decision block present",
      rep_dec["decision"]["decision_id"] == "dec-0000")
check("I10 evidence base evaluated",
      "evidence_base_intact" in rep_dec["decision"])
check("I10 report resealed with decision block",
      rep_dec["report_sha256"] != rep["report_sha256"])

post_q = snapshot(a.cur)   # quarantine legitimately added one event
rep_w = trajectory.what_if_transition(
    a.cur, query_embedding=q, memory_id="mem-0000", excise_seq=qseq,
    actor_id=actors.OPERATOR)
check("I6 widening allowed with COUNTERFACTUAL",
      rep_w["counterfactual_state"]["custody_status"] == "CLEAN")
check("I6 post-widening write-nothing still holds",
      snapshot(a.cur) == post_q)

print()
print("=" * 60)
print("cascade (do_transition) invariants")
print("=" * 60)

# C-scenario: A tainted then rehabilitated; post-rehab decisions used
# it. Excising REHABILITATED must unground them and kill their
# consequences on every used chain.
b = agent.SeasonsAgent()
b.remember("The deploy gate requires staging to pass.")
b.remember("Rollbacks run via ops rollback.")
b.remember("Monitoring dashboards poll every 30s.")
b.remember("Alerting routes to the on-call pager.")
b.remember("Postmortems are written within 48h.")
b.remember("Feature flags default off in prod.")
b.ask("deploy gate staging?")
for et in ("TAINT_FLAGGED", "REHABILITATED"):
    custody.append_event(
        b.cur, memory_id="mem-0000", event_type=et,
        actor_id=actors.AGENT, reason="scenario",
        created_at=custody.now_ts(), payload={})
b.cur.execute("UPDATE memories SET custody_status='CLEAN'"
              " WHERE memory_id='mem-0000'")
b.conn.commit()
for _ in range(3):
    b.ask("deploy gate staging?")

rseq = next(e[0] for e in b.chain("mem-0000")
            if e[1] == "REHABILITATED")
snap_c = snapshot(b.cur)
rep_c = trajectory.do_transition(b.cur, memory_id="mem-0000",
                                 excise_seq=rseq)

check("C1 cf state keeps the taint (excision rewound the clean)",
      rep_c["counterfactual_states"]["mem-0000"]["custody_status"]
      == "TAINT_FLAGGED")
check("C2 post-excision decisions ungrounded",
      [u["decision_id"] for u in rep_c["ungrounded_decisions"]]
      == ["dec-0001", "dec-0002", "dec-0003"])
check("C3 divergent receipts counted",
      len(rep_c["divergent_receipts"]) == 3)
# every invalidated event is a DECISION_USED/REINFORCED pair killed
# by an ungrounded decision — nothing else dies
check("C4 invalidated are endogenous consequences — every one is "
      "reachable from the intervention via declared causes",
      all(et in ("DECISION_USED_MEMORY", "REINFORCED", "STATE_CHANGED")
          for _, _, et in rep_c["invalidated"])
      and all(
          any(c.get("kind") in ("decision", "event")
              for c in json.loads(e["payload_json"]).get("causes", []))
          or json.loads(e["payload_json"]).get("caused_by_decision_id")
          or e["event_type"] == "DECISION_USED_MEMORY"
          for m, s, _ in rep_c["invalidated"]
          for e in [x for x in
                    trajectory.load_chain(b.cur, m)
                    if x["seq"] == s]))
killed = {(m, s) for m, s, _ in rep_c["invalidated"]}
prop = {(m, s) for p in rep_c["propagation"]
        for m, s in p["invalidated"]}
check("C5 every invalidation is propagated from an ungrounded"
      " decision — no orphans", killed == prop)
check("C6 hypothetical + sealed",
      rep_c["hypothetical"] is True
      and len(rep_c["report_sha256"]) == 64)
check("C7 write-nothing", snapshot(b.cur) == snap_c)
check("C8 deterministic",
      trajectory.do_transition(
          b.cur, memory_id="mem-0000",
          excise_seq=rseq)["report_sha256"]
      == rep_c["report_sha256"])
# evidence-only excision produces no cascade
rep_e = trajectory.do_transition(
    b.cur, memory_id="mem-0000",
    excise_seq=next(e[0] for e in b.chain("mem-0000")
                    if e[1] == "DECISION_USED_MEMORY"))
check("C9 evidence excision → empty cascade",
      not rep_e["ungrounded_decisions"]
      and not rep_e["invalidated"])

print()
if FAIL:
    print(f"{len(FAIL)} FAILED: {FAIL}")
    sys.exit(1)
# NC-DISCORDIA — a clock is not a cause. A v2-form DU (declares
# causes) followed IMMEDIATELY by an exogenous REINFORCED that declares
# nothing: under v1-style adjacency it dies by position; under the
# declared-cause rule it survives. Proximity is not causation.
a5 = agent.SeasonsAgent()
a5.remember("The deploy gate requires staging to pass.")
mid5 = "mem-0000"
for et, reason in (("TAINT_FLAGGED", "t"), ("REHABILITATED", "r")):
    custody.append_event(
        a5.cur, memory_id=mid5, event_type=et,
        actor_id="seasons-agent", reason=reason,
        created_at=custody.now_ts(), payload={})
a5.cur.execute(
    "UPDATE memories SET custody_status='CLEAN' WHERE memory_id=?",
    (mid5,))
a5.conn.commit()
r5 = a5.ask("deploy gate staging?")
did5 = r5["decision"]
ch5 = trajectory.load_chain(a5.cur, mid5)
# a second v2-form DU naming the same decision (declared causes) and
# IMMEDIATELY after it an exogenous REINFORCED declaring nothing.
custody.append_event(
    a5.cur, memory_id=mid5, event_type="DECISION_USED_MEMORY",
    actor_id="seasons-agent", reason="second record",
    created_at=custody.now_ts(),
    payload={"decision_id": did5,
             "causes": [{"kind": "decision", "id": did5}]})
exo_seq = custody.append_event(
    a5.cur, memory_id=mid5, event_type="REINFORCED",
    actor_id="seasons-agent", reason="exogenous bump",
    created_at=custody.now_ts(), payload={}).seq
a5.conn.commit()
rehab5 = next(e["seq"] for e in trajectory.load_chain(a5.cur, mid5)
              if e["event_type"] == "REHABILITATED")
rep5 = trajectory.do_transition(a5.cur, memory_id=mid5,
                                excise_seq=rehab5)
dead5 = {(m, s) for m, s, _ in rep5["invalidated"]}
check("NC-DISCORDIA exogenous REINFORCED survives — position is not "
      "causation", (mid5, exo_seq) not in dead5)


# R1/R2 — referential integrity (H16, adapted from memory-graveyard's
# Hallucinated/BROKEN_REFERENCE pattern): a sealed cause pointing at
# something that does not exist is an integrity failure, not an
# inert dependency. The phantom is caught; a real-but-irrelevant
# reference stays legal.
a6 = agent.SeasonsAgent()
mid6 = a6.remember("substrate fact")
custody.append_event(
    a6.cur, memory_id=mid6, event_type="REINFORCED",
    actor_id="seasons-agent", reason="phantom cause",
    created_at=custody.now_ts(),
    payload={"causes": [{"kind": "event", "memory_id": mid6,
                         "seq": 4000000}]})
a6.conn.commit()
errs6 = custody.check_dangling_references(a6.cur)
check("R1 phantom event-cause is an integrity error — silence was "
      "the bug", any("4000000" in x for x in errs6))

# a REAL event referenced but causally irrelevant: legal — only
# existence is checked, not meaning. Fresh field so the R1 phantom
# doesn't bleed into this assertion.
a7 = agent.SeasonsAgent()
mid7a = a7.remember("substrate fact")
mid7b = a7.remember("another fact")
custody.append_event(
    a7.cur, memory_id=mid7b, event_type="REINFORCED",
    actor_id="seasons-agent", reason="irrelevant but real cause",
    created_at=custody.now_ts(),
    payload={"causes": [{"kind": "event", "memory_id": mid7a,
                         "seq": 0}]})
a7.conn.commit()
errs7 = custody.check_dangling_references(a7.cur)
check("R2 real-but-irrelevant reference stays legal",
      not errs7, str(errs7))


print("all trajectory invariants held.")
sys.exit(0)

