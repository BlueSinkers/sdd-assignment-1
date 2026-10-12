"""SQLite connection and schema setup.

The database file lives at $DATA_DIR/hoops.db. DATA_DIR defaults to ./data so
the app runs on a laptop with no setup; the container sets it to /data, which
is a mounted volume.

Each domain owns its own tables. This module only runs their schema scripts.
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

# Games domain. Courts proposed by teams, and challenges between teams.
# Team ids are stored as plain integers with no FOREIGN KEY to teams: the two
# domains must be able to live in separate databases in Assignment 2.
GAMES_SCHEMA = """
CREATE TABLE IF NOT EXISTS courts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT,
    address              TEXT    NOT NULL UNIQUE,
    maps_url             TEXT,
    proposed_by_team_id  INTEGER NOT NULL,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS challenges (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    challenger_team_id  INTEGER NOT NULL,
    opponent_team_id    INTEGER NOT NULL,
    court_id            INTEGER NOT NULL REFERENCES courts(id),
    start_time          TEXT    NOT NULL,
    format              TEXT    NOT NULL CHECK (format IN ('3v3', '5v5')),
    status              TEXT    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled')),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    responded_at        TEXT
);

-- How many of a team's players actually showed up to an agreed game.
-- One row per team per game; recording again replaces the number.
CREATE TABLE IF NOT EXISTS attendance (
    challenge_id      INTEGER NOT NULL REFERENCES challenges(id),
    team_id           INTEGER NOT NULL,
    players_attended  INTEGER NOT NULL CHECK (players_attended >= 0),
    recorded_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (challenge_id, team_id)
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
        conn.executescript(GAMES_SCHEMA)
        conn.commit()
    finally:
        conn.close()
