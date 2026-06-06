from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Callable


StructuredLinkMap = dict[tuple[str, str], list[tuple[str, str | None]]]


_EDITABLE_TOKEN_PATTERN = re.compile(
    r"(?:(?:Variable[\w\.]*)|(?:Game\.[\w\.]*)|(?:Function_[\w\.]*)|(?:Script_[\w\.]*))"
    r"(?:\s*\{[^}]*\})?"
)


class PerceptualEquationsView:
    """Build and own Tkinter widgets/variables for the equation viewer."""

    def __init__(self, root: tk.Tk) -> None:
        """Create UI state and render the layout."""
        self.root = root
        self.root.title("Perception Check")
        self.root.geometry("1000x650")

        self.folder_var = tk.StringVar(value="No folder loaded")
        self.search_var = tk.StringVar()
        self.goals_search_var = tk.StringVar()
        self.players_search_var = tk.StringVar()
        self.templates_search_var = tk.StringVar()
        self.layer_var = tk.StringVar(value="-")
        self.source_var = tk.StringVar(value="-")
        self.range_var = tk.StringVar(value="-")
        self.result_var = tk.StringVar(value="-")
        self.stack_root_var = tk.StringVar(value="")
        self.upper_layer_1_var = tk.StringVar(value="TR")
        self.upper_layer_2_var = tk.StringVar(value="")
        self.current_expression_template = ""

        self.names_listbox: tk.Listbox
        self.goals_listbox: tk.Listbox
        self.players_listbox: tk.Listbox
        self.templates_listbox: tk.Listbox
        self.expression_canvas: tk.Canvas
        self.expression_content: ttk.Frame
        self.evaluate_row: ttk.Frame
        self.links_row: ttk.Frame
        self.links_canvas: tk.Canvas
        self.links_content: ttk.Frame
        self._links_canvas_window: int
        self._expression_canvas_window: int
        self.variable_value_vars: dict[str, tk.StringVar] = {}
        self._on_function_token_click: Callable[[str], None] | None = None
        self._on_entry_link_click: Callable[[str], None] | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Create all widgets for loading, searching, and viewing equations."""
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        self.load_stack_button = ttk.Button(top, text="Load Stack")
        self.load_stack_button.pack(side=tk.LEFT)

        ttk.Label(top, textvariable=self.folder_var).pack(
            side=tk.LEFT, padx=(12, 0), fill=tk.X, expand=True
        )

        stack_frame = ttk.LabelFrame(self.root, text="Stack Settings", padding=10)
        stack_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

        ttk.Label(stack_frame, text="Root").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(stack_frame, textvariable=self.stack_root_var).grid(
            row=0, column=1, sticky=tk.EW, padx=(8, 8)
        )
        self.browse_stack_root_button = ttk.Button(stack_frame, text="Browse")
        self.browse_stack_root_button.grid(row=0, column=2, sticky=tk.W)

        ttk.Label(stack_frame, text="Layer 0 (fixed)").grid(
            row=1, column=0, sticky=tk.W, pady=(6, 0)
        )
        ttk.Label(stack_frame, text="Data").grid(
            row=1, column=1, sticky=tk.W, pady=(6, 0)
        )

        ttk.Label(stack_frame, text="Layer 1").grid(
            row=2, column=0, sticky=tk.W, pady=(6, 0)
        )
        ttk.Entry(stack_frame, textvariable=self.upper_layer_1_var).grid(
            row=2, column=1, sticky=tk.EW, padx=(8, 8), pady=(6, 0)
        )

        ttk.Label(stack_frame, text="Layer 2").grid(
            row=3, column=0, sticky=tk.W, pady=(6, 0)
        )
        ttk.Entry(stack_frame, textvariable=self.upper_layer_2_var).grid(
            row=3, column=1, sticky=tk.EW, padx=(8, 8), pady=(6, 0)
        )

        stack_frame.columnconfigure(1, weight=1)

        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(main, padding=8)
        right = ttk.Frame(main, padding=8)
        main.add(left, weight=1)
        main.add(right, weight=3)

        left_tabs = ttk.Notebook(left)
        left_tabs.pack(fill=tk.BOTH, expand=True)

        entries_tab = ttk.Frame(left_tabs)
        goals_tab = ttk.Frame(left_tabs)
        players_tab = ttk.Frame(left_tabs)
        templates_tab = ttk.Frame(left_tabs)
        left_tabs.add(entries_tab, text="Equations")
        left_tabs.add(goals_tab, text="AI Goals")
        left_tabs.add(players_tab, text="AI Players")
        left_tabs.add(templates_tab, text="AI Templates")

        self.names_listbox = self._build_search_list_tab(entries_tab, self.search_var)
        self.goals_listbox = self._build_search_list_tab(
            goals_tab, self.goals_search_var
        )
        self.players_listbox = self._build_search_list_tab(
            players_tab, self.players_search_var
        )
        self.templates_listbox = self._build_search_list_tab(
            templates_tab, self.templates_search_var
        )

        detail_header = ttk.Frame(right)
        detail_header.pack(fill=tk.X)

        ttk.Label(detail_header, text="Layer:").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(detail_header, textvariable=self.layer_var).grid(
            row=0, column=1, sticky=tk.W, padx=(6, 20)
        )

        ttk.Label(detail_header, text="Source File:").grid(row=0, column=2, sticky=tk.W)
        ttk.Label(detail_header, textvariable=self.source_var).grid(
            row=0, column=3, sticky=tk.W, padx=(6, 0)
        )

        ttk.Label(detail_header, text="Range:").grid(
            row=1, column=0, sticky=tk.W, pady=(6, 0)
        )
        ttk.Label(detail_header, textvariable=self.range_var).grid(
            row=1, column=1, columnspan=3, sticky=tk.W, padx=(6, 0), pady=(6, 0)
        )

        self.links_row = ttk.Frame(right)
        self.links_row.pack(fill=tk.X, pady=(8, 4))
        ttk.Label(self.links_row, text="Links:").pack(side=tk.LEFT, anchor=tk.N)

        links_host = ttk.Frame(self.links_row, relief=tk.SUNKEN, borderwidth=1)
        links_host.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        self.links_canvas = tk.Canvas(links_host, height=88, highlightthickness=0)
        links_scroll = ttk.Scrollbar(
            links_host,
            orient=tk.VERTICAL,
            command=self.links_canvas.yview,
        )
        self.links_canvas.configure(yscrollcommand=links_scroll.set)

        self.links_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        links_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.links_content = ttk.Frame(self.links_canvas)
        self._links_canvas_window = self.links_canvas.create_window(
            (0, 0), window=self.links_content, anchor="nw"
        )
        self.links_content.bind(
            "<Configure>",
            lambda _e: self.links_canvas.configure(
                scrollregion=self.links_canvas.bbox("all")
            ),
        )
        self.links_canvas.bind("<Configure>", self._on_links_canvas_resize)

        ttk.Label(right, text="Expression").pack(anchor=tk.W, pady=(8, 4))

        self.evaluate_row = ttk.Frame(right)
        self.evaluate_row.pack(fill=tk.X, pady=(0, 6))
        self.evaluate_button = ttk.Button(self.evaluate_row, text="Evaluate")
        self.evaluate_button.pack(side=tk.LEFT)
        ttk.Label(self.evaluate_row, text="Result:").pack(side=tk.LEFT, padx=(12, 4))
        ttk.Label(self.evaluate_row, textvariable=self.result_var).pack(side=tk.LEFT)

        expression_host = ttk.Frame(right)
        expression_host.pack(fill=tk.BOTH, expand=True)

        self.expression_canvas = tk.Canvas(expression_host, highlightthickness=0)
        expression_scroll = ttk.Scrollbar(
            expression_host, orient=tk.VERTICAL, command=self.expression_canvas.yview
        )
        self.expression_canvas.configure(yscrollcommand=expression_scroll.set)

        self.expression_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        expression_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.expression_content = ttk.Frame(self.expression_canvas)
        self._expression_canvas_window = self.expression_canvas.create_window(
            (0, 0), window=self.expression_content, anchor="nw"
        )

        self.expression_content.bind(
            "<Configure>",
            lambda _e: self.expression_canvas.configure(
                scrollregion=self.expression_canvas.bbox("all")
            ),
        )
        self.expression_canvas.bind("<Configure>", self._on_expression_canvas_resize)

    def _build_search_list_tab(
        self,
        parent: ttk.Frame,
        search_var: tk.StringVar,
    ) -> tk.Listbox:
        """Create a search field plus scrollable listbox for a notebook tab."""
        ttk.Label(parent, text="Search").pack(anchor=tk.W)
        ttk.Entry(parent, textvariable=search_var).pack(fill=tk.X, pady=(4, 8))

        list_host = ttk.Frame(parent)
        list_host.pack(fill=tk.BOTH, expand=True)

        listbox = tk.Listbox(list_host, exportselection=False)
        scrollbar = ttk.Scrollbar(
            list_host,
            orient=tk.VERTICAL,
            command=listbox.yview,
        )
        listbox.configure(yscrollcommand=scrollbar.set)

        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        return listbox

    def bind_handlers(
        self,
        on_load_stack: Callable[[], None],
        on_browse_stack_root: Callable[[], None],
        on_search_changed: Callable[[], None],
        on_selection_changed: Callable[[tk.Event], None],
        on_goal_selection_changed: Callable[[tk.Event], None],
        on_player_selection_changed: Callable[[tk.Event], None],
        on_template_selection_changed: Callable[[tk.Event], None],
        on_evaluate: Callable[[], None],
        on_function_token_click: Callable[[str], None],
        on_entry_link_click: Callable[[str], None],
    ) -> None:
        """Bind controller callbacks to UI events."""
        self.load_stack_button.configure(command=on_load_stack)
        self.browse_stack_root_button.configure(command=on_browse_stack_root)
        self.evaluate_button.configure(command=on_evaluate)
        self._on_function_token_click = on_function_token_click
        self._on_entry_link_click = on_entry_link_click
        self.search_var.trace_add("write", lambda *_: on_search_changed())
        self.goals_search_var.trace_add("write", lambda *_: on_search_changed())
        self.players_search_var.trace_add("write", lambda *_: on_search_changed())
        self.templates_search_var.trace_add("write", lambda *_: on_search_changed())
        self.names_listbox.bind("<<ListboxSelect>>", on_selection_changed)
        self.goals_listbox.bind("<<ListboxSelect>>", on_goal_selection_changed)
        self.players_listbox.bind("<<ListboxSelect>>", on_player_selection_changed)
        self.templates_listbox.bind("<<ListboxSelect>>", on_template_selection_changed)

    def set_related_links(self, links: list[tuple[str, str]]) -> None:
        """Render related-entry links in the details panel."""
        for child in self.links_content.winfo_children():
            child.destroy()

        if not links:
            ttk.Label(self.links_content, text="-").pack(anchor="w")
            self.links_canvas.yview_moveto(0)
            return

        for text, target in links:
            link = tk.Label(
                self.links_content,
                text=text,
                fg="#1a73e8",
                cursor="hand2",
                justify=tk.LEFT,
                anchor="w",
            )
            link.pack(anchor="w")
            link.bind(
                "<Button-1>",
                lambda _e, entry_name=target: self._handle_entry_link_click(entry_name),
            )

        self.links_canvas.yview_moveto(0)

    def _set_listbox_items(self, listbox: tk.Listbox, items: list[str]) -> None:
        """Replace all items in a listbox."""
        listbox.delete(0, tk.END)
        for item in items:
            listbox.insert(tk.END, item)

    def set_evaluation_controls_visible(self, visible: bool) -> None:
        """Show or hide evaluation controls for the current entry type."""
        if visible:
            if not self.evaluate_row.winfo_manager():
                self.evaluate_row.pack(
                    fill=tk.X, pady=(0, 6), before=self.expression_canvas.master
                )
            return

        if self.evaluate_row.winfo_manager():
            self.evaluate_row.pack_forget()

    def set_expression_text(
        self,
        value: str,
        structured: bool = False,
        structured_links: StructuredLinkMap | None = None,
    ) -> None:
        """Render expression text as equation tokens or structured XML fields."""
        self.current_expression_template = value
        self._clear_expression_widgets()

        if structured:
            structured_fields = self._parse_structured_fields(value)
            if structured_fields is not None:
                self._render_structured_fields(structured_fields, structured_links)
                return

        parts = self._tokenize_expression(value)
        row = 0
        for part_type, text in parts:
            cleaned = text.strip()
            if not cleaned:
                continue

            if part_type == "editable":
                token_key = self._normalize_token_label(cleaned)
                value_var = self.variable_value_vars.get(token_key)
                if value_var is None:
                    value_var = tk.StringVar(value="0")
                    self.variable_value_vars[token_key] = value_var

                token_box = ttk.LabelFrame(
                    self.expression_content,
                    text=token_key,
                    padding=(8, 6),
                )
                token_box.grid(row=row, column=0, sticky="ew", pady=(2, 4))

                if token_key.startswith("Function_"):
                    link = tk.Label(
                        token_box,
                        text="Open function",
                        fg="#1a73e8",
                        cursor="hand2",
                    )
                    link.pack(anchor="w", pady=(0, 4))
                    link.bind(
                        "<Button-1>",
                        lambda _e, token=token_key: self._handle_function_click(token),
                    )

                ttk.Entry(token_box, textvariable=value_var, width=16).pack(anchor="w")
            else:
                ttk.Label(
                    self.expression_content,
                    text=self._normalize_operator_text(cleaned),
                    wraplength=700,
                    justify=tk.LEFT,
                ).grid(row=row, column=0, sticky="w", pady=(2, 2))

            row += 1

        self.expression_content.columnconfigure(0, weight=1)

    def _parse_structured_fields(self, value: str) -> list[tuple[str, str]] | None:
        """Parse key=value lines for non-equation XML entry rendering."""
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if not lines:
            return None

        fields: list[tuple[str, str]] = []
        for line in lines:
            if "=" not in line:
                return None
            key, field_value = line.split("=", 1)
            key = key.strip()
            field_value = field_value.strip()
            if not key:
                return None
            fields.append((key, field_value))

        return fields

    def _value_list_items(self, field_value: str) -> list[str] | None:
        """Return list items when a field value appears to be a token list."""
        newline_items = [
            item.strip() for item in field_value.splitlines() if item.strip()
        ]
        if len(newline_items) > 1:
            return newline_items

        space_items = field_value.split()
        if len(space_items) <= 1:
            return None

        # Treat values as list-like only when each token resembles an identifier.
        if not all(re.fullmatch(r"[A-Za-z0-9_.:-]+", item) for item in space_items):
            return None

        # Avoid splitting plain prose by requiring identifier-style hints.
        if any(re.search(r"[_.\d]|[a-z][A-Z]", item) for item in space_items):
            return space_items

        return None

    def _render_structured_fields(
        self,
        fields: list[tuple[str, str]],
        links: StructuredLinkMap | None = None,
    ) -> None:
        """Render structured key/value fields with hierarchical tag indentation."""
        row = 0
        previous_path: list[str] = []
        links = links or {}

        for key, field_value in fields:
            key_path = [part for part in key.split("/") if part]
            if not key_path:
                key_path = [key]

            shared_depth = 0
            while (
                shared_depth < len(previous_path)
                and shared_depth < len(key_path)
                and previous_path[shared_depth] == key_path[shared_depth]
            ):
                shared_depth += 1

            field_frame = ttk.Frame(self.expression_content)
            field_frame.grid(row=row, column=0, sticky="ew", pady=(2, 6))

            for depth, tag_name in enumerate(key_path):
                if depth < shared_depth:
                    continue
                ttk.Label(
                    field_frame,
                    text=tag_name,
                    font=("TkDefaultFont", 10, "bold"),
                    justify=tk.LEFT,
                    anchor="w",
                ).pack(anchor="w", padx=(depth * 12, 0))

            value_items = self._value_list_items(field_value)
            value_indent = len(key_path) * 12
            if value_items is None:
                self._render_structured_value(
                    field_frame,
                    key,
                    field_value,
                    links,
                    value_indent,
                )
            else:
                values_frame = ttk.Frame(field_frame)
                values_frame.pack(anchor="w", padx=(value_indent, 0), pady=(2, 0))
                for item in value_items:
                    self._render_structured_value(values_frame, key, item, links, 0)

            previous_path = key_path
            row += 1

        self.expression_content.columnconfigure(0, weight=1)

    def _render_structured_value(
        self,
        parent: tk.Widget,
        field_key: str,
        value: str,
        links: StructuredLinkMap,
        indent: int,
    ) -> None:
        """Render one structured value as text or a navigation link."""
        targets = links.get((field_key, value))
        if targets is None:
            ttk.Label(
                parent,
                text=value,
                wraplength=700,
                justify=tk.LEFT,
                anchor="w",
            ).pack(anchor="w", padx=(indent, 0), pady=(2, 0))
            return

        for index, (text, target) in enumerate(targets):
            if target is None:
                ttk.Label(
                    parent,
                    text=text,
                    font=("TkDefaultFont", 10, "bold"),
                    justify=tk.LEFT,
                    anchor="w",
                ).pack(
                    anchor="w",
                    padx=(indent, 0),
                    pady=(2 if index == 0 else 0, 0),
                )
                continue

            link = tk.Label(
                parent,
                text=text,
                fg="#1a73e8",
                cursor="hand2",
                justify=tk.LEFT,
                anchor="w",
            )
            link.pack(
                anchor="w",
                padx=(indent, 0),
                pady=(2 if index == 0 else 0, 0),
            )
            link.bind(
                "<Button-1>",
                lambda _e, entry_name=target: self._handle_entry_link_click(entry_name),
            )

    def _tokenize_expression(self, expression: str) -> list[tuple[str, str]]:
        """Split expression into alternating editable token and operator chunks."""
        parts: list[tuple[str, str]] = []
        cursor = 0

        for match in _EDITABLE_TOKEN_PATTERN.finditer(expression):
            if match.start() > cursor:
                parts.append(("operator", expression[cursor : match.start()]))
            parts.append(("editable", match.group(0)))
            cursor = match.end()

        if cursor < len(expression):
            parts.append(("operator", expression[cursor:]))

        return parts

    def _normalize_token_label(self, text: str) -> str:
        """Normalize token labels while preserving parameter blocks as identity."""
        return " ".join(text.split())

    def _normalize_operator_text(self, text: str) -> str:
        """Normalize operator chunks while preserving explicit line breaks."""
        lines = [" ".join(line.split()) for line in text.splitlines()]
        non_empty_lines = [line for line in lines if line]
        if non_empty_lines:
            return "\n".join(non_empty_lines)
        return " ".join(text.split())

    def _clear_expression_widgets(self) -> None:
        """Remove previously rendered expression form controls."""
        for child in self.expression_content.winfo_children():
            child.destroy()

    def _on_expression_canvas_resize(self, event: tk.Event) -> None:
        """Keep embedded expression frame width synced to canvas width."""
        self.expression_canvas.itemconfigure(
            self._expression_canvas_window, width=event.width
        )

    def _on_links_canvas_resize(self, event: tk.Event) -> None:
        """Keep embedded links frame width synced to canvas width."""
        self.links_canvas.itemconfigure(self._links_canvas_window, width=event.width)

    def _handle_function_click(self, token_key: str) -> None:
        """Notify controller when a function token link is clicked."""
        if self._on_function_token_click is not None:
            self._on_function_token_click(token_key)

    def _handle_entry_link_click(self, entry_name: str) -> None:
        """Notify controller when a related-entry link is clicked."""
        if self._on_entry_link_click is not None:
            self._on_entry_link_click(entry_name)

    def build_evaluable_expression(
        self,
        token_value_transform: Callable[[str, str], str] | None = None,
    ) -> str:
        """Substitute editable token values into the current expression template."""

        def _replace(match: re.Match[str]) -> str:
            token_key = self._normalize_token_label(match.group(0))
            value_var = self.variable_value_vars.get(token_key)
            if value_var is None:
                value_text = "0"
            else:
                value_text = value_var.get().strip() or "0"

            if token_value_transform is None:
                return value_text
            return token_value_transform(token_key, value_text)

        return _EDITABLE_TOKEN_PATTERN.sub(_replace, self.current_expression_template)
