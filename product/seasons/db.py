"""Open/create a Seasons field database (SQLite + mneme schema)."""

from __future__ import annotations

import os
import sqlite3

SCHEMA = os.path.join(os.path.dirname(__file__), "..", "mneme", "schema.sql")


def open_db(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    with open(os.path.abspath(SCHEMA)) as f:
        conn.executescript(f.read())
    # Product-owned tables — outside mneme's schema and its verifier
    # (which reads only the declared tables; these are ignored, not
    # hidden). seasons_decisions binds a decision to the QUESTION text
    # so its recall can be replayed counterfactually — the receipt
    # itself seals only query_sha256, which cannot be replayed.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS seasons_decisions ("
        "  decision_id   TEXT PRIMARY KEY,"
        "  question      TEXT NOT NULL,"
        "  created_at    TEXT NOT NULL"
        ")")
    return conn
