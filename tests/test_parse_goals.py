from pathlib import Path

import pytest

from perceptual_equations_parser import (
    AIPlayerDocument,
    AITemplateDocument,
    GoalDocument,
    GoalFunctionDocument,
    PerceptualEquationsParser,
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


def _write_player_xml(path: Path, name: str, templates: dict[str, str]) -> None:
    lines = ['<?xml version="1.0"?>', "<AIPlayerType>"]
    lines.append(f"  <Name>{name}</Name>")
    lines.append("  <Templates>")
    for mode, template_name in templates.items():
        lines.append(f"    <{mode}>{template_name}</{mode}>")
    lines.append("  </Templates>")
    lines.append("</AIPlayerType>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_templates_xml(path: Path, entries: dict[str, dict[str, str]]) -> None:
    lines = ['<?xml version="1.0"?>', "<AITemplates>"]
    for name, fields in entries.items():
        lines.append(f"  <{name}>")
        for key, value in fields.items():
            lines.append(f"    <{key}>{value}</{key}>")
        lines.append(f"  </{name}>")
    lines.append("</AITemplates>")
    path.write_text("\n".join(lines), encoding="utf-8")


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


def test_parse_players_file_produces_prefixed_single_entry(tmp_path: Path) -> None:
    xml_file = tmp_path / "empire.xml"
    _write_player_xml(
        xml_file,
        name="BasicEmpire",
        templates={
            "Space": "Generic_Space",
            "Land": "Generic_Land",
            "Galactic": "Generic_AI_Default",
        },
    )

    parser = PerceptualEquationsParser()
    document = parser.parse_players_file(xml_file)
    assert isinstance(document, AIPlayerDocument)

    entry = document.require("Player::BasicEmpire")
    assert entry.source_file == xml_file
    assert "Name=BasicEmpire" in entry.normalized_expression
    assert "Templates/Space=Generic_Space" in entry.normalized_expression
    assert "Templates/Land=Generic_Land" in entry.normalized_expression
    assert "Templates/Galactic=Generic_AI_Default" in (entry.normalized_expression)


def test_parse_players_file_rejects_missing_player_name(tmp_path: Path) -> None:
    xml_file = tmp_path / "player_missing_name.xml"
    xml_file.write_text(
        '<?xml version="1.0"?>\n<AIPlayerType><Templates><Galactic>Default</Galactic></Templates></AIPlayerType>\n',
        encoding="utf-8",
    )

    parser = PerceptualEquationsParser()
    with pytest.raises(ValueError, match="Expected non-empty <Name>"):
        parser.parse_players_file(xml_file)


def test_parse_templates_file_produces_prefixed_entries(tmp_path: Path) -> None:
    xml_file = tmp_path / "templates.xml"
    _write_templates_xml(
        xml_file,
        {
            "Basic_Empire_Default": {
                "Priority": "1",
                "Trigger": "One",
            }
        },
    )

    parser = PerceptualEquationsParser()
    document = parser.parse_templates_file(xml_file)
    assert isinstance(document, AITemplateDocument)

    entry = document.require("Template::Basic_Empire_Default")
    assert entry.source_file == xml_file
    assert entry.normalized_expression == "Priority=1\nTrigger=One"


def test_parse_templates_file_preserves_nested_tag_paths(tmp_path: Path) -> None:
    xml_file = tmp_path / "nested_templates.xml"
    xml_file.write_text(
        (
            '<?xml version="1.0"?>\n'
            "<AITemplates>\n"
            "  <Basic_Empire_Default>\n"
            "    <Turn_Off>\n"
            "      <Goals>Goal_1 Goal_2</Goals>\n"
            "    </Turn_Off>\n"
            "  </Basic_Empire_Default>\n"
            "</AITemplates>\n"
        ),
        encoding="utf-8",
    )

    parser = PerceptualEquationsParser()
    document = parser.parse_templates_file(xml_file)
    entry = document.require("Template::Basic_Empire_Default")

    assert "Turn_Off/Goals=Goal_1 Goal_2" in entry.normalized_expression


def test_parse_players_and_templates_folders_collect_documents(tmp_path: Path) -> None:
    players_dir = tmp_path / "Players"
    templates_dir = tmp_path / "Templates"
    players_dir.mkdir()
    templates_dir.mkdir()

    _write_player_xml(
        players_dir / "empire.xml",
        name="BasicEmpire",
        templates={"Galactic": "Generic_AI_Default"},
    )
    _write_templates_xml(
        templates_dir / "templates.xml",
        {"Basic_Empire_Default": {"Priority": "1"}},
    )

    parser = PerceptualEquationsParser()
    player_docs = parser.parse_players_folder(players_dir)
    template_docs = parser.parse_templates_folder(templates_dir)

    assert len(player_docs) == 1
    assert len(template_docs) == 1
    assert isinstance(player_docs[0], AIPlayerDocument)
    assert isinstance(template_docs[0], AITemplateDocument)
    assert player_docs[0].get("Player::BasicEmpire") is not None
    assert template_docs[0].get("Template::Basic_Empire_Default") is not None
