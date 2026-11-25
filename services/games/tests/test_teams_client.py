from unittest.mock import MagicMock, patch

import pytest
import requests

from games.teams_client import TeamsUnavailable, get_team_summary


def test_get_team_summary_ok():
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "id": 1,
        "name": "Retiro",
        "format": "5v5",
        "player_count": 6,
    }
    with patch("games.teams_client.requests.get", return_value=response) as get:
        summary = get_team_summary(1)
    assert summary["name"] == "Retiro"
    get.assert_called_once()
    assert get.call_args.kwargs["timeout"] == 2.0


def test_get_team_summary_404():
    response = MagicMock()
    response.status_code = 404
    with patch("games.teams_client.requests.get", return_value=response):
        assert get_team_summary(99) is None


def test_get_team_summary_timeout():
    with patch(
        "games.teams_client.requests.get",
        side_effect=requests.Timeout("slow"),
    ):
        with pytest.raises(TeamsUnavailable):
            get_team_summary(1)


def test_get_team_summary_5xx():
    response = MagicMock()
    response.status_code = 503
    with patch("games.teams_client.requests.get", return_value=response):
        with pytest.raises(TeamsUnavailable):
            get_team_summary(1)


def test_get_team_summary_connection_error():
    with patch(
        "games.teams_client.requests.get",
        side_effect=requests.ConnectionError("down"),
    ):
        with pytest.raises(TeamsUnavailable):
            get_team_summary(1)


def test_get_team_summary_other_4xx_is_none():
    response = MagicMock()
    response.status_code = 400
    with patch("games.teams_client.requests.get", return_value=response):
        assert get_team_summary(1) is None


def test_madrid_now_is_naive():
    from games.routes import madrid_now

    now = madrid_now()
    assert now.tzinfo is None
