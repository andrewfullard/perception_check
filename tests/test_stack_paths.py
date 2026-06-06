from pathlib import Path

import pytest

from stack_paths import (
    find_ai_content_folder,
    find_perceptual_equations_folder,
    resolve_stack_layer_content_folders,
    resolve_stack_layer_folders,
)


def _make_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_find_perceptual_equations_folder_prefers_ai_variant(tmp_path: Path) -> None:
    data = tmp_path / "Data"
    ai_variant = _make_dir(data / "AI" / "PerceptualEquations")
    _make_dir(data / "XML" / "AI" / "PerceptualEquations")

    found = find_perceptual_equations_folder(data)

    assert found == ai_variant


def test_find_perceptual_equations_folder_finds_xml_variant(tmp_path: Path) -> None:
    data = tmp_path / "Data"
    xml_variant = _make_dir(data / "XML" / "AI" / "PerceptualEquations")

    found = find_perceptual_equations_folder(data)

    assert found == xml_variant


def test_find_perceptual_equations_folder_returns_none_when_missing(
    tmp_path: Path,
) -> None:
    data = _make_dir(tmp_path / "Data")

    assert find_perceptual_equations_folder(data) is None


def test_find_ai_content_folder_resolves_variant_for_requested_content(
    tmp_path: Path,
) -> None:
    data = tmp_path / "Data"
    goals_variant = _make_dir(data / "XML" / "AI" / "Goals")

    found = find_ai_content_folder(data, "Goals")

    assert found == goals_variant


def test_resolve_stack_layer_folders_with_two_upper_layers(tmp_path: Path) -> None:
    root = tmp_path / "mod"

    data_folder = _make_dir(root / "Data" / "AI" / "PerceptualEquations")
    core_saga_folder = _make_dir(
        root / "CoreSaga" / "Data" / "XML" / "AI" / "PerceptualEquations"
    )
    fotr_folder = _make_dir(root / "FotR" / "Data" / "AI" / "PerceptualEquations")

    layers = resolve_stack_layer_folders(root, ["CoreSaga", "FotR"])

    assert layers == [
        ("Data", data_folder),
        ("CoreSaga", core_saga_folder),
        ("FotR", fotr_folder),
    ]


def test_resolve_stack_layer_folders_ignores_blank_upper_layers(tmp_path: Path) -> None:
    root = tmp_path / "mod"
    data_folder = _make_dir(root / "Data" / "AI" / "PerceptualEquations")

    layers = resolve_stack_layer_folders(root, ["", "   "])

    assert layers == [("Data", data_folder)]


def test_resolve_stack_layer_folders_rejects_duplicate_upper_layer_names(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mod"
    _make_dir(root / "Data" / "AI" / "PerceptualEquations")
    _make_dir(root / "CoreSaga" / "Data" / "AI" / "PerceptualEquations")

    with pytest.raises(ValueError, match="Duplicate upper layer name"):
        resolve_stack_layer_folders(root, ["CoreSaga", "CoreSaga"])


def test_resolve_stack_layer_folders_requires_data_layer(tmp_path: Path) -> None:
    root = _make_dir(tmp_path / "mod")

    with pytest.raises(ValueError, match="under root/Data"):
        resolve_stack_layer_folders(root, ["CoreSaga", "FotR"])


def test_resolve_stack_layer_folders_requires_existing_upper_layer_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mod"
    _make_dir(root / "Data" / "AI" / "PerceptualEquations")

    with pytest.raises(
        ValueError, match="Could not find PerceptualEquations for layer"
    ):
        resolve_stack_layer_folders(root, ["CoreSaga", "FotR"])


def test_resolve_stack_layer_content_folders_supports_mixed_variants_per_layer(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mod"

    data_goals = _make_dir(root / "Data" / "AI" / "Goals")
    core_goals = _make_dir(root / "CoreSaga" / "Data" / "XML" / "AI" / "Goals")
    fotr_goals = _make_dir(root / "FotR" / "Data" / "AI" / "Goals")

    layers = resolve_stack_layer_content_folders(
        root=root,
        upper_layers=["CoreSaga", "FotR"],
        content_folder="Goals",
        require_data_layer=False,
        require_selected_upper_layers=False,
    )

    assert layers == [
        ("Data", data_goals),
        ("CoreSaga", core_goals),
        ("FotR", fotr_goals),
    ]


def test_resolve_stack_layer_content_folders_skips_missing_optional_layers(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mod"
    data_goals = _make_dir(root / "Data" / "AI" / "Goals")
    _make_dir(root / "FotR" / "Data" / "AI" / "Goals")

    layers = resolve_stack_layer_content_folders(
        root=root,
        upper_layers=["CoreSaga", "FotR"],
        content_folder="Goals",
        require_data_layer=False,
        require_selected_upper_layers=False,
    )

    assert layers == [
        ("Data", data_goals),
        ("FotR", root / "FotR" / "Data" / "AI" / "Goals"),
    ]
