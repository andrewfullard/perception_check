from __future__ import annotations

import ast
from dataclasses import dataclass
import math
import re

from perceptual_equations_parser import PerceptualEquationIndex
from perceptual_token_bounds import TokenBounds, get_token_bounds
from gui_app_text_utils import extract_function_name


_EDITABLE_TOKEN_PATTERN = re.compile(
    r"(?:(?:Variable[\w\.]*)|(?:Game\.[\w\.]*)|(?:Function_[\w\.]*)|(?:Script_[\w\.]*))"
    r"(?:\s*\{[^}]*\})?"
)

_RANDOM_OPERATOR_PATTERN = re.compile(
    r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*#\s*(-?\d+(?:\.\d+)?)(?![\w.])"
)


@dataclass(frozen=True)
class NumericRange:
    """Closed interval for possible numeric values."""

    minimum: float
    maximum: float

    def is_finite(self) -> bool:
        return math.isfinite(self.minimum) and math.isfinite(self.maximum)

    def clamp(self, minimum: float, maximum: float) -> NumericRange:
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        low = max(self.minimum, minimum)
        high = min(self.maximum, maximum)
        if low > high:
            low, high = minimum, maximum
        return NumericRange(low, high)


class PerceptualEquationRangeAnalyzer:
    """Compute min/max ranges for equations based on token bounds."""

    def __init__(
        self,
        index: PerceptualEquationIndex,
        token_bounds_map: dict[str, TokenBounds],
    ) -> None:
        self._index = index
        self._token_bounds_map = token_bounds_map
        self._cache: dict[str, NumericRange] = {}
        self._visiting: set[str] = set()

    def compute_equation_range(self, equation_name: str) -> NumericRange:
        """Return min/max for the named equation."""
        cached = self._cache.get(equation_name)
        if cached is not None:
            return cached

        if equation_name in self._visiting:
            # Recursive function cycles are conservatively treated as unconstrained.
            return NumericRange(float("-inf"), float("inf"))

        equation = self._index.require(equation_name)
        self._visiting.add(equation_name)
        try:
            expression = self._normalize_expression_for_eval(
                equation.normalized_expression
            )
            transformed, token_ranges = self._replace_tokens_with_names(expression)
            tree = ast.parse(transformed, mode="eval")
            result = self._eval_node(tree.body, token_ranges)
            self._cache[equation_name] = result
            return result
        finally:
            self._visiting.remove(equation_name)

    def _replace_tokens_with_names(
        self, expression: str
    ) -> tuple[str, dict[str, NumericRange]]:
        token_ranges: dict[str, NumericRange] = {}

        def _replace(match: re.Match[str]) -> str:
            token_key = " ".join(match.group(0).split())
            token_name = f"__tok{len(token_ranges)}"
            token_ranges[token_name] = self._resolve_token_range(token_key)
            return token_name

        return _EDITABLE_TOKEN_PATTERN.sub(_replace, expression), token_ranges

    def _resolve_token_range(self, token_key: str) -> NumericRange:
        function_name = extract_function_name(token_key)
        if function_name:
            if self._index.get(function_name) is None:
                return NumericRange(float("-inf"), float("inf"))
            return self.compute_equation_range(function_name)

        bounds = get_token_bounds(token_key, self._token_bounds_map)
        if bounds is None:
            return NumericRange(float("-inf"), float("inf"))

        minimum = float("-inf") if bounds.min_value is None else float(bounds.min_value)
        maximum = float("inf") if bounds.max_value is None else float(bounds.max_value)
        return NumericRange(minimum, maximum)

    def _normalize_expression_for_eval(self, expression: str) -> str:
        normalized = " ".join(expression.split())
        return _RANDOM_OPERATOR_PATTERN.sub(r"rand(\1, \2)", normalized)

    def _eval_node(self, node: ast.AST, env: dict[str, NumericRange]) -> NumericRange:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                value = 1.0 if node.value else 0.0
                return NumericRange(value, value)
            if isinstance(node.value, (int, float)):
                value = float(node.value)
                return NumericRange(value, value)
            return NumericRange(float("-inf"), float("inf"))

        if isinstance(node, ast.Name):
            return env.get(node.id, NumericRange(float("-inf"), float("inf")))

        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, env)
            if isinstance(node.op, ast.UAdd):
                return operand
            if isinstance(node.op, ast.USub):
                return NumericRange(-operand.maximum, -operand.minimum)
            if isinstance(node.op, ast.Not):
                return NumericRange(0.0, 1.0)
            return NumericRange(float("-inf"), float("inf"))

        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, env)
            right = self._eval_node(node.right, env)
            return self._eval_binop(node.op, left, right)

        if isinstance(node, ast.BoolOp):
            return NumericRange(0.0, 1.0)

        if isinstance(node, ast.Compare):
            return NumericRange(0.0, 1.0)

        if isinstance(node, ast.Call):
            return self._eval_call(node, env)

        return NumericRange(float("-inf"), float("inf"))

    def _eval_binop(
        self, op: ast.operator, left: NumericRange, right: NumericRange
    ) -> NumericRange:
        if isinstance(op, ast.Add):
            return NumericRange(
                left.minimum + right.minimum, left.maximum + right.maximum
            )

        if isinstance(op, ast.Sub):
            return NumericRange(
                left.minimum - right.maximum, left.maximum - right.minimum
            )

        if isinstance(op, ast.Mult):
            candidates = [
                left.minimum * right.minimum,
                left.minimum * right.maximum,
                left.maximum * right.minimum,
                left.maximum * right.maximum,
            ]
            return NumericRange(min(candidates), max(candidates))

        if isinstance(op, ast.Div):
            if right.minimum <= 0 <= right.maximum:
                return NumericRange(float("-inf"), float("inf"))
            candidates = [
                left.minimum / right.minimum,
                left.minimum / right.maximum,
                left.maximum / right.minimum,
                left.maximum / right.maximum,
            ]
            return NumericRange(min(candidates), max(candidates))

        if isinstance(op, ast.FloorDiv):
            if right.minimum <= 0 <= right.maximum:
                return NumericRange(float("-inf"), float("inf"))
            candidates = [
                math.floor(left.minimum / right.minimum),
                math.floor(left.minimum / right.maximum),
                math.floor(left.maximum / right.minimum),
                math.floor(left.maximum / right.maximum),
            ]
            return NumericRange(min(candidates), max(candidates))

        if isinstance(op, ast.Mod):
            if right.minimum <= 0 <= right.maximum:
                return NumericRange(float("-inf"), float("inf"))
            max_abs = max(abs(right.minimum), abs(right.maximum))
            return NumericRange(-max_abs, max_abs)

        if isinstance(op, ast.Pow):
            if (
                left.is_finite()
                and right.is_finite()
                and right.minimum == right.maximum
            ):
                exponent = right.minimum
                candidates = [
                    left.minimum**exponent,
                    left.maximum**exponent,
                ]
                if left.minimum <= 0 <= left.maximum:
                    candidates.append(0.0)
                return NumericRange(min(candidates), max(candidates))
            return NumericRange(float("-inf"), float("inf"))

        return NumericRange(float("-inf"), float("inf"))

    def _eval_call(self, node: ast.Call, env: dict[str, NumericRange]) -> NumericRange:
        if not isinstance(node.func, ast.Name):
            return NumericRange(float("-inf"), float("inf"))

        func_name = node.func.id
        args = [self._eval_node(arg, env) for arg in node.args]

        if func_name == "rand" and len(args) == 2:
            minimum = min(args[0].minimum, args[1].minimum)
            maximum = max(args[0].maximum, args[1].maximum)
            return NumericRange(minimum, maximum)

        if func_name == "clamp" and len(args) == 3:
            return args[0].clamp(args[1].minimum, args[2].maximum)

        if func_name == "min" and args:
            return NumericRange(
                min(arg.minimum for arg in args),
                min(arg.maximum for arg in args),
            )

        if func_name == "max" and args:
            return NumericRange(
                max(arg.minimum for arg in args),
                max(arg.maximum for arg in args),
            )

        if func_name == "abs" and len(args) == 1:
            arg = args[0]
            if arg.minimum <= 0 <= arg.maximum:
                return NumericRange(0.0, max(abs(arg.minimum), abs(arg.maximum)))
            candidates = [abs(arg.minimum), abs(arg.maximum)]
            return NumericRange(min(candidates), max(candidates))

        return NumericRange(float("-inf"), float("inf"))
