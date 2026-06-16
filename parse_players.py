from __future__ import annotations

from functools import partial
from pathlib import Path

from data_models import Document, Entry
from xml_common import (
    extract_structured_entry_text_with_paths,
    parse_documents_folder,
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
    return _document(source_file, texts, "player")


def parse_templates_file(xml_file: str | Path) -> Document:
    """Parse one <AITemplates> XML file into prefixed template entries."""
    source_file, texts = parse_named_entries_text_file(
        xml_file=xml_file,
        expected_root_tag="AITemplates",
        name_prefix="Template::",
        entry_text_extractor=extract_structured_entry_text_with_paths,
    )
    return _document(source_file, texts, "template")


def _document(source_file: Path, texts: dict[str, str], entry_type: str) -> Document:
    return Document(
        source_file=source_file,
        entries={
            name: Entry(name, text, text, source_file, entry_type)
            for name, text in texts.items()
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
