from pathlib import Path

import pytest

from perceptual_equations_parser import (
    GoalDocument,
    GoalFunctionDocument,
    PerceptualEquationsParser,
)


def _write_equations_xml(path: Path, equations: dict[str, str]) -> None:
    lines = ['<?xml version="1.0"?>', "<Equations>"]
    for name, body in equations.items():
        lines.append(f"  <{name}>")
        lines.append(body)
        lines.append(f"  </{name}>")
    lines.append("</Equations>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_non_equations_xml(path: Path) -> None:
    path.write_text(
        '<?xml version="1.0"?>\n<NotEquations><A>1</A></NotEquations>\n',
        encoding="utf-8",
    )


def _write_functionset_xml(path: Path, entries: dict[str, tuple[str, str]]) -> None:
    lines = ['<?xml version="1.0"?>', "<FunctionSet>"]
    for name, (goal_name, function_name) in entries.items():
        lines.append(f"  <{name}>")
        lines.append(f"    <Goal>{goal_name}</Goal>")
        lines.append(f"    <Function>{function_name}</Function>")
        lines.append(f"  </{name}>")
    lines.append("</FunctionSet>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_goals_xml(path: Path, entries: dict[str, dict[str, str]]) -> None:
    lines = ['<?xml version="1.0"?>', "<Goals>"]
    for name, fields in entries.items():
        lines.append(f"  <{name}>")
        for key, value in fields.items():
            lines.append(f"    <{key}>{value}</{key}>")
        lines.append(f"  </{name}>")
    lines.append("</Goals>")
    path.write_text("\n".join(lines), encoding="utf-8")


def test_parse_file_creates_equation_objects_with_raw_and_normalized_text(
    tmp_path: Path,
) -> None:
    xml_file = tmp_path / "basic.xml"
    _write_equations_xml(
        xml_file,
        {
            "DisplayDifficulty": "    0\n    +\n    2.0    ",
            "IsCampaign": "Game.IsCampaignGame",
        },
    )

    parser = PerceptualEquationsParser()
    document = parser.parse_file(xml_file)

    assert document.source_file == xml_file
    assert len(document.equations) == 2

    difficulty = document.require("DisplayDifficulty")
    assert difficulty.source_file == xml_file
    assert "\n" in difficulty.raw_expression
    assert difficulty.normalized_expression == "0 + 2.0"

    campaign = document.require("IsCampaign")
    assert campaign.normalized_expression == "Game.IsCampaignGame"


def test_parse_file_rejects_wrong_root_tag(tmp_path: Path) -> None:
    xml_file = tmp_path / "invalid.xml"
    _write_non_equations_xml(xml_file)

    parser = PerceptualEquationsParser()

    with pytest.raises(ValueError, match="Expected root tag 'Equations'"):
        parser.parse_file(xml_file)


def test_parse_folder_and_recursive_modes(tmp_path: Path) -> None:
    top_file = tmp_path / "top.xml"
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested_file = nested_dir / "nested.xml"

    _write_equations_xml(top_file, {"TopOnly": "1"})
    _write_equations_xml(nested_file, {"NestedOnly": "2"})

    parser = PerceptualEquationsParser()

    non_recursive_docs = parser.parse_folder(tmp_path)
    recursive_docs = parser.parse_folder_recursive(tmp_path)

    assert [doc.source_file.name for doc in non_recursive_docs] == ["top.xml"]
    assert sorted(doc.source_file.name for doc in recursive_docs) == [
        "nested.xml",
        "top.xml",
    ]


def test_parse_layer_rejects_duplicate_equation_names_within_layer(
    tmp_path: Path,
) -> None:
    layer_dir = tmp_path / "Base"
    layer_dir.mkdir()

    _write_equations_xml(layer_dir / "one.xml", {"Shared": "1"})
    _write_equations_xml(layer_dir / "two.xml", {"Shared": "2"})

    parser = PerceptualEquationsParser()

    with pytest.raises(ValueError, match="Duplicate equation names found within layer"):
        parser.parse_layer("Base", layer_dir)


def test_build_index_applies_later_layer_override_and_keeps_history(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "Data"
    fotr_dir = tmp_path / "FotR"
    tr_dir = tmp_path / "TR"
    base_dir.mkdir()
    fotr_dir.mkdir()
    tr_dir.mkdir()

    _write_equations_xml(base_dir / "base.xml", {"Budget": "1", "OnlyBase": "10"})
    _write_equations_xml(fotr_dir / "fotr.xml", {"Budget": "2", "OnlyFotR": "20"})
    _write_equations_xml(tr_dir / "tr.xml", {"Budget": "3", "OnlyTR": "30"})

    parser = PerceptualEquationsParser()
    index = parser.build_index_from_folders(
        [
            ("Data", base_dir),
            ("FotR", fotr_dir),
            ("TR", tr_dir),
        ]
    )

    assert index.require("Budget").normalized_expression == "3"
    assert index.layer_for("Budget") == "TR"

    history = index.definitions_for("Budget")
    assert [layer for layer, _eq in history] == ["Data", "FotR", "TR"]
    assert [eq.normalized_expression for _layer, eq in history] == ["1", "2", "3"]

    assert index.layer_for("OnlyBase") == "Data"
    assert index.layer_for("OnlyFotR") == "FotR"
    assert index.layer_for("OnlyTR") == "TR"


def test_index_require_raises_for_missing_name(tmp_path: Path) -> None:
    base_dir = tmp_path / "Data"
    base_dir.mkdir()
    _write_equations_xml(base_dir / "base.xml", {"A": "1"})

    parser = PerceptualEquationsParser()
    index = parser.build_index_from_folders([("Data", base_dir)])

    with pytest.raises(KeyError, match="not found"):
        index.require("MissingEquation")


def test_parse_goal_functions_file_produces_prefixed_entries(tmp_path: Path) -> None:
    xml_file = tmp_path / "functions.xml"
    _write_functionset_xml(
        xml_file,
        {
            "Build_Space_Forces": (
                "Build_Space_Forces",
                "Allow_Blind_Space_Production",
            )
        },
    )

    parser = PerceptualEquationsParser()
    document = parser.parse_goal_functions_file(xml_file)
    assert isinstance(document, GoalFunctionDocument)

    entry = document.require("GoalFunction::Build_Space_Forces")
    assert entry.source_file == xml_file
    assert entry.normalized_expression == (
        "Goal=Build_Space_Forces\nFunction=Allow_Blind_Space_Production"
    )


def test_parse_goals_file_produces_prefixed_entries(tmp_path: Path) -> None:
    xml_file = tmp_path / "goals.xml"
    _write_goals_xml(
        xml_file,
        {
            "Conquer_Pirate": {
                "GameMode": "Galactic",
                "Category": "Offensive",
            }
        },
    )

    parser = PerceptualEquationsParser()
    document = parser.parse_goals_file(xml_file)
    assert isinstance(document, GoalDocument)

    entry = document.require("Goal::Conquer_Pirate")
    assert entry.source_file == xml_file
    assert entry.normalized_expression == "GameMode=Galactic\nCategory=Offensive"


def test_parse_goal_folders_collect_documents(tmp_path: Path) -> None:
    goal_functions_dir = tmp_path / "GoalFunctions"
    goals_dir = tmp_path / "Goals"
    goal_functions_dir.mkdir()
    goals_dir.mkdir()

    _write_functionset_xml(
        goal_functions_dir / "a.xml",
        {"One": ("One", "OneFunction")},
    )
    _write_goals_xml(
        goals_dir / "b.xml",
        {"GoalA": {"Category": "Always"}},
    )

    parser = PerceptualEquationsParser()
    goal_function_docs = parser.parse_goal_functions_folder(goal_functions_dir)
    goal_docs = parser.parse_goals_folder(goals_dir)

    assert len(goal_function_docs) == 1
    assert len(goal_docs) == 1
    assert isinstance(goal_function_docs[0], GoalFunctionDocument)
    assert isinstance(goal_docs[0], GoalDocument)
    assert goal_function_docs[0].get("GoalFunction::One") is not None
    assert goal_docs[0].get("Goal::GoalA") is not None
