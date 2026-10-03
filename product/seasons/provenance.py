"""request_provenance(trace_id, depth) — the facade the consumer asked
for, so they never have to know mneme's internals.

trace_id resolves to one anchor:
    a decision_id    ("dec-0003" or whatever the product used)
    a receipt_sha256 (from recall_receipts)
    a memory_id      ("mem-0007")

depth controls how much evidence gets expanded — bounded, never the
whole graph unprompted:

    summary        what/who served-or-acted; no chains, no graph
    direct         + the relevant custody chain events (seq, type,
                   actor — payloads withheld) and decision links
    impact         + blast radius per involved memory (impact())
    counterfactual + per involved memory, the excisable state
                   transitions — the (memory_id, seq) targets a
                   caller can hand to what_if_transition / decision_what_if.
                   Does NOT run a replay: expansion is evidence
                   projection, not simulation.

The projection is a deterministic read over sealed evidence — no new
truth gets created here, and the caller gets projection_sha256 so the
answer itself is addressable.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from mneme import causality
from mneme.canonical import canonical_json

DEPTHS = ("summary", "direct", "impact", "counterfactual")

_STATE_EVENTS = {"REINFORCED", "STATE_CHANGED", "TAINT_FLAGGED",
                 "QUARANTINED", "REHABILITATED", "SUPERSEDED"}


def _resolve(cur, trace_id: str) -> dict[str, Any]:
    cur.execute(
        "SELECT decision_id, receipt_sha256, used_json, policy_version,"
        " actor_id, reason, created_at FROM decisions"
        " WHERE decision_id = ?", (trace_id,))
    if r := cur.fetchone():
        return {"kind": "decision", "decision_id": r[0],
                "receipt_sha256": r[1],
                "used": sorted(json.loads(r[2])["used"]),
                "policy_version": r[3], "actor_id": r[4],
                "reason": r[5], "created_at": r[6]}
    cur.execute(
        "SELECT receipt_sha256, served_json, top_k, hops, as_of,"
        " custody_override_json FROM recall_receipts"
        " WHERE receipt_sha256 = ?", (trace_id,))
    if r := cur.fetchone():
        return {"kind": "receipt", "receipt_sha256": r[0],
                "served": json.loads(r[1])["served"], "top_k": r[2],
                "hops": r[3], "as_of": r[4],
                "counterfactual": bool(json.loads(r[5])["override"])}
    cur.execute(
        "SELECT memory_id, custody_status, field_state, confidence,"
        " superseded_by FROM memories WHERE memory_id = ?", (trace_id,))
    if r := cur.fetchone():
        ref = {"kind": "memory", "memory_id": r[0],
               "custody_status": r[1], "field_state": r[2],
               "confidence": r[3], "superseded_by": r[4]}
        cur.execute(
            "SELECT payload_json FROM custody_chain WHERE memory_id = ?"
            " AND seq = 0", (trace_id,))
        birth = cur.fetchone()
        if birth:
            ref["supersedes"] = json.loads(birth[0]).get("supersedes")
        return ref
    raise ValueError(f"Unresolvable trace_id {trace_id!r} — not a "
                     "decision, receipt, or memory on record.")


def _memories_of(ref: dict[str, Any]) -> list[str]:
    if ref["kind"] == "memory":
        return [ref["memory_id"]]
    return ref["used"] if ref["kind"] == "decision" else ref["served"]


def _chain_events(cur, memory_id: str) -> list[dict[str, Any]]:
    cur.execute(
        "SELECT seq, event_type, actor_id, created_at FROM custody_chain"
        " WHERE memory_id = ? ORDER BY seq", (memory_id,))
    return [{"seq": s, "event_type": t, "actor_id": a, "created_at": c}
            for s, t, a, c in cur.fetchall()]


def _decisions_using(cur, memory_id: str) -> list[str]:
    cur.execute(
        "SELECT payload_json FROM custody_chain WHERE memory_id = ?"
        " AND event_type = 'DECISION_USED_MEMORY' ORDER BY seq",
        (memory_id,))
    out = []
    for (p,) in cur.fetchall():
        out.append(json.loads(p)["decision_id"])
    return out


def request_provenance(cur, *, trace_id: str,
                       depth: str = "summary") -> dict[str, Any]:
    if depth not in DEPTHS:
        raise ValueError(f"depth must be one of {DEPTHS}, got {depth!r}")
    ref = _resolve(cur, trace_id)
    mems = _memories_of(ref)
    proj: dict[str, Any] = {"trace_id": trace_id, "depth": depth,
                            "anchor": ref, "memories": mems}

    if depth == "summary":
        pass
    else:
        proj["chains"] = {m: _chain_events(cur, m) for m in mems}
        proj["decisions_using"] = {m: _decisions_using(cur, m)
                                   for m in mems}
    if depth in ("impact", "counterfactual"):
        proj["impact"] = {}
        for m in mems:
            rep = causality.impact(cur, memory_id=m)
            proj["impact"][m] = {
                "direct_receipts": list(rep.direct_receipts),
                "direct_decisions": list(rep.direct_decisions),
                "impact_sha256": rep.impact_sha256}
    if depth == "counterfactual":
        proj["excisable"] = {
            m: [{"seq": e["seq"], "event_type": e["event_type"]}
                for e in proj["chains"][m]
                if e["event_type"] in _STATE_EVENTS]
            for m in mems}
        proj["note"] = ("excise targets only — run what_if_transition "
                        "or decision_what_if to actually replay; v1 "
                        "scope is one event on one chain.")

    proj["projection_sha256"] = hashlib.sha256(
        canonical_json(proj).encode("utf-8")).hexdigest()
    return proj
