from __future__ import annotations

from pathlib import Path

from perception.models import Document, make_document
from perception.xml_utils import (
    extract_structured_entry_text_with_paths,
    parse_named_entries_text_file,
    parse_single_named_entry_text_file,
)


def parse_players_file(xml_file: str | Path) -> Document:
    """Parse one <AIPlayerType> XML file into one prefixed player entry."""
    source_file, texts = parse_single_named_entry_text_file(
        xml_file=xml_file,
        expected_root_tag="AIPlayerType",
        name_prefix="Player::",
        name_tag="Name",
        entry_text_extractor=extract_structured_entry_text_with_paths,
    )
    return make_document(source_file, texts, "player")


def parse_templates_file(xml_file: str | Path) -> Document:
    """Parse one <AITemplates> XML file into prefixed template entries."""
    source_file, texts = parse_named_entries_text_file(
        xml_file=xml_file,
        expected_root_tag="AITemplates",
        name_prefix="Template::",
        entry_text_extractor=extract_structured_entry_text_with_paths,
    )
    return make_document(source_file, texts, "template")

