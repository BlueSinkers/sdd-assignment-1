"""Teams domain: web pages for sign-up, login, logout and the team list."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

import db
from teams import logic, store

bp = Blueprint("teams", __name__)


@bp.route("/teams")
def team_list():
    teams = store.list_teams(db.get_conn())
    return render_template("teams/list.html", teams=teams)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        team, errors = logic.validate_new_team(request.form)
        if team:
            team_id = store.create_team(db.get_conn(), team)
            if team_id is None:
                errors = ["That team name is already taken."]
            else:
                session["team_id"] = team_id
                session["team_name"] = team["name"]
                session["team_format"] = team["format"]
                flash(f"Welcome, {team['name']}!")
                return redirect(url_for("teams.team_list"))
        for error in errors:
            flash(error)
    return render_template(
        "teams/register.html",
        form=request.form,
        formats=logic.FORMATS,
        skill_levels=logic.SKILL_LEVELS,
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        team = store.get_team_by_name(db.get_conn(), name)
        if team and logic.password_matches(team["password_hash"], password):
            session["team_id"] = team["id"]
            session["team_name"] = team["name"]
            session["team_format"] = team["format"]
            flash(f"Logged in as {team['name']}.")
            return redirect(url_for("games.dashboard"))
        # Same message either way, so the form does not reveal which team names exist.
        flash("Wrong team name or password.")
    return render_template("teams/login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("games.home"))
