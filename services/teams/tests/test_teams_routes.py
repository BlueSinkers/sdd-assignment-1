"""Route tests with mocked store/db — no SQL Server required."""
from unittest.mock import MagicMock, patch

import pytest

import auth
from app import create_app
from teams.logic import hash_password, public_team


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("VERSION", "testsha")
    monkeypatch.setenv("UI_ORIGIN", "http://localhost:8080")
    application = create_app(run_migrations=False)
    application.config["TESTING"] = True
    return application.test_client()


def _saved(**overrides):
    row = {
        "id": 1,
        "name": "Retiro Five",
        "password_hash": hash_password("secret123"),
        "captain_name": "Cap",
        "format": "5v5",
        "player_count": 6,
        "skill_level": "casual",
        "district": None,
        "badge_color": None,
    }
    row.update(overrides)
    return row


def test_health_ok(client):
    with patch("db.health_check_db", return_value=True):
        res = client.get("/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["db"] == "ok"
    assert body["status"] == "ok"
    assert body["version"] == "testsha"


def test_health_down(client):
    with patch("db.health_check_db", return_value=False):
        res = client.get("/health")
    assert res.status_code == 503
    assert res.get_json()["db"] == "error"


def test_register_success(client):
    saved = _saved()
    with patch("teams.routes.store") as store, patch("teams.routes.db") as db_mod:
        db_mod.get_conn.return_value = MagicMock()
        store.create_team.return_value = 1
        store.get_team.return_value = saved
        res = client.post(
            "/api/register",
            json={
                "name": "Retiro Five",
                "password": "secret123",
                "captain_name": "Cap",
                "format": "5v5",
                "player_count": 6,
                "skill_level": "casual",
            },
        )
    assert res.status_code == 201
    body = res.get_json()
    assert "token" in body
    assert body["team"]["name"] == "Retiro Five"
    assert "password_hash" not in body["team"]


def test_register_validation_error(client):
    res = client.post("/api/register", json={"name": ""})
    assert res.status_code == 400
    assert "errors" in res.get_json()


def test_register_duplicate_name(client):
    with patch("teams.routes.store") as store, patch("teams.routes.db") as db_mod:
        db_mod.get_conn.return_value = MagicMock()
        store.create_team.return_value = None
        res = client.post(
            "/api/register",
            json={
                "name": "Taken",
                "password": "secret123",
                "captain_name": "Cap",
                "format": "3v3",
                "player_count": 3,
                "skill_level": "casual",
            },
        )
    assert res.status_code == 400
    assert "already taken" in res.get_json()["errors"][0]


def test_login_success(client):
    with patch("teams.routes.store") as store, patch("teams.routes.db") as db_mod:
        db_mod.get_conn.return_value = MagicMock()
        store.get_team_by_name.return_value = _saved()
        res = client.post(
            "/api/login",
            json={"name": "Retiro Five", "password": "secret123"},
        )
    assert res.status_code == 200
    assert "token" in res.get_json()


def test_login_failure(client):
    with patch("teams.routes.store") as store, patch("teams.routes.db") as db_mod:
        db_mod.get_conn.return_value = MagicMock()
        store.get_team_by_name.return_value = None
        res = client.post(
            "/api/login",
            json={"name": "Nobody", "password": "nope"},
        )
    assert res.status_code == 401


def test_login_coerces_non_string_password(client):
    with patch("teams.routes.store") as store, patch("teams.routes.db") as db_mod:
        db_mod.get_conn.return_value = MagicMock()
        store.get_team_by_name.return_value = _saved(
            password_hash=hash_password("123456")
        )
        res = client.post(
            "/api/login",
            json={"name": "Retiro Five", "password": 123456},
        )
    assert res.status_code == 200


def test_list_teams(client):
    with patch("teams.routes.store") as store, patch("teams.routes.db"):
        store.list_teams.return_value = [
            {
                "id": 1,
                "name": "A",
                "captain_name": "C",
                "format": "5v5",
                "player_count": 5,
                "skill_level": "casual",
                "district": None,
                "badge_color": None,
            }
        ]
        res = client.get("/api/teams")
    assert res.status_code == 200
    assert res.get_json()[0]["name"] == "A"
    assert "password_hash" not in res.get_json()[0]


def test_team_summary_ok(client):
    with patch("teams.routes.store") as store, patch("teams.routes.db"):
        store.get_team_summary.return_value = {
            "id": 2,
            "name": "Chamberi",
            "format": "3v3",
            "player_count": 4,
        }
        res = client.get("/api/teams/2")
    assert res.status_code == 200
    assert res.get_json() == {
        "id": 2,
        "name": "Chamberi",
        "format": "3v3",
        "player_count": 4,
    }


def test_team_summary_404(client):
    with patch("teams.routes.store") as store, patch("teams.routes.db"):
        store.get_team_summary.return_value = None
        res = client.get("/api/teams/99")
    assert res.status_code == 404


def test_me_requires_token(client):
    res = client.get("/api/me")
    assert res.status_code == 401


def test_me_rejects_payload_without_team_id(client):
    with patch("teams.routes.auth.team_from_token", return_value={"format": "3v3"}):
        res = client.get(
            "/api/me",
            headers={"Authorization": "Bearer anything"},
        )
    assert res.status_code == 401


def test_me_with_valid_token(client, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    saved = _saved()
    token = auth.issue_token(public_team(saved))
    with patch("teams.routes.store") as store, patch("teams.routes.db") as db_mod:
        db_mod.get_conn.return_value = MagicMock()
        store.get_team.return_value = saved
        res = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.get_json()["id"] == 1
    assert "password_hash" not in res.get_json()


def test_me_team_gone(client, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    token = auth.issue_token(public_team(_saved()))
    with patch("teams.routes.store") as store, patch("teams.routes.db") as db_mod:
        db_mod.get_conn.return_value = MagicMock()
        store.get_team.return_value = None
        res = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_cors_header(client):
    with patch("db.health_check_db", return_value=True):
        res = client.get("/health")
    assert res.headers.get("Access-Control-Allow-Origin") == "http://localhost:8080"
