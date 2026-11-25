"""Signed bearer tokens for captain sessions.

Payload shape (must match Games auth.team_from_token):
    team_id, team_name, format, player_count

SECRET_KEY must be the same in Teams and Games.
"""
import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

DEFAULT_MAX_AGE = 60 * 60 * 24 * 7


def _serializer():
    secret = os.environ.get("SECRET_KEY", "dev-only-not-secret")
    return URLSafeTimedSerializer(secret)


def issue_token(team_dict):
    """Sign a token from a team dict (uses id/name or team_id/team_name)."""
    team_id = team_dict.get("team_id", team_dict.get("id"))
    team_name = team_dict.get("team_name", team_dict.get("name"))
    payload = {
        "team_id": team_id,
        "team_name": team_name,
        "format": team_dict.get("format"),
        "player_count": team_dict.get("player_count"),
    }
    return _serializer().dumps(payload)


def team_from_token(token, max_age=DEFAULT_MAX_AGE):
    """Return the token payload, or None if invalid/expired."""
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    required = ("team_id", "team_name", "format", "player_count")
    if any(key not in data for key in required):
        return None
    return data
