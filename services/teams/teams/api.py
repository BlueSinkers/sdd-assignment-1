"""Teams domain: the only functions other domains are allowed to call.

This is the seam. The Games service never reads the teams table; it calls
GET /api/teams/<id> (teams/routes.py), which returns what this function returns.
"""
from teams import store


def get_team_summary(conn, team_id):
    """Public facts about one team, or None if it does not exist."""
    team = store.get_team(conn, team_id)
    if team is None:
        return None
    return {
        "id": team["id"],
        "name": team["name"],
        "format": team["format"],
        "player_count": team["player_count"],
    }
