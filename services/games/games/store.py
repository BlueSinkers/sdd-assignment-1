"""Games domain: SQL Server access for courts, challenges, and attendance."""
from __future__ import annotations

import pymssql


def _row(row):
    """Return a plain dict (pymssql as_dict already does; normalize None)."""
    return None if row is None else dict(row)


def _rows(rows):
    return [dict(r) for r in rows]


# --- Courts -------------------------------------------------------------------

def create_court(conn, court, proposed_by_team_id):
    """Insert a court. Returns its new id, or None if the address is already listed."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO courts (name, address, maps_url, proposed_by_team_id)
                OUTPUT INSERTED.id
                VALUES (%s, %s, %s, %s)
                """,
                (court["name"], court["address"], court["maps_url"], proposed_by_team_id),
            )
            row = cur.fetchone()
        conn.commit()
        return int(row["id"])
    except pymssql.IntegrityError:
        conn.rollback()
        return None


def get_court(conn, court_id):
    if court_id is None:
        return None
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM courts WHERE id = %s", (court_id,))
        return _row(cur.fetchone())


def list_courts(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM courts ORDER BY COALESCE(name, address)"
        )
        return _rows(cur.fetchall())


# --- Challenges ---------------------------------------------------------------

def create_challenge(conn, challenge):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO challenges
                (challenger_team_id, opponent_team_id, court_id, start_time, format, status, note)
            OUTPUT INSERTED.id
            VALUES (%s, %s, %s, %s, %s, 'pending', %s)
            """,
            (
                challenge["challenger_team_id"],
                challenge["opponent_team_id"],
                challenge["court_id"],
                challenge["start_time"],
                challenge["format"],
                challenge.get("note"),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return int(row["id"])


def get_challenge(conn, challenge_id):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM challenges WHERE id = %s", (challenge_id,))
        return _row(cur.fetchone())


def set_status(conn, challenge_id, status):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE challenges
            SET status = %s, responded_at = SYSUTCDATETIME()
            WHERE id = %s
            """,
            (status, challenge_id),
        )
    conn.commit()


def list_challenges_for_team(conn, team_id):
    """Every challenge a team sent or received, soonest game first."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM challenges
            WHERE challenger_team_id = %s OR opponent_team_id = %s
            ORDER BY start_time
            """,
            (team_id, team_id),
        )
        return _rows(cur.fetchall())


def list_accepted(conn):
    """All agreed games, used for the clash check and upcoming list."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM challenges WHERE status = 'accepted' ORDER BY start_time"
        )
        return _rows(cur.fetchall())


def list_all_challenges(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM challenges")
        return _rows(cur.fetchall())


# --- Attendance ---------------------------------------------------------------

def record_attendance(conn, record):
    """Save a team's turnout for a game, replacing any earlier number (MERGE)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            MERGE attendance AS target
            USING (SELECT %s AS challenge_id, %s AS team_id, %s AS players_attended) AS source
            ON target.challenge_id = source.challenge_id AND target.team_id = source.team_id
            WHEN MATCHED THEN
                UPDATE SET
                    players_attended = source.players_attended,
                    recorded_at = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN
                INSERT (challenge_id, team_id, players_attended)
                VALUES (source.challenge_id, source.team_id, source.players_attended);
            """,
            (record["challenge_id"], record["team_id"], record["players_attended"]),
        )
    conn.commit()


def list_attendance(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM attendance")
        return _rows(cur.fetchall())


def attendance_for_team(conn, team_id):
    """{challenge_id: players_attended} for one team."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT challenge_id, players_attended FROM attendance WHERE team_id = %s",
            (team_id,),
        )
        rows = cur.fetchall()
    return {r["challenge_id"]: r["players_attended"] for r in rows}
