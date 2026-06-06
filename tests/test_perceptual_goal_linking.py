from types import MethodType
from types import SimpleNamespace

from tkinter import messagebox

from gui_app import PerceptualEquationsApp
from data_models import GoalFunctionEntry
from perceptual_equations_range import NumericRange


def _app_without_tk() -> PerceptualEquationsApp:
    app = PerceptualEquationsApp.__new__(PerceptualEquationsApp)
    app.goal_to_equations = {}
    app.equation_to_goals = {}
    app.goal_function_links = {}
    app.index = None
    app.range_analyzer = None
    app.token_bounds = {}
    app.entry_types = {}
    app.goal_display_to_entry = {}
    return app


def test_extract_goal_function_link_normalizes_goal_and_function_names() -> None:
    app = _app_without_tk()
    entry = GoalFunctionEntry(
        name="GoalFunction::Build",
        raw_expression="Goal=Conquer\nFunction=Function_Strength_Check.Evaluate",
        normalized_expression="Goal=Conquer\nFunction=Function_Strength_Check.Evaluate",
        source_file=None,
    )

    goal_name, equation_name = app._extract_goal_function_link(entry)

    assert goal_name == "Goal::Conquer"
    assert equation_name == "Strength_Check"


def test_format_goal_range_uses_linked_equation_ranges() -> None:
    app = _app_without_tk()
    app.goal_to_equations = {
        "Goal::Conquer": ["Eq_A", "Eq_B"],
    }

    def compute_range(self, equation_name: str):
        if equation_name == "Eq_A":
            return NumericRange(0.0, 3.0)
        if equation_name == "Eq_B":
            return NumericRange(1.0, 5.0)
        return None

    app._compute_equation_range = MethodType(compute_range, app)

    range_text = app._format_goal_range("Goal::Conquer")

    assert range_text == "min 0, max 5 (from 2 linked equations)"


def test_build_related_links_for_goal_include_equation_ranges() -> None:
    app = _app_without_tk()
    app.goal_to_equations = {
        "Goal::Conquer": ["Eq_A", "Eq_B"],
    }

    app._format_equation_range = MethodType(
        lambda self, equation_name: (
            "min 0, max 3" if equation_name == "Eq_A" else "min 1, max 5"
        ),
        app,
    )

    links = app._build_related_links("Goal::Conquer")

    assert links == [
        ("Equation: Eq_A (min 0, max 3)", "Eq_A"),
        ("Equation: Eq_B (min 1, max 5)", "Eq_B"),
    ]


def test_select_entry_by_name_displays_hidden_goal_entry() -> None:
    app = _app_without_tk()
    displayed: list[str] = []
    shown_messages: list[str] = []

    class _DummySearchVar:
        def set(self, _value: str) -> None:
            pass

    class _DummyListbox:
        def selection_clear(self, _start, _end) -> None:
            pass

        def selection_set(self, _index: int) -> None:
            pass

        def see(self, _index: int) -> None:
            pass

        def event_generate(self, _event: str) -> None:
            pass

    hidden_goal = SimpleNamespace(name="Goal::Conquer")
    app.filtered_names = []
    app.index = SimpleNamespace(
        get=lambda name: hidden_goal if name == "Goal::Conquer" else None
    )
    app.view = SimpleNamespace(
        search_var=_DummySearchVar(),
        names_listbox=_DummyListbox(),
    )
    app._refresh_list = MethodType(lambda self: None, app)
    app._display_equation = MethodType(
        lambda self, equation: displayed.append(equation.name),
        app,
    )

    original_showinfo = messagebox.showinfo
    messagebox.showinfo = lambda _title, message: shown_messages.append(message)
    try:
        app._select_entry_by_name("Goal::Conquer", reset_entries_filter=False)
    finally:
        messagebox.showinfo = original_showinfo

    assert displayed == ["Goal::Conquer"]
    assert shown_messages == []


def test_on_goal_selection_changed_displays_selected_goal_directly() -> None:
    app = _app_without_tk()
    displayed: list[str] = []

    class _DummyGoalsListbox:
        def curselection(self):
            return (0,)

        def get(self, _index: int) -> str:
            return "Goal::Conquer"

    class _DummyNamesListbox:
        def selection_clear(self, _start, _end) -> None:
            pass

    selected_goal = SimpleNamespace(name="Goal::Conquer")
    app.index = SimpleNamespace(
        get=lambda name: selected_goal if name == "Goal::Conquer" else None
    )
    app.view = SimpleNamespace(
        goals_listbox=_DummyGoalsListbox(),
        names_listbox=_DummyNamesListbox(),
    )
    app._display_equation = MethodType(
        lambda self, equation: displayed.append(equation.name),
        app,
    )

    app._on_goal_selection_changed(None)

    assert displayed == ["Goal::Conquer"]


def test_on_goal_selection_changed_resolves_display_name_without_prefix() -> None:
    app = _app_without_tk()
    displayed: list[str] = []

    class _DummyGoalsListbox:
        def curselection(self):
            return (0,)

        def get(self, _index: int) -> str:
            return "Conquer"

    class _DummyNamesListbox:
        def selection_clear(self, _start, _end) -> None:
            pass

    selected_goal = SimpleNamespace(name="Goal::Conquer")
    app.goal_display_to_entry = {"Conquer": "Goal::Conquer"}
    app.index = SimpleNamespace(
        get=lambda name: selected_goal if name == "Goal::Conquer" else None
    )
    app.view = SimpleNamespace(
        goals_listbox=_DummyGoalsListbox(),
        names_listbox=_DummyNamesListbox(),
    )
    app._display_equation = MethodType(
        lambda self, equation: displayed.append(equation.name),
        app,
    )

    app._on_goal_selection_changed(None)

    assert displayed == ["Goal::Conquer"]


def test_goal_display_name_strips_goal_prefix() -> None:
    app = _app_without_tk()

    assert app._goal_display_name("Goal::Conquer") == "Conquer"
    assert app._goal_display_name("NoPrefix") == "NoPrefix"
