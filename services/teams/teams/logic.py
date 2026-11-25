"""Teams domain: rules about what makes a valid team.

Plain Python only, no Flask and no SQL, so every rule here can be unit tested
directly. Accepts form-like objects or plain dicts (both expose .get).
"""
from werkzeug.security import check_password_hash, generate_password_hash

# Minimum players a team needs for each format.
FORMATS = {"3v3": 3, "5v5": 5}
SKILL_LEVELS = ("casual", "intermediate", "competitive")
MIN_PASSWORD_LENGTH = 6
MAX_NAME_LENGTH = 40

PUBLIC_FIELDS = (
    "id",
    "name",
    "captain_name",
    "format",
    "player_count",
    "skill_level",
    "district",
    "badge_color",
)


def _text(value):
    """Coerce a form/JSON value to a stripped string; None/missing → ""."""
    if value is None:
        return ""
    return str(value).strip()


def validate_new_team(form):
    """Check a sign-up form or JSON body.

    Returns (team, errors). `team` is a cleaned dict ready to save, or None if
    there were errors. `errors` is a list of messages to show the captain.
    """
    errors = []

    name = _text(form.get("name", ""))
    password = form.get("password") or ""
    if not isinstance(password, str):
        password = str(password)
    captain_name = _text(form.get("captain_name", ""))
    team_format = _text(form.get("format", ""))
    skill_level = _text(form.get("skill_level", ""))
    district = _text(form.get("district", ""))

    if not name:
        errors.append("Team name is required.")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Team name must be at most {MAX_NAME_LENGTH} characters.")

    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    if not captain_name:
        errors.append("Captain name is required.")

    if team_format not in FORMATS:
        errors.append("Format must be 3v3 or 5v5.")

    if skill_level not in SKILL_LEVELS:
        errors.append("Pick a skill level.")

    raw_count = form.get("player_count", "")
    try:
        if raw_count is None or raw_count == "":
            raise ValueError("empty")
        player_count = int(raw_count)
    except (TypeError, ValueError):
        player_count = None
        errors.append("Number of players must be a whole number.")

    if player_count is not None and team_format in FORMATS:
        needed = FORMATS[team_format]
        if player_count < needed:
            errors.append(f"A {team_format} team needs at least {needed} players.")

    if errors:
        return None, errors

    team = {
        "name": name,
        "password_hash": hash_password(password),
        "captain_name": captain_name,
        "format": team_format,
        "player_count": player_count,
        "skill_level": skill_level,
        "district": district or None,
    }
    return team, []


def hash_password(password):
    return generate_password_hash(password)


def password_matches(password_hash, password):
    return check_password_hash(password_hash, password)


def public_team(team):
    """Return only fields safe to send in API responses (no password_hash)."""
    if team is None:
        return None
    return {field: team.get(field) for field in PUBLIC_FIELDS if field in team or field == "badge_color"}
