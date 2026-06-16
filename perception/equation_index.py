from __future__ import annotations

from pathlib import Path
from typing import Iterable

from perception.models import (
    PerceptualEquation,
    PerceptualEquationIndex,
    PerceptualEquationLayer,
)
from perception.equation_validator import (
    collect_equation_validation_errors,
    load_hint_token_names,
    load_perception_token_names,
    load_script_evaluator_names,
)
from parsers.equations import parse_equations_folder_recursive


def parse_layer(
    name: str,
    folder: str | Path,
    pattern: str = "*.xml",
    recursive: bool = False,
) -> PerceptualEquationLayer:
    """Parse one logical load layer and validate in-layer uniqueness."""
    if recursive:
        documents = parse_equations_folder_recursive(folder, pattern=pattern)
    else:
        from parsers.equations import parse_equations_folder

        documents = parse_equations_folder(folder, pattern=pattern)

    layer = PerceptualEquationLayer(name=name, documents=documents)
    _validate_unique_within_layer(layer)
    return layer


def build_index(layers: Iterable[PerceptualEquationLayer]) -> PerceptualEquationIndex:
    """Build an effective equation index from ordered layers."""
    index = PerceptualEquationIndex()
    for layer in layers:
        for document in layer:
            for equation in document:
                index.all_definitions.setdefault(equation.name, []).append(
                    (layer.name, equation)
                )
                index.effective_equations[equation.name] = equation
                index.effective_layers[equation.name] = layer.name
    return index


def build_index_from_folders(
    layer_folders: Iterable[tuple[str, str | Path]],
    pattern: str = "*.xml",
    recursive: bool = False,
) -> PerceptualEquationIndex:
    """Build an effective index from (layer_name, folder_path) pairs."""
    folders = [(layer_name, Path(folder)) for layer_name, folder in layer_folders]
    index = build_index(
        parse_layer(layer_name, folder, pattern=pattern, recursive=recursive)
        for layer_name, folder in folders
    )
    index.validation_errors = collect_equation_validation_errors(
        index,
        load_perception_token_names(folders),
        load_script_evaluator_names(folders),
        load_hint_token_names(folders),
        _validation_source_labels(index, folders),
    )
    return index


def _validate_unique_within_layer(layer: PerceptualEquationLayer) -> None:
    """Ensure equation names are unique inside one load layer."""
    seen: dict[str, Path] = {}
    duplicates: list[str] = []

    for document in layer:
        for equation in document:
            prior = seen.get(equation.name)
            if prior is None:
                seen[equation.name] = equation.source_file
                continue
            duplicates.append(
                f"{equation.name} ({prior.name} and {equation.source_file.name})"
            )

    if duplicates:
        duplicate_list = ", ".join(sorted(set(duplicates)))
        raise ValueError(
            f"Duplicate equation names found within layer '{layer.name}': "
            f"{duplicate_list}"
        )


def _validation_source_labels(
    index: PerceptualEquationIndex, layer_folders: list[tuple[str, Path]]
) -> dict[Path, str]:
    labels: dict[Path, str] = {}
    layer_display_roots = [
        (layer_name, _display_root_for_layer(layer_name, folder))
        for layer_name, folder in layer_folders
    ]

    for equation in index:
        layer_name = index.layer_for(equation.name)
        display_path = _display_source_path(equation.source_file, layer_display_roots)
        labels[equation.source_file] = (
            f"{layer_name}: {display_path}" if layer_name else display_path
        )
    return labels


def _display_root_for_layer(layer_name: str, equations_folder: Path) -> Path:
    data_folder = _data_folder_for(equations_folder)
    if layer_name == "Data":
        mod_root = data_folder.parent
    else:
        mod_root = data_folder.parent.parent
    return mod_root.parent


def _data_folder_for(equations_folder: Path) -> Path:
    folder = equations_folder
    if folder.name == "PerceptualEquations":
        folder = folder.parent
    if folder.name == "AI":
        folder = folder.parent
    if folder.name == "XML":
        folder = folder.parent
    return folder


def _display_source_path(
    source_file: Path, layer_display_roots: list[tuple[str, Path]]
) -> str:
    for _layer_name, display_root in layer_display_roots:
        try:
            return source_file.relative_to(display_root).as_posix()
        except ValueError:
            continue
    return source_file.name
