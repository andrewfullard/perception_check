from __future__ import annotations

from functools import partial
from pathlib import Path

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


parse_players_folder = partial(
    parse_documents_folder,
    parse_document=parse_players_file,
)
parse_players_folder.__doc__ = "Parse all Players XML files in one folder (non-recursive)."

parse_templates_folder = partial(
    parse_documents_folder,
    parse_document=parse_templates_file,
)
parse_templates_folder.__doc__ = (
    "Parse all Templates XML files in one folder (non-recursive)."
)
