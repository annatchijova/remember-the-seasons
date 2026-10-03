"""Vault layer — the PKM surface over the forensic field.

What Obsidian gives you: notes, [[wikilinks]], a graph.
What this adds: the same, except every note is a custody-chained
memory, every wikilink is a RESONANT edge that actually changes what
the agent recalls (resonant boost, not a visual graph), an "edit" is a
supersession with provable lineage — and you can replay, verify, and
excise any of it.

    import_vault(cur, path)     .md files -> memories, [[links]] -> RESONANT edges
    link(cur, a, b)             explicit RESONANT edge (auto=0)
    update(cur, old_id, text)   supersession — new memory, named lineage

Honest gap: mneme's custody vocabulary has no link event type (schema
intends "custody events on BOTH ends" for link changes, but the fixed
event set doesn't include one). Explicit links are written with
auto=0 and noted here; they affect recall semantics but are not yet
custody-evidenced the way contradiction links are.
"""

from __future__ import annotations

import os
import re
from typing import Any

from mneme import authority, custody, field

from . import actors, embed as _embed

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _note_name(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Strip Obsidian YAML frontmatter; return (meta, body).
    Stdlib-only minimal parse: 'key: value' and 'key: [a, b]' lines —
    enough for tags/title, not a YAML engine."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict[str, Any] = {}
    for ln in m.group(1).splitlines():
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        meta[k.strip()] = v
    return meta, text[m.end():]


def import_vault(cur, path: str, *, actor_id: str = actors.AGENT
                 ) -> dict[str, Any]:
    """Import an Obsidian-style vault: every .md becomes a memory,
    every [[wikilink]] becomes a RESONANT cell_link (directional,
    file -> target). Frontmatter 'tags:' become topics; 'title:'
    overrides the filename as the note name."""
    files = []
    for root, _, names in os.walk(path):
        for n in sorted(names):
            if n.endswith(".md"):
                files.append(os.path.join(root, n))
    if not files:
        raise ValueError(f"no .md files under {path!r}")

    name_to_id: dict[str, str] = {}
    pending: list[tuple[str, list[str]]] = []
    for f in files:
        raw = open(f, encoding="utf-8").read()
        meta, text = _frontmatter(raw)
        name = str(meta.get("title") or _note_name(f))
        body = text.strip()
        qemb, prov = _embed.embed_with_provenance(body)
        mid = field.store(
            cur,
            memory_id=f"note-{len(name_to_id):04d}",
            content=body,
            embedding=qemb,
            embedding_model=_embed.model_name(),
            embedding_provenance=prov,
            actor_id=actor_id,
            reason=f"vault import: {name}",
            topic=name).memory_id
        name_to_id[name] = mid
        pending.append((mid, WIKILINK_RE.findall(body)))

    n_links = 0
    for mid, targets in pending:
        for t in targets:
            t = t.strip()
            if t in name_to_id and name_to_id[t] != mid:
                link(cur, mid, name_to_id[t])
                n_links += 1
    return {"imported": len(files), "links": n_links,
            "name_to_id": name_to_id}


def link(cur, from_id: str, to_id: str,
         link_type: str = "RESONANT",
         actor_id: str = actors.AGENT) -> None:
    """Explicit link between two memories. RESONANT amplifies the
    target in recall (resonant boost); INHIBITORY silences it (the
    rescue rule still applies). See module docstring for the
    custody-event gap."""
    if link_type not in ("RESONANT", "INHIBITORY"):
        raise ValueError(f"link_type must be RESONANT|INHIBITORY, "
                         f"got {link_type!r}")
    if from_id == to_id:
        raise ValueError("self-links are refused — a memory may not "
                         "boost itself.")
    cur.execute("SELECT 1 FROM memories WHERE memory_id IN (?, ?)",
                (from_id, to_id))
    if len(cur.fetchall()) != 2:
        raise ValueError("both link endpoints must exist")
    cur.execute(
        "INSERT OR IGNORE INTO cell_links "
        "(from_id, to_id, link_type, auto, created_at) "
        "VALUES (?, ?, ?, 0, ?)",
        (from_id, to_id, link_type, custody.now_ts()))


def update(cur, old_memory_id: str, new_content: str,
           *, actor_id: str = actors.AGENT,
           reason: str | None = None) -> str:
    """An 'edit' is a supersession: NEW memory names its predecessor,
    the predecessor gains SUPERSEDED_BY — lineage, not overwrite.
    The old note stays visible as evidence (M4), invisible to recall."""
    qemb, prov = _embed.embed_with_provenance(new_content)
    mid = field.supersede(
        cur,
        old_memory_id=old_memory_id,
        memory_id=_next_id(cur),
        content=new_content,
        embedding=qemb,
        embedding_model=_embed.model_name(),
        embedding_provenance=prov,
        actor_id=actor_id,
        reason=reason or f"update of {old_memory_id}").memory_id
    return mid


def forget(cur, memory_id: str, *, actor_id: str = actors.AGENT,
           reason: str = "deliberately forgotten") -> None:
    """Deliberate forgetting: an audited STATE_CHANGED to FORGOTTEN —
    invisible to recall, evidence preserved (M4), revivable. Rides
    the REINFORCE grant the way automatic promotion does (no dedicated
    FORGET capability exists; named, not hidden)."""
    cur.execute("SELECT field_state FROM memories WHERE memory_id = ?",
                (memory_id,))
    r = cur.fetchone()
    if r is None:
        raise ValueError(f"unknown memory {memory_id!r}")
    ts = custody.now_ts()
    grant = authority.gate(cur, actor_id=actor_id,
                           capability="REINFORCE", at_ts=ts)
    payload = {"from": r[0], "to": "FORGOTTEN"}
    if grant is not None:
        payload["grant_id"] = grant
    custody.append_event(
        cur, memory_id=memory_id, event_type="STATE_CHANGED",
        actor_id=actor_id, reason=reason, payload=payload,
        created_at=ts)
    cur.execute("UPDATE memories SET field_state = 'FORGOTTEN' "
                "WHERE memory_id = ?", (memory_id,))


def revive(cur, memory_id: str, *, actor_id: str = actors.AGENT,
           reason: str = "brought back to the field") -> None:
    """Reverse of forget: audited STATE_CHANGED back to NEUTRAL.
    Confidence is preserved — the memory returns as it was, not at
    full strength."""
    cur.execute("SELECT field_state FROM memories WHERE memory_id = ?",
                (memory_id,))
    r = cur.fetchone()
    if r is None:
        raise ValueError(f"unknown memory {memory_id!r}")
    if r[0] != "FORGOTTEN":
        raise ValueError(f"{memory_id} is {r[0]}, not FORGOTTEN — "
                         "nothing to revive.")
    ts = custody.now_ts()
    grant = authority.gate(cur, actor_id=actor_id,
                           capability="REINFORCE", at_ts=ts)
    payload = {"from": "FORGOTTEN", "to": "NEUTRAL"}
    if grant is not None:
        payload["grant_id"] = grant
    custody.append_event(
        cur, memory_id=memory_id, event_type="STATE_CHANGED",
        actor_id=actor_id, reason=reason, payload=payload,
        created_at=ts)
    cur.execute("UPDATE memories SET field_state = 'NEUTRAL' "
                "WHERE memory_id = ?", (memory_id,))


def backlinks(cur, memory_id: str) -> list[dict[str, Any]]:
    """What links TO this note — Obsidian's key panel, except here
    each inbound edge is also a resonant boost on recall."""
    cur.execute(
        "SELECT l.from_id, l.link_type, l.auto, m.field_state,"
        " m.custody_status FROM cell_links l"
        " JOIN memories m ON m.memory_id = l.from_id"
        " WHERE l.to_id = ? ORDER BY l.from_id", (memory_id,))
    return [{"from": r[0], "link_type": r[1], "auto": bool(r[2]),
             "field_state": r[3], "custody_status": r[4]}
            for r in cur.fetchall()]


def outlinks(cur, memory_id: str) -> list[dict[str, Any]]:
    cur.execute(
        "SELECT l.to_id, l.link_type FROM cell_links l"
        " WHERE l.from_id = ? ORDER BY l.to_id", (memory_id,))
    return [{"to": r[0], "link_type": r[1]} for r in cur.fetchall()]


def _next_id(cur) -> str:
    cur.execute("SELECT COUNT(*) FROM memories")
    return f"mem-{cur.fetchone()[0]:04d}"
