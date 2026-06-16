from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class PerceptualEquation:
    """A single parsed AI entry represented as an equation-like record."""

    name: str
    raw_expression: str
    normalized_expression: str
    source_file: Path


@dataclass
class PerceptualEquationDocument:
    """A parsed XML file containing many named equation-like entries."""

    source_file: Path
    equations: dict[str, PerceptualEquation] = field(default_factory=dict)

    def get(self, equation_name: str) -> PerceptualEquation | None:
        return self.equations.get(equation_name)

    def require(self, equation_name: str) -> PerceptualEquation:
        equation = self.get(equation_name)
        if equation is None:
            raise KeyError(
                f"Equation '{equation_name}' not found in {self.source_file}"
            )
        return equation

    def __iter__(self) -> Iterator[PerceptualEquation]:
        return iter(self.equations.values())


@dataclass
class Entry:
    """A single parsed non-equation AI entry."""

    name: str
    raw_expression: str
    normalized_expression: str
    source_file: Path
    entry_type: str = "entry"


@dataclass
class Document:
    """A parsed XML file containing named non-equation AI entries."""

    source_file: Path
    entries: dict[str, Entry] = field(default_factory=dict)

    def get(self, name: str) -> Entry | None:
        return self.entries.get(name)

    def require(self, name: str) -> Entry:
        entry = self.get(name)
        if entry is None:
            raise KeyError(f"Entry '{name}' not found in {self.source_file}")
        return entry

    def __iter__(self) -> Iterator[Entry]:
        return iter(self.entries.values())


def make_document(source_file: Path, texts: dict[str, str], entry_type: str) -> Document:
    return Document(
        source_file=source_file,
        entries={
            name: Entry(name, text, text, source_file, entry_type)
            for name, text in texts.items()
        },
    )


@dataclass
class PerceptualEquationLayer:
    """A logical load layer, such as Data or a specific submod layer."""

    name: str
    documents: list[PerceptualEquationDocument] = field(default_factory=list)

    def __iter__(self) -> Iterator[PerceptualEquationDocument]:
        return iter(self.documents)


@dataclass
class PerceptualEquationIndex:
    """Resolved index across ordered layers (later layers override earlier layers)."""

    effective_equations: dict[str, PerceptualEquation] = field(default_factory=dict)
    effective_layers: dict[str, str] = field(default_factory=dict)
    all_definitions: dict[str, list[tuple[str, PerceptualEquation]]] = field(
        default_factory=dict
    )
    validation_errors: list[str] = field(default_factory=list)

    def get(self, equation_name: str) -> PerceptualEquation | None:
        return self.effective_equations.get(equation_name)

    def require(self, equation_name: str) -> PerceptualEquation:
        equation = self.get(equation_name)
        if equation is None:
            raise KeyError(f"Equation '{equation_name}' not found in effective index")
        return equation

    def layer_for(self, equation_name: str) -> str | None:
        return self.effective_layers.get(equation_name)

    def definitions_for(
        self, equation_name: str
    ) -> list[tuple[str, PerceptualEquation]]:
        """Return all definitions in load order as (layer_name, equation)."""
        return list(self.all_definitions.get(equation_name, []))

    def __iter__(self) -> Iterator[PerceptualEquation]:
        return iter(self.effective_equations.values())
