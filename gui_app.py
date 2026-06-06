from __future__ import annotations

import ast
import random
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

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
    PerceptualEquationIndex,
    PerceptualEquationsParser,
)
from perceptual_equations_range import (
    PerceptualEquationRangeAnalyzer,
)
from perceptual_token_bounds import (
    TokenBounds,
    clamp_token_value,
    load_token_bounds,
)
from stack_paths import (
    resolve_stack_layer_content_folders,
    resolve_stack_layer_folders,
)
from gui_view import PerceptualEquationsView


class PerceptualEquationsApp:
    """Controller that coordinates parser logic and Tkinter view state."""

    def __init__(self, root: tk.Tk) -> None:
        """Initialize parser state, construct view, and bind handlers."""
        self.parser = PerceptualEquationsParser()
        self.index: PerceptualEquationIndex | None = None
        self.filtered_names: list[str] = []
        self.token_bounds: dict[str, TokenBounds] = {}
        self.token_bounds_path = Path(__file__).with_name(
            "perception_token_bounds.json"
        )
        self.range_analyzer: PerceptualEquationRangeAnalyzer | None = None
        self.goal_to_equations: dict[str, list[str]] = {}
        self.equation_to_goals: dict[str, list[str]] = {}
        self.goal_function_links: dict[str, tuple[str, str]] = {}
        self.entry_types: dict[str, str] = {}
        self.goal_display_to_entry: dict[str, str] = {}
        self.player_display_to_entry: dict[str, str] = {}
        self.template_display_to_entry: dict[str, str] = {}

        self.view = PerceptualEquationsView(root)
        self._load_token_bounds_config()
        self.view.bind_handlers(
            on_load_stack=self._load_stack_from_fields,
            on_browse_stack_root=self._choose_stack_root,
            on_search_changed=self._refresh_list,
            on_selection_changed=self._on_selection_changed,
            on_goal_selection_changed=self._on_goal_selection_changed,
            on_player_selection_changed=self._on_player_selection_changed,
            on_template_selection_changed=self._on_template_selection_changed,
            on_evaluate=self._evaluate_expression,
            on_function_token_click=self._on_function_token_click,
            on_entry_link_click=self._on_related_entry_click,
        )

    def _load_token_bounds_config(self) -> None:
        """Load optional token min/max constraints from JSON config file."""
        if not self.token_bounds_path.exists():
            self.token_bounds = {}
            self.range_analyzer = None
            return

        try:
            self.token_bounds = load_token_bounds(self.token_bounds_path)
        except Exception as exc:
            self.token_bounds = {}
            self.range_analyzer = None
            messagebox.showwarning(
                "Token bounds config",
                f"Could not load token bounds from '{self.token_bounds_path.name}': {exc}",
            )

    def _choose_stack_root(self) -> None:
        """Choose a stack root folder and store it in stack settings."""
        root = filedialog.askdirectory(
            title="Select Root Folder Containing Data and Optional Layer Folders"
        )
        if not root:
            return
        self.view.stack_root_var.set(root)

    def _load_stack_from_fields(self) -> None:
        """Load stack using root path plus two optional, ordered upper layers."""
        root_text = self.view.stack_root_var.get().strip()
        if not root_text:
            messagebox.showerror(
                "Load error", "Please choose a stack root folder first"
            )
            return

        upper_layers = [
            self.view.upper_layer_1_var.get().strip(),
            self.view.upper_layer_2_var.get().strip(),
        ]
        self._load_stack(Path(root_text), upper_layers)

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
            documents = self.parser.parse_goal_functions_folder(goal_functions_folder)
            self._merge_goal_function_documents(layer_name, documents)

        goal_layers = resolve_stack_layer_content_folders(
            root=root,
            upper_layers=upper_layers,
            content_folder="Goals",
            require_data_layer=False,
            require_selected_upper_layers=False,
        )
        for layer_name, goals_folder in goal_layers:
            documents = self.parser.parse_goals_folder(goals_folder)
            self._merge_goal_documents(layer_name, documents)

        player_layers = resolve_stack_layer_content_folders(
            root=root,
            upper_layers=upper_layers,
            content_folder="Players",
            require_data_layer=False,
            require_selected_upper_layers=False,
        )
        for layer_name, players_folder in player_layers:
            documents = self.parser.parse_players_folder(players_folder)
            self._merge_player_documents(layer_name, documents)

        template_layers = resolve_stack_layer_content_folders(
            root=root,
            upper_layers=upper_layers,
            content_folder="Templates",
            require_data_layer=False,
            require_selected_upper_layers=False,
        )
        for layer_name, templates_folder in template_layers:
            documents = self.parser.parse_templates_folder(templates_folder)
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
                link_goal_name, link_equation_name = self._extract_goal_function_link(
                    entry
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

    def _refresh_list(self) -> None:
        """Refresh listbox content using current index and search filter."""
        if self.index is None:
            self.filtered_names = []
            filtered_goal_names: list[str] = []
            filtered_player_names: list[str] = []
            filtered_template_names: list[str] = []
        else:
            all_names = sorted(self.index.effective_equations.keys(), key=str.lower)
            goal_names = [
                name for name in all_names if self._entry_type(name) == "goal"
            ]
            goal_term = self.view.goals_search_var.get().strip().lower()
            if goal_term:
                filtered_goal_names = [
                    name
                    for name in goal_names
                    if goal_term in self._goal_display_name(name).lower()
                ]
            else:
                filtered_goal_names = goal_names

            player_names = [
                name for name in all_names if self._entry_type(name) == "player"
            ]
            player_term = self.view.players_search_var.get().strip().lower()
            if player_term:
                filtered_player_names = [
                    name
                    for name in player_names
                    if player_term in self._player_display_name(name).lower()
                ]
            else:
                filtered_player_names = player_names

            template_names = [
                name for name in all_names if self._entry_type(name) == "template"
            ]
            template_term = self.view.templates_search_var.get().strip().lower()
            if template_term:
                filtered_template_names = [
                    name
                    for name in template_names
                    if template_term in self._template_display_name(name).lower()
                ]
            else:
                filtered_template_names = template_names

            names = [name for name in all_names if self._entry_type(name) == "equation"]
            term = self.view.search_var.get().strip().lower()
            if term:
                names = [name for name in names if term in name.lower()]
            self.filtered_names = names

        self.view.names_listbox.delete(0, tk.END)
        for name in self.filtered_names:
            self.view.names_listbox.insert(tk.END, name)

        self.goal_display_to_entry = {}
        goal_display_names: list[str] = []
        for goal_name in filtered_goal_names:
            goal_display_name = self._goal_display_name(goal_name)
            if goal_display_name in self.goal_display_to_entry:
                goal_display_name = goal_name
            self.goal_display_to_entry[goal_display_name] = goal_name
            goal_display_names.append(goal_display_name)

        self.view.set_goal_names(goal_display_names)

        self.player_display_to_entry = {}
        player_display_names: list[str] = []
        for player_name in filtered_player_names:
            player_display_name = self._player_display_name(player_name)
            if player_display_name in self.player_display_to_entry:
                player_display_name = player_name
            self.player_display_to_entry[player_display_name] = player_name
            player_display_names.append(player_display_name)

        self.view.set_player_names(player_display_names)

        self.template_display_to_entry = {}
        template_display_names: list[str] = []
        for template_name in filtered_template_names:
            template_display_name = self._template_display_name(template_name)
            if template_display_name in self.template_display_to_entry:
                template_display_name = template_name
            self.template_display_to_entry[template_display_name] = template_name
            template_display_names.append(template_display_name)

        self.view.set_template_names(template_display_names)

        if self.filtered_names:
            self.view.names_listbox.selection_set(0)
            self.view.names_listbox.event_generate("<<ListboxSelect>>")
        else:
            self._display_equation(None)

    def _on_goal_selection_changed(self, _event: tk.Event) -> None:
        """Jump to selected Goal::* entry from the AI goals tab."""
        if self.index is None:
            return

        selection = self.view.goals_listbox.curselection()
        if not selection:
            return

        selected_display_name = self.view.goals_listbox.get(selection[0])
        if not selected_display_name:
            return

        goal_name = self.goal_display_to_entry.get(
            selected_display_name,
            selected_display_name,
        )
        if goal_name is None:
            return

        selected_goal = self.index.get(goal_name)
        if selected_goal is None:
            messagebox.showinfo(
                "Entry not found",
                f"No loaded entry named '{goal_name}' was found.",
            )
            return

        # Goals are intentionally hidden from the Equations list, so display
        # directly instead of routing through list selection logic.
        self.view.names_listbox.selection_clear(0, tk.END)
        self._display_equation(selected_goal)

    def _on_player_selection_changed(self, _event: tk.Event) -> None:
        """Jump to selected Player::* entry from the AI players tab."""
        if self.index is None:
            return

        selection = self.view.players_listbox.curselection()
        if not selection:
            return

        selected_display_name = self.view.players_listbox.get(selection[0])
        if not selected_display_name:
            return

        player_name = self.player_display_to_entry.get(
            selected_display_name,
            selected_display_name,
        )
        if player_name is None:
            return

        selected_player = self.index.get(player_name)
        if selected_player is None:
            messagebox.showinfo(
                "Entry not found",
                f"No loaded entry named '{player_name}' was found.",
            )
            return

        # Players are intentionally hidden from the Equations list, so display
        # directly instead of routing through list selection logic.
        self.view.names_listbox.selection_clear(0, tk.END)
        self._display_equation(selected_player)

    def _on_template_selection_changed(self, _event: tk.Event) -> None:
        """Jump to selected Template::* entry from the AI templates tab."""
        if self.index is None:
            return

        selection = self.view.templates_listbox.curselection()
        if not selection:
            return

        selected_display_name = self.view.templates_listbox.get(selection[0])
        if not selected_display_name:
            return

        template_name = self.template_display_to_entry.get(
            selected_display_name,
            selected_display_name,
        )
        if template_name is None:
            return

        selected_template = self.index.get(template_name)
        if selected_template is None:
            messagebox.showinfo(
                "Entry not found",
                f"No loaded entry named '{template_name}' was found.",
            )
            return

        # Templates are intentionally hidden from the Equations list, so display
        # directly instead of routing through list selection logic.
        self.view.names_listbox.selection_clear(0, tk.END)
        self._display_equation(selected_template)

    def _on_selection_changed(self, _event: tk.Event) -> None:
        """Display the currently selected equation from the filtered list."""
        if self.index is None:
            self._display_equation(None)
            return

        selection = self.view.names_listbox.curselection()
        if not selection:
            self._display_equation(None)
            return

        name = self.filtered_names[selection[0]]
        equation = self.index.get(name)
        self._display_equation(equation)

    def _display_equation(self, equation: PerceptualEquation | None) -> None:
        """Update the details panel with metadata and expression text."""
        if equation is None:
            self.view.set_evaluation_controls_visible(True)
            self.view.layer_var.set("-")
            self.view.source_var.set("-")
            self.view.range_var.set("-")
            self.view.result_var.set("-")
            self.view.set_expression_text("")
            self.view.set_related_links([])
            return

        self.view.set_evaluation_controls_visible(
            self._entry_type(equation.name) == "equation"
        )

        layer_name = self.index.layer_for(equation.name) if self.index else None
        self.view.layer_var.set(layer_name or "-")
        self.view.source_var.set(equation.source_file.name)
        self.view.range_var.set(self._format_entry_range(equation.name))
        self.view.result_var.set("-")
        self.view.set_expression_text(
            equation.normalized_expression,
            structured=self._entry_type(equation.name) != "equation",
        )
        self.view.set_related_links(self._build_related_links(equation.name))

    def _on_related_entry_click(self, entry_name: str) -> None:
        """Navigate to another loaded entry from a details-panel link."""
        self._select_entry_by_name(entry_name)

    def _format_entry_range(self, entry_name: str) -> str:
        """Return range text for an entry, including goal-linked equation ranges."""
        entry_type = self._entry_type(entry_name)

        if entry_type == "goal":
            return self._format_goal_range(entry_name)

        if entry_type == "goal_function":
            goal_function_link = self.goal_function_links.get(entry_name)
            if not goal_function_link:
                return "-"
            _goal_name, equation_name = goal_function_link
            return self._format_equation_range(equation_name)

        return self._format_equation_range(entry_name)

    def _format_goal_range(self, goal_name: str) -> str:
        """Return an aggregate min/max range across equations linked to one goal."""
        linked_equations = self.goal_to_equations.get(goal_name, [])
        if not linked_equations:
            return "-"

        resolved_ranges: list[tuple[str, str, str, float, float]] = []
        for equation_name in linked_equations:
            numeric_range = self._compute_equation_range(equation_name)
            if numeric_range is None:
                continue
            minimum_text = self._format_range_value(numeric_range.minimum)
            maximum_text = self._format_range_value(numeric_range.maximum)
            resolved_ranges.append(
                (
                    equation_name,
                    minimum_text,
                    maximum_text,
                    numeric_range.minimum,
                    numeric_range.maximum,
                )
            )

        if not resolved_ranges:
            return "unavailable"

        overall_minimum = min(range_data[3] for range_data in resolved_ranges)
        overall_maximum = max(range_data[4] for range_data in resolved_ranges)
        return (
            f"min {self._format_range_value(overall_minimum)}, "
            f"max {self._format_range_value(overall_maximum)} "
            f"(from {len(resolved_ranges)} linked equation"
            f"{'s' if len(resolved_ranges) != 1 else ''})"
        )

    def _compute_equation_range(self, equation_name: str):
        """Compute numeric range for one equation name, returning None on failures."""
        if self.range_analyzer is None or self.index is None:
            return None

        if self.index.get(equation_name) is None:
            return None

        try:
            return self.range_analyzer.compute_equation_range(equation_name)
        except Exception:
            return None

    def _build_related_links(self, entry_name: str) -> list[tuple[str, str]]:
        """Build display links for navigating goal/equation relationships."""
        links: list[tuple[str, str]] = []
        entry_type = self._entry_type(entry_name)

        if entry_type == "goal":
            for equation_name in self.goal_to_equations.get(entry_name, []):
                if self.index is not None and self.index.get(equation_name) is None:
                    continue
                range_text = self._format_equation_range(equation_name)
                links.append(
                    (f"Equation: {equation_name} ({range_text})", equation_name)
                )
            return links

        if entry_type == "goal_function":
            goal_function_link = self.goal_function_links.get(entry_name)
            if not goal_function_link:
                return links
            goal_name, equation_name = goal_function_link
            links.append((f"Goal: {self._goal_display_name(goal_name)}", goal_name))
            links.append(
                (
                    f"Equation: {equation_name} ({self._format_equation_range(equation_name)})",
                    equation_name,
                )
            )
            return links

        for goal_name in self.equation_to_goals.get(entry_name, []):
            if self.index is not None and self.index.get(goal_name) is None:
                continue
            links.append((f"Goal: {self._goal_display_name(goal_name)}", goal_name))

        return links

    def _extract_goal_function_link(
        self, entry: GoalFunctionEntry
    ) -> tuple[str | None, str | None]:
        """Extract normalized Goal::* and equation names from GoalFunction text."""
        fields = self._parse_structured_fields(entry.normalized_expression)
        goal_value = fields.get("goal")
        function_value = fields.get("function")
        goal_name = self._normalize_goal_name(goal_value)
        equation_name = self._normalize_equation_name(function_value)
        return goal_name, equation_name

    def _parse_structured_fields(self, text: str) -> dict[str, str]:
        """Parse normalized key=value lines into a lowercase-key dictionary."""
        fields: dict[str, str] = {}
        for line in text.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key_text = key.strip().lower()
            value_text = value.strip()
            if key_text and value_text:
                fields[key_text] = value_text
        return fields

    def _normalize_goal_name(self, goal_text: str | None) -> str | None:
        """Convert GoalFunction Goal field text into canonical Goal::* form."""
        if goal_text is None:
            return None
        normalized = goal_text.strip()
        if not normalized:
            return None
        if normalized.startswith("Goal::"):
            return normalized
        return f"Goal::{normalized}"

    def _normalize_equation_name(self, function_text: str | None) -> str | None:
        """Convert GoalFunction Function field text into canonical equation name."""
        if function_text is None:
            return None

        normalized = function_text.strip()
        if not normalized:
            return None

        extracted = self._extract_function_name(normalized)
        if extracted:
            return extracted

        if normalized.endswith(".Evaluate"):
            normalized = normalized[: -len(".Evaluate")].strip()

        return normalized or None

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

    def _goal_display_name(self, goal_name: str) -> str:
        """Return UI display name for a goal entry."""
        if goal_name.startswith("Goal::"):
            return goal_name[len("Goal::") :]
        return goal_name

    def _player_display_name(self, player_name: str) -> str:
        """Return UI display name for a player entry."""
        if player_name.startswith("Player::"):
            return player_name[len("Player::") :]
        return player_name

    def _template_display_name(self, template_name: str) -> str:
        """Return UI display name for a template entry."""
        if template_name.startswith("Template::"):
            return template_name[len("Template::") :]
        return template_name

    def _format_equation_range(self, equation_name: str) -> str:
        """Return display text for equation min/max derived from token bounds."""
        if self.range_analyzer is None:
            return "-"

        try:
            value_range = self.range_analyzer.compute_equation_range(equation_name)
        except Exception:
            return "unavailable"

        return f"min {self._format_range_value(value_range.minimum)}, max {self._format_range_value(value_range.maximum)}"

    def _format_range_value(self, value: float) -> str:
        """Format range endpoint values for compact UI display."""
        if value == float("inf"):
            return "inf"
        if value == float("-inf"):
            return "-inf"
        return f"{value:.15g}"

    def _evaluate_expression(self) -> None:
        """Compute a result from current variable inputs and displayed operators."""
        try:
            expression = self._normalize_expression_for_eval(
                self.view.build_evaluable_expression(self._resolve_token_value_for_eval)
            )
            if not expression:
                self.view.result_var.set("-")
                return

            result = self._safe_eval_expression(expression)
        except Exception as exc:
            messagebox.showerror("Evaluation error", str(exc))
            return

        if isinstance(result, bool):
            numeric_result = 1.0 if result else 0.0
            self.view.result_var.set(f"{numeric_result} ({result})")
        else:
            self.view.result_var.set(str(result))

    def _on_function_token_click(self, token_key: str) -> None:
        """Jump to the equation referenced by a Function_* token."""
        function_name = self._extract_function_name(token_key)
        if not function_name:
            return

        self._select_entry_by_name(function_name)

    def _select_entry_by_name(
        self, entry_name: str, reset_entries_filter: bool = True
    ) -> None:
        """Select an entry in the main list by name."""
        if reset_entries_filter:
            # Reset the entries filter so deep links can always be found.
            self.view.search_var.set("")
            self._refresh_list()

        target_index = None
        for index, name in enumerate(self.filtered_names):
            if name.lower() == entry_name.lower():
                target_index = index
                break

        if target_index is None and not reset_entries_filter:
            # If entries are currently filtered, clear only that filter and retry.
            self.view.search_var.set("")
            self._refresh_list()
            for index, name in enumerate(self.filtered_names):
                if name.lower() == entry_name.lower():
                    target_index = index
                    break

        if target_index is None:
            # Some entry types (for example Goal::* and GoalFunction::*) are
            # intentionally hidden from the Equations list. If the entry exists
            # in the loaded index, display it directly instead of failing.
            if self.index is not None:
                hidden_entry = self.index.get(entry_name)
                if hidden_entry is not None:
                    self.view.names_listbox.selection_clear(0, tk.END)
                    self._display_equation(hidden_entry)
                    return

            messagebox.showinfo(
                "Entry not found",
                f"No loaded entry named '{entry_name}' was found.",
            )
            return

        self.view.names_listbox.selection_clear(0, tk.END)
        self.view.names_listbox.selection_set(target_index)
        self.view.names_listbox.see(target_index)
        self.view.names_listbox.event_generate("<<ListboxSelect>>")

    def _extract_function_name(self, token_key: str) -> str | None:
        """Extract equation name from Function_* token text."""
        token_no_params = token_key.split("{", 1)[0].strip()
        if not token_no_params.startswith("Function_"):
            return None

        function_ref = token_no_params[len("Function_") :]
        if function_ref.endswith(".Evaluate"):
            function_ref = function_ref[: -len(".Evaluate")]

        function_ref = function_ref.strip()
        return function_ref or None

    def _resolve_token_value_for_eval(self, token_key: str, raw_value: str) -> str:
        """Translate token input into a numeric expression segment for evaluation."""
        return clamp_token_value(token_key, raw_value, self.token_bounds)

    def _normalize_expression_for_eval(self, expression: str) -> str:
        """Normalize and translate game syntax into Python-evaluable expression text."""
        normalized = " ".join(expression.split())

        # EAW uses '#' as a random-range operator (e.g. 0#1). In Python '#'
        # starts a comment, which can lead to parse errors like "( was never closed".
        normalized = re.sub(
            r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*#\s*(-?\d+(?:\.\d+)?)(?![\w.])",
            r"rand(\1, \2)",
            normalized,
        )

        return normalized

    def _safe_eval_expression(self, expression: str) -> float | bool:
        """Evaluate arithmetic/boolean expression using a restricted AST whitelist."""

        def clamp(value: float, minimum: float, maximum: float) -> float:
            return max(minimum, min(value, maximum))

        allowed_funcs = {
            "clamp": clamp,
            "rand": random.uniform,
            "min": min,
            "max": max,
            "abs": abs,
        }

        tree = ast.parse(expression, mode="eval")
        self._validate_ast(tree, allowed_funcs)

        result = eval(
            compile(tree, "<expression>", "eval"),
            {"__builtins__": {}},
            allowed_funcs,
        )
        if not isinstance(result, (int, float, bool)):
            raise ValueError("Expression did not evaluate to a numeric/boolean result")
        return result

    def _validate_ast(self, tree: ast.AST, allowed_funcs: dict[str, object]) -> None:
        """Reject unsafe or unsupported AST nodes before evaluation."""
        allowed_node_types = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.BoolOp,
            ast.Compare,
            ast.Call,
            ast.Name,
            ast.Load,
            ast.Constant,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Mod,
            ast.Pow,
            ast.FloorDiv,
            ast.UAdd,
            ast.USub,
            ast.Not,
            ast.And,
            ast.Or,
            ast.Eq,
            ast.NotEq,
            ast.Lt,
            ast.LtE,
            ast.Gt,
            ast.GtE,
        )

        for node in ast.walk(tree):
            if not isinstance(node, allowed_node_types):
                raise ValueError(
                    f"Unsupported expression construct: {node.__class__.__name__}"
                )

            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name):
                    raise ValueError("Only direct function calls are allowed")
                if node.func.id not in allowed_funcs:
                    raise ValueError(f"Unsupported function: {node.func.id}")

            if isinstance(node, ast.Name) and node.id not in allowed_funcs:
                raise ValueError(f"Unknown name in expression: {node.id}")
