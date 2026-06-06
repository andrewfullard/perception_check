from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple


@dataclass
class PerceptualEquation:
    """A single parsed AI entry represented as an equation-like record."""

    name: str
    raw_expression: str
    normalized_expression: str
    source_file: Path

    def update_expression(self, new_expression: str) -> None:
        """Replace text fields when callers update the expression payload."""
        self.raw_expression = new_expression
        self.normalized_expression = " ".join(new_expression.split())


@dataclass
class PerceptualEquationDocument:
    """A parsed XML file containing many named equation-like entries."""

    source_file: Path
    equations: Dict[str, PerceptualEquation] = field(default_factory=dict)

    def get(self, equation_name: str) -> Optional[PerceptualEquation]:
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
class GoalFunctionEntry:
    """A single entry parsed from a <FunctionSet> file."""

    name: str
    raw_expression: str
    normalized_expression: str
    source_file: Path


@dataclass
class GoalEntry:
    """A single entry parsed from a <Goals> file."""

    name: str
    raw_expression: str
    normalized_expression: str
    source_file: Path


@dataclass
class GoalFunctionDocument:
    """A parsed GoalFunctions XML file containing named goal-function entries."""

    source_file: Path
    goal_functions: Dict[str, GoalFunctionEntry] = field(default_factory=dict)

    def get(self, name: str) -> Optional[GoalFunctionEntry]:
        return self.goal_functions.get(name)

    def require(self, name: str) -> GoalFunctionEntry:
        entry = self.get(name)
        if entry is None:
            raise KeyError(f"GoalFunction '{name}' not found in {self.source_file}")
        return entry

    def __iter__(self) -> Iterator[GoalFunctionEntry]:
        return iter(self.goal_functions.values())


@dataclass
class GoalDocument:
    """A parsed Goals XML file containing named goal entries."""

    source_file: Path
    goals: Dict[str, GoalEntry] = field(default_factory=dict)

    def get(self, name: str) -> Optional[GoalEntry]:
        return self.goals.get(name)

    def require(self, name: str) -> GoalEntry:
        entry = self.get(name)
        if entry is None:
            raise KeyError(f"Goal '{name}' not found in {self.source_file}")
        return entry

    def __iter__(self) -> Iterator[GoalEntry]:
        return iter(self.goals.values())


@dataclass
class PerceptualEquationLayer:
    """A logical load layer, such as Data or a specific submod layer."""

    name: str
    documents: List[PerceptualEquationDocument] = field(default_factory=list)

    def __iter__(self) -> Iterator[PerceptualEquationDocument]:
        return iter(self.documents)


@dataclass
class PerceptualEquationIndex:
    """Resolved index across ordered layers (later layers override earlier layers)."""

    effective_equations: Dict[str, PerceptualEquation] = field(default_factory=dict)
    effective_layers: Dict[str, str] = field(default_factory=dict)
    all_definitions: Dict[str, List[Tuple[str, PerceptualEquation]]] = field(
        default_factory=dict
    )

    def get(self, equation_name: str) -> Optional[PerceptualEquation]:
        return self.effective_equations.get(equation_name)

    def require(self, equation_name: str) -> PerceptualEquation:
        equation = self.get(equation_name)
        if equation is None:
            raise KeyError(f"Equation '{equation_name}' not found in effective index")
        return equation

    def layer_for(self, equation_name: str) -> Optional[str]:
        return self.effective_layers.get(equation_name)

    def definitions_for(
        self, equation_name: str
    ) -> List[Tuple[str, PerceptualEquation]]:
        """Return all definitions in load order as (layer_name, equation)."""
        return list(self.all_definitions.get(equation_name, []))

    def __iter__(self) -> Iterator[PerceptualEquation]:
        return iter(self.effective_equations.values())
