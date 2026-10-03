#!/usr/bin/env python3
"""Golden-vector conformance: production field.recall vs the
verifier's independent transcription of ranking_protocol/1.0.0.

Two transcriptions of one protocol is what 'independent' means — and
it only counts if they agree. Generate varied worlds (custody mixes,
links, inhibition, rescue, decay depths, FORGOTTEN, score ties) and
require identical served sets, every world, every query.

Exit 0 = byte-identical agreement on all vectors.
"""

import os
import random
import sys
from decimal import Decimal
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mneme import field
import verify_cf_offline as V

from seasons import agent
from mneme import custody


def vec(rng, d=64):
    return [rng.uniform(-1, 1) for _ in range(d)]


def main():
    rng = random.Random(20261003)
    FAIL = 0
    cases = 0

    for trial in range(60):
        a = agent.SeasonsAgent()
        n = rng.randint(3, 10)
        for i in range(n):
            a.remember(f"memory {i} about {rng.choice(['deploy','auth','cache','queue'])}")
        # random custody states via direct row edits + chain events
        for i in range(n):
            mid = f"mem-{i:04d}"
            roll = rng.random()
            if roll < 0.15:
                custody.append_event(
                    a.cur, memory_id=mid, event_type="TAINT_FLAGGED",
                    actor_id="seasons-agent", reason="t",
                    created_at=custody.now_ts(), payload={})
                a.cur.execute(
                    "UPDATE memories SET custody_status='TAINT_FLAGGED'"
                    " WHERE memory_id=?", (mid,))
            elif roll < 0.25:
                custody.append_event(
                    a.cur, memory_id=mid, event_type="QUARANTINED",
                    actor_id="seasons-agent", reason="t",
                    created_at=custody.now_ts(), payload={})
                a.cur.execute(
                    "UPDATE memories SET custody_status='QUARANTINED'"
                    " WHERE memory_id=?", (mid,))
            elif roll < 0.35:
                a.cur.execute(
                    "UPDATE memories SET field_state='FORGOTTEN'"
                    " WHERE memory_id=?", (mid,))
            elif roll < 0.5:
                a.cur.execute(
                    "UPDATE memories SET field_state='REINFORCED'"
                    " WHERE memory_id=?", (mid,))
        # random links
        for _ in range(rng.randint(0, n)):
            f_, t_ = rng.randrange(n), rng.randrange(n)
            if f_ == t_:
                continue
            a.cur.execute(
                "INSERT OR IGNORE INTO cell_links"
                " (from_id, to_id, link_type, auto, created_at)"
                " VALUES (?,?,?,?,?)",
                (f"mem-{f_:04d}", f"mem-{t_:04d}",
                 rng.choice(["RESONANT", "INHIBITORY"]), 0,
                 custody.now_ts()))
        a.conn.commit()

        # build the verifier's world view
        memories = []
        for r in a.cur.execute(
                "SELECT memory_id, embedding_json, field_state,"
                " custody_status FROM memories"):
            memories.append({
                "memory_id": r[0],
                "embedding": __import__('json').loads(r[1])["v"],
                "field_state": r[2], "custody_status": r[3]})
        links = [dict(zip(["from_id", "to_id", "link_type"], r))
                 for r in a.cur.execute(
                     "SELECT from_id, to_id, link_type"
                     " FROM cell_links")]

        for _ in range(3):
            qemb = field.quantize_embedding(vec(rng))
            top_k = rng.randint(1, n)
            hops = rng.randint(0, 3)
            prod = [h.memory_id for h in field.recall(
                a.cur, query_embedding=qemb,
                top_k=top_k, hops=hops)[0]]
            indep = V.independent_recall(
                memories, links,
                [Fraction(Decimal(x)) for x in
                 __import__('json').loads(
                     field.embedding_to_json(qemb))["v"]],
                top_k=top_k, hops=hops)
            cases += 1
            if prod != indep:
                FAIL += 1
                print(f"  DIVERGENCE trial={trial} top_k={top_k}"
                      f" hops={hops}\n    prod : {prod}\n    indep:"
                      f" {indep}")

    print(f"{cases} recall vectors, {FAIL} divergences")
    if FAIL:
        sys.exit(1)
    print("CONFORMANT — independent transcription agrees byte-for-byte.")
    sys.exit(0)


if __name__ == "__main__":
    main()
