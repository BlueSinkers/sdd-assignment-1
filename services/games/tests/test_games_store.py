"""Store tests against a fake pymssql connection (no real SQL Server)."""
from unittest.mock import MagicMock

import pymssql

from games import store


def _conn_with_cursor(fetchone=None, fetchall=None, side_effect=None):
    conn = MagicMock()
    cur = MagicMock()
    if side_effect is not None:
        cur.execute.side_effect = side_effect
    cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall or []
    # Support `with conn.cursor() as cur`
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    return conn, cur


def test_create_court_returns_id():
    conn, cur = _conn_with_cursor(fetchone={"id": 10})
    court_id = store.create_court(
        conn, {"name": "Río", "address": "Calle 1", "maps_url": None}, proposed_by_team_id=1
    )
    assert court_id == 10
    conn.commit.assert_called_once()


def test_create_court_duplicate_address_returns_none():
    conn, cur = _conn_with_cursor()
    cur.execute.side_effect = pymssql.IntegrityError("uq")
    assert store.create_court(
        conn, {"name": None, "address": "Calle 1", "maps_url": None}, 1
    ) is None
    conn.rollback.assert_called_once()


def test_get_court_none_id():
    conn, _ = _conn_with_cursor()
    assert store.get_court(conn, None) is None


def test_get_court_found():
    conn, _ = _conn_with_cursor(fetchone={"id": 10, "address": "Calle 1"})
    assert store.get_court(conn, 10)["address"] == "Calle 1"


def test_list_courts():
    conn, _ = _conn_with_cursor(fetchall=[{"id": 1}, {"id": 2}])
    assert len(store.list_courts(conn)) == 2


def test_create_challenge():
    conn, _ = _conn_with_cursor(fetchone={"id": 5})
    challenge_id = store.create_challenge(
        conn,
        {
            "challenger_team_id": 1,
            "opponent_team_id": 2,
            "court_id": 10,
            "start_time": "2026-10-18T18:00",
            "format": "5v5",
        },
    )
    assert challenge_id == 5


def test_get_set_list_challenges():
    conn, cur = _conn_with_cursor(fetchone={"id": 5, "status": "pending"})
    assert store.get_challenge(conn, 5)["id"] == 5

    store.set_status(conn, 5, "accepted")
    conn.commit.assert_called()

    conn2, _ = _conn_with_cursor(fetchall=[{"id": 1}])
    assert store.list_challenges_for_team(conn2, 1) == [{"id": 1}]
    assert store.list_accepted(conn2) == [{"id": 1}]
    assert store.list_all_challenges(conn2) == [{"id": 1}]


def test_record_attendance_merge():
    conn, cur = _conn_with_cursor()
    store.record_attendance(
        conn, {"challenge_id": 5, "team_id": 1, "players_attended": 4}
    )
    sql = cur.execute.call_args[0][0]
    assert "MERGE" in sql
    conn.commit.assert_called_once()


def test_list_and_attendance_for_team():
    conn, _ = _conn_with_cursor(
        fetchall=[{"challenge_id": 5, "players_attended": 4, "team_id": 1}]
    )
    assert store.list_attendance(conn)[0]["players_attended"] == 4

    conn2, _ = _conn_with_cursor(
        fetchall=[{"challenge_id": 5, "players_attended": 4}]
    )
    assert store.attendance_for_team(conn2, 1) == {5: 4}
