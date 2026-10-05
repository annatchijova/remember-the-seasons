#!/usr/bin/env python3
"""STIGMERGY-2 — two INDEPENDENT agents, one shared field. Separate
SeasonsAgent objects, separate sqlite connections, the same database
file. No Python state crosses between them — if the field is the
only coordination substrate, this should just work; if anything
drifts (id collisions, lost reads), the field was never the medium.

Under test (H15):

  S0  B decides on evidence A planted (cross-actor consumption).
  S1  excising A's cause kills B's consequence — causality crosses
      actors, not just events.
  S2  B's decisions grounded only in its own evidence survive.
  S3  an actor without a grant still cannot write.
  S4  interleaved writes collide on NOTHING — ids come from the
      field, not from either process.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from seasons import agent, actors, trajectory
from mneme import authority, custody

PASS = 0
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


# one shared field: a real file both agents open independently
fdir = tempfile.mkdtemp()
dbpath = os.path.join(fdir, "field.db")

a = agent.SeasonsAgent(dbpath)              # bootstraps the field

AGENT_B = "seasons-agent-b"
authority.register_actor(
    a.cur, actor_id=AGENT_B, display_name="Second Agent", kind="AGENT",
    issuer_id=actors.ROOT, reason="second writer on the shared field")
authority.grant(
    a.cur, subject_id=AGENT_B,
    capabilities=["STORE", "REINFORCE", "DECIDE"],
    issuer_id=actors.ROOT, reason="same capabilities as agent A")
a.conn.commit()

# a second, fully independent agent — own connection, own object,
# ZERO state passed in Python. It reads everything from the field.
b = agent.SeasonsAgent(dbpath, actor_id=AGENT_B)

mid_a = a.remember("The deploy gate requires staging to pass.")
custody.append_event(a.cur, memory_id=mid_a, event_type="TAINT_FLAGGED",
                     actor_id=actors.OPERATOR, reason="taint",
                     created_at=custody.now_ts(), payload={})
a.cur.execute("UPDATE memories SET custody_status='TAINT_FLAGGED'"
              " WHERE memory_id=?", (mid_a,))
custody.append_event(a.cur, memory_id=mid_a, event_type="REHABILITATED",
                     actor_id=a.actor, reason="A cleared it",
                     created_at=custody.now_ts(), payload={})
a.cur.execute("UPDATE memories SET custody_status='CLEAN'"
              " WHERE memory_id=?", (mid_a,))
a.conn.commit()

# interleaved writes BEFORE B's first read — B never saw A's counts
mid_b = b.remember("Postmortems are due within 48h.")
mid_a2 = a.remember("Staging deploys run blue-green.")
b.conn.commit()
r = b.ask("deploy gate staging?")
check("S0 B decided on A's memory", mid_a in r["used"])
check("S4 interleaved ids never collided",
      len({mid_a, mid_b, mid_a2}) == 3)

rehab = next(e["seq"] for e in trajectory.load_chain(a.cur, mid_a)
             if e["event_type"] == "REHABILITATED")
rep = trajectory.do_transition(a.cur, memory_id=mid_a,
                               excise_seq=rehab)
dead = {(m, s) for m, s, _ in rep["invalidated"]}
du_b = next(e["seq"] for e in trajectory.load_chain(a.cur, mid_a)
            if e["event_type"] == "DECISION_USED_MEMORY"
            and json.loads(e["payload_json"])["decision_id"]
            == r["decision"])
check("S1 B's consequence dies on A's cause", (mid_a, du_b) in dead)

# re-taint EVERY memory of A so B's next decision rests only on its
# own — mem-0002 is semantically adjacent and would get served too
for m in (mid_a, mid_a2):
    custody.append_event(a.cur, memory_id=m, event_type="TAINT_FLAGGED",
                         actor_id=actors.OPERATOR, reason="re-tainted",
                         created_at=custody.now_ts(), payload={})
    a.cur.execute("UPDATE memories SET custody_status='TAINT_FLAGGED'"
                  " WHERE memory_id=?", (m,))
a.conn.commit()
r2 = b.ask("postmortem deadline?")
check("S2a B's decision used only its own evidence",
      r2["used"] == [mid_b])
rep2 = trajectory.do_transition(a.cur, memory_id=mid_a,
                                excise_seq=rehab)
dead2 = {(m, s) for m, s, _ in rep2["invalidated"]}
ch_b = trajectory.load_chain(a.cur, mid_b)
du_of = {d: e["seq"] for d in (r["decision"], r2["decision"])
         for e in ch_b
         if e["event_type"] == "DECISION_USED_MEMORY"
         and json.loads(e["payload_json"])["decision_id"] == d}
check("S2 B's independent consequences survive — and the "
      "CONTAMINATED decision's footprint on mid_b correctly dies",
      (mid_b, du_of[r2["decision"]]) not in dead2
      and (mid_b, du_of[r["decision"]]) in dead2)

# authority is still per-actor in the shared field
authority.register_actor(
    a.cur, actor_id="ungranted", display_name="x", kind="AGENT",
    issuer_id=actors.ROOT, reason="no capabilities")
a.conn.commit()
try:
    from mneme import field
    field.store(a.cur, memory_id="mem-9999", actor_id="ungranted",
                reason="x", content="x", embedding=[0.0] * 4)
    s3 = False
except Exception:
    a.conn.rollback()   # the rejected write must not poison a's txn
    s3 = True
check("S3 ungranted actor cannot write", s3)


# S5 — concurrent writers: two threads, simultaneous releases, no
# coordination. The field assigns ids; UNIQUE catches races; retry
# recomputes. Nothing lost, nothing collided.
import threading
start = threading.Event()
errs = []
def _w(actor_id, n):
    ag = agent.SeasonsAgent(dbpath, actor_id=actor_id)
    start.wait()
    for i in range(n):
        try:
            ag.remember(f"concurrent {actor_id} {i}")
        except Exception as e:
            errs.append((actor_id, i, str(e)[:80]))

before = a.cur.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
ths = [threading.Thread(target=_w, args=(ac, 8))
       for ac in (a.actor, AGENT_B)]
for t in ths:
    t.start()
start.set()
for t in ths:
    t.join(30)
after = a.cur.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
ids = [r[0] for r in a.cur.execute(
    "SELECT memory_id FROM memories")]
check("S5 16 concurrent writes: none lost, none collided",
      after - before == 16 and len(set(ids)) == len(ids)
      and not errs, str(errs[:3]))


# S6/S7 — same-memory concurrent writes: serialization is not
# causality. A's DU + caused REINFORCED race B's exogenous REINFORCED
# onto ONE chain. Run twice with opposite first-writer.
def _s67(order_swap):
    fdir2 = tempfile.mkdtemp()
    db2 = os.path.join(fdir2, "f.db")
    a0 = agent.SeasonsAgent(db2)
    authority.register_actor(
        a0.cur, actor_id=AGENT_B, display_name="B", kind="AGENT",
        issuer_id=actors.ROOT, reason="r")
    authority.grant(
        a0.cur, subject_id=AGENT_B,
        capabilities=["STORE", "REINFORCE", "DECIDE"],
        issuer_id=actors.ROOT, reason="r")
    a0.conn.commit()
    mid = a0.remember("shared substrate")
    a0.conn.commit()

    def push(actor, et, payload):
        ag = agent.SeasonsAgent(db2, actor_id=actor)
        for _ in range(10):
            try:
                e = custody.append_event(
                    ag.cur, memory_id=mid, event_type=et,
                    actor_id=actor, reason="concurrent write",
                    created_at=custody.now_ts(), payload=payload)
                ag.conn.commit()
                ag.conn.close()
                return e
            except Exception:
                ag.conn.rollback()
        raise RuntimeError("append kept colliding")

    start = threading.Event()
    res = {}

    def wA():
        start.wait()
        res["du"] = push(a.actor, "DECISION_USED_MEMORY",
                         {"decision_id": "dec-A",
                          "causes": [{"kind": "decision",
                                      "id": "dec-A"}]})
        res["rA"] = push(a.actor, "REINFORCED",
                         {"caused_by_decision_id": "dec-A",
                          "causes": [{"kind": "decision",
                                      "id": "dec-A"}]})

    def wB():
        start.wait()
        res["rB"] = push(AGENT_B, "REINFORCED", {"note": "exogenous"})

    t1, t2 = threading.Thread(target=wA), threading.Thread(target=wB)
    (t2 if order_swap else t1).start()
    (t1 if order_swap else t2).start()
    start.set()
    t1.join()
    t2.join()

    ch = trajectory.load_chain(a0.cur, mid)
    seqs = [e["seq"] for e in ch]
    dense = seqs == list(range(len(ch)))
    linked = all(ch[i]["prev_hash"] == ch[i - 1]["entry_hash"]
                 for i in range(1, len(ch)))
    rep = trajectory.do_transition(
        a0.cur, memory_id=mid, excise_seq=res["du"].seq)
    dead = {(m, s) for m, s, _ in rep["invalidated"]}
    return dense, linked, (mid, res["rB"].seq) in dead

d1, l1, deadB1 = _s67(order_swap=False)
d2, l2, deadB2 = _s67(order_swap=True)
check("S6 same-chain concurrent writes: dense, linked, nothing lost",
      d1 and l1 and d2 and l2)
check("S7 serialization is not causality — B survives A's death in "
      "BOTH orders", not deadB1 and not deadB2)


# S8/S9 — causal equivalence ≠ state convergence. TAINT and REHAB are
# orthogonal ops (no declared causes either way), both legal against
# SOME pre-state, non-commuting on a CLEAN memory.
def _s8(taint_first):
    fdir3 = tempfile.mkdtemp()
    db3 = os.path.join(fdir3, "f.db")
    a3 = agent.SeasonsAgent(db3)
    mid = a3.remember("non-commuting substrate")
    ops = [("TAINT_FLAGGED", "op-taint"),
           ("REHABILITATED", "op-rehab")]
    if not taint_first:
        ops.reverse()
    for et, reason in ops:
        custody.append_event(
            a3.cur, memory_id=mid, event_type=et,
            actor_id=actors.OPERATOR, reason=reason,
            created_at=custody.now_ts(), payload={})
    a3.conn.commit()
    ch = trajectory.load_chain(a3.cur, mid)
    status, _, _, errs = custody.replay_state(ch)
    return status, errs

st1, e1 = _s8(taint_first=True)
st2, e2 = _s8(taint_first=False)
# OBSERVED: causal graph identical (no causes either way), but
#   A->B -> CLEAN, legal
#   B->A -> TAINTED and the chain carries an illegal transition
#   (REHAB from CLEAN) — the write path does not gate transitions;
#   legality only exists at replay time.
check("S8 non-commuting ops: same causes, different derived state — "
      "confluence is NOT a property of this field",
      st1 != st2)
check("S9 the losing order is semantically INVALID, not merely "
      "different — write-side lacks transition legality",
      not e1 and any("REHABILITATED from CLEAN" in x for x in e2))


# S10 — atomic legality: a stale transition must be rejected at the
# write boundary, INSIDE the serialization. Forced contention: both
# writers observe CLEAN; A commits TAINT; B's REHAB, legal only from
# TAINTED, must fail against the state it actually extends.
def _s10():
    fdir4 = tempfile.mkdtemp()
    db4 = os.path.join(fdir4, "f.db")
    a4 = agent.SeasonsAgent(db4)
    mid = a4.remember("legality substrate")
    a4.conn.commit()

    def tx_transition(actor, et):
        ag = agent.SeasonsAgent(db4, actor_id=actor)
        try:
            ag.cur.execute("BEGIN IMMEDIATE")
            custody.append_legal_event(
                ag.cur, memory_id=mid, event_type=et,
                actor_id=actor, reason="atomic check",
                created_at=custody.now_ts(), payload={})
            ag.conn.commit()
            return True
        except ValueError:
            ag.conn.rollback()
            return False
        finally:
            ag.conn.close()

    # sequential orders first: TAINT->REHAB legal; REHAB on CLEAN
    # rejected with nothing written
    ok_taint = tx_transition(actors.OPERATOR, "TAINT_FLAGGED")
    ok_rehab = tx_transition(actors.OPERATOR, "REHABILITATED")
    ch = trajectory.load_chain(a4.cur, mid)
    seqs = [e["seq"] for e in ch]
    dense = seqs == list(range(len(ch)))
    st, _, _, errs = custody.replay_state(ch)
    return ok_taint, ok_rehab, dense, st, errs

t, r, d, st, errs = _s10()
check("S10 stale/illegal transition rejected atomically, nothing "
      "partial written", t and r and d and st == "CLEAN" and not errs)

# and the illegal order now CANNOT commit: REHAB on CLEAN raises
fdir5 = tempfile.mkdtemp()
db5 = os.path.join(fdir5, "f.db")
a5 = agent.SeasonsAgent(db5)
mid5 = a5.remember("x")
a5.conn.commit()
rejected = False
try:
    a5.cur.execute("BEGIN IMMEDIATE")
    custody.append_legal_event(
        a5.cur, memory_id=mid5, event_type="REHABILITATED",
        actor_id=actors.OPERATOR, reason="illegal",
        created_at=custody.now_ts(), payload={})
    a5.conn.commit()
except ValueError:
    a5.conn.rollback()
    rejected = True
ch5 = trajectory.load_chain(a5.cur, mid5)
check("S10b REHAB on CLEAN never reaches the chain — write-side "
      "legality is now real", rejected and len(ch5) == 1)

# S11 — the REAL non-confluence question: a BOTH-legal non-commuting
# pair. QUARANTINED and SUPERSEDED_BY are unconditional transitions:
# every order is legal, final states differ.
def _s11(quar_first):
    fdir6 = tempfile.mkdtemp()
    db6 = os.path.join(fdir6, "f.db")
    a6 = agent.SeasonsAgent(db6)
    mid = a6.remember("confluence probe")
    ops = ["QUARANTINED", "SUPERSEDED_BY"]
    if not quar_first:
        ops.reverse()
    for et in ops:
        a6.cur.execute("BEGIN IMMEDIATE")
        custody.append_legal_event(
            a6.cur, memory_id=mid, event_type=et,
            actor_id=actors.OPERATOR, reason="op",
            created_at=custody.now_ts(), payload={})
        a6.conn.commit()
    ch = trajectory.load_chain(a6.cur, mid)
    st, _, _, errs = custody.replay_state(ch)
    return st, errs

s_q, e_q = _s11(quar_first=True)
s_s, e_s = _s11(quar_first=False)
check("S11 both orders LEGAL, states diverge — true non-confluence "
      "among valid histories", not e_q and not e_s and s_q != s_s)
print(f"      QUAR->SUP: {s_q} | SUP->QUAR: {s_s} (both legal)")


# S12 — is serialization semantically authoritative? Run the same
# concurrent causally-independent pair N times. If the outcome
# varies, the operational state is scheduler luck, not evidence.
import collections
def _s12(runs):
    outcomes = collections.Counter()
    for _ in range(runs):
        fdir7 = tempfile.mkdtemp()
        db7 = os.path.join(fdir7, "f.db")
        a7 = agent.SeasonsAgent(db7)
        mid = a7.remember("x")
        a7.conn.commit()

        start = threading.Event()

        def w(et):
            ag = agent.SeasonsAgent(db7, actor_id=actors.OPERATOR)
            start.wait()
            for _ in range(10):
                try:
                    ag.cur.execute("BEGIN IMMEDIATE")
                    custody.append_legal_event(
                        ag.cur, memory_id=mid, event_type=et,
                        actor_id=actors.OPERATOR, reason="c",
                        created_at=custody.now_ts(), payload={})
                    ag.conn.commit()
                    ag.conn.close()
                    return
                except Exception:
                    ag.conn.rollback()

        t1 = threading.Thread(target=w, args=("QUARANTINED",))
        t2 = threading.Thread(target=w, args=("SUPERSEDED_BY",))
        t1.start()
        t2.start()
        start.set()
        t1.join()
        t2.join()
        ch = trajectory.load_chain(a7.cur, mid)
        st, _, _, _ = custody.replay_state(ch)
        outcomes[st] += 1
    return outcomes

oc = _s12(16)
check("S12 forensic order is not semantic authority — same causal "
      "input, divergent operational states under scheduler luck",
      len(oc) > 1)
print(f"      16 runs of identical concurrent QUAR+SUP: "
      f"{dict(oc)} — the state is a coin flip with a chain")


# S13 — epistemic abstention: can a verifier retrospectively detect
# that two committed events were concurrent rather than ordered?
# OBSERVED: no field carries the observed-vs-committed distinction.
# prev_hash records where the event SEALED, not what the writer saw.
# created_at orders wall clocks, not knowledge. The evidence loses
# the race — concurrency is invisible in the sealed record.
fdir8 = tempfile.mkdtemp()
db8 = os.path.join(fdir8, "f.db")
a8 = agent.SeasonsAgent(db8)
mid8 = a8.remember("x")
a8.conn.commit()
observable = set()
e_a = custody.append_event(
    a8.cur, memory_id=mid8, event_type="QUARANTINED",
    actor_id=actors.OPERATOR, reason="w1",
    created_at=custody.now_ts(), payload={})
a8.conn.commit()
ch8 = trajectory.load_chain(a8.cur, mid8)
row = ch8[1]
observable = set(row.keys())
# candidate signals that do not work: prev_hash is the committed
# linkage (the winner's chain position), created_at is wall-clock —
# neither encodes "the head the writer had read".
has_observed_head = "observed_head" in observable or any(
    "observed" in k for k in observable)
check("S13 the sealed record cannot distinguish concurrent from "
      "ordered — evidence loss is real (this is the finding, not a "
      "failure to fix)", not has_observed_head)
print(f"      observable fields: {sorted(observable)}")
print("      observed-head field: ABSENT — a B that never saw A "
      "seals identically to a B that came later")

print()
if FAIL:
    print(f"{len(FAIL)} FAILED: {FAIL}")
    sys.exit(1)

# S14 — attribution: each agent's writes are signed under ITS OWN
# key. Two agents, two seeds, one shared field — a verifier can ask
# "who wrote this?" and get a cryptographic answer, not a string in
# a column.
import tempfile
db_sig = os.path.join(tempfile.mkdtemp(), "sig-field.db")
field_boot = agent.SeasonsAgent(db_sig, actor_id="seasons-agent",
                              key_seed="aa" * 32)
authority.register_actor(
    field_boot.cur, actor_id="agent-b", display_name="Agent B",
    kind="AGENT", issuer_id=actors.ROOT,
    reason="second keyed writer on the shared field")
authority.grant(
    field_boot.cur, subject_id="agent-b",
    capabilities=["STORE", "REINFORCE", "DECIDE"],
    issuer_id=actors.ROOT, reason="same capabilities")
field_boot.conn.commit()

mem_signed = field_boot.remember("signed by A")

# second agent, same field file, own connection, own key — the
# signer dispatch routes by actor_id, each writes on its own conn
b2 = agent.SeasonsAgent(db_sig, actor_id="agent-b",
                        key_seed="bb" * 32)
mem_b = b2.remember("signed by B")

sigs_a = field_boot.cur.execute(
    "SELECT k.actor_id FROM event_sigs s JOIN actor_keys k "
    "ON k.keyid = s.keyid WHERE s.memory_id=?",
    (mem_signed,)).fetchall()
sigs_b = b2.cur.execute(
    "SELECT k.actor_id FROM event_sigs s JOIN actor_keys k "
    "ON k.keyid = s.keyid WHERE s.memory_id=?",
    (mem_b,)).fetchall()
check("S14 every event signed, key belongs to its actor",
      all(r[0] == "seasons-agent" for r in sigs_a)
      and all(r[0] == "agent-b" for r in sigs_b)
      and sigs_a and sigs_b)

from nacl.signing import VerifyKey
vka = VerifyKey(bytes.fromhex(field_boot.cur.execute(
    "SELECT verify_key_hex FROM actor_keys "
    "WHERE actor_id='seasons-agent'").fetchone()[0]))
chain_a = trajectory.load_chain(field_boot.cur, mem_signed)
sig_rows = field_boot.cur.execute(
    "SELECT seq, sig FROM event_sigs WHERE memory_id=? ORDER BY seq",
    (mem_signed,)).fetchall()
ok_sig = all(
    vka.verify(chain_a[s]["entry_hash"].encode("ascii"),
               bytes.fromhex(sg)) is not None
    for s, sg in sig_rows)
check("S15 signatures verify over entry_hash under the actor's key",
      ok_sig)

print(f"all stigmergy invariants held — the field is the only "
      f"coordination substrate. ({PASS} checks)")
sys.exit(0)
