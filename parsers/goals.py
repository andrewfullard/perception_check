from __future__ import annotations

from functools import partial
from pathlib import Path

from perception.models import Document, Entry
from perception.xml_utils import (
    parse_documents_folder,
    parse_named_entries_text_file,
)


def parse_goal_functions_file(xml_file: str | Path) -> Document:
    """Parse one <FunctionSet> XML file into prefixed entries."""
    source_file, texts = parse_named_entries_text_file(
        xml_file=xml_file,
        expected_root_tag="FunctionSet",
        name_prefix="GoalFunction::",
    )
    return _document(source_file, texts, "goal_function")


def parse_goals_file(xml_file: str | Path) -> Document:
    """Parse one <Goals> XML file into prefixed entries."""
    source_file, texts = parse_named_entries_text_file(
        xml_file=xml_file,
        expected_root_tag="Goals",
        name_prefix="Goal::",
    )
    return _document(source_file, texts, "goal")


def _document(source_file: Path, texts: dict[str, str], entry_type: str) -> Document:
    return Document(
        source_file=source_file,
        entries={
            name: Entry(name, text, text, source_file, entry_type)
            for name, text in texts.items()
        },
    )


parse_goal_functions_folder = partial(
    parse_documents_folder,
    parse_document=parse_goal_functions_file,
)
parse_goal_functions_folder.__doc__ = (
    "Parse all GoalFunctions XML files in one folder (non-recursive)."
)

parse_goals_folder = partial(
    parse_documents_folder,
    parse_document=parse_goals_file,
)
parse_goals_folder.__doc__ = "Parse all Goals XML files in one folder (non-recursive)."
