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
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seasons import agent, actors, trajectory
from mneme import field, trust

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
if FAIL:
    print(f"{len(FAIL)} FAILED: {FAIL}")
    sys.exit(1)
print("all trajectory invariants held.")
sys.exit(0)
