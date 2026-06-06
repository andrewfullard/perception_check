from types import MethodType
from types import SimpleNamespace
from pathlib import Path

from tkinter import messagebox

from gui_app import PerceptualEquationsApp
from data_models import GoalFunctionEntry
from gui_app_text_utils import (
    extract_goal_function_link,
    extract_player_template_links,
    strip_entry_prefix,
)
from perceptual_equations_parser import PerceptualEquationsParser
from perceptual_equations_range import NumericRange


def _app_without_tk() -> PerceptualEquationsApp:
    app = PerceptualEquationsApp.__new__(PerceptualEquationsApp)
    app.goal_to_equations = {}
    app.equation_to_goals = {}
    app.player_to_templates = {}
    app.template_to_players = {}
    app.goal_function_links = {}
    app.index = None
    app.range_analyzer = None
    app.token_bounds = {}
    app.entry_types = {}
    app.goal_display_to_entry = {}
    app.player_display_to_entry = {}
    app.template_display_to_entry = {}
    return app


def _write_equations_xml(path: Path, equations: dict[str, str]) -> None:
    lines = ['<?xml version="1.0"?>', "<Equations>"]
    for name, body in equations.items():
        lines.append(f"  <{name}>{body}</{name}>")
    lines.append("</Equations>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_player_xml(
    path: Path,
    name: str,
    galactic_template: str = "Basic_Empire_Default",
) -> None:
    path.write_text(
        (
            '<?xml version="1.0"?>\n'
            "<AIPlayerType>\n"
            f"  <Name>{name}</Name>\n"
            "  <Templates>\n"
            f"    <Galactic>{galactic_template}</Galactic>\n"
            "  </Templates>\n"
            "</AIPlayerType>\n"
        ),
        encoding="utf-8",
    )


def _write_templates_xml(path: Path, template_name: str, priority: str) -> None:
    path.write_text(
        (
            '<?xml version="1.0"?>\n'
            "<AITemplates>\n"
            f"  <{template_name}>\n"
            f"    <Priority>{priority}</Priority>\n"
            f"  </{template_name}>\n"
            "</AITemplates>\n"
        ),
        encoding="utf-8",
    )


def test_extract_goal_function_link_normalizes_goal_and_function_names() -> None:
    app = _app_without_tk()
    entry = GoalFunctionEntry(
        name="GoalFunction::Build",
        raw_expression="Goal=Conquer\nFunction=Function_Strength_Check.Evaluate",
        normalized_expression="Goal=Conquer\nFunction=Function_Strength_Check.Evaluate",
        source_file=None,
    )

    goal_name, equation_name = extract_goal_function_link(
        entry.normalized_expression,
        app._extract_function_name,
    )

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


def test_extract_player_template_links_reads_templates_fields() -> None:
    app = _app_without_tk()
    entry = SimpleNamespace(
        normalized_expression=(
            "Name=BasicEmpire\n"
            "Templates/Space=Generic_Space\n"
            "Templates/Land=Generic_Land\n"
            "Templates/Galactic=Generic_AI_Default"
        )
    )

    links = extract_player_template_links(entry.normalized_expression)

    assert links == [
        "Template::Generic_Space",
        "Template::Generic_Land",
        "Template::Generic_AI_Default",
    ]


def test_extract_player_template_links_splits_multi_template_field_values() -> None:
    app = _app_without_tk()
    entry = SimpleNamespace(
        normalized_expression=(
            "Name=IsolationistAI\n"
            "Templates/Galactic=Generic_AI_Isolationist Generic_AI_Isolationist_Attacks"
        )
    )

    links = extract_player_template_links(entry.normalized_expression)

    assert links == [
        "Template::Generic_AI_Isolationist",
        "Template::Generic_AI_Isolationist_Attacks",
    ]


def test_build_related_links_for_player_excludes_templates() -> None:
    app = _app_without_tk()
    app.entry_types = {"Player::BasicEmpire": "player"}
    app.player_to_templates = {
        "Player::BasicEmpire": ["Template::Generic_AI_Default"],
    }
    app.index = SimpleNamespace(get=lambda name: object() if name else None)

    links = app._build_related_links("Player::BasicEmpire")

    assert links == []


def test_build_structured_expression_links_for_player_templates() -> None:
    app = _app_without_tk()
    app.entry_types = {"Player::BasicEmpire": "player"}
    app.player_to_templates = {
        "Player::BasicEmpire": ["Template::Generic_AI_Default"],
    }
    player_entry = SimpleNamespace(
        normalized_expression=(
            "Name=BasicEmpire\n"
            "Templates/Galactic=Generic_AI_Default\n"
            "Templates/Land=Generic_Land"
        )
    )

    def get_entry(name: str):
        if name == "Player::BasicEmpire":
            return player_entry
        if name == "Template::Generic_AI_Default":
            return object()
        return None

    app.index = SimpleNamespace(get=get_entry)

    links = app._build_structured_expression_links("Player::BasicEmpire")

    assert links == {
        ("Templates/Galactic", "Generic_AI_Default"): [
            ("Generic_AI_Default", "Template::Generic_AI_Default")
        ],
        (
            "Templates/Galactic",
            "Template::Generic_AI_Default",
        ): [("Generic_AI_Default", "Template::Generic_AI_Default")],
    }


def test_build_structured_expression_links_for_template_goal_names() -> None:
    app = _app_without_tk()
    app.entry_types = {
        "Template::Basic": "template",
        "Goal::Conquer_Pirate": "goal",
    }
    template_entry = SimpleNamespace(
        normalized_expression="Turn_Off/Goals/Goal_Type=Conquer_Pirate"
    )
    goal_entry = SimpleNamespace(normalized_expression="Category=Offensive")

    def get_entry(name: str):
        if name == "Template::Basic":
            return template_entry
        if name == "Goal::Conquer_Pirate":
            return goal_entry
        return None

    app.index = SimpleNamespace(
        get=get_entry,
        effective_equations={
            "Template::Basic": template_entry,
            "Goal::Conquer_Pirate": goal_entry,
        },
    )

    links = app._build_structured_expression_links("Template::Basic")

    assert links == {
        ("Turn_Off/Goals/Goal_Type", "Conquer_Pirate"): [
            ("Conquer_Pirate", "Goal::Conquer_Pirate")
        ],
    }


def test_build_structured_expression_links_for_template_goal_categories() -> None:
    app = _app_without_tk()
    app.entry_types = {
        "Template::Basic": "template",
        "Goal::Conquer_Pirate": "goal",
        "Goal::Raid_Convoy": "goal",
        "Goal::Build_Defenses": "goal",
    }
    template_entry = SimpleNamespace(
        normalized_expression="Turn_On/Goals/Category=Offensive"
    )
    goals = {
        "Goal::Conquer_Pirate": SimpleNamespace(
            normalized_expression="Category=Offensive"
        ),
        "Goal::Raid_Convoy": SimpleNamespace(normalized_expression="Category=Offensive"),
        "Goal::Build_Defenses": SimpleNamespace(normalized_expression="Category=Defensive"),
    }

    def get_entry(name: str):
        if name == "Template::Basic":
            return template_entry
        return goals.get(name)

    app.index = SimpleNamespace(
        get=get_entry,
        effective_equations={
            "Template::Basic": template_entry,
            **goals,
        },
    )

    links = app._build_structured_expression_links("Template::Basic")

    assert links == {
        ("Turn_On/Goals/Category", "Offensive"): [
            ("Offensive", None),
            ("Conquer_Pirate", "Goal::Conquer_Pirate"),
            ("Raid_Convoy", "Goal::Raid_Convoy"),
        ],
    }


def test_build_structured_expression_links_for_template_goal_categories_by_plan_key() -> None:
    app = _app_without_tk()
    app.entry_types = {
        "Template::Basic": "template",
        "Goal::Conquer_Pirate": "goal",
    }
    template_entry = SimpleNamespace(
        normalized_expression="Plans/Goal_Category=Offensive"
    )
    goal_entry = SimpleNamespace(normalized_expression="Category=Offensive")

    def get_entry(name: str):
        if name == "Template::Basic":
            return template_entry
        if name == "Goal::Conquer_Pirate":
            return goal_entry
        return None

    app.index = SimpleNamespace(
        get=get_entry,
        effective_equations={
            "Template::Basic": template_entry,
            "Goal::Conquer_Pirate": goal_entry,
        },
    )

    links = app._build_structured_expression_links("Template::Basic")

    assert links == {
        ("Plans/Goal_Category", "Offensive"): [
            ("Offensive", None),
            ("Conquer_Pirate", "Goal::Conquer_Pirate")
        ],
    }


def test_build_related_links_for_template_include_players() -> None:
    app = _app_without_tk()
    app.entry_types = {"Template::Generic_AI_Default": "template"}
    app.template_to_players = {
        "Template::Generic_AI_Default": ["Player::BasicEmpire"],
    }
    app.index = SimpleNamespace(get=lambda name: object() if name else None)

    links = app._build_related_links("Template::Generic_AI_Default")

    assert links == [
        ("Player: BasicEmpire", "Player::BasicEmpire"),
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


def test_select_entry_by_name_displays_hidden_player_entry() -> None:
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

    hidden_player = SimpleNamespace(name="Player::BasicEmpire")
    app.filtered_names = []
    app.index = SimpleNamespace(
        get=lambda name: hidden_player if name == "Player::BasicEmpire" else None
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
        app._select_entry_by_name("Player::BasicEmpire", reset_entries_filter=False)
    finally:
        messagebox.showinfo = original_showinfo

    assert displayed == ["Player::BasicEmpire"]
    assert shown_messages == []


def test_select_entry_by_name_displays_hidden_template_entry() -> None:
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

    hidden_template = SimpleNamespace(name="Template::Basic_Empire_Default")
    app.filtered_names = []
    app.index = SimpleNamespace(
        get=lambda name: (
            hidden_template if name == "Template::Basic_Empire_Default" else None
        )
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
        app._select_entry_by_name(
            "Template::Basic_Empire_Default", reset_entries_filter=False
        )
    finally:
        messagebox.showinfo = original_showinfo

    assert displayed == ["Template::Basic_Empire_Default"]
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


def test_on_player_selection_changed_displays_selected_player_directly() -> None:
    app = _app_without_tk()
    displayed: list[str] = []

    class _DummyPlayersListbox:
        def curselection(self):
            return (0,)

        def get(self, _index: int) -> str:
            return "Player::BasicEmpire"

    class _DummyNamesListbox:
        def selection_clear(self, _start, _end) -> None:
            pass

    selected_player = SimpleNamespace(name="Player::BasicEmpire")
    app.index = SimpleNamespace(
        get=lambda name: selected_player if name == "Player::BasicEmpire" else None
    )
    app.view = SimpleNamespace(
        players_listbox=_DummyPlayersListbox(),
        names_listbox=_DummyNamesListbox(),
    )
    app._display_equation = MethodType(
        lambda self, equation: displayed.append(equation.name),
        app,
    )

    app._on_player_selection_changed(None)

    assert displayed == ["Player::BasicEmpire"]


def test_on_player_selection_changed_resolves_display_name_without_prefix() -> None:
    app = _app_without_tk()
    displayed: list[str] = []

    class _DummyPlayersListbox:
        def curselection(self):
            return (0,)

        def get(self, _index: int) -> str:
            return "BasicEmpire"

    class _DummyNamesListbox:
        def selection_clear(self, _start, _end) -> None:
            pass

    selected_player = SimpleNamespace(name="Player::BasicEmpire")
    app.player_display_to_entry = {"BasicEmpire": "Player::BasicEmpire"}
    app.index = SimpleNamespace(
        get=lambda name: selected_player if name == "Player::BasicEmpire" else None
    )
    app.view = SimpleNamespace(
        players_listbox=_DummyPlayersListbox(),
        names_listbox=_DummyNamesListbox(),
    )
    app._display_equation = MethodType(
        lambda self, equation: displayed.append(equation.name),
        app,
    )

    app._on_player_selection_changed(None)

    assert displayed == ["Player::BasicEmpire"]


def test_on_template_selection_changed_displays_selected_template_directly() -> None:
    app = _app_without_tk()
    displayed: list[str] = []

    class _DummyTemplatesListbox:
        def curselection(self):
            return (0,)

        def get(self, _index: int) -> str:
            return "Template::Basic_Empire_Default"

    class _DummyNamesListbox:
        def selection_clear(self, _start, _end) -> None:
            pass

    selected_template = SimpleNamespace(name="Template::Basic_Empire_Default")
    app.index = SimpleNamespace(
        get=lambda name: (
            selected_template if name == "Template::Basic_Empire_Default" else None
        )
    )
    app.view = SimpleNamespace(
        templates_listbox=_DummyTemplatesListbox(),
        names_listbox=_DummyNamesListbox(),
    )
    app._display_equation = MethodType(
        lambda self, equation: displayed.append(equation.name),
        app,
    )

    app._on_template_selection_changed(None)

    assert displayed == ["Template::Basic_Empire_Default"]


def test_on_template_selection_changed_resolves_display_name_without_prefix() -> None:
    app = _app_without_tk()
    displayed: list[str] = []

    class _DummyTemplatesListbox:
        def curselection(self):
            return (0,)

        def get(self, _index: int) -> str:
            return "Basic_Empire_Default"

    class _DummyNamesListbox:
        def selection_clear(self, _start, _end) -> None:
            pass

    selected_template = SimpleNamespace(name="Template::Basic_Empire_Default")
    app.template_display_to_entry = {
        "Basic_Empire_Default": "Template::Basic_Empire_Default"
    }
    app.index = SimpleNamespace(
        get=lambda name: (
            selected_template if name == "Template::Basic_Empire_Default" else None
        )
    )
    app.view = SimpleNamespace(
        templates_listbox=_DummyTemplatesListbox(),
        names_listbox=_DummyNamesListbox(),
    )
    app._display_equation = MethodType(
        lambda self, equation: displayed.append(equation.name),
        app,
    )

    app._on_template_selection_changed(None)

    assert displayed == ["Template::Basic_Empire_Default"]


def test_goal_display_name_strips_goal_prefix() -> None:
    assert strip_entry_prefix("Goal::Conquer", "Goal::") == "Conquer"
    assert strip_entry_prefix("NoPrefix", "Goal::") == "NoPrefix"


def test_player_display_name_strips_player_prefix() -> None:
    assert strip_entry_prefix("Player::BasicEmpire", "Player::") == "BasicEmpire"
    assert strip_entry_prefix("NoPrefix", "Player::") == "NoPrefix"


def test_template_display_name_strips_template_prefix() -> None:
    assert (
        strip_entry_prefix("Template::Basic_Empire_Default", "Template::")
        == "Basic_Empire_Default"
    )
    assert strip_entry_prefix("NoPrefix", "Template::") == "NoPrefix"


def test_merge_non_equation_data_reads_players_templates_with_stack_order(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mod"

    data_eq = root / "Data" / "AI" / "PerceptualEquations"
    data_players = root / "Data" / "XML" / "AI" / "Players"
    data_templates = root / "Data" / "XML" / "AI" / "Templates"
    fotr_players = root / "FotR" / "Data" / "AI" / "Players"
    fotr_templates = root / "FotR" / "Data" / "AI" / "Templates"

    data_eq.mkdir(parents=True)
    data_players.mkdir(parents=True)
    data_templates.mkdir(parents=True)
    fotr_players.mkdir(parents=True)
    fotr_templates.mkdir(parents=True)

    _write_equations_xml(data_eq / "eq.xml", {"EqA": "1"})
    _write_player_xml(data_players / "player.xml", "BasicEmpire")
    _write_player_xml(fotr_players / "player.xml", "BasicEmpire")
    _write_templates_xml(data_templates / "templates.xml", "Basic_Empire_Default", "1")
    _write_templates_xml(fotr_templates / "templates.xml", "Basic_Empire_Default", "2")

    app = _app_without_tk()
    app.parser = PerceptualEquationsParser()
    app.index = app.parser.build_index_from_folders([("Data", data_eq)])

    app._merge_non_equation_data_into_index(root, ["FotR"])

    assert app.index is not None
    assert app.index.layer_for("Player::BasicEmpire") == "FotR"
    assert app.index.layer_for("Template::Basic_Empire_Default") == "FotR"
    assert app.entry_types["Player::BasicEmpire"] == "player"
    assert app.entry_types["Template::Basic_Empire_Default"] == "template"
    assert app.player_to_templates["Player::BasicEmpire"] == [
        "Template::Basic_Empire_Default"
    ]
    assert app.template_to_players["Template::Basic_Empire_Default"] == [
        "Player::BasicEmpire"
    ]
