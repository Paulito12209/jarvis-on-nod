"""Bridge phrases, name / router, tools, images, thinking ahead."""
import time

import numpy as np

from jarvis_stimme import app as app_mod
from jarvis_stimme.app import Conversation, Settings
from jarvis_stimme.bilder import find_image_paths, strip_paths
from jarvis_stimme.bruecken import PHRASES, FillerBank, classify, make_breath, strip_leading_filler
from jarvis_stimme.llm import ToolCalls, pick_small_model
from jarvis_stimme.vorausdenken import Thinker
from jarvis_stimme.zuhoeren import Attention, mentions_name

from test_core import FakePlayer, FakeSTT, FakeTTS


class ScriptLLM:
    """Fake model: returns scripted rounds; a round may be a ToolCalls object."""

    def __init__(self, rounds, delay=0.0):
        self.rounds, self.delay, self.calls = list(rounds), delay, []

    def stream(self, model, messages, stop=None, tools=None, max_tokens=None):
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        rnd = self.rounds.pop(0) if self.rounds else ["Okay."]
        if isinstance(rnd, ToolCalls):
            yield rnd
            return
        for t in rnd:
            if stop is not None and stop.is_set():
                return
            time.sleep(self.delay)
            yield t


class FakeRouter:
    def __init__(self, answer, delay=0.05):
        self.answer, self.delay, self.asked = answer, delay, []

    def is_for_me(self, text, history):
        self.asked.append(text)
        time.sleep(self.delay)
        return self.answer


def conv_with(llm, text="Wie spät ist es?", fillers=False, router=None, thinker=None, **kw):
    out = []
    tts, player = FakeTTS(), FakePlayer()
    bank = None
    if fillers:
        bank = FillerBank(tts, seed=1, breath_chance=0.0)
        bank.prepare(background=False)
    s = Settings(model="m", **kw)
    c = Conversation(s, FakeSTT(text), llm, tts, player, out=lambda *x, **k: out.append(" ".join(map(str, x))),
                     fillers=bank, router=router, thinker=thinker)
    return c, tts, player, out


def run(c):
    c.handle_audio(np.zeros(16000, np.int16)).join(5)


# -- phrases ------------------------------------------------------------------------------
def test_about_100_phrases_and_classify():
    assert sum(len(v) for v in PHRASES.values()) >= 100
    assert classify("Jarvis, wie wird das Wetter?") == "frage"
    assert classify("Mach bitte das Licht aus") == "befehl"
    assert classify("Ich bin heute total müde") == "gefuehl"
    assert classify("Ich hab die Prüfung bestanden!") == "freude"
    assert classify("Was denkst du über Elektroautos") == "meinung"
    assert classify("Hey Jarvis") == "hallo"
    assert classify("Ich war heute im Park") == "erzaehlung"


def test_strip_leading_filler_and_breath():
    assert strip_leading_filler("Okay, also das Wetter wird gut.") == "Das Wetter wird gut."
    assert strip_leading_filler("Gute Frage! Es ist zehn.") == "Es ist zehn."
    assert strip_leading_filler("Ja.") == "Ja."
    b = make_breath(22050)
    assert 0.3 < len(b) / 22050 < 0.6 and np.max(np.abs(b)) <= 0.08


def test_filler_plays_when_model_is_slow_and_answer_is_not_doubled():
    llm = ScriptLLM([["Okay, ", "es ist", " zehn", " Uhr."]], delay=0.15)
    c, tts, player, out = conv_with(llm, fillers=True, filler_delay=0.1)
    filler_count = len(tts.spoken)  # phrases synthesized at start
    run(c)
    assert any("💬" in o for o in out)
    assert tts.spoken[filler_count:] == ["Es ist zehn Uhr."]


def test_no_filler_when_model_is_fast():
    llm = ScriptLLM([["Es ist zehn Uhr."]])
    c, tts, player, out = conv_with(llm, fillers=True, filler_delay=0.3)
    run(c)
    assert not any("💬" in o for o in out)


def test_name_only_answers_instantly_without_model():
    llm = ScriptLLM([])
    c, tts, player, out = conv_with(llm, text="Jarvis?", fillers=True, listen_mode="name")
    run(c)
    assert llm.calls == [] and any("💬" in o for o in out)
    assert c.attention.in_window()


# -- listening / router --------------------------------------------------------------------
def test_name_fuzzy():
    assert mentions_name("Hey Dschawis, hörst du mich?", "Jarvis")
    assert mentions_name("Jarvis!", "Jarvis")
    assert not mentions_name("Ich gehe jetzt einkaufen", "Jarvis")
    assert mentions_name("Friday, mach Musik an", "Friday")


def test_attention_modes():
    a = Attention("Jarvis", "name", window=10)
    assert a.decide("Wie spät ist es?", now=100).answer == "nein"
    assert a.decide("Jarvis, wie spät ist es?", now=100).answer == "ja"
    a.open_window(now=100)
    assert a.decide("Und morgen?", now=105).answer == "fragen"
    assert a.decide("Und morgen?", now=120).answer == "nein"
    assert a.decide("Jarvis, sei mal still, ich telefoniere", now=121).answer == "still"
    assert a.decide("Was?", now=122).answer == "nein" and a.quiet
    assert a.decide("Jarvis, bist du da?", now=130).answer == "ja" and not a.quiet


def test_not_addressed_stays_silent_in_name_mode():
    llm = ScriptLLM([["Hallo."]])
    c, tts, player, out = conv_with(llm, text="Schreib Tom, ich komme später", listen_mode="name")
    run(c)
    assert llm.calls == [] and tts.spoken == [] and c.history == []


def test_router_rejects_whatsapp_dictation_in_window():
    llm = ScriptLLM([["Klar", ", ich", " schreibe", " Tom", "."]], delay=0.01)
    router = FakeRouter(False, delay=0.2)
    c, tts, player, out = conv_with(llm, text="Schreib Tom, ich komme später", router=router, listen_mode="name")
    c.attention.open_window()
    run(c)
    assert router.asked and tts.spoken == [] and c.history == []
    assert any("nicht an mich" in o for o in out)


def test_router_approves_followup_and_answer_is_spoken_in_order():
    llm = ScriptLLM([["Morgen", " wird", " es", " sonnig.", " Und", " warm."]], delay=0.01)
    router = FakeRouter(True, delay=0.1)
    c, tts, player, out = conv_with(llm, text="Und morgen?", router=router, listen_mode="name")
    c.attention.open_window()
    run(c)
    assert tts.spoken == ["Morgen wird es sonnig.", "Und warm."]


def test_typed_text_needs_no_name():
    llm = ScriptLLM([["Hallo!"]])
    c, tts, player, out = conv_with(llm, listen_mode="name")
    c.handle_text("Wie geht's?").join(5)
    assert tts.spoken == ["Hallo!"]


# -- tools ----------------------------------------------------------------------------------
def test_web_search_tool_round(monkeypatch):
    seen = []
    monkeypatch.setattr(app_mod, "run_tool", lambda name, args: seen.append((name, args)) or "Barça führt 2:1.")
    call = ToolCalls([{"function": {"name": "web_suche", "arguments": {"suchbegriff": "FC Barcelona heute"}}}])
    llm = ScriptLLM([call, ["Barça", " führt", " gerade", " 2:1."]])
    c, tts, player, out = conv_with(llm, text="Wie steht's bei Barça?", fillers=True, filler_delay=5)
    n0 = len(tts.spoken)
    run(c)
    assert seen == [("web_suche", {"suchbegriff": "FC Barcelona heute"})]
    assert llm.calls[0]["tools"] and llm.calls[1]["messages"][-1]["role"] == "tool"
    assert tts.spoken[n0:] == ["Barça führt gerade 2:1."]
    assert any("schau" in o.lower() or "such" in o.lower() or "check" in o.lower() for o in out if "💬" in o)
    assert "web_suche" in llm.calls[0]["messages"][0]["content"]


# -- images ---------------------------------------------------------------------------------
def test_find_image_paths():
    t = "Was ist auf /Users/hxh91txg0q/Ressourcen/Bilder/IMG_0943.HEIC zu sehen?"
    assert find_image_paths(t) == ["/Users/hxh91txg0q/Ressourcen/Bilder/IMG_0943.HEIC"]
    assert strip_paths(t) == "Was ist auf zu sehen?"
    assert find_image_paths(r"/Users/me/Mein\ Bild.png") == ["/Users/me/Mein Bild.png"]
    assert find_image_paths("'/tmp/a b.jpg' bitte") == ["/tmp/a b.jpg"]
    assert find_image_paths("kein bild hier.") == []


def test_image_goes_to_vision_model(tmp_path):
    img = tmp_path / "foto.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    llm = ScriptLLM([["Ein", " Hund", " am", " Strand."]])
    c, tts, player, out = conv_with(llm, vision_model="gemma4:12b")
    c.handle_text(f"Was siehst du? {img}").join(5)
    call = llm.calls[0]
    assert call["model"] == "gemma4:12b"
    assert call["messages"][-1]["images"] and call["messages"][-1]["content"] == "Was siehst du?"
    assert "images" not in c.history[0] and "foto.png" in c.history[0]["content"]


def test_image_without_vision_model_is_honest(tmp_path):
    img = tmp_path / "foto.jpg"
    img.write_bytes(b"x")
    llm = ScriptLLM([])
    c, tts, player, out = conv_with(llm)
    c.handle_text(f"{img}").join(5)
    assert llm.calls == [] and "keine Bilder" in tts.spoken[0]


# -- thinking ahead -------------------------------------------------------------------------
def test_thinker_notes_used_and_proactive_suggestion():
    think_llm = ScriptLLM([["- Er fragt gleich nach Rezepten.\n", "VORSCHLAG: Soll ich dir ein schnelles Rezept raussuchen?"]])
    th = Thinker(think_llm, "m", delay=0.0)
    th.start([{"role": "user", "content": "Ich hab Hunger"}, {"role": "assistant", "content": "Oh!"}])
    th._thread.join(2)
    assert "Rezept" in th.notes and th.suggestion.startswith("Soll ich")

    llm = ScriptLLM([["Klar."]])
    c, tts, player, out = conv_with(llm, thinker=th, proactive_after=0.0)
    c.last_answer = time.monotonic()
    c.last_activity = 0
    c.tick()
    time.sleep(0.1)
    assert tts.spoken and tts.spoken[-1].startswith("Übrigens, soll ich")
    th.notes = "Notiz: Pizza dauert 15 Minuten."
    c.handle_text("Was soll ich kochen?").join(5)
    assert "Pizza dauert" in llm.calls[-1]["messages"][0]["content"]


def test_pick_small_model():
    assert pick_small_model(["qwen3.8:27b-mlx", "qwen3.5:2b", "gemma4:12b"]) == "qwen3.5:2b"
    assert pick_small_model(["foo:3b", "gemma4:12b"]) == "foo:3b"
    assert pick_small_model(["gemma4:12b"]) is None
