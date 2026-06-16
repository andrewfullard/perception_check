from pathlib import Path

import pytest

from perception.token_bounds import (
    TokenBounds,
    clamp_token_value,
    get_token_bounds,
    load_token_bounds,
)


def test_load_token_bounds_reads_numeric_and_null_bounds(tmp_path: Path) -> None:
    config_file = tmp_path / "bounds.json"
    config_file.write_text(
        """
        {
          "IsCampaignGame": {"min": 0, "max": 1},
          "SpaceTotal": {"min": null, "max": 120.5}
        }
        """,
        encoding="utf-8",
    )

    bounds = load_token_bounds(config_file)

    assert bounds["IsCampaignGame"] == TokenBounds(min_value=0.0, max_value=1.0)
    assert bounds["SpaceTotal"] == TokenBounds(min_value=None, max_value=120.5)


def test_load_token_bounds_rejects_min_greater_than_max(tmp_path: Path) -> None:
    config_file = tmp_path / "invalid_bounds.json"
    config_file.write_text(
        '{"Force": {"min": 10, "max": 5}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="min cannot exceed max"):
        load_token_bounds(config_file)


def test_get_token_bounds_matches_game_aliases() -> None:
    bounds_map = {
        "IsCampaignGame": TokenBounds(min_value=0.0, max_value=1.0),
    }

    assert get_token_bounds("Game.IsCampaignGame", bounds_map) == TokenBounds(
        min_value=0.0,
        max_value=1.0,
    )


def test_get_token_bounds_does_not_use_variable_prefix_aliases() -> None:
    bounds_map = {
        "Variable_Target": TokenBounds(min_value=0.0, max_value=100.0),
    }

    assert get_token_bounds("Variable.Target", bounds_map) is None


def test_get_token_bounds_matches_final_literal_in_chained_variable_token() -> None:
    bounds_map = {
        "HasSpaceUnitsBitfield": TokenBounds(min_value=0.0, max_value=1.0),
    }

    assert get_token_bounds(
        'Variable_Target.FriendlyForce.HasSpaceUnitsBitfield {Parameter_Type = "Ackbar_Home_One"}',
        bounds_map,
    ) == TokenBounds(min_value=0.0, max_value=1.0)


def test_clamp_token_value_applies_bounds_and_preserves_unbounded_values() -> None:
    bounds_map = {
        "Income": TokenBounds(min_value=0.0, max_value=10.0),
    }

    assert clamp_token_value("Game.Income", "99", bounds_map) == "10"
    assert clamp_token_value("Game.Income", "-3", bounds_map) == "0"
    assert clamp_token_value("Game.UnknownToken", "99", bounds_map) == "99"


def test_clamp_token_value_rejects_non_numeric_when_bounded() -> None:
    bounds_map = {
        "Income": TokenBounds(min_value=0.0, max_value=10.0),
    }

    with pytest.raises(ValueError, match="requires a numeric value"):
        clamp_token_value("Game.Income", "abc", bounds_map)
