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

from . import embed as _embed

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
                          capability="COUNTERFACTUAL",
                          at_ts=custody.now_ts())

    hits_a, rec_a = field.recall(
        cur, query_embedding=query_embedding, top_k=top_k, hops=hops)
    hits_b, rec_b = _recall_in_world(
        cur, query_embedding, memory_id,
        (cf_status, cf_fstate, cf_conf), top_k, hops)

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


def _replay_minus(chain: list[dict[str, Any]],
                  dead: set[int]) -> tuple[str, str, Fraction]:
    """Replay_excised generalized to a SET of dead events — same
    recompute-never-trust rule, applied to the cascade's
    invalidations, not only the excised event."""
    status, fstate = "CLEAN", "NEUTRAL"
    conf = Fraction(1, 2)
    for ev in chain:
        if ev["seq"] in dead:
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
                    fstate = "REINFORCED"
            elif to is not None:
                fstate = to
    return status, fstate, conf


def _recall_in_world_multi(cur, query_embedding, cf: dict, top_k, hops):
    """Recall against a cf world where MANY memories' rows are
    replaced — the general form of _recall_in_world. Write-nothing."""
    cur.execute("SAVEPOINT trajectory_cf")
    try:
        for mid, (st, fs, cf_conf) in cf.items():
            conf_q = (Decimal(cf_conf.numerator) /
                      Decimal(cf_conf.denominator)).quantize(
                          Decimal("0.0000000001"))
            cur.execute(
                "UPDATE memories SET custody_status = ?, field_state = ?,"
                " confidence = ? WHERE memory_id = ?",
                (st, fs, str(conf_q), mid))
        return field.recall(cur, query_embedding=query_embedding,
                            top_k=top_k, hops=hops)
    finally:
        cur.execute("ROLLBACK TO trajectory_cf")
        cur.execute("RELEASE trajectory_cf")


def do_transition(cur, *, memory_id: str, excise_seq: int,
                  top_k: int = 5, hops: int = field.DEFAULT_HOPS,
                  actor_id: str | None = None) -> dict[str, Any]:
    """`do(T_i = ∅)` — the cascade, per docs/CAUSAL_REWIND.md.

    v1 asks "does one recall change". This asks what the v1 question
    hides: which LATER receipts diverged, which decisions were
    counterfactually ungrounded, and which events on OTHER chains die
    as consequences. Forward pass over the decision timeline:

      excise (mem, seq) at t_i -> for each decision citing a receipt
      after t_i: replay its stored question under the cf world built
      so far -> if its declared used set falls out of cf served, the
      decision is cf-ungrounded and its consequences (DECISION_USED +
      the reinforcement it caused on each used memory) join the dead
      set -> their chains recompute -> the world shifts under the next
      receipt.

    The consequential subset is exactly the replayable subset: a
    receipt stores query_sha256, not the query — but seasons_decisions
    keeps the question, and receipts nobody acted on have no
    downstream effect anyway. Stated, not hidden.

    Output is sealed, hypothetical: true, write-nothing.
    """
    chain = load_chain(cur, memory_id)
    if not chain:
        raise ValueError(f"Unknown memory {memory_id!r}.")
    excised = next((e for e in chain if e["seq"] == excise_seq), None)
    if excised is None:
        raise ValueError(f"{memory_id} has no custody event seq "
                         f"{excise_seq}.")
    if excised["event_type"] == "STORED":
        raise ValueError("Excising STORED means 'never existed' — a "
                         "different counterfactual.")
    t_i = excised["created_at"]

    # dead = the excised event plus every event the cascade kills.
    dead: dict[str, set[int]] = {memory_id: {excise_seq}}
    chains: dict[str, list] = {memory_id: chain}

    def own_consequences(did: str) -> dict[str, set[int]]:
        """Events that are THIS decision's consequences — identified
        structurally by declared causes: anything whose payload's
        causes[] names the decision, plus the legacy pair (DECISION_USED
        naming it + an adjacent REINFORCED with no explicit reference)
        for events written before causal-ontology/v2. A decision's own
        effects never count toward the world it was decided in."""
        out: dict[str, set[int]] = {}
        for mid, ch in chains.items():
            for j, e in enumerate(ch):
                p = json.loads(e["payload_json"])
                caused = any(
                    c.get("kind") == "decision" and c.get("id") == did
                    for c in p.get("causes", []))
                et = e["event_type"]
                if caused or (et == "DECISION_USED_MEMORY"
                              and p.get("decision_id") == did):
                    out.setdefault(mid, set()).add(e["seq"])
                    # legacy adjacency fires only in a fully-legacy
                    # world: the DU itself declares no causes AND the
                    # neighbour has no explicit cause either. With v2
                    # evidence, proximity is never causal — the
                    # DISCORDIA lesson: a clock is not a cause.
                    if (j + 1 < len(ch)
                            and not p.get("causes")
                            and ch[j + 1]["event_type"] == "REINFORCED"
                            and json.loads(
                                ch[j + 1]["payload_json"]).get(
                                    "caused_by_decision_id") is None
                            and not json.loads(
                                ch[j + 1]["payload_json"]).get("causes")):
                        out[mid].add(ch[j + 1]["seq"])
                elif (et == "REINFORCED"
                        and p.get("caused_by_decision_id") == did):
                    out.setdefault(mid, set()).add(e["seq"])
        return out

    def closure(dead_nodes: dict[str, set[int]],
                dead_decisions: set[str]) -> None:
        """causal-ontology/v2 fixpoint: an event dies if ANY declared
        cause names a dead event or a dead decision. Runs to fixpoint —
        a dead promotion kills the events it caused, and so on. This
        replaces per-type kill rules with the declared dependency
        graph."""
        changed = True
        while changed:
            changed = False
            for mid, ch in chains.items():
                for e in ch:
                    if e["seq"] in dead_nodes.get(mid, set()):
                        continue
                    p = json.loads(e["payload_json"])
                    # caused_by_decision_id is the pre-v2 spelling of
                    # a decision-cause; the closure treats both
                    # uniformly.
                    if (p.get("caused_by_decision_id")
                            in dead_decisions
                            and p.get("caused_by_decision_id")
                            is not None):
                        dead_nodes.setdefault(mid, set()).add(
                            e["seq"])
                        changed = True
                        continue
                    for c in p.get("causes", []):
                        if (c.get("kind") == "decision"
                                and c.get("id") in dead_decisions):
                            dead_nodes.setdefault(mid, set()).add(
                                e["seq"])
                            changed = True
                            break
                        if (c.get("kind") == "event"
                                and c.get("seq") in
                                dead_nodes.get(
                                    c.get("memory_id"), set())):
                            dead_nodes.setdefault(mid, set()).add(
                                e["seq"])
                            changed = True
                            break

    def cf_world(as_of: str, exclude: dict[str, set[int]]) -> dict:
        """Recomputed states for chains that LOST events — the
        cascade's exact causal boundary — truncated at `as_of`.
        Chains with no dead events recompute to their actual state
        (up to confidence quantization), so touching them would only
        inject noise.

        Precedence rule: an event belongs to the world at as_of iff
        created_at < as_of — same-timestamp events are conservatively
        treated as concurrent/unknown and EXCLUDED — except that a
        decision's own consequences are excluded structurally too,
        even under timestamp collisions."""
        world = {}
        for mid in set(dead) | set(exclude):
            ch = chains.setdefault(mid, load_chain(cur, mid))
            gone = dead.get(mid, set()) | exclude.get(mid, set())
            prefix = [e for e in ch if e["created_at"] < as_of]
            world[mid] = _replay_minus(prefix, gone)
        return world

    divergent, ungrounded, invalidated, propagation = [], [], [], []
    dead_decisions: set[str] = set()

    cur.execute(
        "SELECT sd.decision_id, sd.question, d.receipt_sha256,"
        " d.used_json, d.created_at FROM seasons_decisions sd"
        " JOIN decisions d ON d.decision_id = sd.decision_id"
        " WHERE d.created_at > ?"
        " ORDER BY d.created_at ASC, d.decision_id ASC", (t_i,))
    for did, question, rsha, used_json, ts_d in cur.fetchall():
        if did in {u["decision_id"] for u in ungrounded}:
            continue
        world = cf_world(ts_d, own_consequences(did))
        qemb = field.quantize_embedding(_embed.embed(question))
        hits_cf, _ = _recall_in_world_multi(cur, qemb, world,
                                          top_k, hops)
        cf_served = {h.memory_id for h in hits_cf}
        used = json.loads(used_json)["used"]
        fallen = sorted(m for m in used if m not in cf_served)
        if not fallen:
            continue
        # The decision's evidence base did not survive: its consequences
        # die — the bilateral DECISION_USED record naming it, and the
        # REINFORCED event each used memory earned from that act (the
        # write path appends it immediately after the DECISION_USED).
        divergent.append(rsha)
        dead_decisions.add(did)
        before = {m: set(s) for m, s in dead.items()}
        for mid in used:                      # chains must be loaded
            chains.setdefault(mid, load_chain(cur, mid))  # BEFORE
        # legacy fallback for pre-v2 events with no causes[]:
        for mid in sorted(used):
            ch = chains[mid]
            for j, ev in enumerate(ch):
                ep = json.loads(ev["payload_json"])
                if (ev["event_type"] == "DECISION_USED_MEMORY" and
                        ep.get("decision_id") == did):
                    dead.setdefault(mid, set()).add(ev["seq"])
                    if (j + 1 < len(ch)
                            and not ep.get("causes")
                            and ch[j + 1]["event_type"] == "REINFORCED"
                            and json.loads(
                                ch[j + 1]["payload_json"]).get(
                                    "caused_by_decision_id") is None
                            and not json.loads(
                                ch[j + 1]["payload_json"]).get(
                                    "causes")):
                        dead[mid].add(ch[j + 1]["seq"])
        # causal-ontology/v2: the closure walks declared causes, not
        # event-type rules — a dead decision kills everything it
        # caused, and a dead event kills whatever it caused, to
        # fixpoint.
        closure(dead, dead_decisions)
        kill = sorted(
            (m, s) for m, ds in dead.items() for s in ds
            if s not in before.get(m, set()))
        kill = [(m, s, next(e["event_type"] for e in chains[m]
                            if e["seq"] == s)) for m, s in kill]
        ungrounded.append({"decision_id": did, "used": used,
                           "fallen": fallen})
        invalidated.extend(kill)
        propagation.append({"decision_id": did,
                            "invalidated": [(m, s) for m, s, _ in kill]})

    final_world = {}
    for mid, dead_seqs in dead.items():
        ch = chains.setdefault(mid, load_chain(cur, mid))
        final_world[mid] = _replay_minus(ch, dead_seqs)
    report = {
        "hypothetical": True,
        "kind": "trajectory_counterfactual/v2_cascade",
        "excised": {"memory_id": memory_id, "seq": excise_seq,
                    "event_type": excised["event_type"],
                    "created_at": t_i},
        "counterfactual_states": {
            m: {"custody_status": s[0], "field_state": s[1],
                "confidence": str(s[2])}
            for m, s in sorted(final_world.items())},
        "divergent_receipts": divergent,
        "ungrounded_decisions": ungrounded,
        "invalidated": invalidated,
        "propagation": propagation,
        "scope_note": "consequential subset = decision-cited receipts;"
                      " reads nobody acted on have no downstream effect",
    }
    report["report_sha256"] = hashlib.sha256(
        canonical_json(report).encode("utf-8")).hexdigest()
    return report


def export_cf_bundle(cur, *, memory_id: str, excise_seq: int,
                     top_k: int = 5, hops: int = field.DEFAULT_HOPS,
                     actor_id: str | None = None) -> dict[str, Any]:
    """A SELF-CONTAINED counterfactual evidence bundle: everything an
    independent verifier needs to recompute do(T_i=0) and reach the
    same cascade — without trusting trajectory.py's account of it.

    Contents per docs/CAUSAL_REWIND.md §5:
      - intervention: (memory_id, seq) — the do()
      - actual-world evidence: memories (content+quantized embedding
        + current row), full custody chains, cell_links, the
        decision-cited receipts (served_json, top_k, hops, protocol)
      - replay inputs: each decision's question AND its quantized
        query embedding — the embedding is an exogenous model output,
        carried as sealed input because a verifier cannot re-derive it
      - the report whose claims the verifier recomputes

    Deliberate: the bundle does not contain mneme code or the cascade
    implementation. The verifier rebuilds a world from this evidence
    and re-derives the cascade; divergence is detected, not asserted.
    """
    report = do_transition(cur, memory_id=memory_id,
                           excise_seq=excise_seq, top_k=top_k,
                           hops=hops, actor_id=actor_id)

    cur.execute("SELECT memory_id, content, content_sha256,"
                " embedding_json, embedding_model, topic, created_by,"
                " created_at, field_state, custody_status, confidence,"
                " superseded_by FROM memories ORDER BY memory_id")
    mems = [dict(zip(["memory_id", "content", "content_sha256",
                      "embedding_json", "embedding_model", "topic",
                      "created_by", "created_at", "field_state",
                      "custody_status", "confidence",
                      "superseded_by"], r))
            for r in cur.fetchall()]

    cur.execute("SELECT actor_id, display_name, kind, status,"
                " created_at FROM actors")
    actor_rows = [dict(zip(["actor_id", "display_name", "kind",
                            "status", "created_at"], r))
                  for r in cur.fetchall()]

    chains = {}
    for m in mems:
        chains[m["memory_id"]] = load_chain(cur, m["memory_id"])

    cur.execute("SELECT from_id, to_id, link_type, auto FROM cell_links")
    links = [dict(zip(["from_id", "to_id", "link_type", "auto"], r))
             for r in cur.fetchall()]

    cur.execute(
        "SELECT sd.decision_id, sd.question, d.receipt_sha256,"
        " d.used_json, d.created_at FROM seasons_decisions sd"
        " JOIN decisions d ON d.decision_id = sd.decision_id"
        " ORDER BY d.created_at ASC")
    decisions = []
    for did, question, rsha, used_json, ts in cur.fetchall():
        qemb = field.quantize_embedding(_embed.embed(question))
        decisions.append({
            "decision_id": did, "question": question,
            "receipt_sha256": rsha,
            "used": json.loads(used_json)["used"],
            "created_at": ts,
            "query_embedding": json.loads(
                field.embedding_to_json(qemb))["v"],
            "query_embedding_sha256": field.embedding_sha256(qemb)})

    cur.execute(
        "SELECT receipt_sha256, query_sha256, served_json, top_k,"
        " hops, ranking_protocol FROM recall_receipts")
    receipts = {r[0]: {"query_sha256": r[1],
                       "served": json.loads(r[2])["served"],
                       "top_k": r[3], "hops": r[4],
                       "ranking_protocol": r[5]}
                for r in cur.fetchall()}

    # Frozen semantics: the bundle declares exactly which protocol
    # versions the result was computed under — mneme's own version
    # registry plus the cf layers. A verifier that does not know these
    # semantics must refuse, not silently apply new rules to old
    # evidence.
    from mneme import protocol
    semantics = {
        "bundle_protocol": "mneme-cf-bundle/v1",
        "causal_rewind_protocol": "cf-cascade/v2",
        **protocol.CURRENT_PROTOCOLS,
    }

    bundle = {
        "protocol": "mneme-cf-bundle/v1",
        "semantics": semantics,
        "intervention": {"memory_id": memory_id, "seq": excise_seq},
        "report": report,
        "evidence": {
            "memories": mems, "actors": actor_rows, "chains": chains,
            "cell_links": links, "decisions": decisions,
            "receipts": receipts},
    }
    bundle["bundle_sha256"] = hashlib.sha256(
        canonical_json(bundle).encode("utf-8")).hexdigest()
    return bundle


def export_cf_bundle_signed(cur, *, memory_id: str, excise_seq: int,
                            sign_seed_hex: str, keyid: str = "",
                            top_k: int = 5) -> dict[str, Any]:
    """The bundle as a signed DSSE envelope — the trust anchor that
    makes full-history recommit detectable: an attacker can recompute
    every hash, but not a signature under a key they don't hold."""
    from . import signing
    bundle = export_cf_bundle(cur, memory_id=memory_id,
                              excise_seq=excise_seq, top_k=top_k)
    payload = canonical_json(bundle).encode("utf-8")
    return signing.sign_envelope(payload, sign_seed_hex, keyid=keyid)


def _recall_in_world(cur, query_embedding, memory_id, cf_state,
                     top_k, hops):
    """Run the UNMODIFIED production recall inside a savepoint with
    one memory's row replaced by counterfactual state; roll back."""
    cf_status, cf_fstate, cf_conf = cf_state
    cur.execute("SAVEPOINT trajectory_cf")
    try:
        conf_q = (Decimal(cf_conf.numerator) /
                  Decimal(cf_conf.denominator)).quantize(
                      Decimal("0.0000000001"))
        cur.execute(
            "UPDATE memories SET custody_status = ?, field_state = ?,"
            " confidence = ? WHERE memory_id = ?",
            (cf_status, cf_fstate, str(conf_q), memory_id))
        return field.recall(cur, query_embedding=query_embedding,
                            top_k=top_k, hops=hops)
    finally:
        cur.execute("ROLLBACK TO trajectory_cf")
        cur.execute("RELEASE trajectory_cf")


def decision_what_if(cur, *, decision_id: str, memory_id: str,
                     excise_seq: int, top_k: int = 5,
                     actor_id: str | None = None) -> dict[str, Any]:
    """Would this decision's evidence base survive without that
    transition?

    Replays the question that fed the decision in the world where
    (memory_id, excise_seq) never happened, then asks the only thing
    that matters: does the recall still serve the memories the decision
    actually used? If not, the decision depended on that transition —
    and the sealed report says which ones fell out.
    """
    row = cur.execute(
        "SELECT question FROM seasons_decisions WHERE decision_id = ?",
        (decision_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown decision {decision_id!r} — seasons "
                         "stores the question so the recall can be "
                         "replayed; a receipt alone cannot.")
    question = row[0]

    cur.execute(
        "SELECT used_json FROM decisions WHERE decision_id = ?",
        (decision_id,))
    drow = cur.fetchone()
    if drow is None:
        raise ValueError(f"Decision {decision_id!r} not in the causal "
                         "record — cannot replay its evidence base.")
    used = sorted(json.loads(drow[0])["used"])

    qemb = field.quantize_embedding(_embed.embed(question))
    rep = what_if_transition(
        cur, query_embedding=qemb, memory_id=memory_id,
        excise_seq=excise_seq, top_k=top_k, actor_id=actor_id)

    cf_served = set(rep["counterfactual"]["served"])
    still_served = sorted(m for m in used if m in cf_served)
    fallen = sorted(m for m in used if m not in cf_served)
    rep["decision"] = {
        "decision_id": decision_id,
        "used_memory_ids": used,
        "survived": still_served,
        "fallen": fallen,
        "evidence_base_intact": not fallen,
    }
    rep["report_sha256"] = hashlib.sha256(
        canonical_json(
            {k: v for k, v in rep.items() if k != "report_sha256"}
        ).encode("utf-8")).hexdigest()
    return rep
