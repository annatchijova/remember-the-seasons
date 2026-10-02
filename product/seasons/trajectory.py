"""Trajectory counterfactual: what if THIS transition had not happened?

The gap identified in research/PRODUCT_EXPLORATION_RUSTY_LAKE_MNEME.md:
mneme's compare_worlds asks "what if custody had been different" — it
cannot ask "what if event e in this chain had never occurred", because
the override touches custody state, not the history of transitions.

This module answers the second question:

  excise event (memory_id, seq) -> generous replay (transitions
  RECOMPUTED, not verified) -> counterfactual (custody, field_state,
  confidence) -> run the real recall against that world under a
  SAVEPOINT, roll back -> seal a delta report that SAYS it is
  hypothetical.

Two disciplines make it honest:

  - the excised replay recomputes confidence (c' = c + a(1-c)) rather
    than trusting recorded values, and a NEUTRAL->REINFORCED promotion
    fires only if the recomputed confidence reaches the threshold —
    the same "arithmetically due" rule replay 1.1.0 enforces, applied
    to a world that diverges from the evidence.
  - the counterfactual recall runs the UNMODIFIED recall inside a
    savepoint, so the ranking semantics are literally the production
    ones; the world is rolled back — nothing is written. The sealed
    report carries "hypothetical": true so its digest can never pass
    for evidence about the actual field.

v1 scope: excision affects ONE memory's replayed state. Cross-effects
that in a real system would flow through decisions and recall history
(links created by a transition, decisions that consumed the state) are
not rewound — stated, not hidden.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from fractions import Fraction
from typing import Any

from mneme import authority, custody, field
from mneme.canonical import canonical_json

CHAIN_COLS = ["memory_id", "seq", "event_type", "actor_id", "reason",
              "created_at", "payload_json", "prev_hash", "entry_hash"]

_ALPHA = field.REINFORCEMENT_ALPHA
_THRESHOLD = custody.PROMOTION_THRESHOLD


def load_chain(cur, memory_id: str) -> list[dict[str, Any]]:
    cur.execute(
        "SELECT memory_id, seq, event_type, actor_id, reason, created_at,"
        " payload_json, prev_hash, entry_hash FROM custody_chain"
        " WHERE memory_id = ? ORDER BY seq ASC", (memory_id,))
    return [dict(zip(CHAIN_COLS, r)) for r in cur.fetchall()]


def replay_excised(chain: list[dict[str, Any]],
                   excise_seq: int) -> tuple[str, str, Fraction]:
    """Replay a chain with one event excised — recomputing transitions.

    Unlike custody.replay_state this does not VERIFY anything: recorded
    confidence_before/after are untrusted (they describe the world where
    the event happened), and a promotion STATE_CHANGED applies only when
    the recomputed confidence makes it arithmetically due.
    Returns (custody_status, field_state, confidence).
    """
    status, fstate = "CLEAN", "NEUTRAL"
    conf = Fraction(1, 2)                     # INITIAL_CONFIDENCE
    for ev in chain:
        if ev["seq"] == excise_seq:
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
            conf = conf + _ALPHA * (1 - conf)
        elif et == "STATE_CHANGED":
            payload = json.loads(ev["payload_json"])
            to = payload.get("to")
            if payload.get("from") == "NEUTRAL" and to == "REINFORCED":
                if conf >= _THRESHOLD:
                    fstate = "REINFORCED"     # promotion was due
                # else: in this world the promotion never fired
            elif to is not None:
                fstate = to
        # CONTRADICTED_BY / DECISION_USED_MEMORY change no state
    return status, fstate, conf


def what_if_transition(cur, *, query_embedding, memory_id: str,
                       excise_seq: int, top_k: int = 5,
                       hops: int = field.DEFAULT_HOPS,
                       actor_id: str | None = None) -> dict[str, Any]:
    """Same query in the world where custody event (memory_id,
    excise_seq) never happened. Sealed report, marked hypothetical.

    The counterfactual state replaces the row inside a SAVEPOINT so the
    recall is the production one — identical ranking, gate, rescue rule.
    The receipt produced inside belongs to the hypothetical world; it is
    wrapped (not persisted) and the report says so.
    """
    chain = load_chain(cur, memory_id)
    if not chain:
        raise ValueError(f"Unknown memory {memory_id!r}.")
    if not any(e["seq"] == excise_seq for e in chain):
        raise ValueError(f"{memory_id} has no custody event seq "
                         f"{excise_seq}.")
    excised = next(e for e in chain if e["seq"] == excise_seq)
    if excised["event_type"] == "STORED":
        raise ValueError("Excising STORED (seq 0) means 'the memory never "
                         "existed' — a different counterfactual; v1 only "
                         "excises post-birth transitions.")

    cf_status, cf_fstate, cf_conf = replay_excised(chain, excise_seq)

    # WIDENING check — same rule as custody_override: if the excised
    # world makes the memory servable where the actual gate withholds
    # it, the counterfactual discloses gated content and demands an
    # actor holding COUNTERFACTUAL.
    cur.execute("SELECT custody_status FROM memories WHERE memory_id = ?",
                (memory_id,))
    actual_status = cur.fetchone()[0]
    if actual_status != "CLEAN" and cf_status == "CLEAN":
        if actor_id is None:
            raise ValueError(
                f"Excising {memory_id} seq {excise_seq} would make a "
                f"{actual_status} memory servable — disclosing what the "
                "custody gate withholds. Requires actor_id holding "
                "COUNTERFACTUAL.")
        authority.require(cur, actor_id=actor_id,
                          capability="COUNTERFACTUAL")

    hits_a, rec_a = field.recall(
        cur, query_embedding=query_embedding, top_k=top_k, hops=hops)

    cur.execute("SAVEPOINT trajectory_cf")
    try:
        conf_q = (Decimal(cf_conf.numerator) /
                  Decimal(cf_conf.denominator)).quantize(
                      Decimal("0.0000000001"))
        cur.execute(
            "UPDATE memories SET custody_status = ?, field_state = ?,"
            " confidence = ? WHERE memory_id = ?",
            (cf_status, cf_fstate, str(conf_q), memory_id))
        hits_b, rec_b = field.recall(
            cur, query_embedding=query_embedding, top_k=top_k, hops=hops)
    finally:
        cur.execute("ROLLBACK TO trajectory_cf")
        cur.execute("RELEASE trajectory_cf")

    rank_a = {h.memory_id: i for i, h in enumerate(hits_a)}
    rank_b = {h.memory_id: i for i, h in enumerate(hits_b)}
    removed = sorted(set(rank_a) - set(rank_b))
    entered = sorted(set(rank_b) - set(rank_a))
    rank_changed = sorted(
        (m, rank_a[m], rank_b[m]) for m in set(rank_a) & set(rank_b)
        if rank_a[m] != rank_b[m])

    report = {
        "hypothetical": True,
        "kind": "trajectory_counterfactual/v1",
        "question_sha256": rec_a.query_sha256,
        "excised": {"memory_id": memory_id, "seq": excise_seq,
                    "event_type": excised["event_type"],
                    "created_at": excised["created_at"]},
        "counterfactual_state": {"custody_status": cf_status,
                                 "field_state": cf_fstate,
                                 "confidence": str(cf_conf)},
        "actual": {"served": list(rec_a.served),
                   "receipt_sha256": rec_a.receipt_sha256},
        "counterfactual": {"served": list(rec_b.served),
                           "receipt_sha256": rec_b.receipt_sha256},
        "delta": {"removed": removed, "entered": entered,
                  "rank_changed": rank_changed},
    }
    report["report_sha256"] = hashlib.sha256(
        canonical_json(report).encode("utf-8")).hexdigest()
    return report
