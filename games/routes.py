"""Games domain: web pages for courts, challenges, the dashboard and home."""
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

import db
from games import logic, store
from teams import api as teams_api

bp = Blueprint("games", __name__)

MADRID = ZoneInfo("Europe/Madrid")


def madrid_now():
    """Current Madrid wall-clock time, matching the times captains type in."""
    return datetime.now(MADRID).replace(tzinfo=None)


def logged_in_team_id():
    """The captain's team id, or None. Pages that need a login check this."""
    return session.get("team_id")


def describe(conn, challenge):
    """Turn a challenge row into what a page shows: team and court names.

    Team names come from teams_api, not a SQL join, so Games never reads
    the teams table (ADR 2).
    """
    challenger = teams_api.get_team_summary(conn, challenge["challenger_team_id"])
    opponent = teams_api.get_team_summary(conn, challenge["opponent_team_id"])
    court = store.get_court(conn, challenge["court_id"])
    return {
        **dict(challenge),
        "challenger_name": challenger["name"] if challenger else "(deleted team)",
        "opponent_name": opponent["name"] if opponent else "(deleted team)",
        "court_label": court["name"] or court["address"],
        "court_maps_url": court["maps_url"],
        "when": challenge["start_time"].replace("T", " "),
    }


@bp.route("/")
def home():
    conn = db.get_conn()
    now = madrid_now().strftime(logic.TIME_FORMAT)
    upcoming = [describe(conn, g) for g in store.list_accepted(conn) if g["start_time"] >= now]
    return render_template("home.html", games=upcoming)


# --- Courts -------------------------------------------------------------------

@bp.route("/courts", methods=["GET", "POST"])
def courts():
    conn = db.get_conn()
    form = {}
    if request.method == "POST":
        if not logged_in_team_id():
            flash("Log in as a team captain to add a court.")
            return redirect(url_for("teams.login"))
        form = request.form
        court, errors = logic.validate_court(form)
        if court:
            if store.create_court(conn, court, logged_in_team_id()) is None:
                errors = ["That address is already listed."]
            else:
                flash("Court added.")
                return redirect(url_for("games.courts"))
        for error in errors:
            flash(error)
    return render_template("games/courts.html", courts=store.list_courts(conn), form=form)


# --- Challenges ---------------------------------------------------------------

@bp.route("/challenge/<int:opponent_id>", methods=["GET", "POST"])
def challenge(opponent_id):
    if not logged_in_team_id():
        flash("Log in as a team captain to send a challenge.")
        return redirect(url_for("teams.login"))

    conn = db.get_conn()
    challenger = teams_api.get_team_summary(conn, logged_in_team_id())
    opponent = teams_api.get_team_summary(conn, opponent_id)
    if opponent is None:
        flash("That team does not exist.")
        return redirect(url_for("teams.team_list"))

    if request.method == "POST":
        court = store.get_court(conn, request.form.get("court_id", type=int))
        new, errors = logic.validate_challenge(
            challenger, opponent, court, request.form.get("start_time"), madrid_now()
        )
        if new:
            clash = logic.find_conflict(new, store.list_accepted(conn))
            if clash:
                errors = [clash]
            else:
                store.create_challenge(conn, new)
                flash(f"Challenge sent to {opponent['name']}.")
                return redirect(url_for("games.dashboard"))
        for error in errors:
            flash(error)

    return render_template(
        "games/challenge.html",
        opponent=opponent,
        courts=store.list_courts(conn),
        form=request.form,
    )


@bp.route("/challenges/<int:challenge_id>/<action>", methods=["POST"])
def respond(challenge_id, action):
    if not logged_in_team_id():
        return redirect(url_for("teams.login"))

    conn = db.get_conn()
    existing = store.get_challenge(conn, challenge_id)
    if existing is None:
        flash("That challenge does not exist.")
        return redirect(url_for("games.dashboard"))

    new_status, error = logic.next_status(existing, logged_in_team_id(), action)
    if new_status == "accepted":
        # Re-check at accept time: another game may have been agreed since it was sent.
        error = logic.find_conflict(existing, store.list_accepted(conn))
    if error:
        flash(error)
    else:
        store.set_status(conn, challenge_id, new_status)
        flash(f"Challenge {new_status}.")
    return redirect(url_for("games.dashboard"))


@bp.route("/dashboard")
def dashboard():
    team_id = logged_in_team_id()
    if not team_id:
        flash("Log in as a team captain to see your dashboard.")
        return redirect(url_for("teams.login"))

    conn = db.get_conn()
    now = madrid_now().strftime(logic.TIME_FORMAT)
    received, sent, upcoming, history = [], [], [], []
    for row in store.list_challenges_for_team(conn, team_id):
        c = describe(conn, row)
        if c["status"] == "pending" and c["start_time"] >= now:
            (received if c["opponent_team_id"] == team_id else sent).append(c)
        elif c["status"] == "accepted" and c["start_time"] >= now:
            upcoming.append(c)
        else:
            history.append(c)
    return render_template(
        "games/dashboard.html",
        received=received, sent=sent, upcoming=upcoming, history=history,
    )
