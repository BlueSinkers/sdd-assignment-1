"""Asks the Teams service about a team, over HTTP.

This is the seam (ADR 2). The Games service has no access to the teams table;
it calls GET {TEAMS_URL}/api/teams/<id> and gets back the same small dict that
teams.api.get_team_summary returned inside the monolith.
"""
import os

import requests

TEAMS_URL = os.environ.get("TEAMS_URL", "http://localhost:8001")
TIMEOUT_S = float(os.environ.get("TEAMS_TIMEOUT_S", "2"))


class TeamsUnavailable(Exception):
    """The Teams service did not answer in time, or answered with an error."""


def get_team_summary(team_id):
    """Public facts about one team, or None if Teams says it does not exist.

    Raises TeamsUnavailable if Teams is down, slow or broken, so the caller
    can decide what the user sees instead of hanging or crashing.
    """
    try:
        response = requests.get(f"{TEAMS_URL}/api/teams/{team_id}", timeout=TIMEOUT_S)
    except requests.RequestException as error:
        raise TeamsUnavailable() from error
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise TeamsUnavailable()
    return response.json()
