from __future__ import annotations

from pathlib import Path
from typing import List

from data_models import (
    AIPlayerDocument,
    AIPlayerEntry,
    AITemplateDocument,
    AITemplateEntry,
)
from xml_common import (
    extract_structured_entry_text_with_paths,
    parse_documents_folder,
    parse_named_entries_text_file,
    parse_single_named_entry_text_file,
)


def parse_players_file(xml_file: str | Path) -> AIPlayerDocument:
    """Parse one <AIPlayerType> XML file into one prefixed player entry."""
    source_file, entries = parse_single_named_entry_text_file(
        xml_file=xml_file,
        expected_root_tag="AIPlayerType",
        name_prefix="Player::",
        name_tag="Name",
        entry_text_extractor=extract_structured_entry_text_with_paths,
    )
    return AIPlayerDocument(
        source_file=source_file,
        players={
            name: AIPlayerEntry(
                name=name,
                raw_expression=normalized_text,
                normalized_expression=normalized_text,
                source_file=source_file,
            )
            for name, normalized_text in entries.items()
        },
    )


def parse_templates_file(xml_file: str | Path) -> AITemplateDocument:
    """Parse one <AITemplates> XML file into prefixed template entries."""
    source_file, entries = parse_named_entries_text_file(
        xml_file=xml_file,
        expected_root_tag="AITemplates",
        name_prefix="Template::",
        entry_text_extractor=extract_structured_entry_text_with_paths,
    )
    return AITemplateDocument(
        source_file=source_file,
        templates={
            name: AITemplateEntry(
                name=name,
                raw_expression=normalized_text,
                normalized_expression=normalized_text,
                source_file=source_file,
            )
            for name, normalized_text in entries.items()
        },
    )


def parse_players_folder(
    folder: str | Path, pattern: str = "*.xml"
) -> List[AIPlayerDocument]:
    """Parse all Players XML files in one folder (non-recursive)."""
    return parse_documents_folder(folder, parse_players_file, pattern=pattern)


def parse_templates_folder(
    folder: str | Path, pattern: str = "*.xml"
) -> List[AITemplateDocument]:
    """Parse all Templates XML files in one folder (non-recursive)."""
    return parse_documents_folder(folder, parse_templates_file, pattern=pattern)
