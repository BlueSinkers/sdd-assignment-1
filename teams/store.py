"""Teams domain: SQL for the teams table. Nothing else reads this table."""
import sqlite3


def create_team(conn, team):
    """Insert a team. Returns its new id, or None if the name is taken."""
    try:
        cur = conn.execute(
            """INSERT INTO teams
               (name, password_hash, captain_name, format, player_count, skill_level, district)
               VALUES (:name, :password_hash, :captain_name, :format, :player_count, :skill_level, :district)""",
            team,
        )
    except sqlite3.IntegrityError:
        return None
    conn.commit()
    return cur.lastrowid


def get_team_by_name(conn, name):
    return conn.execute("SELECT * FROM teams WHERE name = ?", (name,)).fetchone()


def get_team(conn, team_id):
    return conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()


def list_teams(conn):
    # Leaves out password_hash: the public list never needs it.
    return conn.execute(
        """SELECT id, name, captain_name, format, player_count, skill_level, district
           FROM teams ORDER BY name"""
    ).fetchall()
