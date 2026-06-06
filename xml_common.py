from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
import re
import xml.etree.ElementTree as ET


_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_expression(text: str) -> str:
    """Collapse all whitespace to single spaces and trim ends."""
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def extract_raw_expression(element: ET.Element) -> str:
    """Return concatenated text content for an XML element."""
    return "".join(list(element.itertext()))


def extract_structured_entry_text(entry_element: ET.Element) -> str:
    """Return key/value text for non-equation AI nodes, one field per line."""
    fields: List[str] = []

    for child in entry_element:
        if not isinstance(child.tag, str):
            continue
        value = normalize_expression("".join(child.itertext()))
        if value:
            fields.append(f"{child.tag}={value}")
        else:
            fields.append(child.tag)

    if fields:
        return "\n".join(fields)

    return normalize_expression(extract_raw_expression(entry_element))


def parse_named_entries_text_file(
    xml_file: str | Path,
    expected_root_tag: str,
    name_prefix: str,
) -> Tuple[Path, Dict[str, str]]:
    """Parse direct root children into a prefixed name->summary text map."""
    xml_path = Path(xml_file)
    tree = ET.parse(xml_path)
    root = tree.getroot()

    if root.tag != expected_root_tag:
        raise ValueError(
            f"Expected root tag '{expected_root_tag}' in {xml_path}, found '{root.tag}'"
        )

    entries: Dict[str, str] = {}

    for child in root:
        if not isinstance(child.tag, str):
            continue

        summary_text = extract_structured_entry_text(child)
        entry_name = f"{name_prefix}{child.tag}"
        entries[entry_name] = summary_text

    return xml_path, entries


def parse_single_named_entry_text_file(
    xml_file: str | Path,
    expected_root_tag: str,
    name_prefix: str,
    name_tag: str = "Name",
) -> Tuple[Path, Dict[str, str]]:
    """Parse one XML root as a single prefixed name->summary text entry."""
    xml_path = Path(xml_file)
    tree = ET.parse(xml_path)
    root = tree.getroot()

    if root.tag != expected_root_tag:
        raise ValueError(
            f"Expected root tag '{expected_root_tag}' in {xml_path}, found '{root.tag}'"
        )

    entry_name_text = normalize_expression(root.findtext(name_tag, default=""))
    if not entry_name_text:
        raise ValueError(
            f"Expected non-empty <{name_tag}> in {xml_path} under '{expected_root_tag}'"
        )

    summary_text = extract_structured_entry_text(root)
    return xml_path, {f"{name_prefix}{entry_name_text}": summary_text}
