from __future__ import annotations

from pathlib import Path


def find_ai_content_folder(data_folder: Path, content_folder: str) -> Path | None:
    """Find an AI content folder under one Data folder using known path variants."""
    candidates = [
        data_folder / "AI" / content_folder,
        data_folder / "XML" / "AI" / content_folder,
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def find_perceptual_equations_folder(data_folder: Path) -> Path | None:
    """Find PerceptualEquations under one Data folder."""
    return find_ai_content_folder(data_folder, "PerceptualEquations")


def _normalize_selected_layer_names(upper_layers: list[str]) -> list[str]:
    """Return ordered, non-blank layer names and reject duplicates."""
    selected_names: list[str] = []
    for layer_name in upper_layers:
        layer_name = layer_name.strip()
        if not layer_name:
            continue
        if layer_name in selected_names:
            raise ValueError(f"Duplicate upper layer name: {layer_name}")
        selected_names.append(layer_name)
    return selected_names


def resolve_stack_layer_content_folders(
    root: Path,
    upper_layers: list[str],
    content_folder: str,
    require_data_layer: bool,
    require_selected_upper_layers: bool,
) -> list[tuple[str, Path]]:
    """Resolve one AI content folder across stack layers in load order."""
    resolved: list[tuple[str, Path]] = []

    data_folder = find_ai_content_folder(root / "Data", content_folder)
    if data_folder is None:
        if require_data_layer:
            raise ValueError(f"Could not find {content_folder} under root/Data")
    else:
        resolved.append(("Data", data_folder))

    for layer_name in _normalize_selected_layer_names(upper_layers):
        base_folder = root / layer_name / "Data"
        folder = find_ai_content_folder(base_folder, content_folder)
        if folder is None:
            if require_selected_upper_layers:
                raise ValueError(
                    f"Could not find {content_folder} for layer "
                    f"'{layer_name}' under {base_folder}"
                )
            continue
        resolved.append((layer_name, folder))

    return resolved


def resolve_stack_layer_folders(
    root: Path, upper_layers: list[str]
) -> list[tuple[str, Path]]:
    """Resolve root/Data plus user-selected upper layers."""
    return resolve_stack_layer_content_folders(
        root=root,
        upper_layers=upper_layers,
        content_folder="PerceptualEquations",
        require_data_layer=True,
        require_selected_upper_layers=True,
    )
