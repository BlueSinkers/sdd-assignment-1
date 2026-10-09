from teams import logic


def valid_form(**overrides):
    form = {
        "name": "Lavapiés Ballers",
        "password": "secret123",
        "captain_name": "Abhi",
        "format": "3v3",
        "player_count": "4",
        "skill_level": "casual",
        "district": "Lavapiés",
    }
    form.update(overrides)
    return form


def test_valid_team_is_accepted():
    team, errors = logic.validate_new_team(valid_form())
    assert errors == []
    assert team["name"] == "Lavapiés Ballers"
    assert team["player_count"] == 4


def test_password_is_hashed_not_stored_plain():
    team, _ = logic.validate_new_team(valid_form())
    assert "password" not in team
    assert team["password_hash"] != "secret123"
    assert logic.password_matches(team["password_hash"], "secret123")
    assert not logic.password_matches(team["password_hash"], "wrong-password")


def test_whitespace_is_trimmed_and_blank_district_becomes_none():
    team, _ = logic.validate_new_team(valid_form(name="  Retiro Five  ", district="   "))
    assert team["name"] == "Retiro Five"
    assert team["district"] is None


def test_blank_name_is_rejected():
    team, errors = logic.validate_new_team(valid_form(name="   "))
    assert team is None
    assert "Team name is required." in errors


def test_too_long_name_is_rejected():
    _, errors = logic.validate_new_team(valid_form(name="x" * 41))
    assert any("at most" in e for e in errors)


def test_short_password_is_rejected():
    _, errors = logic.validate_new_team(valid_form(password="abc"))
    assert any("Password" in e for e in errors)


def test_missing_captain_is_rejected():
    _, errors = logic.validate_new_team(valid_form(captain_name=""))
    assert "Captain name is required." in errors


def test_unknown_format_is_rejected():
    _, errors = logic.validate_new_team(valid_form(format="4v4"))
    assert "Format must be 3v3 or 5v5." in errors


def test_unknown_skill_level_is_rejected():
    _, errors = logic.validate_new_team(valid_form(skill_level="pro"))
    assert "Pick a skill level." in errors


def test_non_number_player_count_is_rejected():
    _, errors = logic.validate_new_team(valid_form(player_count="lots"))
    assert "Number of players must be a whole number." in errors


def test_3v3_team_needs_at_least_3_players():
    _, errors = logic.validate_new_team(valid_form(format="3v3", player_count="2"))
    assert "A 3v3 team needs at least 3 players." in errors


def test_5v5_team_needs_at_least_5_players():
    _, errors = logic.validate_new_team(valid_form(format="5v5", player_count="4"))
    assert "A 5v5 team needs at least 5 players." in errors


def test_exact_minimum_players_is_allowed():
    _, errors = logic.validate_new_team(valid_form(format="5v5", player_count="5"))
    assert errors == []


def test_all_errors_are_reported_at_once():
    _, errors = logic.validate_new_team({})
    assert len(errors) >= 5
