from __future__ import annotations

from pathlib import Path

from perception.models import Document, make_document
from perception.xml_utils import parse_named_entries_text_file


def parse_goal_functions_file(xml_file: str | Path) -> Document:
    """Parse one <FunctionSet> XML file into prefixed entries."""
    source_file, texts = parse_named_entries_text_file(
        xml_file=xml_file,
        expected_root_tag="FunctionSet",
        name_prefix="GoalFunction::",
    )
    return make_document(source_file, texts, "goal_function")


def parse_goals_file(xml_file: str | Path) -> Document:
    """Parse one <Goals> XML file into prefixed entries."""
    source_file, texts = parse_named_entries_text_file(
        xml_file=xml_file,
        expected_root_tag="Goals",
        name_prefix="Goal::",
    )
    return make_document(source_file, texts, "goal")

