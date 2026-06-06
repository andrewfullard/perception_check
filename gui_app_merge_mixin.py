from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from perceptual_equations_parser import (
    AIPlayerDocument,
    AIPlayerEntry,
    AITemplateDocument,
    AITemplateEntry,
    GoalDocument,
    GoalEntry,
    GoalFunctionDocument,
    GoalFunctionEntry,
    PerceptualEquation,
)
from perceptual_equations_range import PerceptualEquationRangeAnalyzer
from parse_goals import parse_goal_functions_folder, parse_goals_folder
from parse_players import parse_players_folder, parse_templates_folder
from stack_paths import (
    resolve_stack_layer_content_folders,
    resolve_stack_layer_folders,
)
from gui_app_text_utils import (
    extract_goal_function_link,
    extract_player_template_links,
)


class PerceptualEquationsAppMergeMixin:
    """Stack loading and non-equation merge behavior for the app controller."""

    def _load_stack(self, root: Path, upper_layers: list[str]) -> None:
        """Load equations plus Goals/GoalFunctions from configured load stack."""
        try:
            layer_folders = resolve_stack_layer_folders(root, upper_layers)
            if not layer_folders:
                raise ValueError(
                    "No valid PerceptualEquations folders found in the configured stack"
                )

            self.index = self.parser.build_index_from_folders(layer_folders)
            self.goal_to_equations = {}
            self.equation_to_goals = {}
            self.player_to_templates = {}
            self.template_to_players = {}
            self.goal_function_links = {}
            self.entry_types = {
                name: "equation" for name in self.index.effective_equations.keys()
            }
            self.goal_display_to_entry = {}
            self.player_display_to_entry = {}
            self.template_display_to_entry = {}
            self._merge_non_equation_data_into_index(root, upper_layers)
            self.range_analyzer = PerceptualEquationRangeAnalyzer(
                self.index,
                self.token_bounds,
            )
        except Exception as exc:
            messagebox.showerror("Load error", str(exc))
            return

        loaded_layers = " -> ".join(layer_name for layer_name, _ in layer_folders)
        self.view.folder_var.set(f"{root} [{loaded_layers}]")
        self._refresh_list()

    def _merge_non_equation_data_into_index(
        self, root: Path, upper_layers: list[str]
    ) -> None:
        """Merge AI non-equation entries resolved per layer across stack folders."""
        if self.index is None:
            return

        goal_function_layers = resolve_stack_layer_content_folders(
            root=root,
            upper_layers=upper_layers,
            content_folder="GoalFunctions",
            require_data_layer=False,
            require_selected_upper_layers=False,
        )
        for layer_name, goal_functions_folder in goal_function_layers:
            documents = parse_goal_functions_folder(goal_functions_folder)
            self._merge_goal_function_documents(layer_name, documents)

        goal_layers = resolve_stack_layer_content_folders(
            root=root,
            upper_layers=upper_layers,
            content_folder="Goals",
            require_data_layer=False,
            require_selected_upper_layers=False,
        )
        for layer_name, goals_folder in goal_layers:
            documents = parse_goals_folder(goals_folder)
            self._merge_goal_documents(layer_name, documents)

        player_layers = resolve_stack_layer_content_folders(
            root=root,
            upper_layers=upper_layers,
            content_folder="Players",
            require_data_layer=False,
            require_selected_upper_layers=False,
        )
        for layer_name, players_folder in player_layers:
            documents = parse_players_folder(players_folder)
            self._merge_player_documents(layer_name, documents)

        template_layers = resolve_stack_layer_content_folders(
            root=root,
            upper_layers=upper_layers,
            content_folder="Templates",
            require_data_layer=False,
            require_selected_upper_layers=False,
        )
        for layer_name, templates_folder in template_layers:
            documents = parse_templates_folder(templates_folder)
            self._merge_template_documents(layer_name, documents)

    def _merge_goal_function_documents(
        self,
        layer_name: str,
        documents: list[GoalFunctionDocument],
    ) -> None:
        """Apply goal-function documents into current effective index."""
        if self.index is None:
            return

        for document in documents:
            for entry in document:
                link_goal_name, link_equation_name = extract_goal_function_link(
                    entry.normalized_expression,
                    self._extract_function_name,
                )
                if link_goal_name and link_equation_name:
                    self.goal_function_links[entry.name] = (
                        link_goal_name,
                        link_equation_name,
                    )
                    self._append_unique(
                        self.goal_to_equations,
                        link_goal_name,
                        link_equation_name,
                    )
                    self._append_unique(
                        self.equation_to_goals,
                        link_equation_name,
                        link_goal_name,
                    )
                self._merge_non_equation_entry(layer_name, entry)

    def _merge_goal_documents(
        self,
        layer_name: str,
        documents: list[GoalDocument],
    ) -> None:
        """Apply goal documents into current effective index."""
        if self.index is None:
            return

        for document in documents:
            for entry in document:
                self._merge_non_equation_entry(layer_name, entry)

    def _merge_player_documents(
        self,
        layer_name: str,
        documents: list[AIPlayerDocument],
    ) -> None:
        """Apply player documents into current effective index."""
        if self.index is None:
            return

        for document in documents:
            for entry in document:
                for template_name in extract_player_template_links(
                    entry.normalized_expression
                ):
                    self._append_unique(
                        self.player_to_templates,
                        entry.name,
                        template_name,
                    )
                    self._append_unique(
                        self.template_to_players,
                        template_name,
                        entry.name,
                    )
                self._merge_non_equation_entry(layer_name, entry)

    def _merge_template_documents(
        self,
        layer_name: str,
        documents: list[AITemplateDocument],
    ) -> None:
        """Apply template documents into current effective index."""
        if self.index is None:
            return

        for document in documents:
            for entry in document:
                self._merge_non_equation_entry(layer_name, entry)

    def _merge_non_equation_entry(
        self,
        layer_name: str,
        entry: GoalFunctionEntry | GoalEntry | AIPlayerEntry | AITemplateEntry,
    ) -> None:
        """Adapt non-equation entries so they can be shown in the unified UI list."""
        if self.index is None:
            return

        equation = PerceptualEquation(
            name=entry.name,
            raw_expression=entry.raw_expression,
            normalized_expression=entry.normalized_expression,
            source_file=entry.source_file,
        )
        history = self.index.all_definitions.setdefault(equation.name, [])
        history.append((layer_name, equation))
        self.index.effective_equations[equation.name] = equation
        self.index.effective_layers[equation.name] = layer_name
        if isinstance(entry, GoalEntry):
            self.entry_types[equation.name] = "goal"
        elif isinstance(entry, GoalFunctionEntry):
            self.entry_types[equation.name] = "goal_function"
        elif isinstance(entry, AIPlayerEntry):
            self.entry_types[equation.name] = "player"
        else:
            self.entry_types[equation.name] = "template"

    def _append_unique(
        self,
        mapping: dict[str, list[str]],
        key: str,
        value: str,
    ) -> None:
        """Append to list-valued mapping while preserving first-seen order."""
        items = mapping.setdefault(key, [])
        if value not in items:
            items.append(value)

    def _entry_type(self, entry_name: str) -> str:
        """Return entry type metadata used by list, links, and evaluation UI."""
        explicit_type = self.entry_types.get(entry_name)
        if explicit_type is not None:
            return explicit_type

        if entry_name in self.goal_to_equations:
            return "goal"
        if entry_name in self.goal_function_links:
            return "goal_function"
        return "equation"
