from __future__ import annotations

import ast
from pathlib import Path
import random
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable

from perception.models import Document, Entry
from perception.entry_text import (
    extract_function_name,
    extract_goal_function_link,
    extract_player_template_links,
    normalize_goal_name,
    parse_structured_fields,
)
from gui.view import PerceptualEquationsView
from parsers.goals import parse_goal_functions_folder, parse_goals_folder
from parsers.players import parse_players_folder, parse_templates_folder
from perception.equation_index import (
    PerceptualEquation,
    PerceptualEquationIndex,
    build_index_from_folders,
)
from perception.equation_ranges import PerceptualEquationRangeAnalyzer
from perception.token_bounds import TokenBounds, clamp_token_value, load_token_bounds
from perception.stack_paths import (
    resolve_stack_layer_content_folders,
    resolve_stack_layer_folders,
)


def _goal_display_name(entry_name: str) -> str:
    return entry_name.removeprefix("Goal::")


def _player_display_name(entry_name: str) -> str:
    return entry_name.removeprefix("Player::")


def _template_display_name(entry_name: str) -> str:
    return entry_name.removeprefix("Template::")


class PerceptualEquationsApp:
    """Controller that coordinates parser logic and Tkinter view state."""

    def __init__(self, root: tk.Tk) -> None:
        """Initialize parser state, construct view, and bind handlers."""
        self.index: PerceptualEquationIndex | None = None
        self.filtered_names: list[str] = []
        self.token_bounds: dict[str, TokenBounds] = {}
        self.token_bounds_path = Path(__file__).with_name(
            "perception_token_bounds.json"
        )
        self.range_analyzer: PerceptualEquationRangeAnalyzer | None = None
        self.goal_to_equations: dict[str, list[str]] = {}
        self.equation_to_goals: dict[str, list[str]] = {}
        self.player_to_templates: dict[str, list[str]] = {}
        self.player_template_modes: dict[tuple[str, str], list[str]] = {}
        self.template_to_players: dict[str, list[str]] = {}
        self.goal_function_links: dict[str, tuple[str, str]] = {}
        self.goal_equation_function_sets: dict[tuple[str, str], list[str]] = {}
        self.player_goal_function_sets: dict[str, list[str]] = {}
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
            on_entry_link_click=self._select_entry_by_name,
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

            self.index = build_index_from_folders(layer_folders)
            self.goal_to_equations = {}
            self.equation_to_goals = {}
            self.player_to_templates = {}
            self.player_template_modes = {}
            self.template_to_players = {}
            self.goal_function_links = {}
            self.goal_equation_function_sets = {}
            self.player_goal_function_sets = {}
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
        documents: list[Document],
    ) -> None:
        """Apply goal-function documents into current effective index."""
        if self.index is None:
            return

        for document in documents:
            for entry in document:
                link_goal_name, link_equation_name = extract_goal_function_link(
                    entry.normalized_expression
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
                    self._append_unique(
                        self.goal_equation_function_sets,
                        (link_goal_name, link_equation_name),
                        self._normalize_goal_function_set_name(entry.source_file.stem),
                    )
                self._merge_non_equation_entry(layer_name, entry)

    def _merge_goal_documents(
        self,
        layer_name: str,
        documents: list[Document],
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
        documents: list[Document],
    ) -> None:
        """Apply player documents into current effective index."""
        if self.index is None:
            return

        for document in documents:
            for entry in document:
                for template_name, game_mode in self._extract_player_template_modes(
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
                    self._append_unique(
                        self.player_template_modes,
                        (entry.name, template_name),
                        game_mode,
                    )
                for goal_function_set in self._extract_player_goal_function_sets(
                    entry.normalized_expression
                ):
                    self._append_unique(
                        self.player_goal_function_sets,
                        entry.name,
                        goal_function_set,
                    )
                self._merge_non_equation_entry(layer_name, entry)

    def _merge_template_documents(
        self,
        layer_name: str,
        documents: list[Document],
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
        entry: Entry,
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
        self.entry_types[equation.name] = entry.entry_type

    def _append_unique(
        self,
        mapping,
        key,
        value: str,
    ) -> None:
        """Append to list-valued mapping while preserving first-seen order."""
        items = mapping.setdefault(key, [])
        if value not in items:
            items.append(value)

    def _extract_player_template_modes(
        self,
        normalized_expression: str,
    ) -> list[tuple[str, str]]:
        """Extract Template::* references with their player template mode."""
        template_modes: list[tuple[str, str]] = []
        for line in normalized_expression.splitlines():
            if "=" not in line:
                continue
            field_key, field_value = line.split("=", 1)
            field_key = field_key.strip()
            key_parts = [part for part in field_key.split("/") if part]
            if len(key_parts) < 2 or key_parts[0].lower() != "templates":
                continue
            game_mode = key_parts[-1].strip()
            if not game_mode:
                continue
            for template_name in extract_player_template_links(line):
                template_modes.append((template_name, game_mode))
        return template_modes

    def _extract_player_goal_function_sets(
        self,
        normalized_expression: str,
    ) -> list[str]:
        """Extract GoalProposalFunctionSets file/set names from one player."""
        goal_function_sets: list[str] = []
        for line in normalized_expression.splitlines():
            if "=" not in line:
                continue
            field_key, field_value = line.split("=", 1)
            if "goalproposalfunctionsets" not in field_key.lower().split("/"):
                continue
            for set_ref in re.split(r"[\s,]+", field_value.strip()):
                if not set_ref:
                    continue
                goal_function_sets.append(
                    self._normalize_goal_function_set_name(set_ref)
                )
        return goal_function_sets

    def _normalize_goal_function_set_name(self, set_ref: str) -> str:
        """Normalize a GoalFunction set/file reference for matching."""
        normalized = Path(set_ref.strip().replace("\\", "/")).stem
        return normalized.lower()

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

    def _refresh_list(self) -> None:
        """Refresh listbox content using current index and search filter."""
        if self.index is None:
            self.filtered_names = []
            filtered_goal_names: list[str] = []
            filtered_player_names: list[str] = []
            filtered_template_names: list[str] = []
        else:
            all_names = sorted(self.index.effective_equations.keys(), key=str.lower)
            filtered_goal_names = self._filter_hidden_tab_names(
                all_names,
                entry_type="goal",
                search_text=self.view.goals_search_var.get(),
                display_name_for=_goal_display_name,
            )
            filtered_player_names = self._filter_hidden_tab_names(
                all_names,
                entry_type="player",
                search_text=self.view.players_search_var.get(),
                display_name_for=_player_display_name,
            )
            filtered_template_names = self._filter_hidden_tab_names(
                all_names,
                entry_type="template",
                search_text=self.view.templates_search_var.get(),
                display_name_for=_template_display_name,
            )

            names = [name for name in all_names if self._entry_type(name) == "equation"]
            term = self.view.search_var.get().strip().lower()
            if term:
                names = [name for name in names if term in name.lower()]
            self.filtered_names = names

        self.view.names_listbox.delete(0, tk.END)
        for name in self.filtered_names:
            self.view.names_listbox.insert(tk.END, name)

        goal_display_names, self.goal_display_to_entry = self._build_display_name_map(
            filtered_goal_names,
            _goal_display_name,
        )
        self.view._set_listbox_items(self.view.goals_listbox, goal_display_names)

        (
            player_display_names,
            self.player_display_to_entry,
        ) = self._build_display_name_map(
            filtered_player_names,
            _player_display_name,
        )
        self.view._set_listbox_items(self.view.players_listbox, player_display_names)

        (
            template_display_names,
            self.template_display_to_entry,
        ) = self._build_display_name_map(
            filtered_template_names,
            _template_display_name,
        )
        self.view._set_listbox_items(
            self.view.templates_listbox,
            template_display_names,
        )

        if self.filtered_names:
            self.view.names_listbox.selection_set(0)
            self.view.names_listbox.event_generate("<<ListboxSelect>>")
        else:
            self._display_equation(None)

    def _filter_hidden_tab_names(
        self,
        all_names: list[str],
        entry_type: str,
        search_text: str,
        display_name_for: Callable[[str], str],
    ) -> list[str]:
        """Return hidden-tab entries of one type matching display-name search."""
        names = [name for name in all_names if self._entry_type(name) == entry_type]
        term = search_text.strip().lower()
        if not term:
            return names
        return [name for name in names if term in display_name_for(name).lower()]

    def _build_display_name_map(
        self,
        entry_names: list[str],
        display_name_for: Callable[[str], str],
    ) -> tuple[list[str], dict[str, str]]:
        """Build listbox labels plus a collision-safe label->entry lookup."""
        display_to_entry: dict[str, str] = {}
        display_names: list[str] = []

        for entry_name in entry_names:
            display_name = display_name_for(entry_name)
            if display_name in display_to_entry:
                display_name = entry_name
            display_to_entry[display_name] = entry_name
            display_names.append(display_name)

        return display_names, display_to_entry

    def _on_goal_selection_changed(self, _event: tk.Event) -> None:
        """Jump to selected Goal::* entry from the AI goals tab."""
        self._on_hidden_tab_selection_changed(
            listbox=self.view.goals_listbox,
            display_map=self.goal_display_to_entry,
        )

    def _on_player_selection_changed(self, _event: tk.Event) -> None:
        """Jump to selected Player::* entry from the AI players tab."""
        self._on_hidden_tab_selection_changed(
            listbox=self.view.players_listbox,
            display_map=self.player_display_to_entry,
        )

    def _on_template_selection_changed(self, _event: tk.Event) -> None:
        """Jump to selected Template::* entry from the AI templates tab."""
        self._on_hidden_tab_selection_changed(
            listbox=self.view.templates_listbox,
            display_map=self.template_display_to_entry,
        )

    def _on_hidden_tab_selection_changed(
        self,
        listbox: tk.Listbox,
        display_map: dict[str, str],
    ) -> None:
        """Display selected hidden entry from goals/players/templates tabs."""
        if self.index is None:
            return

        selection = listbox.curselection()
        if not selection:
            return

        selected_display_name = listbox.get(selection[0])
        if not selected_display_name:
            return

        entry_name = display_map.get(
            selected_display_name,
            selected_display_name,
        )
        if entry_name is None:
            return

        selected_entry = self.index.get(entry_name)
        if selected_entry is None:
            messagebox.showinfo(
                "Entry not found",
                f"No loaded entry named '{entry_name}' was found.",
            )
            return

        # These entries are intentionally hidden from the Equations list, so display
        # directly instead of routing through list selection logic.
        self.view.names_listbox.selection_clear(0, tk.END)
        self._display_equation(selected_entry)

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
            self.view.set_relationship_graph([], [])
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
            structured_links=self._build_structured_expression_links(equation.name),
        )
        self.view.set_related_links(self._build_related_links(equation.name))
        graph_columns, graph_edges = self._build_relationship_graph(equation.name)
        self.view.set_relationship_graph(graph_columns, graph_edges)

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
            links.append((f"Goal: {_goal_display_name(goal_name)}", goal_name))
            links.append(
                (
                    f"Equation: {equation_name} ({self._format_equation_range(equation_name)})",
                    equation_name,
                )
            )
            return links

        if entry_type == "player":
            return links

        if entry_type == "template":
            for player_name in self.template_to_players.get(entry_name, []):
                if self.index is not None and self.index.get(player_name) is None:
                    continue
                links.append(
                    (
                        f"Player: {_player_display_name(player_name)}",
                        player_name,
                    )
                )
            return links

        for goal_name in self.equation_to_goals.get(entry_name, []):
            if self.index is not None and self.index.get(goal_name) is None:
                continue
            links.append((f"Goal: {_goal_display_name(goal_name)}", goal_name))

        return links

    def _build_structured_expression_links(
        self,
        entry_name: str,
    ) -> dict[tuple[str, str], list[tuple[str, str | None]]]:
        """Build field-value links for structured entry rendering."""
        entry_type = self._entry_type(entry_name)
        if entry_type == "player":
            return self._build_player_template_field_links(entry_name)
        if entry_type == "template":
            return self._build_template_goal_field_links(entry_name)
        return {}

    def _build_player_template_field_links(
        self,
        entry_name: str,
    ) -> dict[tuple[str, str], list[tuple[str, str | None]]]:
        """Build field-value links from player template fields to templates."""
        links: dict[tuple[str, str], list[tuple[str, str | None]]] = {}
        for template_name in self.player_to_templates.get(entry_name, []):
            if self.index is not None and self.index.get(template_name) is None:
                continue
            display_name = _template_display_name(template_name)
            for field_key in self._template_field_keys(
                entry_name,
                display_name,
                template_name,
            ):
                link = [(display_name, template_name)]
                links[(field_key, display_name)] = link
                links[(field_key, template_name)] = link
        return links

    def _build_relationship_graph(
        self,
        entry_name: str,
    ) -> tuple[
        list[tuple[str, list[tuple[str, str, str | None]]]],
        list[tuple[str, str]],
    ]:
        """Build a small lane-based graph around one selected entry."""
        column_order = ("player", "template", "goal", "equation")
        column_titles = {
            "player": "AI Players",
            "template": "AI Templates",
            "goal": "AI Goals",
            "equation": "Equations",
        }
        nodes: dict[str, list[tuple[str, str, str | None]]] = {
            column: [] for column in column_order
        }
        node_ids: set[str] = set()
        edges: list[tuple[str, str]] = []
        edge_ids: set[tuple[str, str]] = set()

        def node_id(column: str, entry_name: str) -> str:
            return f"{column}:{entry_name}"

        def add_entry(column: str, entry_name: str, label_for) -> None:
            current_id = node_id(column, entry_name)
            if current_id in node_ids:
                return
            node_ids.add(current_id)
            nodes[column].append((current_id, label_for(entry_name), entry_name))

        def add_edge(
            source_column: str,
            source_name: str,
            target_column: str,
            target_name: str,
        ) -> None:
            edge = (
                node_id(source_column, source_name),
                node_id(target_column, target_name),
            )
            if edge in edge_ids:
                return
            edge_ids.add(edge)
            edges.append(edge)

        entry_type = self._entry_type(entry_name)

        if entry_type == "player":
            self._add_player_graph(add_entry, add_edge, entry_name)
        elif entry_type == "template":
            self._add_template_graph(add_entry, add_edge, entry_name)
            for player_name in self.template_to_players.get(entry_name, []):
                if self._entry_exists(player_name):
                    add_entry("player", player_name, _player_display_name)
                    add_edge("player", player_name, "template", entry_name)
        elif entry_type == "goal":
            self._add_goal_graph(add_entry, add_edge, entry_name)
            for template_name in self._templates_for_goal(entry_name):
                self._add_template_graph(
                    add_entry, add_edge, template_name, include_goal_edges=False
                )
                add_edge("template", template_name, "goal", entry_name)
                for player_name in self.template_to_players.get(template_name, []):
                    if self._entry_exists(player_name):
                        add_entry("player", player_name, _player_display_name)
                        add_edge("player", player_name, "template", template_name)
        elif entry_type == "goal_function":
            goal_function_link = self.goal_function_links.get(entry_name)
            if goal_function_link:
                goal_name, equation_name = goal_function_link
                self._add_goal_graph(add_entry, add_edge, goal_name)
                self._add_equation_graph_node(add_entry, equation_name)
                add_edge("goal", goal_name, "equation", equation_name)
        else:
            self._add_equation_graph_node(add_entry, entry_name)
            for goal_name in self.equation_to_goals.get(entry_name, []):
                if not self._entry_exists(goal_name):
                    continue
                self._add_goal_graph(add_entry, add_edge, goal_name)
                add_edge("goal", goal_name, "equation", entry_name)
                for template_name in self._templates_for_goal(goal_name):
                    self._add_template_graph(
                        add_entry, add_edge, template_name, include_goal_edges=False
                    )
                    add_edge("template", template_name, "goal", goal_name)
                    for player_name in self.template_to_players.get(template_name, []):
                        if self._entry_exists(player_name):
                            add_entry("player", player_name, _player_display_name)
                            add_edge(
                                "player",
                                player_name,
                                "template",
                                template_name,
                            )

        columns = [
            (column_titles[column], nodes[column])
            for column in column_order
            if nodes[column]
        ]
        return columns, edges

    def _add_player_graph(self, add_entry, add_edge, player_name: str) -> None:
        """Add a player plus its templates, goals, and goal equations."""
        if not self._entry_exists(player_name):
            return
        add_entry("player", player_name, _player_display_name)
        goal_function_sets = self.player_goal_function_sets.get(player_name)
        for template_name in self.player_to_templates.get(player_name, []):
            if not self._entry_exists(template_name):
                continue
            game_modes = self.player_template_modes.get((player_name, template_name))
            self._add_template_graph(
                add_entry,
                add_edge,
                template_name,
                game_modes=game_modes,
                goal_function_sets=goal_function_sets,
            )
            add_edge("player", player_name, "template", template_name)

    def _add_template_graph(
        self,
        add_entry,
        add_edge,
        template_name: str,
        include_goal_edges: bool = True,
        game_modes: list[str] | None = None,
        goal_function_sets: list[str] | None = None,
    ) -> None:
        """Add a template plus goals referenced by it."""
        if not self._entry_exists(template_name):
            return
        add_entry("template", template_name, _template_display_name)
        if not include_goal_edges:
            return
        for goal_name in self._template_goal_names(template_name, game_modes):
            if not self._entry_exists(goal_name):
                continue
            if not self._goal_matches_function_sets(goal_name, goal_function_sets):
                continue
            add_entry("goal", goal_name, _goal_display_name)
            add_edge("template", template_name, "goal", goal_name)
            self._add_goal_graph(add_entry, add_edge, goal_name, goal_function_sets)

    def _add_goal_graph(
        self,
        add_entry,
        add_edge,
        goal_name: str,
        goal_function_sets: list[str] | None = None,
    ) -> None:
        """Add a goal plus equations linked through goal functions."""
        if not self._entry_exists(goal_name):
            return
        add_entry("goal", goal_name, _goal_display_name)
        for equation_name in self._goal_equation_names(goal_name, goal_function_sets):
            self._add_equation_graph_node(add_entry, equation_name)
            add_edge("goal", goal_name, "equation", equation_name)

    def _goal_equation_names(
        self,
        goal_name: str,
        goal_function_sets: list[str] | None = None,
    ) -> list[str]:
        """Return equations linked to a goal, optionally filtered by function set."""
        equation_names = self.goal_to_equations.get(goal_name, [])
        if not goal_function_sets:
            return equation_names

        allowed_sets = {
            goal_function_set.lower() for goal_function_set in goal_function_sets
        }
        filtered_equations: list[str] = []
        for equation_name in equation_names:
            edge_sets = self.goal_equation_function_sets.get(
                (goal_name, equation_name),
                [],
            )
            if any(edge_set.lower() in allowed_sets for edge_set in edge_sets):
                filtered_equations.append(equation_name)
        return filtered_equations

    def _goal_matches_function_sets(
        self,
        goal_name: str,
        goal_function_sets: list[str] | None,
    ) -> bool:
        """Return whether a goal has a valid equation for the function set filter."""
        if not goal_function_sets:
            return True
        return bool(self._goal_equation_names(goal_name, goal_function_sets))

    def _add_equation_graph_node(self, add_entry, equation_name: str) -> None:
        """Add one equation node if loaded."""
        if self._entry_exists(equation_name):
            add_entry("equation", equation_name, lambda name: name)

    def _template_goal_names(
        self,
        template_name: str,
        game_modes: list[str] | None = None,
    ) -> list[str]:
        """Return concrete goal names referenced by one template."""
        if self.index is None:
            return []

        entry = self.index.get(template_name)
        if entry is None:
            return []

        goal_names: list[str] = []
        for line in entry.normalized_expression.splitlines():
            if "=" not in line:
                continue
            field_key, field_value = line.split("=", 1)
            resolver = self._template_goal_field_resolver(field_key.strip())
            if resolver is None:
                continue
            for value in self._split_structured_value(field_value):
                for _text, target in resolver(value):
                    if target is None or target in goal_names:
                        continue
                    if not self._goal_matches_game_modes(target, game_modes):
                        continue
                    goal_names.append(target)

        return goal_names

    def _goal_matches_game_modes(
        self,
        goal_name: str,
        game_modes: list[str] | None,
    ) -> bool:
        """Return whether a goal matches the player template mode filter."""
        if not game_modes:
            return True
        fields = self._goal_fields(goal_name)
        game_mode = fields.get("gamemode")
        if game_mode is None:
            return False
        return game_mode.lower() in {mode.lower() for mode in game_modes}

    def _goal_fields(self, goal_name: str) -> dict[str, str]:
        """Return parsed structured fields for one loaded goal."""
        if self.index is None:
            return {}
        goal = self.index.get(goal_name)
        if goal is None:
            return {}
        return parse_structured_fields(goal.normalized_expression)

    def _templates_for_goal(self, goal_name: str) -> list[str]:
        """Return loaded templates that reference one goal directly or by category."""
        if self.index is None:
            return []
        template_names: list[str] = []
        for entry_name in self.index.effective_equations.keys():
            if self._entry_type(entry_name) != "template":
                continue
            if goal_name in self._template_goal_names(entry_name):
                template_names.append(entry_name)
        return template_names

    def _entry_exists(self, entry_name: str) -> bool:
        """Return whether an entry is loaded."""
        return self.index is not None and self.index.get(entry_name) is not None

    def _build_template_goal_field_links(
        self,
        entry_name: str,
    ) -> dict[tuple[str, str], list[tuple[str, str | None]]]:
        """Build field-value links from template goal fields to matching goals."""
        if self.index is None:
            return {}

        entry = self.index.get(entry_name)
        if entry is None:
            return {}

        links: dict[tuple[str, str], list[tuple[str, str | None]]] = {}
        for line in entry.normalized_expression.splitlines():
            if "=" not in line:
                continue
            field_key, field_value = line.split("=", 1)
            field_key = field_key.strip()
            resolver = self._template_goal_field_resolver(field_key)
            if resolver is None:
                continue
            for value in self._split_structured_value(field_value):
                goal_links = resolver(value)
                if goal_links:
                    links[(field_key, value)] = goal_links

        return links

    def _template_goal_field_resolver(
        self,
        field_key: str,
    ) -> Callable[[str], list[tuple[str, str | None]]] | None:
        """Return the resolver for a template goal-list field."""
        leaf_key = field_key.rsplit("/", 1)[-1].lower()
        if leaf_key == "goal_type":
            return self._resolve_goal_name_links
        if leaf_key in {"category", "goal_category"}:
            return self._resolve_goal_category_links
        if leaf_key == "goals":
            return self._resolve_goal_value_links
        return None

    def _resolve_goal_value_links(self, value: str) -> list[tuple[str, str | None]]:
        """Resolve legacy template goal values as a name first, then category."""
        direct_links = self._resolve_goal_name_links(value)
        if direct_links:
            return direct_links
        return self._resolve_goal_category_links(value)

    def _resolve_goal_name_links(self, value: str) -> list[tuple[str, str | None]]:
        """Resolve one template goal-list value as an explicit goal name."""
        if self.index is None:
            return []

        direct_goal_name = normalize_goal_name(value)
        if direct_goal_name is not None and self.index.get(direct_goal_name) is not None:
            return [(_goal_display_name(direct_goal_name), direct_goal_name)]
        return []

    def _resolve_goal_category_links(self, value: str) -> list[tuple[str, str | None]]:
        """Resolve one template goal-list value as a goal category."""
        if self.index is None:
            return []

        matching_goals: list[tuple[str, str | None]] = []
        for goal_name in sorted(self._goal_names(), key=str.lower):
            fields = self._goal_fields(goal_name)
            category = fields.get("category")
            if category is not None and category.lower() == value.strip().lower():
                matching_goals.append((_goal_display_name(goal_name), goal_name))

        if not matching_goals:
            return []
        return [(value, None), *matching_goals]

    def _goal_names(self) -> list[str]:
        """Return loaded goal entry names."""
        if self.index is None:
            return []
        return [
            name
            for name in self.index.effective_equations.keys()
            if self._entry_type(name) == "goal"
        ]

    def _template_field_keys(
        self,
        entry_name: str,
        template_display_name: str,
        template_name: str,
    ) -> set[str]:
        """Find player structured fields containing one template value."""
        if self.index is None:
            return set()

        entry = self.index.get(entry_name)
        if entry is None:
            return set()

        field_keys: set[str] = set()
        for line in entry.normalized_expression.splitlines():
            if "=" not in line:
                continue
            field_key, field_value = line.split("=", 1)
            field_key = field_key.strip()
            if not field_key.lower().startswith("templates/"):
                continue
            field_values = self._split_structured_value(field_value)
            if template_display_name in field_values or template_name in field_values:
                field_keys.add(field_key)

        return field_keys

    def _split_structured_value(self, field_value: str) -> list[str]:
        """Split a structured field value into individual tokens."""
        return [item.strip() for item in field_value.replace(",", " ").split()]

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
                self.view.build_evaluable_expression(
                    lambda token_key, raw_value: clamp_token_value(
                        token_key,
                        raw_value,
                        self.token_bounds,
                    )
                )
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
        function_name = extract_function_name(token_key)
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
