from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class TokenBounds:
    """Optional minimum/maximum constraints for a perception token."""

    min_value: float | None = None
    max_value: float | None = None

    def clamp(self, value: float) -> float:
        """Clamp numeric input to configured bounds."""
        clamped = value
        if self.min_value is not None:
            clamped = max(clamped, self.min_value)
        if self.max_value is not None:
            clamped = min(clamped, self.max_value)
        return clamped


def load_token_bounds(config_path: str | Path) -> dict[str, TokenBounds]:
    """Load token bounds mapping from JSON file."""
    path = Path(config_path)
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Token bounds config must be a JSON object")

    result: dict[str, TokenBounds] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Token bounds keys must be non-empty strings")
        if not isinstance(value, dict):
            raise ValueError(f"Token bounds for '{key}' must be an object")

        minimum = _coerce_bound(value.get("min"), key, "min")
        maximum = _coerce_bound(value.get("max"), key, "max")

        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError(
                f"Token bounds for '{key}' are invalid: min cannot exceed max"
            )

        result[key.strip()] = TokenBounds(min_value=minimum, max_value=maximum)

    return result


def get_token_bounds(
    token_key: str, token_bounds_map: dict[str, TokenBounds]
) -> TokenBounds | None:
    """Return matching bounds for a UI token key using enum-friendly aliases."""
    for candidate in _token_lookup_candidates(token_key):
        bounds = token_bounds_map.get(candidate)
        if bounds is not None:
            return bounds
    return None


def clamp_token_value(
    token_key: str,
    raw_value: str,
    token_bounds_map: dict[str, TokenBounds],
) -> str:
    """Clamp a token value when bounds are configured; otherwise return as-is."""
    value_text = (raw_value or "").strip() or "0"
    bounds = get_token_bounds(token_key, token_bounds_map)
    if bounds is None:
        return value_text

    try:
        numeric_value = float(value_text)
    except ValueError as exc:
        raise ValueError(
            f"Token '{token_key}' has configured bounds and requires a numeric value"
        ) from exc

    return f"{bounds.clamp(numeric_value):.15g}"


def _coerce_bound(raw_value: object, token_name: str, bound_name: str) -> float | None:
    """Normalize optional numeric bound values from JSON data."""
    if raw_value is None:
        return None

    if isinstance(raw_value, bool):
        raise ValueError(
            f"Token bound '{bound_name}' for '{token_name}' must be numeric or null"
        )

    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    raise ValueError(
        f"Token bound '{bound_name}' for '{token_name}' must be numeric or null"
    )


def _token_lookup_candidates(token_key: str) -> list[str]:
    """Build lookup keys that bridge UI token names and enum token names."""
    cleaned = " ".join(token_key.split())
    base = cleaned.split("{", 1)[0].strip()

    candidates: list[str] = []

    def add(candidate: str) -> None:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    add(cleaned)
    add(base)

    if "." in base:
        if not (base.startswith("Variable.") or base.startswith("Parameter.")):
            add(base.replace(".", "_"))
        # Variable_Target.FriendlyForce.HasSpaceUnitsBitfield should match
        # final literal bounds keyed as HasSpaceUnitsBitfield.
        tail = base.rsplit(".", 1)[-1]
        add(tail)
        add(tail.replace(".", "_"))

    if base.startswith("Game."):
        suffix = base[len("Game.") :]
        add(suffix)
        add(suffix.replace(".", "_"))

    return candidates
