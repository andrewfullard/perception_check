from __future__ import annotations

from pathlib import Path
from typing import List

from data_models import (
    GoalDocument,
    GoalEntry,
    GoalFunctionDocument,
    GoalFunctionEntry,
)
from xml_common import (
    parse_documents_folder,
    parse_named_entries_text_file,
)


def parse_goal_functions_file(xml_file: str | Path) -> GoalFunctionDocument:
    """Parse one <FunctionSet> XML file into prefixed entries."""
    source_file, entries = parse_named_entries_text_file(
        xml_file=xml_file,
        expected_root_tag="FunctionSet",
        name_prefix="GoalFunction::",
    )
    return GoalFunctionDocument(
        source_file=source_file,
        goal_functions={
            name: GoalFunctionEntry(
                name=name,
                raw_expression=normalized_text,
                normalized_expression=normalized_text,
                source_file=source_file,
            )
            for name, normalized_text in entries.items()
        },
    )


def parse_goals_file(xml_file: str | Path) -> GoalDocument:
    """Parse one <Goals> XML file into prefixed entries."""
    source_file, entries = parse_named_entries_text_file(
        xml_file=xml_file,
        expected_root_tag="Goals",
        name_prefix="Goal::",
    )
    return GoalDocument(
        source_file=source_file,
        goals={
            name: GoalEntry(
                name=name,
                raw_expression=normalized_text,
                normalized_expression=normalized_text,
                source_file=source_file,
            )
            for name, normalized_text in entries.items()
        },
    )


def parse_goal_functions_folder(
    folder: str | Path, pattern: str = "*.xml"
) -> List[GoalFunctionDocument]:
    """Parse all GoalFunctions XML files in one folder (non-recursive)."""
    return parse_documents_folder(folder, parse_goal_functions_file, pattern=pattern)


def parse_goals_folder(
    folder: str | Path, pattern: str = "*.xml"
) -> List[GoalDocument]:
    """Parse all Goals XML files in one folder (non-recursive)."""
    return parse_documents_folder(folder, parse_goals_file, pattern=pattern)
