from __future__ import annotations

import ast
import random
import re
import tkinter as tk
from tkinter import messagebox
from perceptual_token_bounds import clamp_token_value


class PerceptualEquationsAppEvalMixin:
    """Expression evaluation, function token navigation, and safe eval helpers."""

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
