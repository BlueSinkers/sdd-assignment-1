"""End-to-end checks through the real pages, using Flask's test client.

The detailed rules are tested in the logic tests; these make sure the pages
wire those rules up correctly for two captains using the app.
"""
import re

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return create_app()


def flashes(response):
    return re.findall(r'class="flash">([^<]*)', response.get_data(as_text=True))


def register(app, name, team_format="5v5", players=6):
    client = app.test_client()
    client.post("/register", data={
        "name": name, "password": "secret123", "captain_name": "Cap",
        "format": team_format, "player_count": players, "skill_level": "casual",
    })
    return client


@pytest.fixture
def captains(app):
    """Two 5v5 teams (ids 1 and 2) and one court (id 1)."""
    a = register(app, "Retiro Five")
    b = register(app, "Chamberi Hoops")
    a.post("/courts", data={"name": "Madrid Rio", "address": "Paseo de la Ermita del Santo"})
    return a, b


def challenge(client, opponent_id, start="2030-05-01T18:00", court_id=1):
    return client.post(f"/challenge/{opponent_id}",
                       data={"court_id": court_id, "start_time": start}, follow_redirects=True)


# --- Teams pages --------------------------------------------------------------

def test_register_bad_form_shows_errors(app):
    r = app.test_client().post("/register", data={"name": ""}, follow_redirects=True)
    assert "Team name is required." in flashes(r)


def test_register_duplicate_name(app):
    register(app, "Retiro Five")
    r = app.test_client().post("/register", data={
        "name": "Retiro Five", "password": "secret123", "captain_name": "X",
        "format": "5v5", "player_count": 5, "skill_level": "casual",
    }, follow_redirects=True)
    assert "That team name is already taken." in flashes(r)


def test_login_logout(app):
    register(app, "Retiro Five")
    client = app.test_client()
    bad = client.post("/login", data={"name": "Retiro Five", "password": "nope"})
    assert "Wrong team name or password." in flashes(bad)
    good = client.post("/login", data={"name": "Retiro Five", "password": "secret123"},
                       follow_redirects=True)
    assert "Logged in as Retiro Five." in flashes(good)
    out = client.post("/logout", follow_redirects=True)
    assert "Logged out." in flashes(out)


def test_team_list_offers_challenge_only_to_same_format(app):
    a = register(app, "Retiro Five", "5v5", 6)
    register(app, "Chamberi Hoops", "5v5", 5)
    register(app, "Lavapies 3", "3v3", 4)
    page = a.get("/teams").get_data(as_text=True)
    assert "/challenge/2" in page
    assert "/challenge/3" not in page
    assert "plays 3v3" in page


# --- Courts -------------------------------------------------------------------

def test_must_log_in_to_add_court(app):
    r = app.test_client().post("/courts", data={"address": "X"}, follow_redirects=True)
    assert "Log in as a team captain to add a court." in flashes(r)


def test_add_and_duplicate_court(captains):
    a, b = captains
    assert "Paseo de la Ermita del Santo" in a.get("/courts").get_data(as_text=True)
    r = b.post("/courts", data={"address": "Paseo de la Ermita del Santo"}, follow_redirects=True)
    assert "That address is already listed." in flashes(r)
    r = b.post("/courts", data={"address": ""}, follow_redirects=True)
    assert "Address is required." in flashes(r)


# --- Challenges ---------------------------------------------------------------

def test_full_challenge_flow(app, captains):
    a, b = captains
    assert "Challenge sent to Chamberi Hoops." in flashes(challenge(a, 2))
    assert "Agree to play" in b.get("/dashboard").get_data(as_text=True)

    assert "Only the challenged team can accept or decline." in flashes(
        a.post("/challenges/1/accept", follow_redirects=True))
    assert "Challenge accepted." in flashes(b.post("/challenges/1/accept", follow_redirects=True))
    assert "This challenge is already accepted." in flashes(
        b.post("/challenges/1/accept", follow_redirects=True))

    assert "Retiro Five vs Chamberi Hoops" in app.test_client().get("/").get_data(as_text=True)


def test_challenger_can_cancel(captains):
    a, b = captains
    challenge(a, 2)
    assert "Challenge cancelled." in flashes(a.post("/challenges/1/cancel", follow_redirects=True))
    assert "cancelled" in a.get("/dashboard").get_data(as_text=True)


def test_invalid_challenge_shows_rule_message(captains):
    a, _ = captains
    assert "The game has to be in the future." in flashes(challenge(a, 2, start="2020-01-01T18:00"))


def test_clash_is_caught_when_sending_and_when_accepting(app, captains):
    a, b = captains
    c = register(app, "Tetuan Ten")
    c.post("/courts", data={"address": "Calle de Alcala 1"})  # court 2

    challenge(a, 2, start="2030-05-01T18:00")             # challenge 1: a vs b
    challenge(c, 2, start="2030-05-01T19:00", court_id=2)  # challenge 2: c vs b, overlaps
    b.post("/challenges/1/accept")
    r = b.post("/challenges/2/accept", follow_redirects=True)
    assert "One of the teams already has a game at that time." in flashes(r)

    r = challenge(c, 1, start="2030-05-01T18:30", court_id=2)
    assert "One of the teams already has a game at that time." in flashes(r)


def test_pages_that_need_login_redirect(app):
    client = app.test_client()
    assert "Log in as a team captain to see your dashboard." in flashes(
        client.get("/dashboard", follow_redirects=True))
    assert "Log in as a team captain to send a challenge." in flashes(
        client.get("/challenge/1", follow_redirects=True))
    assert client.post("/challenges/1/accept").status_code == 302


def test_missing_team_and_challenge(captains):
    a, _ = captains
    assert "That team does not exist." in flashes(a.get("/challenge/999", follow_redirects=True))
    assert "That challenge does not exist." in flashes(
        a.post("/challenges/999/accept", follow_redirects=True))


# --- Turnout and stats --------------------------------------------------------

def add_played_game(tmp_path):
    """Insert an agreed game in the past directly: the pages only allow future games."""
    import db
    from games import store as games_store
    conn = db.connect(tmp_path / "hoops.db")
    challenge_id = games_store.create_challenge(conn, {
        "challenger_team_id": 1, "opponent_team_id": 2, "court_id": 1,
        "start_time": "2026-01-10T18:00", "format": "5v5",
    })
    games_store.set_status(conn, challenge_id, "accepted")
    conn.close()
    return challenge_id


def test_record_turnout_and_see_it_on_stats(app, captains, tmp_path):
    a, b = captains
    game_id = add_played_game(tmp_path)

    assert "How many of your players came?" in a.get("/dashboard").get_data(as_text=True)
    assert "Turnout saved." in flashes(a.post(f"/games/{game_id}/turnout", data={"players": 5},
                                              follow_redirects=True))
    assert "Turnout saved." in flashes(b.post(f"/games/{game_id}/turnout", data={"players": 4},
                                              follow_redirects=True))
    assert "Enter a number from 0 to 6 (your roster size)." in flashes(
        a.post(f"/games/{game_id}/turnout", data={"players": 9}, follow_redirects=True))

    page = app.test_client().get("/stats").get_data(as_text=True)
    assert "Players attended" in page
    assert ">9<" in page                 # 5 + 4 players
    assert ">75%<" in page               # 9 of 12 roster spots (6 + 6)
    assert "Madrid Rio" in page and "Retiro Five" in page


def test_turnout_for_missing_game(captains):
    a, _ = captains
    assert "That game does not exist." in flashes(
        a.post("/games/999/turnout", data={"players": 1}, follow_redirects=True))


def test_turnout_logged_out_redirects(app):
    assert app.test_client().post("/games/1/turnout", data={"players": 1}).status_code == 302


def test_stats_page_with_no_games(app):
    page = app.test_client().get("/stats").get_data(as_text=True)
    assert "No agreed games yet." in page
