"""Teams JSON API: register, login, list, summary, and current team."""
from flask import Blueprint, jsonify, request

import auth
import db
from teams import logic, store

bp = Blueprint("teams", __name__)


def _bearer_team():
    """Resolve Authorization: Bearer <token> to a team payload, or None."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    return auth.team_from_token(token)


@bp.post("/api/register")
def register():
    body = request.get_json(silent=True) or {}
    team, errors = logic.validate_new_team(body)
    if errors:
        return jsonify({"errors": errors}), 400

    team_id = store.create_team(db.get_conn(), team)
    if team_id is None:
        return jsonify({"errors": ["That team name is already taken."]}), 400

    saved = store.get_team(db.get_conn(), team_id) or {**team, "id": team_id}
    public = logic.public_team(saved)
    token = auth.issue_token(public)
    return jsonify({"token": token, "team": public}), 201


@bp.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip() if isinstance(body.get("name"), str) else str(body.get("name") or "").strip()
    password = body.get("password") or ""
    if not isinstance(password, str):
        password = str(password)

    team = store.get_team_by_name(db.get_conn(), name)
    if team and logic.password_matches(team["password_hash"], password):
        public = logic.public_team(team)
        token = auth.issue_token(public)
        return jsonify({"token": token, "team": public}), 200

    return jsonify({"error": "Wrong team name or password."}), 401


@bp.get("/api/teams")
def team_list():
    teams = store.list_teams(db.get_conn())
    return jsonify([logic.public_team(t) for t in teams]), 200


@bp.get("/api/teams/<int:team_id>")
def team_summary(team_id):
    summary = store.get_team_summary(db.get_conn(), team_id)
    if summary is None:
        return jsonify({"error": "Team not found."}), 404
    return jsonify(
        {
            "id": summary["id"],
            "name": summary["name"],
            "format": summary["format"],
            "player_count": summary["player_count"],
        }
    ), 200


@bp.get("/api/me")
def me():
    payload = _bearer_team()
    if payload is None:
        return jsonify({"error": "Unauthorized."}), 401

    team_id = payload.get("team_id")
    if team_id is None:
        return jsonify({"error": "Unauthorized."}), 401

    team = store.get_team(db.get_conn(), team_id)
    if team is None:
        return jsonify({"error": "Unauthorized."}), 401

    return jsonify(logic.public_team(team)), 200

