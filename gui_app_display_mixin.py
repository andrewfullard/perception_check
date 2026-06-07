from __future__ import annotations

from functools import partial
import tkinter as tk
from tkinter import messagebox
from typing import Callable

from perceptual_equations_parser import PerceptualEquation
from gui_app_text_utils import (
    normalize_goal_name,
    parse_structured_fields,
    strip_entry_prefix,
)


_goal_display_name = partial(strip_entry_prefix, prefix="Goal::")
_player_display_name = partial(strip_entry_prefix, prefix="Player::")
_template_display_name = partial(strip_entry_prefix, prefix="Template::")


class _RelationshipGraphBuilder:
    """Collect graph nodes and edges in fixed display lanes."""

    _COLUMN_ORDER = ("player", "template", "goal", "equation")
    _COLUMN_TITLES = {
        "player": "AI Players",
        "template": "AI Templates",
        "goal": "AI Goals",
        "equation": "Equations",
    }

    def __init__(self) -> None:
        self.nodes: dict[str, list[tuple[str, str, str | None]]] = {
            column: [] for column in self._COLUMN_ORDER
        }
        self.node_ids: set[str] = set()
        self.edges: list[tuple[str, str]] = []
        self.edge_ids: set[tuple[str, str]] = set()

    def add_entry(
        self,
        column: str,
        entry_name: str,
        label_for,
    ) -> None:
        """Add one clickable entry node."""
        node_id = self.node_id(column, entry_name)
        if node_id in self.node_ids:
            return
        self.node_ids.add(node_id)
        self.nodes[column].append((node_id, label_for(entry_name), entry_name))

    def add_edge(
        self,
        source_column: str,
        source_name: str,
        target_column: str,
        target_name: str,
    ) -> None:
        """Add one directed edge between entry nodes."""
        edge = (
            self.node_id(source_column, source_name),
            self.node_id(target_column, target_name),
        )
        if edge in self.edge_ids:
            return
        self.edge_ids.add(edge)
        self.edges.append(edge)

    def to_view_data(
        self,
    ) -> tuple[
        list[tuple[str, list[tuple[str, str, str | None]]]],
        list[tuple[str, str]],
    ]:
        """Return non-empty graph columns and edges for the view."""
        columns = [
            (self._COLUMN_TITLES[column], self.nodes[column])
            for column in self._COLUMN_ORDER
            if self.nodes[column]
        ]
        return columns, self.edges

    def node_id(self, column: str, entry_name: str) -> str:
        """Return stable graph node ID for one lane entry."""
        return f"{column}:{entry_name}"


class PerceptualEquationsAppDisplayMixin:
    """UI list refresh, selection handlers, and related-link rendering."""

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
        graph = _RelationshipGraphBuilder()
        entry_type = self._entry_type(entry_name)

        if entry_type == "player":
            self._add_player_graph(graph, entry_name)
        elif entry_type == "template":
            self._add_template_graph(graph, entry_name)
            for player_name in self.template_to_players.get(entry_name, []):
                if self._entry_exists(player_name):
                    graph.add_entry("player", player_name, _player_display_name)
                    graph.add_edge("player", player_name, "template", entry_name)
        elif entry_type == "goal":
            self._add_goal_graph(graph, entry_name)
            for template_name in self._templates_for_goal(entry_name):
                self._add_template_graph(graph, template_name, include_goal_edges=False)
                graph.add_edge("template", template_name, "goal", entry_name)
                for player_name in self.template_to_players.get(template_name, []):
                    if self._entry_exists(player_name):
                        graph.add_entry("player", player_name, _player_display_name)
                        graph.add_edge("player", player_name, "template", template_name)
        elif entry_type == "goal_function":
            goal_function_link = self.goal_function_links.get(entry_name)
            if goal_function_link:
                goal_name, equation_name = goal_function_link
                self._add_goal_graph(graph, goal_name)
                self._add_equation_graph_node(graph, equation_name)
                graph.add_edge("goal", goal_name, "equation", equation_name)
        else:
            self._add_equation_graph_node(graph, entry_name)
            for goal_name in self.equation_to_goals.get(entry_name, []):
                if not self._entry_exists(goal_name):
                    continue
                self._add_goal_graph(graph, goal_name)
                graph.add_edge("goal", goal_name, "equation", entry_name)
                for template_name in self._templates_for_goal(goal_name):
                    self._add_template_graph(graph, template_name, include_goal_edges=False)
                    graph.add_edge("template", template_name, "goal", goal_name)
                    for player_name in self.template_to_players.get(template_name, []):
                        if self._entry_exists(player_name):
                            graph.add_entry("player", player_name, _player_display_name)
                            graph.add_edge(
                                "player",
                                player_name,
                                "template",
                                template_name,
                            )

        return graph.to_view_data()

    def _add_player_graph(self, graph, player_name: str) -> None:
        """Add a player plus its templates, goals, and goal equations."""
        if not self._entry_exists(player_name):
            return
        graph.add_entry("player", player_name, _player_display_name)
        goal_function_sets = self.player_goal_function_sets.get(player_name)
        for template_name in self.player_to_templates.get(player_name, []):
            if not self._entry_exists(template_name):
                continue
            game_modes = self.player_template_modes.get((player_name, template_name))
            self._add_template_graph(
                graph,
                template_name,
                game_modes=game_modes,
                goal_function_sets=goal_function_sets,
            )
            graph.add_edge("player", player_name, "template", template_name)

    def _add_template_graph(
        self,
        graph,
        template_name: str,
        include_goal_edges: bool = True,
        game_modes: list[str] | None = None,
        goal_function_sets: list[str] | None = None,
    ) -> None:
        """Add a template plus goals referenced by it."""
        if not self._entry_exists(template_name):
            return
        graph.add_entry("template", template_name, _template_display_name)
        if not include_goal_edges:
            return
        for goal_name in self._template_goal_names(template_name, game_modes):
            if not self._entry_exists(goal_name):
                continue
            if not self._goal_matches_function_sets(goal_name, goal_function_sets):
                continue
            graph.add_entry("goal", goal_name, _goal_display_name)
            graph.add_edge("template", template_name, "goal", goal_name)
            self._add_goal_graph(graph, goal_name, goal_function_sets)

    def _add_goal_graph(
        self,
        graph,
        goal_name: str,
        goal_function_sets: list[str] | None = None,
    ) -> None:
        """Add a goal plus equations linked through goal functions."""
        if not self._entry_exists(goal_name):
            return
        graph.add_entry("goal", goal_name, _goal_display_name)
        for equation_name in self._goal_equation_names(goal_name, goal_function_sets):
            self._add_equation_graph_node(graph, equation_name)
            graph.add_edge("goal", goal_name, "equation", equation_name)

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

    def _add_equation_graph_node(self, graph, equation_name: str) -> None:
        """Add one equation node if loaded."""
        if self._entry_exists(equation_name):
            graph.add_entry("equation", equation_name, lambda name: name)

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
