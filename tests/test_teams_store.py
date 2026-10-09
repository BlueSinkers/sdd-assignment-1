import pytest

import db
from teams import store


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    conn = db.connect(path)
    yield conn
    conn.close()


def make_team(name="Retiro Five"):
    return {
        "name": name,
        "password_hash": "hashed",
        "captain_name": "Abhi",
        "format": "5v5",
        "player_count": 6,
        "skill_level": "intermediate",
        "district": "Retiro",
    }


def test_create_and_fetch_team(conn):
    team_id = store.create_team(conn, make_team())
    assert team_id is not None
    assert store.get_team(conn, team_id)["name"] == "Retiro Five"
    assert store.get_team_by_name(conn, "Retiro Five")["id"] == team_id


def test_duplicate_name_returns_none(conn):
    store.create_team(conn, make_team())
    assert store.create_team(conn, make_team()) is None


def test_missing_team_returns_none(conn):
    assert store.get_team(conn, 999) is None
    assert store.get_team_by_name(conn, "Nobody") is None


def test_list_is_sorted_and_hides_password_hash(conn):
    store.create_team(conn, make_team("Zeta"))
    store.create_team(conn, make_team("Alpha"))
    teams = store.list_teams(conn)
    assert [t["name"] for t in teams] == ["Alpha", "Zeta"]
    assert "password_hash" not in teams[0].keys()


def test_init_db_twice_keeps_data(tmp_path):
    path = tmp_path / "twice.db"
    db.init_db(path)
    conn = db.connect(path)
    store.create_team(conn, make_team())
    conn.close()

    db.init_db(path)
    conn = db.connect(path)
    assert len(store.list_teams(conn)) == 1
    conn.close()
