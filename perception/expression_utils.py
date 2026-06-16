from __future__ import annotations

import ast
import re


TOKEN_PATTERN = re.compile(
    r"(?:(?:Variable[\w\.]*)|(?:Game\.[\w\.]*)|(?:Function_[\w\.]*)|(?:Script_[\w\.]*))"
    r"(?:\s*\{[^}]*\})?"
)
RANDOM_OPERATOR_PATTERN = re.compile(
    r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*#\s*(-?\d+(?:\.\d+)?)(?![\w.])"
)
ALLOWED_AST_NODES = (
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


class ExpressionValidationError(ValueError):
    def __init__(self, message: str, needle: str | None = None) -> None:
        super().__init__(message)
        self.needle = needle


def normalize_for_eval(expression: str) -> str:
    normalized = " ".join(expression.split())
    return RANDOM_OPERATOR_PATTERN.sub(r"rand(\1, \2)", normalized)


def validate_eval_ast(
    tree: ast.AST,
    allowed_func_names: set[str],
    *,
    message_style: str = "lower",
) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise ExpressionValidationError(
                _message(
                    f"unsupported expression construct {node.__class__.__name__}",
                    message_style,
                )
            )

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ExpressionValidationError(
                    _message("only direct function calls are allowed", message_style)
                )
            if node.func.id not in allowed_func_names:
                raise ExpressionValidationError(
                    _message(f"unsupported function '{node.func.id}'", message_style),
                    node.func.id,
                )

        if isinstance(node, ast.Name) and node.id not in allowed_func_names:
            raise ExpressionValidationError(
                _message(f"unknown name in expression: {node.id}", message_style),
                node.id,
            )


def _message(message: str, style: str) -> str:
    if style == "sentence":
        return message[:1].upper() + message[1:]
    return message
