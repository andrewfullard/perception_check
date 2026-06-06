from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from data_models import (
    AIPlayerDocument,
    AIPlayerEntry,
    AITemplateDocument,
    AITemplateEntry,
    GoalDocument,
    GoalEntry,
    GoalFunctionDocument,
    GoalFunctionEntry,
    PerceptualEquation,
    PerceptualEquationDocument,
    PerceptualEquationIndex,
    PerceptualEquationLayer,
)
from parse_equations import (
    parse_equations_file,
    parse_equations_folder,
    parse_equations_folder_recursive,
)
from parse_goals import (
    parse_goal_functions_file,
    parse_goal_functions_folder,
    parse_goals_file,
    parse_goals_folder,
)
from parse_players import (
    parse_players_file,
    parse_players_folder,
    parse_templates_file,
    parse_templates_folder,
)


class PerceptualEquationsParser:
    """Facade parser coordinating equation and goal parsing components."""

    parse_file = staticmethod(parse_equations_file)
    parse_goal_functions_file = staticmethod(parse_goal_functions_file)
    parse_goals_file = staticmethod(parse_goals_file)
    parse_players_file = staticmethod(parse_players_file)
    parse_templates_file = staticmethod(parse_templates_file)
    parse_folder = staticmethod(parse_equations_folder)
    parse_goal_functions_folder = staticmethod(parse_goal_functions_folder)
    parse_goals_folder = staticmethod(parse_goals_folder)
    parse_players_folder = staticmethod(parse_players_folder)
    parse_templates_folder = staticmethod(parse_templates_folder)
    parse_folder_recursive = staticmethod(parse_equations_folder_recursive)

    def parse_many(
        self, xml_files: Iterable[str | Path]
    ) -> List[PerceptualEquationDocument]:
        return [parse_equations_file(path) for path in xml_files]

    def parse_layer(
        self,
        name: str,
        folder: str | Path,
        pattern: str = "*.xml",
        recursive: bool = False,
    ) -> PerceptualEquationLayer:
        """Parse one logical load layer and validate in-layer uniqueness."""
        if recursive:
            documents = parse_equations_folder_recursive(folder, pattern=pattern)
        else:
            documents = parse_equations_folder(folder, pattern=pattern)

        layer = PerceptualEquationLayer(name=name, documents=documents)
        self._validate_unique_within_layer(layer)
        return layer

    def build_index(
        self, layers: Iterable[PerceptualEquationLayer]
    ) -> PerceptualEquationIndex:
        """Build an effective equation index from ordered layers.

        The later a layer appears in the iterable, the higher its precedence.
        """
        index = PerceptualEquationIndex()

        for layer in layers:
            for document in layer:
                for equation in document:
                    history = index.all_definitions.setdefault(equation.name, [])
                    history.append((layer.name, equation))
                    index.effective_equations[equation.name] = equation
                    index.effective_layers[equation.name] = layer.name

        return index

    def build_index_from_folders(
        self,
        layer_folders: Iterable[Tuple[str, str | Path]],
        pattern: str = "*.xml",
        recursive: bool = False,
    ) -> PerceptualEquationIndex:
        """Build an effective index from (layer_name, folder_path) pairs.

        Pass pairs in load order: base first, then each overriding submod.
        """
        layers: List[PerceptualEquationLayer] = []
        for layer_name, folder in layer_folders:
            layers.append(
                self.parse_layer(
                    name=layer_name,
                    folder=folder,
                    pattern=pattern,
                    recursive=recursive,
                )
            )
        return self.build_index(layers)

    def _validate_unique_within_layer(self, layer: PerceptualEquationLayer) -> None:
        """Ensure equation names are unique inside one load layer."""
        seen: Dict[str, Path] = {}
        duplicates: List[str] = []

        for document in layer:
            for equation in document:
                prior = seen.get(equation.name)
                if prior is None:
                    seen[equation.name] = equation.source_file
                    continue
                duplicates.append(
                    f"{equation.name} ({prior.name} and {equation.source_file.name})"
                )

        if duplicates:
            duplicate_list = ", ".join(sorted(set(duplicates)))
            raise ValueError(
                f"Duplicate equation names found within layer '{layer.name}': "
                f"{duplicate_list}"
            )


__all__ = [
    "PerceptualEquation",
    "PerceptualEquationDocument",
    "PerceptualEquationLayer",
    "PerceptualEquationIndex",
    "AIPlayerEntry",
    "AIPlayerDocument",
    "AITemplateEntry",
    "AITemplateDocument",
    "GoalFunctionEntry",
    "GoalFunctionDocument",
    "GoalEntry",
    "GoalDocument",
    "PerceptualEquationsParser",
]
