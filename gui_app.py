from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from perceptual_equations_parser import PerceptualEquationIndex, PerceptualEquationsParser
from perceptual_equations_range import PerceptualEquationRangeAnalyzer
from perceptual_token_bounds import TokenBounds, load_token_bounds
from gui_view import PerceptualEquationsView
from gui_app_merge_mixin import PerceptualEquationsAppMergeMixin
from gui_app_display_mixin import PerceptualEquationsAppDisplayMixin
from gui_app_eval_mixin import PerceptualEquationsAppEvalMixin


class PerceptualEquationsApp(
    PerceptualEquationsAppMergeMixin,
    PerceptualEquationsAppDisplayMixin,
    PerceptualEquationsAppEvalMixin,
):
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
        self.player_to_templates: dict[str, list[str]] = {}
        self.player_template_modes: dict[tuple[str, str], list[str]] = {}
        self.template_to_players: dict[str, list[str]] = {}
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
