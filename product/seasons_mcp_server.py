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
    db_path=os.environ.get("RTS_DB_PATH", "seasons.db"))


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
def export_bundle() -> dict:
    """Sealed evidence bundle for offline verification (B0-B9)."""
    return {"bundle_json": A.export_bundle()}


if __name__ == "__main__":
    mcp.run()
