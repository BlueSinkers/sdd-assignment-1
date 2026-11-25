"""Teams domain: SQL for the teams table. Nothing else reads this table."""
import pymssql

_PUBLIC_COLUMNS = (
    "id, name, captain_name, format, player_count, skill_level, district, badge_color"
)


def create_team(conn, team):
    """Insert a team. Returns its new id, or None if the name is taken."""
    cur = conn.cursor(as_dict=True)
    try:
        cur.execute(
            """
            INSERT INTO teams
                (name, password_hash, captain_name, format, player_count, skill_level, district)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                team["name"],
                team["password_hash"],
                team["captain_name"],
                team["format"],
                team["player_count"],
                team["skill_level"],
                team.get("district"),
            ),
        )
        cur.execute("SELECT SCOPE_IDENTITY() AS id")
        row = cur.fetchone()
        conn.commit()
        return int(row["id"]) if row and row.get("id") is not None else None
    except pymssql.IntegrityError:
        conn.rollback()
        return None


def get_team_by_name(conn, name):
    cur = conn.cursor(as_dict=True)
    cur.execute("SELECT * FROM teams WHERE name = %s", (name,))
    return cur.fetchone()


def get_team(conn, team_id):
    cur = conn.cursor(as_dict=True)
    cur.execute("SELECT * FROM teams WHERE id = %s", (team_id,))
    return cur.fetchone()


def list_teams(conn):
    """Public list of teams (no password_hash)."""
    cur = conn.cursor(as_dict=True)
    cur.execute(
        f"""
        SELECT {_PUBLIC_COLUMNS}
        FROM teams
        ORDER BY name
        """
    )
    return list(cur.fetchall())


def get_team_summary(conn, team_id):
    """Public facts about one team for the Games seam, or None."""
    cur = conn.cursor(as_dict=True)
    cur.execute(
        """
        SELECT id, name, format, player_count
        FROM teams
        WHERE id = %s
        """,
        (team_id,),
    )
    return cur.fetchone()
