"""Games domain: SQL for the courts and challenges tables."""
import sqlite3


# --- Courts -------------------------------------------------------------------

def create_court(conn, court, proposed_by_team_id):
    """Insert a court. Returns its new id, or None if the address is already listed."""
    try:
        cur = conn.execute(
            """INSERT INTO courts (name, address, maps_url, proposed_by_team_id)
               VALUES (?, ?, ?, ?)""",
            (court["name"], court["address"], court["maps_url"], proposed_by_team_id),
        )
    except sqlite3.IntegrityError:
        return None
    conn.commit()
    return cur.lastrowid


def get_court(conn, court_id):
    return conn.execute("SELECT * FROM courts WHERE id = ?", (court_id,)).fetchone()


def list_courts(conn):
    return conn.execute("SELECT * FROM courts ORDER BY COALESCE(name, address)").fetchall()


# --- Challenges ---------------------------------------------------------------

def create_challenge(conn, challenge):
    cur = conn.execute(
        """INSERT INTO challenges
           (challenger_team_id, opponent_team_id, court_id, start_time, format)
           VALUES (:challenger_team_id, :opponent_team_id, :court_id, :start_time, :format)""",
        challenge,
    )
    conn.commit()
    return cur.lastrowid


def get_challenge(conn, challenge_id):
    return conn.execute("SELECT * FROM challenges WHERE id = ?", (challenge_id,)).fetchone()


def set_status(conn, challenge_id, status):
    conn.execute(
        "UPDATE challenges SET status = ?, responded_at = datetime('now') WHERE id = ?",
        (status, challenge_id),
    )
    conn.commit()


def list_challenges_for_team(conn, team_id):
    """Every challenge a team sent or received, soonest game first."""
    return conn.execute(
        """SELECT * FROM challenges
           WHERE challenger_team_id = ? OR opponent_team_id = ?
           ORDER BY start_time""",
        (team_id, team_id),
    ).fetchall()


def list_accepted(conn):
    """All agreed games, used for the clash check and the home page."""
    return conn.execute(
        "SELECT * FROM challenges WHERE status = 'accepted' ORDER BY start_time"
    ).fetchall()
