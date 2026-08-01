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
    normalized = RANDOM_OPERATOR_PATTERN.sub(r"rand(\1, \2)", normalized)
    return _normalize_parenthesized_random_ranges(normalized)


def _normalize_parenthesized_random_ranges(expression: str) -> str:
    """Normalize parenthesized EAW random ranges with expression operands."""
    result: list[str] = []
    index = 0
    while index < len(expression):
        if expression[index] != "(":
            result.append(expression[index])
            index += 1
            continue

        paren_depth = brace_depth = 0
        hash_position: int | None = None
        multiple_hashes = False
        quoted = False
        closing = None
        cursor = index + 1
        while cursor < len(expression):
            character = expression[cursor]
            if quoted:
                quoted = character != '"' or expression[cursor - 1] == "\\"
            elif character == '"':
                quoted = True
            elif character == "{":
                brace_depth += 1
            elif character == "}" and brace_depth:
                brace_depth -= 1
            elif brace_depth == 0 and character == "(":
                paren_depth += 1
            elif brace_depth == 0 and character == ")":
                if paren_depth == 0:
                    closing = cursor
                    break
                paren_depth -= 1
            elif brace_depth == 0 and character == "#":
                if hash_position is None:
                    hash_position = cursor
                else:
                    multiple_hashes = True
            cursor += 1

        if closing is None:
            result.append(expression[index:])
            break

        if hash_position is not None and not multiple_hashes:
            left = _normalize_parenthesized_random_ranges(
                expression[index + 1 : hash_position]
            ).strip()
            right = _normalize_parenthesized_random_ranges(
                expression[hash_position + 1 : closing]
            ).strip()
            result.append(f"rand({left}, {right})" if left and right else expression[index : closing + 1])
        else:
            inner = _normalize_parenthesized_random_ranges(
                expression[index + 1 : closing]
            )
            result.append(f"({inner})")
        index = closing + 1

    return "".join(result)


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
