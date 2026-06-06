from __future__ import annotations

import re


def parse_structured_fields(text: str) -> dict[str, str]:
    """Parse normalized key=value lines into a lowercase-key dictionary."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key_text = key.strip().lower()
        value_text = value.strip()
        if key_text and value_text:
            fields[key_text] = value_text
    return fields


def normalize_goal_name(goal_text: str | None) -> str | None:
    """Convert GoalFunction Goal field text into canonical Goal::* form."""
    if goal_text is None:
        return None
    normalized = goal_text.strip()
    if not normalized:
        return None
    if normalized.startswith("Goal::"):
        return normalized
    return f"Goal::{normalized}"


def normalize_template_name(template_text: str | None) -> str | None:
    """Convert a template reference into canonical Template::* form."""
    if template_text is None:
        return None

    normalized = template_text.strip()
    if not normalized:
        return None

    if normalized.startswith("Template::"):
        return normalized

    return f"Template::{normalized}"


def normalize_equation_name(
    function_text: str | None,
    extract_function_name: callable,
) -> str | None:
    """Convert GoalFunction Function field text into canonical equation name."""
    if function_text is None:
        return None

    normalized = function_text.strip()
    if not normalized:
        return None

    extracted = extract_function_name(normalized)
    if extracted:
        return extracted

    if normalized.endswith(".Evaluate"):
        normalized = normalized[: -len(".Evaluate")].strip()

    return normalized or None


def extract_goal_function_link(
    normalized_expression: str,
    extract_function_name: callable,
) -> tuple[str | None, str | None]:
    """Extract normalized Goal::* and equation names from GoalFunction text."""
    fields = parse_structured_fields(normalized_expression)
    goal_value = fields.get("goal")
    function_value = fields.get("function")
    goal_name = normalize_goal_name(goal_value)
    equation_name = normalize_equation_name(function_value, extract_function_name)
    return goal_name, equation_name


def extract_player_template_links(normalized_expression: str) -> list[str]:
    """Extract Template::* references from one Player::* entry text."""
    fields = parse_structured_fields(normalized_expression)
    templates: list[str] = []

    for field_key, field_value in fields.items():
        if not field_key.startswith("templates/"):
            continue
        for template_ref in re.split(r"[\s,]+", field_value.strip()):
            if not template_ref:
                continue
            normalized_template = normalize_template_name(template_ref)
            if normalized_template is not None:
                templates.append(normalized_template)

    return templates


def strip_entry_prefix(entry_name: str, prefix: str) -> str:
    """Return entry name without the given prefix when present."""
    if entry_name.startswith(prefix):
        return entry_name[len(prefix) :]
    return entry_name
