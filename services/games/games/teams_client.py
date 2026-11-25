"""HTTP client for the Teams service seam.

Replaces the in-process teams.api.get_team_summary from Assignment 1.
"""
from __future__ import annotations

import os

import requests

TEAMS_UNAVAILABLE_BODY = {
    "error": "teams_unavailable",
    "message": "Teams service is unavailable. Try again.",
}


class TeamsUnavailable(Exception):
    """Teams timed out, returned 5xx, or could not be reached."""


def _teams_url() -> str:
    return os.environ.get("TEAMS_URL", "http://teams:8000").rstrip("/")


def _timeout() -> float:
    return float(os.environ.get("TEAMS_TIMEOUT_S", "2"))


def get_team_summary(team_id: int):
    """Public facts about one team, or None if it does not exist (404).

    Raises TeamsUnavailable on timeout, connection error, or 5xx.
    """
    url = f"{_teams_url()}/api/teams/{team_id}"
    try:
        response = requests.get(url, timeout=_timeout())
    except requests.RequestException as exc:
        raise TeamsUnavailable(str(exc)) from exc

    if response.status_code == 404:
        return None
    if response.status_code >= 500:
        raise TeamsUnavailable(f"Teams returned {response.status_code}")
    if response.status_code != 200:
        # Unexpected 4xx other than 404 — treat as missing rather than hanging.
        return None

    data = response.json()
    return {
        "id": data["id"],
        "name": data["name"],
        "format": data["format"],
        "player_count": data["player_count"],
    }
