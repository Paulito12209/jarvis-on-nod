import numpy as np
import pytest

pytest.importorskip("prompt_toolkit")
from prompt_toolkit.application import create_app_session  # noqa: E402
from prompt_toolkit.input import create_pipe_input  # noqa: E402
from prompt_toolkit.output import DummyOutput  # noqa: E402

from jarvis_stimme.tui import TerminalUI, wrap  # noqa: E402
from test_core import make_conv  # noqa: E402


@pytest.fixture()
def tui_for():
    with create_pipe_input() as inp, create_app_session(input=inp, output=DummyOutput()):
        def make(tokens, **kw):
            conv, tts, player, out = make_conv(tokens, **kw)
            ui = TerminalUI(conv, {"modell": "m", "kontext_limit": 8192})
            conv.on_event = ui.on_event
            return conv, ui
        yield make


def test_wrap_breaks_between_words_and_indents():
    lines = wrap("Jarvis › " + "Barcelona führt gerade zwei zu eins " * 3, 30, 9)
    assert all(len(x) <= 30 for x in lines)
    assert all(x.startswith(" " * 9) for x in lines[1:])
    assert "Barcel ona" not in " ".join(lines)


def test_answer_follows_user_line_and_stats_go_to_top_bar(tui_for):
    conv, ui = tui_for(["Es ist", " zehn Uhr", "."])
    conv.handle_audio(np.zeros(16000, np.int16)).join(5)
    text = "\n".join(ui.lines)
    assert "Du › Wie spät ist es?" in text
    assert "Jarvis › Es ist zehn Uhr." in text
    assert "Sekunden" not in text and "Tokens" not in text  # no timing line under the answer
    assert ui.last and "sekunden" in ui.last
    assert any("letzte" in part[1] for part in ui._top())


def test_commands_name_stats_and_unknown(tui_for):
    conv, ui = tui_for(["Hallo."])
    saved = []
    ui.save_name = saved.append
    ui.command("/name Friday")
    assert conv.s.name == "Friday" and conv.attention.name == "Friday" and saved == ["Friday"]
    ui.command("/stats")
    assert "Noch keine Antworten" in ui.lines[-1]
    conv.handle_text("hallo").join(5)
    ui.command("/stats")
    assert "Schnitt" in ui.lines[-1]
    ui.command("/quatsch")
    assert "Unbekannter Befehl" in ui.lines[-1]


def test_search_shows_spinner_label(tui_for):
    conv, ui = tui_for(["x"])
    ui.on_event({"typ": "suche", "text": "FC Barcelona"})
    assert ui.activity == "sucht"
    assert "sucht" in "".join(p[1] for p in ui._activity())
    ui.on_event({"typ": "status", "status": "bereit"})
    assert ui.activity == ""
