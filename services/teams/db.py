"""SQLite connection and schema setup.

The database file lives at $DATA_DIR/hoops.db. DATA_DIR defaults to ./data so
the app runs on a laptop with no setup; the container sets it to /data, which
is a mounted volume.

This is the Teams service, so it only creates the Teams tables. The Games
tables live in the Games service's own database.
Every statement is CREATE ... IF NOT EXISTS, so booting twice changes nothing
and existing data is never dropped.
"""
import os
import sqlite3

from flask import g

DB_FILENAME = "hoops.db"

# Teams domain. Owns everything about a team and its captain's login.
TEAMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    captain_name  TEXT    NOT NULL,
    format        TEXT    NOT NULL CHECK (format IN ('3v3', '5v5')),
    player_count  INTEGER NOT NULL CHECK (player_count > 0),
    skill_level   TEXT    NOT NULL CHECK (skill_level IN ('casual', 'intermediate', 'competitive')),
    district      TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

def get_db_path():
    data_dir = os.environ.get("DATA_DIR", "./data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, DB_FILENAME)


def connect(path=None):
    conn = sqlite3.connect(path or get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_conn():
    """One connection per web request, opened the first time it is needed."""
    if "conn" not in g:
        g.conn = connect()
    return g.conn


def close_conn(exception=None):
    """Called by Flask at the end of every request."""
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


def init_db(path=None):
    conn = connect(path)
    try:
        conn.executescript(TEAMS_SCHEMA)
        conn.commit()
    finally:
        conn.close()
