"""Bearer-token auth shared with the Teams service.

Teams issues a timed token with URLSafeTimedSerializer(SECRET_KEY).dumps({
    "team_id": int,
    "team_name": str,
    "format": str,
    "player_count": int,
}). Games only loads that payload — it does not issue tokens.
"""
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# Default max age matches a long captain session (7 days).
DEFAULT_MAX_AGE = 60 * 60 * 24 * 7


def team_from_token(token, secret_key, max_age=DEFAULT_MAX_AGE):
    """Return the team payload dict, or None if the token is missing/invalid/expired."""
    if not token or not secret_key:
        return None
    serializer = URLSafeTimedSerializer(secret_key)
    try:
        data = serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    required = ("team_id", "team_name", "format", "player_count")
    if any(key not in data for key in required):
        return None
    return data
