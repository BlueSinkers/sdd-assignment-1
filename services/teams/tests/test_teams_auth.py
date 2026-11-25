import auth


def sample_team():
    return {
        "id": 7,
        "name": "Retiro Five",
        "captain_name": "Sofia",
        "format": "5v5",
        "player_count": 5,
        "skill_level": "intermediate",
        "district": "Retiro",
    }


def test_token_roundtrip(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-for-auth")
    token = auth.issue_token(sample_team())
    restored = auth.team_from_token(token)
    assert restored["team_id"] == 7
    assert restored["team_name"] == "Retiro Five"
    assert restored["format"] == "5v5"
    assert restored["player_count"] == 5
    assert "password_hash" not in restored


def test_invalid_token_returns_none(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-for-auth")
    assert auth.team_from_token("not-a-real-token") is None
    assert auth.team_from_token("") is None
    assert auth.team_from_token(None) is None


def test_wrong_secret_rejects_token(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "secret-a")
    token = auth.issue_token(sample_team())
    monkeypatch.setenv("SECRET_KEY", "secret-b")
    assert auth.team_from_token(token) is None


def test_expired_token_returns_none(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-for-auth")
    token = auth.issue_token(sample_team())
    assert auth.team_from_token(token, max_age=-1) is None


def test_games_can_load_teams_token(monkeypatch):
    """Same SECRET_KEY + payload shape Games expects."""
    monkeypatch.setenv("SECRET_KEY", "shared-secret")
    token = auth.issue_token(sample_team())
    from itsdangerous import URLSafeTimedSerializer

    data = URLSafeTimedSerializer("shared-secret").loads(token)
    assert data["team_id"] == 7
    assert data["team_name"] == "Retiro Five"


def test_incomplete_payload_rejected(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-for-auth")
    from itsdangerous import URLSafeTimedSerializer

    token = URLSafeTimedSerializer("test-secret-for-auth").dumps({"team_id": 1})
    assert auth.team_from_token(token) is None

    # Non-dict payload
    token = URLSafeTimedSerializer("test-secret-for-auth").dumps("not-a-dict")
    assert auth.team_from_token(token) is None
