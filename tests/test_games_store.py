import pytest

import db
from games import store
from teams import api as teams_api
from teams import store as teams_store


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    conn = db.connect(path)
    yield conn
    conn.close()


COURT = {"name": "Madrid Río", "address": "Paseo de la Ermita del Santo", "maps_url": None}


def make_challenge(court_id, start="2026-10-18T18:00"):
    return {
        "challenger_team_id": 1,
        "opponent_team_id": 2,
        "court_id": court_id,
        "start_time": start,
        "format": "5v5",
    }


def test_create_and_list_courts(conn):
    court_id = store.create_court(conn, COURT, proposed_by_team_id=1)
    assert store.get_court(conn, court_id)["address"] == COURT["address"]
    assert [c["id"] for c in store.list_courts(conn)] == [court_id]


def test_duplicate_court_address_returns_none(conn):
    store.create_court(conn, COURT, proposed_by_team_id=1)
    assert store.create_court(conn, dict(COURT, name="Other name"), proposed_by_team_id=2) is None


def test_new_challenge_starts_pending(conn):
    court_id = store.create_court(conn, COURT, proposed_by_team_id=1)
    challenge_id = store.create_challenge(conn, make_challenge(court_id))
    challenge = store.get_challenge(conn, challenge_id)
    assert challenge["status"] == "pending"
    assert challenge["responded_at"] is None


def test_set_status_records_response_time(conn):
    court_id = store.create_court(conn, COURT, proposed_by_team_id=1)
    challenge_id = store.create_challenge(conn, make_challenge(court_id))
    store.set_status(conn, challenge_id, "accepted")
    challenge = store.get_challenge(conn, challenge_id)
    assert challenge["status"] == "accepted"
    assert challenge["responded_at"] is not None


def test_list_for_team_and_accepted(conn):
    court_id = store.create_court(conn, COURT, proposed_by_team_id=1)
    later = store.create_challenge(conn, make_challenge(court_id, "2026-10-20T18:00"))
    sooner = store.create_challenge(conn, make_challenge(court_id, "2026-10-19T18:00"))
    store.set_status(conn, later, "accepted")

    assert [c["id"] for c in store.list_challenges_for_team(conn, 2)] == [sooner, later]
    assert store.list_challenges_for_team(conn, 3) == []
    assert [c["id"] for c in store.list_accepted(conn)] == [later]


def test_challenge_cannot_point_at_missing_court(conn):
    # court_id has a real foreign key, because courts are in the same domain.
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        store.create_challenge(conn, make_challenge(court_id=999))


def test_teams_api_summary_hides_private_fields(conn):
    team_id = teams_store.create_team(conn, {
        "name": "Retiro Five", "password_hash": "hashed", "captain_name": "Abhi",
        "format": "5v5", "player_count": 6, "skill_level": "casual", "district": None,
    })
    assert teams_api.get_team_summary(conn, team_id) == {
        "id": team_id, "name": "Retiro Five", "format": "5v5", "player_count": 6,
    }
    assert teams_api.get_team_summary(conn, 999) is None


def test_record_attendance_replaces_earlier_number(conn):
    court_id = store.create_court(conn, COURT, proposed_by_team_id=1)
    challenge_id = store.create_challenge(conn, make_challenge(court_id))
    store.record_attendance(conn, {"challenge_id": challenge_id, "team_id": 1, "players_attended": 4})
    store.record_attendance(conn, {"challenge_id": challenge_id, "team_id": 1, "players_attended": 6})
    store.record_attendance(conn, {"challenge_id": challenge_id, "team_id": 2, "players_attended": 5})

    assert len(store.list_attendance(conn)) == 2
    assert store.attendance_for_team(conn, 1) == {challenge_id: 6}
    assert len(store.list_all_challenges(conn)) == 1
