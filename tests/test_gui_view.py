from gui.view import PerceptualEquationsView


def _view_without_tk() -> PerceptualEquationsView:
    return PerceptualEquationsView.__new__(PerceptualEquationsView)


def test_parse_structured_fields_returns_key_value_pairs() -> None:
    view = _view_without_tk()

    parsed = view._parse_structured_fields("Goal=Conquer\nCategory=Offensive")

    assert parsed == [
        ("Goal", "Conquer"),
        ("Category", "Offensive"),
    ]


def test_parse_structured_fields_returns_none_for_non_structured_text() -> None:
    view = _view_without_tk()

    assert view._parse_structured_fields("Game.Income * 2 + 1") is None


def test_value_list_items_detects_identifier_lists() -> None:
    view = _view_without_tk()

    items = view._value_list_items(
        "SystemFunctions BasicOffensiveGalacticSet BasicDefensiveGalacticSet"
    )

    assert items == [
        "SystemFunctions",
        "BasicOffensiveGalacticSet",
        "BasicDefensiveGalacticSet",
    ]


def test_value_list_items_keeps_free_text_as_scalar() -> None:
    view = _view_without_tk()

    assert view._value_list_items("This is not an identifier list") is None
