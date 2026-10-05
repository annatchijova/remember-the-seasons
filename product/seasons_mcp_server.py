#!/usr/bin/env python3
"""Seasons MCP server — forensic agent memory as MCP tools.

Exposes the SeasonsAgent loop (remember/ask/season/what_if_transition/
request_provenance) over FastMCP stdio, the same transport model as
mneme, raven-memory, CRONOS and CORVUS. Any MCP-capable agent that
plugs this in gets memory whose answers are sealed, whose history is
replayable, and whose causal leverage is excisable — not memory it
must take on trust.

Run
    python3 seasons_mcp_server.py            # stdio transport

Env
    RTS_DB_PATH      sqlite path (default: seasons.db in cwd)
    RTS_KEY_SEED     Ed25519 seed hex — if set, every write this
                     server authors is signed under the agent's key
                     (attribution; CF1.8-verifiable on export)
    NEBIUS_API_KEY   enables live LLM + embeddings; absent = stub
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from seasons import agent

mcp = FastMCP("remember-the-seasons")
A = agent.SeasonsAgent(
    db_path=os.environ.get("RTS_DB_PATH", "seasons.db"),
    key_seed=os.environ.get("RTS_KEY_SEED"))


@mcp.tool()
def remember(content: str) -> dict:
    """Store a memory. Returns its id — the anchor for provenance."""
    return {"memory_id": A.remember(content)}


@mcp.tool()
def ask(question: str, top_k: int = 5) -> dict:
    """Recall + answer. Returns answer, sealed receipt, served and
    DECLARED-used ids (served != used: only used enters the causal
    record and gets reinforced)."""
    return A.ask(question, top_k=top_k)


@mcp.tool()
def season(question: str, as_of: str, top_k: int = 5) -> dict:
    """Replay the past: same query, reconstructed at as_of from
    truncated custody chains — not a stored snapshot."""
    return A.season(question, as_of=as_of, top_k=top_k)


@mcp.tool()
def what_if_transition(question: str, memory_id: str,
                       excise_seq: int) -> dict:
    """Counterfactual: excise one transition, run the SAME production
    recall inside a savepoint, roll back. Report marked hypothetical —
    it can never pass for real evidence."""
    return A.what_if_transition(question, memory_id,
                                excise_seq=excise_seq)


@mcp.tool()
def request_provenance(trace_id: str, depth: str = "summary") -> dict:
    """Bounded provenance facade. trace_id: decision / receipt /
    memory. depth: summary | direct | impact | counterfactual."""
    return A.request_provenance(trace_id, depth=depth)


@mcp.tool()
def import_vault(path: str) -> dict:
    """Import an Obsidian-style vault: every .md becomes a memory,
    every [[wikilink]] a RESONANT edge that changes recall."""
    return A.import_vault(path)


@mcp.tool()
def update(memory_id: str, new_content: str) -> dict:
    """'Edit' = supersession: new memory names its predecessor; the
    old stays as evidence. Returns the successor id."""
    return {"memory_id": A.update(memory_id, new_content)}


@mcp.tool()
def forget(memory_id: str, reason: str = "deliberately forgotten") -> dict:
    """Audited STATE_CHANGED to FORGOTTEN — leaves recall, not the
    record. Revivable."""
    A.forget(memory_id, reason=reason)
    return {"memory_id": memory_id, "field_state": "FORGOTTEN"}


@mcp.tool()
def revive(memory_id: str) -> dict:
    """Reverse of forget: audited STATE_CHANGED back to NEUTRAL."""
    A.revive(memory_id)
    return {"memory_id": memory_id, "field_state": "NEUTRAL"}


@mcp.tool()
def link(from_id: str, to_id: str, link_type: str = "RESONANT") -> dict:
    """Explicit edge: RESONANT amplifies, INHIBITORY silences."""
    A.link(from_id, to_id, link_type)
    return {"from": from_id, "to": to_id, "link_type": link_type}


@mcp.tool()
def decision_what_if(decision_id: str, memory_id: str,
                     excise_seq: int) -> dict:
    """Does a recorded decision's evidence base survive the excision?
    Reports survived / fallen / evidence_base_intact."""
    return A.decision_what_if(decision_id, memory_id,
                              excise_seq=excise_seq)


@mcp.tool()
def do_transition(memory_id: str, excise_seq: int) -> dict:
    """`do(T_i = ∅)` — the cascade: which downstream receipts diverge,
    which decisions unground, which events on other chains die.
    Sealed, hypothetical, write-nothing."""
    return A.do_transition(memory_id, excise_seq)


@mcp.tool()
def chain(memory_id: str) -> dict:
    """Raw custody chain for a memory — the forensic read."""
    from seasons import trajectory
    rows = trajectory.load_chain(A.cur, memory_id)
    if not rows:
        return {"memory_id": memory_id, "events": [],
                "error": "no such memory"}
    return {"memory_id": memory_id, "events": rows}


@mcp.tool()
def impact(memory_id: str) -> dict:
    """Blast radius: which recalls served it, which decisions used
    it, which derived claims stand on it."""
    rep = A.impact(memory_id)
    return {"memory_id": memory_id,
            "direct_receipts": list(rep.direct_receipts),
            "direct_decisions": list(rep.direct_decisions),
            "derived_memories": list(rep.derived_memories),
            "derived_decisions": list(rep.derived_decisions),
            "possible_memories": list(rep.possible_memories),
            "impact_sha256": rep.impact_sha256}


@mcp.tool()
def field_integrity() -> dict:
    """Audit sweep over the whole field: every sealed reference must
    resolve, every event signature must verify under the actor's
    registered key. A clean field returns empty lists — failures are
    integrity errors, never silently inert."""
    from mneme import custody
    from seasons import trajectory, signing
    dangling = custody.check_dangling_references(A.cur)
    vkeys = {r[0]: r[1] for r in A.cur.execute(
        "SELECT keyid, verify_key_hex FROM actor_keys")}
    hashes = {}
    for mid, in A.cur.execute(
            "SELECT DISTINCT memory_id FROM custody_chain"):
        hashes[mid] = {r["seq"]: r["entry_hash"]
                       for r in trajectory.load_chain(A.cur, mid)}
    bad_sigs = []
    sigged = {(r[0], r[1]) for r in A.cur.execute(
        "SELECT memory_id, seq FROM event_sigs")}
    for mid, seq, keyid, sig in A.cur.execute(
            "SELECT memory_id, seq, keyid, sig FROM event_sigs"):
        eh = hashes.get(mid, {}).get(seq)
        vk = vkeys.get(keyid)
        if eh is None or vk is None:
            bad_sigs.append(f"{mid}#{seq}: unattributable")
            continue
        try:
            signing.VerifyKey(bytes.fromhex(vk)).verify(
                eh.encode("ascii"), bytes.fromhex(sig))
        except Exception:
            bad_sigs.append(f"{mid}#{seq}: invalid signature")
    # and the inverse: an UNSIGNED event by a keyed actor — CF1.8's
    # rule applied to the live field, not only to exports
    keyed_actors = {r[0] for r in A.cur.execute(
        "SELECT DISTINCT actor_id FROM actor_keys")}
    for mid, seqs in hashes.items():
        for r in trajectory.load_chain(A.cur, mid):
            if r["actor_id"] in keyed_actors \
                    and (mid, r["seq"]) not in sigged:
                bad_sigs.append(
                    f"{mid}#{r['seq']}: keyed actor {r['actor_id']} "
                    f"wrote unsigned")
    return {"dangling_references": dangling,
            "bad_signatures": bad_sigs,
            "events_checked": sum(len(c) for c in hashes.values()),
            "sigs_checked": sum(1 for _ in A.cur.execute(
                "SELECT 1 FROM event_sigs")),
            "verdict": "CLEAN" if not dangling and not bad_sigs
            else "INTEGRITY_ERRORS"}


if __name__ == "__main__":
    mcp.run()
