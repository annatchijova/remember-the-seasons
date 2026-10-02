"""Open/create a Seasons field database (SQLite + mneme schema)."""

from __future__ import annotations

import os
import sqlite3

SCHEMA = os.path.join(os.path.dirname(__file__), "..", "mneme", "schema.sql")


def open_db(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    with open(os.path.abspath(SCHEMA)) as f:
        conn.executescript(f.read())
    return conn
