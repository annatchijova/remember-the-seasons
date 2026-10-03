#!/usr/bin/env python3
"""Adversarial mutants for the counterfactual bundle verifier.

Each mutant ships a sealed, digest-consistent bundle (we reseal after
mutating, so CF0 must NOT be what catches it) whose deeper claim is
false. A verifier that only checks hashes passes every one of these;
one that recomputes catches them all. Exit 0 = every mutant rejected.
"""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal

from seasons import agent, trajectory
from mneme import custody, field
from mneme.canonical import canonical_json

FAIL = []


def check(name, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAIL.append(name)


def reseal(b):
    b.pop("bundle_sha256", None)
    b["bundle_sha256"] = hashlib.sha256(
        canonical_json(b).encode("utf-8")).hexdigest()
    return b


def verify(bundle) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False) as f:
        json.dump(bundle, f)
        p = f.name
    r = subprocess.run(
        [sys.executable, os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "verify_cf_offline.py"), p],
        capture_output=True, text=True)
    return r.returncode, r.stdout


print("=" * 64)
print("counterfactual bundle mutants — a sealed lie must not verify")
print("=" * 64)

a = agent.SeasonsAgent()
for c in ["The deploy gate requires staging to pass.",
          "Rollbacks run via ops rollback.",
          "Monitoring dashboards poll every 30s.",
          "Alerting routes to the on-call pager.",
          "Postmortems are written within 48h.",
          "Feature flags default off in prod."]:
    a.remember(c)
a.ask("deploy gate staging?")
for et in ("TAINT_FLAGGED", "REHABILITATED"):
    custody.append_event(
        a.cur, memory_id="mem-0000", event_type=et,
        actor_id="seasons-agent", reason="test",
        created_at=custody.now_ts(), payload={})
a.cur.execute("UPDATE memories SET custody_status='CLEAN'"
              " WHERE memory_id='mem-0000'")
a.conn.commit()
for _ in range(3):
    a.ask("deploy gate staging?")
seq = next(e[0] for e in a.chain("mem-0000") if e[1] == "REHABILITATED")
GOOD = trajectory.export_cf_bundle(a.cur, memory_id="mem-0000",
                                   excise_seq=seq)

rc, out = verify(GOOD)
check("baseline verifies", rc == 0)

# M1 — change the excised event (resealed)
b = copy.deepcopy(GOOD)
b["intervention"]["seq"] = 2
rc, out = verify(reseal(b))
check("M1 wrong excised seq rejected", rc != 0 and "CF3" in out)

# M2 — tamper a chain event's type (evidence itself is false)
b = copy.deepcopy(GOOD)
for e in b["evidence"]["chains"]["mem-0000"]:
    if e["seq"] == seq:
        e["event_type"] = "REINFORCED"
rc, out = verify(reseal(b))
check("M2 tampered chain event rejected", rc != 0)

# M3 — remove a propagation edge (claim less propagation)
b = copy.deepcopy(GOOD)
b["report"]["propagation"][0]["invalidated"].pop()
rc, out = verify(reseal(b))
check("M3 dropped propagation edge rejected",
      rc != 0 and "propagation" in out)

# M4 — orphan invalidation (claim an event died with no decision)
b = copy.deepcopy(GOOD)
b["report"]["invalidated"].append(["mem-0004", 1, "REINFORCED"])
rc, out = verify(reseal(b))
check("M4 orphan invalidation rejected", rc != 0)

# M5 — declare a surviving decision ungrounded (overclaim)
b = copy.deepcopy(GOOD)
b["report"]["ungrounded_decisions"].append(
    {"decision_id": "dec-0000", "used": ["mem-0000"],
     "fallen": ["mem-0000"]})
rc, out = verify(reseal(b))
check("M5 phantom ungrounding rejected",
      rc != 0 and "ungrounded" in out)

# M6 — drop one REINFORCED kill (underclaim the cascade)
b = copy.deepcopy(GOOD)
b["report"]["invalidated"] = [
    x for x in b["report"]["invalidated"]
    if list(x) != ["mem-0000", 6, "REINFORCED"]]
b["report"]["propagation"][0]["invalidated"] = [
    x for x in b["report"]["propagation"][0]["invalidated"]
    if list(x) != ["mem-0000", 6]]
rc, out = verify(reseal(b))
check("M6 dropped REINFORCED kill rejected", rc != 0)

# M7 — tamper an exogenous input (query embedding)
b = copy.deepcopy(GOOD)
b["evidence"]["decisions"][1]["query_embedding"][0] = "9.9900000000"
rc, out = verify(reseal(b))
check("M7 tampered query embedding rejected", rc != 0)

# M8 — swap two events' seqs in a chain (history falsified, not just
# reordered — ordering is by seq, so moving list positions is inert)
b = copy.deepcopy(GOOD)
ch = b["evidence"]["chains"]["mem-0000"]
ch[1]["seq"], ch[2]["seq"] = ch[2]["seq"], ch[1]["seq"]
rc, out = verify(reseal(b))
check("M8 swapped seqs rejected", rc != 0)

# M10 — tamper a field that does NOT affect the cascade (reason text)
#     keeping entry_hash + prev_hash intact: linkage holds but the
#     envelope no longer re-derives — history falsified.
b = copy.deepcopy(GOOD)
b["evidence"]["chains"]["mem-0000"][1]["reason"] = "rewritten reason"
rc, out = verify(reseal(b))
check("M10 envelope-tampered event rejected by CF1 recompute",
      rc != 0 and "CF1" in out)

# M11 — recommitted embedding: change the embedding AND its hash to
#      match each other — internally consistent but not the input the
#      receipt committed to at recall time.
b = copy.deepcopy(GOOD)
d = b["evidence"]["decisions"][1]
d["query_embedding"][0] = "9.9900000000"
d["query_embedding_sha256"] = field.embedding_sha256(
    [Decimal(x) for x in d["query_embedding"]])
rc, out = verify(reseal(b))
check("M11 recommitted embedding rejected (receipt commitment)",
      rc != 0 and "CF1.5" in out)

# M12 — unknown semantics: a bundle sealed under a rewind protocol
#      this verifier does not implement must fail CLOSED.
b = copy.deepcopy(GOOD)
b["semantics"]["causal_rewind_protocol"] = "cf-cascade/v99"
rc, out = verify(reseal(b))
check("M12 unknown protocol version refused",
      rc != 0 and "CF0.5" in out)

# M13 — timestamp collision: two decisions sharing created_at must
#      still produce a deterministic cascade (ordering by
#      (created_at, decision_id), and a decision's own consequences
#      excluded structurally — the clock alone does not decide).
a2 = agent.SeasonsAgent()
a2.remember("The deploy gate requires staging to pass.")
a2.remember("Rollbacks run via ops rollback.")
a2.ask("deploy gate staging?")
a2.cur.execute(
    "UPDATE decisions SET created_at = (SELECT MIN(created_at)"
    " FROM decisions) WHERE 1")
a2.cur.execute(
    "UPDATE seasons_decisions SET created_at = (SELECT MIN(created_at)"
    " FROM decisions) WHERE 1")
a2.conn.commit()
d1 = trajectory.do_transition(a2.cur, memory_id="mem-0000",
                              excise_seq=2)["report_sha256"]
d2 = trajectory.do_transition(a2.cur, memory_id="mem-0000",
                              excise_seq=2)["report_sha256"]
check("M13 timestamp collision still deterministic", d1 == d2)

# M9 — hash-consistent but causally false: fabricate the whole result
#     coherently (different excision story, resealed end-to-end)
b = copy.deepcopy(GOOD)
b["report"]["divergent_receipts"] = []
b["report"]["ungrounded_decisions"] = []
b["report"]["invalidated"] = []
b["report"]["propagation"] = []
b["report"]["counterfactual_states"] = {
    "mem-0000": {"custody_status": "TAINT_FLAGGED",
                 "field_state": "NEUTRAL", "confidence": "5/8"}}
b["report"]["report_sha256"] = hashlib.sha256(
    canonical_json({k: v for k, v in b["report"].items()
                    if k != "report_sha256"}).encode()).hexdigest()
rc, out = verify(reseal(b))
check("M9 coherent-but-false cascade rejected (empty result claimed)",
      rc != 0 and "REJECTED" in out)

print()
if FAIL:
    print(f"{len(FAIL)} FAILED: {FAIL}")
    sys.exit(1)
print("all mutants rejected — the verifier recomputes, not trusts.")
sys.exit(0)
