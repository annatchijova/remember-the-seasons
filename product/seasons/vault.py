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

from mneme import custody, field

from . import actors, embed as _embed

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def _note_name(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def import_vault(cur, path: str, *, actor_id: str = actors.AGENT
                 ) -> dict[str, Any]:
    """Import an Obsidian-style vault: every .md becomes a memory,
    every [[wikilink]] becomes a RESONANT cell_link (directional,
    file -> target). Returns the name->id map and link count."""
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
        text = open(f, encoding="utf-8").read()
        name = _note_name(f)
        mid = field.store(
            cur,
            memory_id=f"note-{len(name_to_id):04d}",
            content=text,
            embedding=field.quantize_embedding(_embed.embed(text)),
            embedding_model=_embed.model_name(),
            actor_id=actor_id,
            reason=f"vault import: {name}",
            topic=name).memory_id
        name_to_id[name] = mid
        pending.append((mid, WIKILINK_RE.findall(text)))

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
    emb = field.quantize_embedding(_embed.embed(new_content))
    mid = field.supersede(
        cur,
        old_memory_id=old_memory_id,
        memory_id=_next_id(cur),
        content=new_content,
        embedding=emb,
        embedding_model=_embed.model_name(),
        actor_id=actor_id,
        reason=reason or f"update of {old_memory_id}").memory_id
    return mid


def _next_id(cur) -> str:
    cur.execute("SELECT COUNT(*) FROM memories")
    return f"mem-{cur.fetchone()[0]:04d}"
