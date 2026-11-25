"""Route tests: mock store + teams_client so no SQL Server is required."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from itsdangerous import URLSafeTimedSerializer

from app import create_app
from games.teams_client import TeamsUnavailable

SECRET = "test-secret"
NOW = datetime(2026, 10, 10, 12, 0)

RETIRO = {"id": 1, "name": "Retiro Five", "format": "5v5", "player_count": 6}
CHAMBERI = {"id": 2, "name": "Chamberí Hoops", "format": "5v5", "player_count": 5}
COURT = {
    "id": 10,
    "name": "Madrid Río",
    "address": "Paseo de la Ermita del Santo",
    "maps_url": None,
    "proposed_by_team_id": 1,
}
PENDING = {
    "id": 5,
    "challenger_team_id": 1,
    "opponent_team_id": 2,
    "court_id": 10,
    "start_time": "2026-10-18T18:00",
    "format": "5v5",
    "status": "pending",
}
PLAYED = {
    "id": 5,
    "challenger_team_id": 1,
    "opponent_team_id": 2,
    "court_id": 10,
    "start_time": "2026-10-09T18:00",
    "format": "5v5",
    "status": "accepted",
}


def make_token(payload=None):
    data = payload or {
        "team_id": 1,
        "team_name": "Retiro Five",
        "format": "5v5",
        "player_count": 6,
    }
    return URLSafeTimedSerializer(SECRET).dumps(data)


def auth_headers(token=None):
    return {"Authorization": f"Bearer {token or make_token()}"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", SECRET)
    monkeypatch.setenv("VERSION", "abc123")
    app = create_app(run_migrations=False)
    app.config["SECRET_KEY"] = SECRET
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# --- Health -------------------------------------------------------------------

def test_health_ok(client):
    with patch("games.routes.db.ping", return_value=True):
        res = client.get("/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["version"] == "abc123"


def test_health_db_error(client):
    with patch("games.routes.db.ping", side_effect=RuntimeError("db down")):
        res = client.get("/health")
    assert res.status_code == 503
    body = res.get_json()
    assert body["status"] == "error"
    assert body["db"] == "error"


def test_health_db_false(client):
    with patch("games.routes.db.ping", return_value=False):
        res = client.get("/health")
    assert res.status_code == 503
    assert res.get_json()["status"] == "error"


# --- Auth ---------------------------------------------------------------------

def test_create_court_requires_auth(client):
    res = client.post("/api/courts", json={"address": "Calle 1"})
    assert res.status_code == 401


def test_create_court_rejects_bad_token(client):
    res = client.post(
        "/api/courts",
        json={"address": "Calle 1"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert res.status_code == 401


# --- Courts -------------------------------------------------------------------

def test_list_courts(client):
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.list_courts", return_value=[COURT]
    ):
        res = client.get("/api/courts")
    assert res.status_code == 200
    assert res.get_json()["courts"][0]["id"] == 10


def test_create_court_201(client):
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.create_court", return_value=10
    ), patch("games.routes.store.get_court", return_value=COURT):
        res = client.post(
            "/api/courts",
            json={"address": "Paseo de la Ermita del Santo", "name": "Madrid Río"},
            headers=auth_headers(),
        )
    assert res.status_code == 201
    assert res.get_json()["court"]["id"] == 10


def test_create_court_validation_error(client):
    with patch("games.routes.db.get_conn", return_value=MagicMock()):
        res = client.post("/api/courts", json={"name": "No address"}, headers=auth_headers())
    assert res.status_code == 400
    assert "Address is required." in res.get_json()["errors"]


def test_create_court_duplicate_address(client):
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.create_court", return_value=None
    ):
        res = client.post(
            "/api/courts",
            json={"address": "Calle 1"},
            headers=auth_headers(),
        )
    assert res.status_code == 400
    assert "already listed" in res.get_json()["errors"][0]


# --- Challenges (cross-seam) --------------------------------------------------

def test_create_challenge_201(client):
    created = {**PENDING, "id": 5}

    def summaries(tid):
        return {1: RETIRO, 2: CHAMBERI}.get(tid)

    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.get_team_summary", side_effect=summaries
    ), patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_court", return_value=COURT
    ), patch("games.routes.store.list_accepted", return_value=[]), patch(
        "games.routes.store.create_challenge", return_value=5
    ), patch("games.routes.store.get_challenge", return_value=created):
        res = client.post(
            "/api/challenges",
            json={"opponent_team_id": 2, "court_id": 10, "start_time": "2026-10-18T18:00"},
            headers=auth_headers(),
        )
    assert res.status_code == 201
    assert res.get_json()["challenge"]["id"] == 5


def test_create_challenge_teams_unavailable_returns_503(client):
    """Cross-seam failure: Teams raises → designed 503, never a stack trace."""
    with patch("games.routes.get_team_summary", side_effect=TeamsUnavailable("down")):
        res = client.post(
            "/api/challenges",
            json={"opponent_team_id": 2, "court_id": 10, "start_time": "2026-10-18T18:00"},
            headers=auth_headers(),
        )
    assert res.status_code == 503
    body = res.get_json()
    assert body["error"] == "teams_unavailable"
    assert "unavailable" in body["message"].lower()


def test_create_challenge_own_team_400(client):
    def summaries(tid):
        return {1: RETIRO, 2: CHAMBERI}.get(tid)

    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.get_team_summary", side_effect=summaries
    ), patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_court", return_value=COURT
    ), patch("games.routes.store.list_accepted", return_value=[]):
        res = client.post(
            "/api/challenges",
            json={"opponent_team_id": 1, "court_id": 10, "start_time": "2026-10-18T18:00"},
            headers=auth_headers(),
        )
    assert res.status_code == 400
    assert any("own team" in e for e in res.get_json()["errors"])


def test_create_challenge_clash_400(client):
    def summaries(tid):
        return {1: RETIRO, 2: CHAMBERI}.get(tid)

    existing = {
        "id": 7,
        "challenger_team_id": 1,
        "opponent_team_id": 3,
        "court_id": 99,
        "start_time": "2026-10-18T19:00",
        "format": "5v5",
        "status": "accepted",
    }
    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.get_team_summary", side_effect=summaries
    ), patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_court", return_value=COURT
    ), patch("games.routes.store.list_accepted", return_value=[existing]):
        res = client.post(
            "/api/challenges",
            json={"opponent_team_id": 2, "court_id": 10, "start_time": "2026-10-18T18:00"},
            headers=auth_headers(),
        )
    assert res.status_code == 400
    assert any("already has a game" in e for e in res.get_json()["errors"])


def test_create_challenge_bad_ids_and_missing_challenger(client):
    with patch("games.routes.get_team_summary", return_value=None), patch(
        "games.routes.db.get_conn", return_value=MagicMock()
    ):
        res = client.post(
            "/api/challenges",
            json={"opponent_team_id": "x", "court_id": "y", "start_time": "2026-10-18T18:00"},
            headers=auth_headers(),
        )
    assert res.status_code == 400


def test_create_challenge_with_note(client):
    def summaries(tid):
        return {1: RETIRO, 2: CHAMBERI}.get(tid)

    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.get_team_summary", side_effect=summaries
    ), patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_court", return_value=COURT
    ), patch("games.routes.store.list_accepted", return_value=[]), patch(
        "games.routes.store.create_challenge", return_value=5
    ) as mock_create, patch(
        "games.routes.store.get_challenge", return_value=PENDING
    ):
        res = client.post(
            "/api/challenges",
            json={
                "opponent_team_id": 2,
                "court_id": 10,
                "start_time": "2026-10-18T18:00",
                "note": "  bring water  ",
            },
            headers=auth_headers(),
        )
    assert res.status_code == 201
    assert mock_create.call_args[0][1].get("note") == "bring water"


# --- Accept / decline / cancel -----------------------------------------------

def test_opponent_can_accept(client):
    token = make_token(
        {"team_id": 2, "team_name": "Chamberí Hoops", "format": "5v5", "player_count": 5}
    )
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_challenge",
        side_effect=[PENDING, {**PENDING, "status": "accepted"}],
    ), patch("games.routes.store.list_accepted", return_value=[]), patch(
        "games.routes.store.set_status"
    ) as mock_set:
        res = client.post("/api/challenges/5/accept", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.get_json()["challenge"]["status"] == "accepted"
    mock_set.assert_called_once()


def test_challenger_cannot_accept(client):
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_challenge", return_value=PENDING
    ):
        res = client.post("/api/challenges/5/accept", headers=auth_headers())
    assert res.status_code == 400


def test_challenger_can_cancel(client):
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_challenge",
        side_effect=[PENDING, {**PENDING, "status": "cancelled"}],
    ), patch("games.routes.store.set_status") as mock_set:
        res = client.post("/api/challenges/5/cancel", headers=auth_headers())
    assert res.status_code == 200
    mock_set.assert_called_once()


def test_opponent_can_decline(client):
    token = make_token(
        {"team_id": 2, "team_name": "Chamberí Hoops", "format": "5v5", "player_count": 5}
    )
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_challenge",
        side_effect=[PENDING, {**PENDING, "status": "declined"}],
    ), patch("games.routes.store.set_status"):
        res = client.post("/api/challenges/5/decline", headers=auth_headers(token))
    assert res.status_code == 200


def test_respond_missing_challenge(client):
    token = make_token(
        {"team_id": 2, "team_name": "Chamberí Hoops", "format": "5v5", "player_count": 5}
    )
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_challenge", return_value=None
    ):
        res = client.post("/api/challenges/99/decline", headers=auth_headers(token))
    assert res.status_code == 404


def test_accept_clash_recheck(client):
    token = make_token(
        {"team_id": 2, "team_name": "Chamberí Hoops", "format": "5v5", "player_count": 5}
    )
    other = {
        "id": 7,
        "challenger_team_id": 2,
        "opponent_team_id": 3,
        "court_id": 99,
        "start_time": "2026-10-18T19:00",
        "format": "5v5",
        "status": "accepted",
    }
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_challenge", return_value=PENDING
    ), patch("games.routes.store.list_accepted", return_value=[other]):
        res = client.post("/api/challenges/5/accept", headers=auth_headers(token))
    assert res.status_code == 400


# --- Upcoming -----------------------------------------------------------------

def test_upcoming_enriches_names(client):
    game = {**PENDING, "status": "accepted"}
    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.db.get_conn", return_value=MagicMock()
    ), patch("games.routes.store.list_accepted", return_value=[game]), patch(
        "games.routes.store.get_court", return_value=COURT
    ), patch(
        "games.routes.get_team_summary",
        side_effect=lambda tid: {1: RETIRO, 2: CHAMBERI}[tid],
    ):
        res = client.get("/api/games/upcoming")
    assert res.status_code == 200
    body = res.get_json()
    assert body["games"][0]["challenger_name"] == "Retiro Five"
    assert "teams_degraded" not in body


def test_upcoming_degrades_when_teams_down(client):
    game = {**PENDING, "status": "accepted"}
    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.db.get_conn", return_value=MagicMock()
    ), patch("games.routes.store.list_accepted", return_value=[game]), patch(
        "games.routes.store.get_court", return_value=COURT
    ), patch("games.routes.get_team_summary", side_effect=TeamsUnavailable("down")):
        res = client.get("/api/games/upcoming")
    assert res.status_code == 200
    body = res.get_json()
    assert body["teams_degraded"] is True
    assert body["games"][0]["challenger_name"] is None


# --- Dashboard ----------------------------------------------------------------

def test_dashboard_503_when_teams_down(client):
    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.db.get_conn", return_value=MagicMock()
    ), patch("games.routes.store.list_challenges_for_team", return_value=[PENDING]), patch(
        "games.routes.store.attendance_for_team", return_value={}
    ), patch("games.routes.get_team_summary", side_effect=TeamsUnavailable("down")):
        res = client.get("/api/dashboard", headers=auth_headers())
    assert res.status_code == 503
    assert res.get_json()["error"] == "teams_unavailable"


def test_dashboard_ok_buckets(client):
    rows = [
        PENDING,  # received for team 2
        {**PENDING, "id": 6, "status": "accepted", "start_time": "2026-10-20T18:00"},  # upcoming
        {**PENDING, "id": 7, "status": "accepted", "start_time": "2026-10-01T18:00"},  # played
        {**PENDING, "id": 8, "status": "declined"},  # history
        {**PENDING, "id": 9, "challenger_team_id": 2, "opponent_team_id": 1, "status": "pending"},  # sent by 2
    ]
    token = make_token(
        {"team_id": 2, "team_name": "Chamberí Hoops", "format": "5v5", "player_count": 5}
    )
    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.db.get_conn", return_value=MagicMock()
    ), patch("games.routes.store.list_challenges_for_team", return_value=rows), patch(
        "games.routes.store.attendance_for_team", return_value={7: 4}
    ), patch("games.routes.store.get_court", return_value=COURT), patch(
        "games.routes.get_team_summary",
        side_effect=lambda tid: {1: RETIRO, 2: CHAMBERI}[tid],
    ):
        res = client.get("/api/dashboard", headers=auth_headers(token))
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["received"]) == 1
    assert len(body["sent"]) == 1
    assert len(body["upcoming"]) == 1
    assert len(body["played"]) == 1
    assert body["played"][0]["my_turnout"] == 4
    assert len(body["history"]) == 1


# --- Turnout ------------------------------------------------------------------

def test_turnout_ok(client):
    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.db.get_conn", return_value=MagicMock()
    ), patch("games.routes.store.get_challenge", return_value=PLAYED), patch(
        "games.routes.get_team_summary", return_value=RETIRO
    ), patch("games.routes.store.record_attendance") as mock_record:
        res = client.post(
            "/api/challenges/5/turnout",
            json={"players": 5},
            headers=auth_headers(),
        )
    assert res.status_code == 200
    assert res.get_json()["attendance"]["players_attended"] == 5
    mock_record.assert_called_once()


def test_turnout_teams_unavailable(client):
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_challenge", return_value=PLAYED
    ), patch("games.routes.get_team_summary", side_effect=TeamsUnavailable("down")):
        res = client.post(
            "/api/challenges/5/turnout",
            json={"players": 5},
            headers=auth_headers(),
        )
    assert res.status_code == 503


def test_turnout_missing_game(client):
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_challenge", return_value=None
    ):
        res = client.post(
            "/api/challenges/5/turnout",
            json={"players": 5},
            headers=auth_headers(),
        )
    assert res.status_code == 404


def test_turnout_team_gone(client):
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.get_challenge", return_value=PLAYED
    ), patch("games.routes.get_team_summary", return_value=None):
        res = client.post(
            "/api/challenges/5/turnout",
            json={"players": 5},
            headers=auth_headers(),
        )
    assert res.status_code == 400


def test_turnout_validation_error(client):
    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.db.get_conn", return_value=MagicMock()
    ), patch("games.routes.store.get_challenge", return_value=PLAYED), patch(
        "games.routes.get_team_summary", return_value=RETIRO
    ):
        res = client.post(
            "/api/challenges/5/turnout",
            json={"players": "lots"},
            headers=auth_headers(),
        )
    assert res.status_code == 400


# --- Stats --------------------------------------------------------------------

def test_stats_ok(client):
    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.db.get_conn", return_value=MagicMock()
    ), patch("games.routes.store.list_attendance", return_value=[]), patch(
        "games.routes.store.list_all_challenges", return_value=[]
    ), patch("games.routes.get_team_summary", return_value=None):
        res = client.get("/api/stats")
    assert res.status_code == 200
    assert res.get_json()["games_played"] == 0


def test_stats_degrades_when_teams_down(client):
    challenges = [
        {
            "id": 1,
            "challenger_team_id": 1,
            "opponent_team_id": 2,
            "court_id": 10,
            "start_time": "2026-10-01T18:00",
            "format": "5v5",
            "status": "accepted",
        }
    ]
    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.db.get_conn", return_value=MagicMock()
    ), patch("games.routes.store.list_attendance", return_value=[]), patch(
        "games.routes.store.list_all_challenges", return_value=challenges
    ), patch("games.routes.store.get_court", return_value=COURT), patch(
        "games.routes.get_team_summary", side_effect=TeamsUnavailable("down")
    ):
        res = client.get("/api/stats")
    assert res.status_code == 200
    body = res.get_json()
    assert body["teams_degraded"] is True
    assert body["most_active_teams"][0]["name"] is None
    assert body["most_active_teams"][0]["id"] == 1
    assert body["busiest_courts"][0]["label"] == "Madrid Río"


def test_stats_with_attendance_and_missing_court(client):
    challenges = [
        {
            "id": 1,
            "challenger_team_id": 1,
            "opponent_team_id": 2,
            "court_id": 99,
            "start_time": "2026-10-01T18:00",
            "format": "5v5",
            "status": "accepted",
        }
    ]
    attendance = [{"challenge_id": 1, "team_id": 1, "players_attended": 5}]
    with patch("games.routes.madrid_now", return_value=NOW), patch(
        "games.routes.db.get_conn", return_value=MagicMock()
    ), patch("games.routes.store.list_attendance", return_value=attendance), patch(
        "games.routes.store.list_all_challenges", return_value=challenges
    ), patch("games.routes.store.get_court", return_value=None), patch(
        "games.routes.get_team_summary",
        side_effect=lambda tid: {1: RETIRO, 2: CHAMBERI}.get(tid),
    ):
        res = client.get("/api/stats")
    assert res.status_code == 200
    body = res.get_json()
    assert body["busiest_courts"][0]["label"] == "99"
    assert body["most_active_teams"][0]["name"] == "Retiro Five"


# --- CORS ---------------------------------------------------------------------

def test_cors_header_present(client):
    client.application.config["UI_ORIGIN"] = "http://ui.example"
    with patch("games.routes.db.get_conn", return_value=MagicMock()), patch(
        "games.routes.store.list_courts", return_value=[]
    ):
        res = client.get("/api/courts")
    assert res.status_code == 200
    assert res.headers.get("Access-Control-Allow-Origin") == "http://ui.example"
