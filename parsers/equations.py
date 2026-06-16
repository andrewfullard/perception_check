from __future__ import annotations

from pathlib import Path

from perception.models import PerceptualEquation, PerceptualEquationDocument
from perception.xml_utils import (
    extract_raw_expression,
    normalize_expression,
    parse_xml_file,
)


def parse_equations_file(xml_file: str | Path) -> PerceptualEquationDocument:
    """Parse one <Equations> XML file into equation records."""
    xml_path = Path(xml_file)
    tree = parse_xml_file(xml_path)
    root = tree.getroot()

    if root.tag != "Equations":
        raise ValueError(
            f"Expected root tag 'Equations' in {xml_path}, found '{root.tag}'"
        )

    equations: dict[str, PerceptualEquation] = {}

    for child in root:
        if not isinstance(child.tag, str):
            continue

        raw_expression = extract_raw_expression(child)
        equation = PerceptualEquation(
            name=child.tag,
            raw_expression=raw_expression,
            normalized_expression=normalize_expression(raw_expression),
            source_file=xml_path,
        )
        equations[equation.name] = equation

    return PerceptualEquationDocument(source_file=xml_path, equations=equations)

def parse_equations_folder_recursive(
    folder: str | Path, pattern: str = "*.xml"
) -> list[PerceptualEquationDocument]:
    """Parse all equation XML files in a folder tree."""
    folder_path = Path(folder)
    documents: list[PerceptualEquationDocument] = []

    for xml_path in sorted(folder_path.rglob(pattern)):
        if xml_path.is_file():
            documents.append(parse_equations_file(xml_path))

    return documents
