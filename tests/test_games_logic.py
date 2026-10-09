from datetime import datetime

from games import logic

NOW = datetime(2026, 10, 10, 12, 0)

RETIRO = {"id": 1, "name": "Retiro Five", "format": "5v5", "player_count": 6}
CHAMBERI = {"id": 2, "name": "Chamberí Hoops", "format": "5v5", "player_count": 5}
LAVAPIES = {"id": 3, "name": "Lavapiés 3", "format": "3v3", "player_count": 4}
COURT = {"id": 10, "name": "Madrid Río", "address": "Paseo de la Ermita del Santo"}


def game(id, challenger, opponent, court_id, start, status="accepted"):
    return {
        "id": id,
        "challenger_team_id": challenger,
        "opponent_team_id": opponent,
        "court_id": court_id,
        "start_time": start,
        "status": status,
    }


# --- validate_court -----------------------------------------------------------

def test_court_with_only_address_is_valid():
    court, errors = logic.validate_court({"address": "  Calle de Alcalá 1  "})
    assert errors == []
    assert court == {"name": None, "address": "Calle de Alcalá 1", "maps_url": None}


def test_court_without_address_is_rejected():
    court, errors = logic.validate_court({"name": "Retiro"})
    assert court is None
    assert "Address is required." in errors


def test_court_address_too_long_is_rejected():
    _, errors = logic.validate_court({"address": "x" * 201})
    assert any("at most" in e for e in errors)


def test_court_maps_link_must_be_a_url():
    _, errors = logic.validate_court({"address": "Calle 1", "maps_url": "maps.google.com/x"})
    assert "Google Maps link must start with https://" in errors


def test_court_with_maps_link_is_valid():
    court, errors = logic.validate_court(
        {"address": "Calle 1", "name": "Retiro", "maps_url": "https://maps.app.goo.gl/abc"}
    )
    assert errors == []
    assert court["maps_url"] == "https://maps.app.goo.gl/abc"


# --- validate_challenge -------------------------------------------------------

def test_valid_challenge_is_accepted():
    challenge, errors = logic.validate_challenge(RETIRO, CHAMBERI, COURT, "2026-10-18T18:00", NOW)
    assert errors == []
    assert challenge == {
        "challenger_team_id": 1,
        "opponent_team_id": 2,
        "court_id": 10,
        "start_time": "2026-10-18T18:00",
        "format": "5v5",
    }


def test_cannot_challenge_own_team():
    _, errors = logic.validate_challenge(RETIRO, RETIRO, COURT, "2026-10-18T18:00", NOW)
    assert "You can't challenge your own team." in errors


def test_3v3_cannot_challenge_5v5():
    _, errors = logic.validate_challenge(LAVAPIES, RETIRO, COURT, "2026-10-18T18:00", NOW)
    assert errors == ["Retiro Five plays 5v5; your team plays 3v3."]


def test_missing_opponent_is_rejected():
    _, errors = logic.validate_challenge(RETIRO, None, COURT, "2026-10-18T18:00", NOW)
    assert "That team does not exist." in errors


def test_missing_court_is_rejected():
    _, errors = logic.validate_challenge(RETIRO, CHAMBERI, None, "2026-10-18T18:00", NOW)
    assert "Pick a court." in errors


def test_bad_time_is_rejected():
    _, errors = logic.validate_challenge(RETIRO, CHAMBERI, COURT, "next saturday", NOW)
    assert "Pick a valid date and time." in errors


def test_missing_time_is_rejected():
    _, errors = logic.validate_challenge(RETIRO, CHAMBERI, COURT, None, NOW)
    assert "Pick a valid date and time." in errors


def test_past_time_is_rejected():
    _, errors = logic.validate_challenge(RETIRO, CHAMBERI, COURT, "2026-10-09T18:00", NOW)
    assert "The game has to be in the future." in errors


def test_time_exactly_now_is_rejected():
    _, errors = logic.validate_challenge(RETIRO, CHAMBERI, COURT, "2026-10-10T12:00", NOW)
    assert "The game has to be in the future." in errors


# --- next_status --------------------------------------------------------------

PENDING = game(5, challenger=1, opponent=2, court_id=10, start="2026-10-18T18:00", status="pending")


def test_opponent_can_accept():
    assert logic.next_status(PENDING, 2, "accept") == ("accepted", None)


def test_opponent_can_decline():
    assert logic.next_status(PENDING, 2, "decline") == ("declined", None)


def test_challenger_can_cancel():
    assert logic.next_status(PENDING, 1, "cancel") == ("cancelled", None)


def test_challenger_cannot_accept_own_challenge():
    status, error = logic.next_status(PENDING, 1, "accept")
    assert status is None
    assert error == "Only the challenged team can accept or decline."


def test_opponent_cannot_cancel():
    status, error = logic.next_status(PENDING, 2, "cancel")
    assert status is None
    assert error == "Only the team that sent the challenge can cancel it."


def test_outside_team_cannot_act():
    assert logic.next_status(PENDING, 3, "accept")[0] is None


def test_finished_challenge_cannot_change():
    declined = dict(PENDING, status="declined")
    assert logic.next_status(declined, 2, "accept") == (None, "This challenge is already declined.")


def test_unknown_action_is_rejected():
    assert logic.next_status(PENDING, 2, "reschedule") == (None, "Unknown action.")


# --- find_conflict ------------------------------------------------------------

NEW = game(None, challenger=1, opponent=2, court_id=10, start="2026-10-18T18:00", status="pending")


def test_no_accepted_games_means_no_conflict():
    assert logic.find_conflict(NEW, []) is None


def test_same_team_overlapping_game_conflicts():
    other = game(7, challenger=1, opponent=3, court_id=99, start="2026-10-18T19:00")
    assert logic.find_conflict(NEW, [other]) == "One of the teams already has a game at that time."


def test_opponent_team_overlapping_game_conflicts():
    other = game(7, challenger=4, opponent=2, court_id=99, start="2026-10-18T17:00")
    assert logic.find_conflict(NEW, [other]) == "One of the teams already has a game at that time."


def test_same_court_overlapping_game_conflicts():
    other = game(7, challenger=4, opponent=5, court_id=10, start="2026-10-18T18:30")
    assert logic.find_conflict(NEW, [other]) == "That court is already booked at that time."


def test_games_exactly_two_hours_apart_do_not_conflict():
    other = game(7, challenger=1, opponent=3, court_id=10, start="2026-10-18T20:00")
    assert logic.find_conflict(NEW, [other]) is None


def test_different_teams_and_court_do_not_conflict():
    other = game(7, challenger=4, opponent=5, court_id=99, start="2026-10-18T18:00")
    assert logic.find_conflict(NEW, [other]) is None


def test_challenge_does_not_conflict_with_itself():
    saved = dict(NEW, id=5)
    assert logic.find_conflict(saved, [dict(saved, status="accepted")]) is None
