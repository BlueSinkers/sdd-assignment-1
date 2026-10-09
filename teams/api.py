"""Teams domain: the only functions other domains are allowed to call.

This is the seam. The Games domain never reads the teams table itself; it asks
here and gets back a small plain dict. In Assignment 2, when Teams becomes its
own service, these functions become HTTP calls and Games does not change.
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
