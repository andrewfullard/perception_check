from __future__ import annotations

import ast
import re
from pathlib import Path

from perception.entry_text import extract_function_name
from perception.expression_utils import (
    ExpressionValidationError,
    TOKEN_PATTERN,
    normalize_for_eval,
    validate_eval_ast,
)
from perception.models import PerceptualEquationIndex
from perception.xml_utils import parse_xml_file


_ALLOWED_FUNCTIONS = {"abs", "clamp", "max", "min", "rand"}
_PARAMETER_PATTERN = re.compile(r"\bParameter_\w+\b")


def load_perception_token_names(layer_folders: list[tuple[str, Path]]) -> set[str]:
    """Load PerceptionTokenType enum names from stack folders that have one."""
    names: set[str] = set()
    for _layer_name, equations_folder in layer_folders:
        enum_file = (
            _data_folder_for(equations_folder)
            / "XML"
            / "Enum"
            / "PerceptionTokenType.xml"
        )
        if not enum_file.is_file():
            continue
        root = parse_xml_file(enum_file).getroot()
        if root.tag != "EnumDefinition":
            raise ValueError(
                f"Expected root tag 'EnumDefinition' in {enum_file}, found '{root.tag}'"
            )
        names.update(child.tag for child in root if isinstance(child.tag, str))
    return names


def load_script_evaluator_names(layer_folders: list[tuple[str, Path]]) -> set[str]:
    """Load evaluator script names from stack folders that have them."""
    names: set[str] = set()
    for _layer_name, equations_folder in layer_folders:
        scripts_folder = _data_folder_for(equations_folder) / "Scripts" / "Evaluators"
        if not scripts_folder.is_dir():
            continue
        names.update(script_file.stem for script_file in scripts_folder.glob("*.lua"))
    return names


def load_hint_token_names(layer_folders: list[tuple[str, Path]]) -> set[str]:
    """Load final hint token names from HintSets XML files."""
    names: set[str] = set()
    for _layer_name, equations_folder in layer_folders:
        hint_folder = _data_folder_for(equations_folder) / "XML" / "AI" / "HintSets"
        if not hint_folder.is_dir():
            continue
        for hint_file in sorted(hint_folder.glob("*.xml")):
            root = parse_xml_file(hint_file).getroot()
            if root.tag != "HintSets":
                raise ValueError(
                    f"Expected root tag 'HintSets' in {hint_file}, found '{root.tag}'"
                )
            for hint_set in root:
                if isinstance(hint_set.tag, str):
                    names.update(
                        child.tag for child in hint_set if isinstance(child.tag, str)
                    )
    return names


def collect_equation_validation_errors(
    index: PerceptualEquationIndex,
    perception_token_names: set[str] | None = None,
    script_evaluator_names: set[str] | None = None,
    hint_token_names: set[str] | None = None,
    source_labels: dict[Path, str] | None = None,
) -> list[str]:
    """Return validation errors without blocking equation loading."""
    valid_names = set(index.effective_equations)
    perception_token_names = perception_token_names or set()
    perception_token_case = {
        token_name.lower(): token_name for token_name in perception_token_names
    }
    script_evaluator_names = script_evaluator_names or set()
    hint_token_names = hint_token_names or set()
    source_labels = source_labels or {}
    errors: list[str] = []
    for equation in index:
        try:
            _validate_equation(
                equation,
                valid_names,
                perception_token_case,
                script_evaluator_names,
                hint_token_names,
                errors,
                source_labels.get(equation.source_file),
            )
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def _validate_equation(
    equation,
    valid_names: set[str],
    perception_token_case: dict[str, str],
    script_evaluator_names: set[str],
    hint_token_names: set[str],
    errors: list[str],
    source_label: str | None,
) -> None:
    expression = normalize_for_eval(equation.normalized_expression)
    if expression.count("{") != expression.count("}"):
        raise _error(
            equation.source_file,
            equation.raw_expression,
            f"Unmatched parameter braces in {equation.name}",
            source_label=source_label,
        )

    def replace_token(match: re.Match[str]) -> str:
        token = " ".join(match.group(0).split())
        _validate_evaluate_suffix(
            equation.source_file,
            equation.raw_expression,
            equation.name,
            token,
            source_label,
        )
        script_name = _script_name(token)
        if (
            script_name
            and script_evaluator_names
            and script_name not in script_evaluator_names
        ):
            raise _error(
                equation.source_file,
                equation.raw_expression,
                f"Unknown script evaluator '{script_name}' in {equation.name}",
                token,
                source_label,
            )
        function_name = extract_function_name(token)
        if function_name and function_name not in valid_names:
            raise _error(
                equation.source_file,
                equation.raw_expression,
                f"Unknown perception name '{function_name}' in {equation.name}",
                token,
                source_label,
            )
        if perception_token_case:
            hint_name = _hint_name(token)
            if hint_name and hint_token_names and hint_name not in hint_token_names:
                raise _error(
                    equation.source_file,
                    equation.raw_expression,
                    f"Unknown hint token '{hint_name}' in {equation.name}",
                    hint_name,
                    source_label,
                )
            for token_name in _perception_token_parts(token, hint_token_names):
                canonical_name = perception_token_case.get(token_name.lower())
                if canonical_name is None:
                    raise _error(
                        equation.source_file,
                        equation.raw_expression,
                        f"Unknown perception token '{token_name}' in {equation.name}",
                        token_name,
                        source_label,
                    )
                if token_name != canonical_name:
                    errors.append(
                        str(
                            _error(
                                equation.source_file,
                                equation.raw_expression,
                                (
                                    f"Style note: perception token '{token_name}' "
                                    f"in {equation.name} should be '{canonical_name}'"
                                ),
                                token_name,
                                source_label,
                            )
                        )
                    )
        return "0"

    expression = TOKEN_PATTERN.sub(replace_token, expression)
    try:
        tree = ast.parse(expression, mode="eval")
        validate_eval_ast(tree, _ALLOWED_FUNCTIONS)
    except SyntaxError as exc:
        raise _error(
            equation.source_file,
            equation.raw_expression,
            f"Invalid equation math in {equation.name}: {exc.msg}",
            source_label=source_label,
        ) from exc
    except ExpressionValidationError as exc:
        raise _error(
            equation.source_file,
            equation.raw_expression,
            f"Invalid equation math in {equation.name}: {exc}",
            exc.needle,
            source_label,
        ) from exc


def _data_folder_for(equations_folder: Path) -> Path:
    folder = equations_folder
    if folder.name == "PerceptualEquations":
        folder = folder.parent
    if folder.name == "AI":
        folder = folder.parent
    if folder.name == "XML":
        folder = folder.parent
    return folder


def _perception_token_parts(token: str, hint_token_names: set[str]) -> list[str]:
    base, _, parameters = token.partition("{")
    if base.strip().startswith("Script_"):
        return []
    parts: list[str] = []
    base_parts = base.strip().split(".")
    for index, part in enumerate(base_parts):
        if index > 0 and base_parts[index - 1] == "Hints" and hint_token_names:
            continue
        if part.startswith("Function_"):
            function_name = extract_function_name(part)
            if function_name:
                parts.append("Evaluate")
            continue
        parts.append(part)
    parts.extend(_PARAMETER_PATTERN.findall(parameters))
    return [part for part in parts if part]


def _hint_name(token: str) -> str | None:
    base_parts = token.split("{", 1)[0].strip().split(".")
    for index, part in enumerate(base_parts[:-1]):
        if part == "Hints":
            return base_parts[index + 1] or None
    return None


def _script_name(token: str) -> str | None:
    base = token.split("{", 1)[0].strip()
    if not base.startswith("Script_"):
        return None
    script_ref = base[len("Script_") :]
    if script_ref.endswith(".Evaluate"):
        script_ref = script_ref[: -len(".Evaluate")]
    return script_ref or None


def _validate_evaluate_suffix(
    source_file: Path,
    raw_expression: str,
    equation_name: str,
    token: str,
    source_label: str | None = None,
) -> None:
    base = token.split("{", 1)[0].strip()
    if not (base.startswith("Function_") or base.startswith("Script_")):
        return
    if base.endswith(".Evaluate"):
        return
    raise _error(
        source_file,
        raw_expression,
        f"{base.split('.', 1)[0]} in {equation_name} must end with .Evaluate",
        base,
        source_label,
    )


def _error(
    source_file: Path,
    raw_expression: str,
    message: str,
    needle: str | None = None,
    source_label: str | None = None,
) -> ValueError:
    source = source_label or str(source_file)
    return ValueError(
        f"{source}:{_line_number(source_file, raw_expression, needle)}: {message}"
    )


def _line_number(source_file: Path, raw_expression: str, needle: str | None) -> int:
    try:
        text = source_file.read_text(encoding="utf-8-sig")
    except OSError:
        return 1

    candidates = [needle, raw_expression.strip()]
    position = -1
    for candidate in candidates:
        position = text.find(candidate) if candidate else -1
        if position >= 0:
            break
    if position < 0:
        return 1
    return text.count("\n", 0, position) + 1
