from pathlib import Path

from perceptual_equations_parser import PerceptualEquationsParser
from perceptual_equations_range import PerceptualEquationRangeAnalyzer
from perceptual_token_bounds import TokenBounds


def _write_equations_xml(path: Path, equations: dict[str, str]) -> None:
    lines = ['<?xml version="1.0"?>', "<Equations>"]
    for name, body in equations.items():
        lines.append(f"  <{name}>{body}</{name}>")
    lines.append("</Equations>")
    path.write_text("\n".join(lines), encoding="utf-8")


def test_range_uses_game_token_bounds_and_expression_math(tmp_path: Path) -> None:
    data_dir = tmp_path / "Data"
    data_dir.mkdir()
    _write_equations_xml(
        data_dir / "eq.xml",
        {
            "Score": "Game.Income * 2 + 1",
        },
    )

    parser = PerceptualEquationsParser()
    index = parser.build_index_from_folders([("Data", data_dir)])
    analyzer = PerceptualEquationRangeAnalyzer(
        index,
        {
            "Income": TokenBounds(min_value=0.0, max_value=1.0),
        },
    )

    score_range = analyzer.compute_equation_range("Score")

    assert score_range.minimum == 1.0
    assert score_range.maximum == 3.0


def test_range_follows_function_token_references(tmp_path: Path) -> None:
    data_dir = tmp_path / "Data"
    data_dir.mkdir()
    _write_equations_xml(
        data_dir / "eq.xml",
        {
            "BaseScore": "Game.Income",
            "DerivedScore": "Function_BaseScore.Evaluate + 2",
        },
    )

    parser = PerceptualEquationsParser()
    index = parser.build_index_from_folders([("Data", data_dir)])
    analyzer = PerceptualEquationRangeAnalyzer(
        index,
        {
            "Income": TokenBounds(min_value=0.0, max_value=1.0),
        },
    )

    derived_range = analyzer.compute_equation_range("DerivedScore")

    assert derived_range.minimum == 2.0
    assert derived_range.maximum == 3.0


def test_range_defaults_to_infinite_when_token_bounds_missing(tmp_path: Path) -> None:
    data_dir = tmp_path / "Data"
    data_dir.mkdir()
    _write_equations_xml(
        data_dir / "eq.xml",
        {
            "UnknownTokenEquation": "Game.DoesNotExist + 1",
        },
    )

    parser = PerceptualEquationsParser()
    index = parser.build_index_from_folders([("Data", data_dir)])
    analyzer = PerceptualEquationRangeAnalyzer(index, {})

    unknown_range = analyzer.compute_equation_range("UnknownTokenEquation")

    assert unknown_range.minimum == float("-inf")
    assert unknown_range.maximum == float("inf")


def test_range_uses_final_literal_bounds_for_chained_variable_tokens(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "Data"
    data_dir.mkdir()
    _write_equations_xml(
        data_dir / "eq.xml",
        {
            "HeroScore": (
                'Variable_Target.FriendlyForce.HasSpaceUnitsBitfield {Parameter_Type = "Ackbar_Home_One"} '
                '+ Variable_Target.FriendlyForce.HasSpaceUnitsBitfield {Parameter_Type = "Ackbar_Galactic_Voyager"} '
                '+ Variable_Target.FriendlyForce.HasSpaceUnitsBitfield {Parameter_Type = "Ackbar_Guardian"}'
            )
        },
    )

    parser = PerceptualEquationsParser()
    index = parser.build_index_from_folders([("Data", data_dir)])
    analyzer = PerceptualEquationRangeAnalyzer(
        index,
        {
            "HasSpaceUnitsBitfield": TokenBounds(min_value=0.0, max_value=1.0),
        },
    )

    hero_range = analyzer.compute_equation_range("HeroScore")

    assert hero_range.minimum == 0.0
    assert hero_range.maximum == 3.0
