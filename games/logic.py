"""Games domain: rules for courts and challenges between teams.

Plain Python only, no Flask and no SQL. Teams arrive as the small dicts from
teams.api.get_team_summary, and the current time is passed in as `now` so the
tests can control it.
"""
from datetime import datetime, timedelta

# How long a court is considered busy for one game.
GAME_LENGTH = timedelta(hours=2)
# The format an HTML <input type="datetime-local"> sends, e.g. 2026-10-18T18:00.
TIME_FORMAT = "%Y-%m-%dT%H:%M"
MAX_ADDRESS_LENGTH = 200

# Which team may do what, and only while the challenge is still pending.
ACTIONS = {
    "accept": ("opponent", "accepted"),
    "decline": ("opponent", "declined"),
    "cancel": ("challenger", "cancelled"),
}


def validate_court(form):
    """Check a proposed court. Returns (court, errors) like teams.logic."""
    errors = []
    name = form.get("name", "").strip()
    address = form.get("address", "").strip()
    maps_url = form.get("maps_url", "").strip()

    if not address:
        errors.append("Address is required.")
    elif len(address) > MAX_ADDRESS_LENGTH:
        errors.append(f"Address must be at most {MAX_ADDRESS_LENGTH} characters.")

    if maps_url and not maps_url.startswith(("https://", "http://")):
        errors.append("Google Maps link must start with https://")

    if errors:
        return None, errors
    return {"name": name or None, "address": address, "maps_url": maps_url or None}, []


def parse_start_time(text):
    """Turn the form's date/time text into a datetime, or None if it is invalid."""
    try:
        return datetime.strptime(text, TIME_FORMAT)
    except (TypeError, ValueError):
        return None


def validate_challenge(challenger, opponent, court, start_time_text, now):
    """Check a new challenge before it is saved.

    challenger / opponent: team summary dicts (or None if not found).
    court: a court row/dict (or None if not found).
    Returns (challenge, errors).
    """
    errors = []

    if opponent is None:
        errors.append("That team does not exist.")
    elif challenger["id"] == opponent["id"]:
        errors.append("You can't challenge your own team.")
    elif challenger["format"] != opponent["format"]:
        errors.append(
            f"{opponent['name']} plays {opponent['format']}; "
            f"your team plays {challenger['format']}."
        )

    if court is None:
        errors.append("Pick a court.")

    start_time = parse_start_time(start_time_text)
    if start_time is None:
        errors.append("Pick a valid date and time.")
    elif start_time <= now:
        errors.append("The game has to be in the future.")

    if errors:
        return None, errors

    challenge = {
        "challenger_team_id": challenger["id"],
        "opponent_team_id": opponent["id"],
        "court_id": court["id"],
        "start_time": start_time.strftime(TIME_FORMAT),
        "format": challenger["format"],
    }
    return challenge, []


def next_status(challenge, team_id, action):
    """Work out the new status when a team acts on a challenge.

    Returns (new_status, error). Exactly one of them is None.
    """
    if action not in ACTIONS:
        return None, "Unknown action."

    allowed_side, new_status = ACTIONS[action]
    allowed_team_id = challenge[f"{allowed_side}_team_id"]

    if team_id != allowed_team_id:
        if allowed_side == "opponent":
            return None, "Only the challenged team can accept or decline."
        return None, "Only the team that sent the challenge can cancel it."

    if challenge["status"] != "pending":
        return None, f"This challenge is already {challenge['status']}."

    return new_status, None


def games_overlap(start_a, start_b):
    """True if two games starting at these times would overlap."""
    return abs(start_a - start_b) < GAME_LENGTH


def find_conflict(challenge, accepted_games):
    """Check a challenge against games that are already agreed.

    Returns a message describing the first clash, or None if it is free.
    A clash is either team already playing, or the court already in use,
    within GAME_LENGTH of this game's start.
    """
    challenge = dict(challenge)  # works for a new dict or a saved database row
    start = parse_start_time(challenge["start_time"])
    teams ={challenge["challenger_team_id"], challenge["opponent_team_id"]}

    for game in accepted_games:
        if game["id"] == challenge.get("id"):
            continue
        if not games_overlap(start, parse_start_time(game["start_time"])):
            continue
        if teams & {game["challenger_team_id"], game["opponent_team_id"]}:
            return "One of the teams already has a game at that time."
        if game["court_id"] == challenge["court_id"]:
            return "That court is already booked at that time."
    return None
