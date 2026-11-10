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


# --- validate_attendance ------------------------------------------------------

PLAYED = game(5, challenger=1, opponent=2, court_id=10, start="2026-10-09T18:00")


def test_team_in_played_game_can_record_turnout():
    record, errors = logic.validate_attendance(PLAYED, 1, "5", roster_size=6, now=NOW)
    assert errors == []
    assert record == {"challenge_id": 5, "team_id": 1, "players_attended": 5}


def test_zero_players_is_allowed():
    record, _ = logic.validate_attendance(PLAYED, 2, "0", roster_size=5, now=NOW)
    assert record["players_attended"] == 0


def test_outside_team_cannot_record_turnout():
    _, errors = logic.validate_attendance(PLAYED, 3, "4", roster_size=6, now=NOW)
    assert "Only the two teams in this game can record turnout." in errors


def test_turnout_only_for_agreed_games():
    declined = dict(PLAYED, status="declined")
    _, errors = logic.validate_attendance(declined, 1, "4", roster_size=6, now=NOW)
    assert "Turnout can only be recorded for agreed games." in errors


def test_turnout_not_before_game_starts():
    future = dict(PLAYED, start_time="2026-10-18T18:00")
    _, errors = logic.validate_attendance(future, 1, "4", roster_size=6, now=NOW)
    assert "You can record turnout once the game has started." in errors


def test_turnout_must_be_a_number():
    _, errors = logic.validate_attendance(PLAYED, 1, "lots", roster_size=6, now=NOW)
    assert "Number of players must be a whole number." in errors


def test_turnout_cannot_exceed_roster_or_be_negative():
    _, too_many = logic.validate_attendance(PLAYED, 1, "7", roster_size=6, now=NOW)
    _, negative = logic.validate_attendance(PLAYED, 1, "-1", roster_size=6, now=NOW)
    assert too_many == ["Enter a number from 0 to 6 (your roster size)."]
    assert negative == ["Enter a number from 0 to 6 (your roster size)."]


# --- compute_stats ------------------------------------------------------------

def test_stats_with_no_data():
    s = logic.compute_stats([], [], {}, NOW)
    assert s["games_played"] == 0
    assert s["acceptance_rate"] is None
    assert s["avg_players_per_game"] is None
    assert s["turnout_rate"] is None
    assert s["busiest_courts"] == []


def test_stats_counts_games_and_rates():
    challenges = [
        dict(game(1, 1, 2, 10, "2026-10-01T18:00"), format="5v5"),                       # played
        dict(game(2, 1, 3, 10, "2026-10-05T18:00"), format="5v5"),                       # played
        dict(game(3, 2, 3, 11, "2026-10-20T18:00"), format="3v3"),                       # upcoming
        dict(game(4, 1, 2, 11, "2026-10-21T18:00", status="declined"), format="5v5"),
        dict(game(5, 3, 1, 11, "2026-10-22T18:00", status="pending"), format="5v5"),     # open
        dict(game(6, 3, 1, 11, "2026-10-02T18:00", status="pending"), format="5v5"),     # expired
    ]
    attendance = [
        {"challenge_id": 1, "team_id": 1, "players_attended": 5},
        {"challenge_id": 1, "team_id": 2, "players_attended": 4},
        {"challenge_id": 2, "team_id": 1, "players_attended": 6},
    ]
    s = logic.compute_stats(challenges, attendance, {1: 6, 2: 5}, NOW)

    assert s["games_played"] == 2
    assert s["upcoming_games"] == 1
    assert s["pending_challenges"] == 1
    assert s["acceptance_rate"] == 75            # 3 accepted out of 4 answered
    assert s["players_attended"] == 15
    assert s["avg_players_per_game"] == 7.5      # 15 players over 2 games
    assert s["turnout_rate"] == 88               # 15 of 17 roster spots (6 + 5 + 6)
    assert s["games_by_format"] == {"3v3": 1, "5v5": 2}
    assert s["busiest_courts"] == [(10, 2), (11, 1)]
    assert s["most_active_teams"] == [(1, 2), (2, 2), (3, 2)]
