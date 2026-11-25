"""Games domain: JSON API for courts, challenges, dashboard, turnout, and stats."""
from __future__ import annotations

from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, jsonify, request

import db
from auth import team_from_token
from games import logic, store
from games.teams_client import TEAMS_UNAVAILABLE_BODY, TeamsUnavailable, get_team_summary

bp = Blueprint("games", __name__)

MADRID = ZoneInfo("Europe/Madrid")


def madrid_now():
    """Current Madrid wall-clock time, matching the times captains type in."""
    return datetime.now(MADRID).replace(tzinfo=None)


def teams_unavailable_response():
    return jsonify(TEAMS_UNAVAILABLE_BODY), 503


def require_auth(view):
    """Load the captain's team from the Bearer token, or 401."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "unauthorized", "message": "Bearer token required."}), 401
        token = header[7:].strip()
        team = team_from_token(token, current_app.config["SECRET_KEY"])
        if team is None:
            return jsonify({"error": "unauthorized", "message": "Invalid or expired token."}), 401
        return view(team, *args, **kwargs)

    return wrapped


def _team_name(summary):
    return summary["name"] if summary else None


def _enrich_challenge(challenge, team_cache, court_cache, degraded=False):
    """Attach challenger/opponent names and court label. Names may be None if degraded."""
    del degraded  # flag is carried on the response envelope, not per-row
    challenger = team_cache.get(challenge["challenger_team_id"])
    opponent = team_cache.get(challenge["opponent_team_id"])
    court = court_cache.get(challenge["court_id"])
    return {
        **dict(challenge),
        "challenger_name": _team_name(challenger),
        "opponent_name": _team_name(opponent),
        "court_label": (court["name"] or court["address"]) if court else None,
        "court_maps_url": court["maps_url"] if court else None,
        "when": challenge["start_time"].replace("T", " "),
    }


def _load_team_cache(team_ids):
    """Fetch summaries for unique ids. Raises TeamsUnavailable if Teams is down."""
    cache = {}
    for team_id in sorted({tid for tid in team_ids if tid is not None}):
        cache[team_id] = get_team_summary(team_id)
    return cache


def _try_load_team_cache(team_ids):
    """Like _load_team_cache but returns (cache, degraded) instead of raising."""
    cache = {}
    degraded = False
    for team_id in sorted({tid for tid in team_ids if tid is not None}):
        try:
            cache[team_id] = get_team_summary(team_id)
        except TeamsUnavailable:
            degraded = True
            cache[team_id] = None
    return cache, degraded


def _court_cache_for(conn, challenges):
    cache = {}
    for c in challenges:
        court_id = c["court_id"]
        if court_id not in cache:
            cache[court_id] = store.get_court(conn, court_id)
    return cache


# --- Health -------------------------------------------------------------------

@bp.get("/health")
def health():
    """Own DB only — does not call Teams."""
    import os

    version = os.environ.get("VERSION", "unknown")
    try:
        ok = db.ping()
    except Exception:  # noqa: BLE001 — health must never stack-trace to client
        return jsonify({"status": "error", "db": "error", "version": version}), 503
    if not ok:
        return jsonify({"status": "error", "db": "error", "version": version}), 503
    return jsonify({"status": "ok", "db": "ok", "version": version})



# --- Courts -------------------------------------------------------------------

@bp.get("/api/courts")
def list_courts():
    conn = db.get_conn()
    courts = store.list_courts(conn)
    return jsonify({"courts": courts})


@bp.post("/api/courts")
@require_auth
def create_court(team):
    body = request.get_json(silent=True) or {}
    court, errors = logic.validate_court(body)
    if court is None:
        return jsonify({"errors": errors}), 400

    conn = db.get_conn()
    court_id = store.create_court(conn, court, team["team_id"])
    if court_id is None:
        return jsonify({"errors": ["That address is already listed."]}), 400

    created = store.get_court(conn, court_id)
    return jsonify({"court": created}), 201


# --- Upcoming games -----------------------------------------------------------

@bp.get("/api/games/upcoming")
def upcoming_games():
    conn = db.get_conn()
    now = madrid_now().strftime(logic.TIME_FORMAT)
    accepted = [g for g in store.list_accepted(conn) if g["start_time"] >= now]

    team_ids = []
    for g in accepted:
        team_ids.extend([g["challenger_team_id"], g["opponent_team_id"]])
    team_cache, degraded = _try_load_team_cache(team_ids)
    court_cache = _court_cache_for(conn, accepted)

    games = [
        _enrich_challenge(g, team_cache, court_cache, degraded=degraded) for g in accepted
    ]
    payload = {"games": games}
    if degraded:
        payload["teams_degraded"] = True
    return jsonify(payload)


# --- Challenges ---------------------------------------------------------------

@bp.post("/api/challenges")
@require_auth
def create_challenge(team):
    body = request.get_json(silent=True) or {}
    opponent_team_id = body.get("opponent_team_id")
    court_id = body.get("court_id")
    start_time = body.get("start_time")

    try:
        opponent_team_id = int(opponent_team_id) if opponent_team_id is not None else None
    except (TypeError, ValueError):
        opponent_team_id = None
    try:
        court_id = int(court_id) if court_id is not None else None
    except (TypeError, ValueError):
        court_id = None

    # Cross-seam: always resolve challenger + opponent through Teams HTTP.
    try:
        challenger = get_team_summary(team["team_id"])
        opponent = get_team_summary(opponent_team_id) if opponent_team_id is not None else None
    except TeamsUnavailable:
        return teams_unavailable_response()

    if challenger is None:
        return jsonify({"errors": ["Your team no longer exists."]}), 400

    conn = db.get_conn()
    court = store.get_court(conn, court_id)
    new, errors = logic.validate_challenge(
        challenger, opponent, court, start_time, madrid_now()
    )
    if new is None:
        return jsonify({"errors": errors}), 400

    clash = logic.find_conflict(new, store.list_accepted(conn))
    if clash:
        return jsonify({"errors": [clash]}), 400

    if body.get("note") is not None:
        note = str(body.get("note")).strip()
        new["note"] = note[:200] if note else None

    challenge_id = store.create_challenge(conn, new)
    created = store.get_challenge(conn, challenge_id)
    return jsonify({"challenge": created}), 201


def _respond(team, challenge_id, action):
    conn = db.get_conn()
    existing = store.get_challenge(conn, challenge_id)
    if existing is None:
        return jsonify({"errors": ["That challenge does not exist."]}), 404

    new_status, error = logic.next_status(existing, team["team_id"], action)
    if new_status == "accepted":
        # Re-check at accept time: another game may have been agreed since it was sent.
        error = logic.find_conflict(existing, store.list_accepted(conn)) or error
    if error:
        return jsonify({"errors": [error]}), 400

    store.set_status(conn, challenge_id, new_status)
    updated = store.get_challenge(conn, challenge_id)
    return jsonify({"challenge": updated})


@bp.post("/api/challenges/<int:challenge_id>/accept")
@require_auth
def accept_challenge(team, challenge_id):
    return _respond(team, challenge_id, "accept")


@bp.post("/api/challenges/<int:challenge_id>/decline")
@require_auth
def decline_challenge(team, challenge_id):
    return _respond(team, challenge_id, "decline")


@bp.post("/api/challenges/<int:challenge_id>/cancel")
@require_auth
def cancel_challenge(team, challenge_id):
    return _respond(team, challenge_id, "cancel")


# --- Dashboard ----------------------------------------------------------------

@bp.get("/api/dashboard")
@require_auth
def dashboard(team):
    """Captain dashboard. Needs team names — prefer 503 if Teams is down."""
    team_id = team["team_id"]
    conn = db.get_conn()
    now = madrid_now().strftime(logic.TIME_FORMAT)
    rows = store.list_challenges_for_team(conn, team_id)
    turnout = store.attendance_for_team(conn, team_id)

    team_ids = []
    for row in rows:
        team_ids.extend([row["challenger_team_id"], row["opponent_team_id"]])
    try:
        team_cache = _load_team_cache(team_ids)
    except TeamsUnavailable:
        return teams_unavailable_response()

    court_cache = _court_cache_for(conn, rows)
    received, sent, upcoming, played, history = [], [], [], [], []
    for row in rows:
        c = _enrich_challenge(row, team_cache, court_cache)
        if c["status"] == "pending" and c["start_time"] >= now:
            (received if c["opponent_team_id"] == team_id else sent).append(c)
        elif c["status"] == "accepted" and c["start_time"] >= now:
            upcoming.append(c)
        elif c["status"] == "accepted":
            c["my_turnout"] = turnout.get(c["id"])
            played.append(c)
        else:
            history.append(c)

    return jsonify(
        {
            "received": received,
            "sent": sent,
            "upcoming": upcoming,
            "played": played,
            "history": history,
        }
    )


# --- Turnout ------------------------------------------------------------------

@bp.post("/api/challenges/<int:challenge_id>/turnout")
@require_auth
def record_turnout(team, challenge_id):
    body = request.get_json(silent=True) or {}
    players = body.get("players")

    conn = db.get_conn()
    game = store.get_challenge(conn, challenge_id)
    if game is None:
        return jsonify({"errors": ["That game does not exist."]}), 404

    # Cross-seam: roster size comes from Teams.
    try:
        summary = get_team_summary(team["team_id"])
    except TeamsUnavailable:
        return teams_unavailable_response()
    if summary is None:
        return jsonify({"errors": ["Your team no longer exists."]}), 400

    record, errors = logic.validate_attendance(
        game, team["team_id"], players, summary["player_count"], madrid_now()
    )
    if record is None:
        return jsonify({"errors": errors}), 400

    store.record_attendance(conn, record)
    return jsonify({"attendance": record})


# --- Stats --------------------------------------------------------------------

@bp.get("/api/stats")
def stats():
    """Public stats. Resolve names via Teams; degrade to ids if Teams is down."""
    conn = db.get_conn()
    attendance = store.list_attendance(conn)
    challenges = store.list_all_challenges(conn)

    team_ids = {a["team_id"] for a in attendance}
    for c in challenges:
        team_ids.add(c["challenger_team_id"])
        team_ids.add(c["opponent_team_id"])
    # busiest courts need court labels from our own DB
    court_ids = {c["court_id"] for c in challenges if c["status"] == "accepted"}

    team_cache, degraded = _try_load_team_cache(team_ids)

    roster_sizes = {
        a["team_id"]: team_cache[a["team_id"]]["player_count"]
        for a in attendance
        if team_cache.get(a["team_id"])
    }
    numbers = logic.compute_stats(challenges, attendance, roster_sizes, madrid_now())

    court_cache = {cid: store.get_court(conn, cid) for cid in court_ids}

    def court_label(court_id):
        court = court_cache.get(court_id)
        if court is None:
            return str(court_id)
        return court["name"] or court["address"]

    numbers["busiest_courts"] = [
        {"id": i, "label": court_label(i), "count": n} for i, n in numbers["busiest_courts"]
    ]
    numbers["most_active_teams"] = [
        {
            "id": i,
            "name": (team_cache[i]["name"] if team_cache.get(i) else None),
            "count": n,
        }
        for i, n in numbers["most_active_teams"]
    ]

    if degraded:
        numbers["teams_degraded"] = True
    return jsonify(numbers)
