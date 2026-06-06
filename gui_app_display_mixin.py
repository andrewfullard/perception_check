from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from perceptual_equations_parser import PerceptualEquation
from gui_app_text_utils import (
    goal_display_name,
    player_display_name,
    template_display_name,
)


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

        if entry_type == "player":
            for template_name in self.player_to_templates.get(entry_name, []):
                if self.index is not None and self.index.get(template_name) is None:
                    continue
                links.append(
                    (
                        f"Template: {self._template_display_name(template_name)}",
                        template_name,
                    )
                )
            return links

        if entry_type == "template":
            for player_name in self.template_to_players.get(entry_name, []):
                if self.index is not None and self.index.get(player_name) is None:
                    continue
                links.append(
                    (
                        f"Player: {self._player_display_name(player_name)}",
                        player_name,
                    )
                )
            return links

        for goal_name in self.equation_to_goals.get(entry_name, []):
            if self.index is not None and self.index.get(goal_name) is None:
                continue
            links.append((f"Goal: {self._goal_display_name(goal_name)}", goal_name))

        return links

    def _goal_display_name(self, goal_name: str) -> str:
        """Return UI display name for a goal entry."""
        return goal_display_name(goal_name)

    def _player_display_name(self, player_name: str) -> str:
        """Return UI display name for a player entry."""
        return player_display_name(player_name)

    def _template_display_name(self, template_name: str) -> str:
        """Return UI display name for a template entry."""
        return template_display_name(template_name)

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
