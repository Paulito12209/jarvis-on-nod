import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

from jarvis_stimme.app import Conversation, Settings
from jarvis_stimme.llm import OllamaChat, OllamaError, pick_model
from jarvis_stimme.text import (SentenceChunker, clean_for_speech, is_goodbye,
                                looks_like_hallucination)
from jarvis_stimme.vad import CHUNK, TurnDetector


def chunk_all(text, step=3):
    c = SentenceChunker()
    out = []
    for i in range(0, len(text), step):
        out += c.feed(text[i:i + step])
    return out + c.flush()


# -- text -------------------------------------------------------------------------------
def test_first_chunk_ends_early_at_comma():
    out = chunk_all("Klar, das mache ich gern für dich, warte kurz. Der Termin steht am 3. Mai um 10 Uhr.")
    assert out[0] == "Klar, das mache ich gern für dich,"
    assert out[1] == "warte kurz."
    assert out[2] == "Der Termin steht am 3. Mai um 10 Uhr."


def test_abbreviations_do_not_split():
    out = chunk_all("Das ist z.B. bei Dr. Müller so. Ende!")
    assert out == ["Das ist z.B. bei Dr. Müller so.", "Ende!"]


def test_markdown_and_emoji_removed():
    assert clean_for_speech("**Hallo** 😀 [hier](https://x.de) - `code`") == "Hallo hier - code"
    assert chunk_all("## Titel\n- Punkt eins.\n- Punkt zwei.") == ["Titel Punkt eins.", "Punkt zwei."]


def test_think_blocks_are_skipped():
    out = chunk_all("<think>hmm lass mich überlegen.</think>Die Antwort ist zwölf.")
    assert out == ["Die Antwort ist zwölf."]


def test_long_text_without_punctuation_is_cut():
    out = chunk_all("wort " * 100)
    assert len(out) > 2 and all(len(x) <= 230 for x in out)


def test_hallucination_and_goodbye():
    assert looks_like_hallucination("Untertitel der Amara.org-Community")
    assert looks_like_hallucination(" ... ")
    assert not looks_like_hallucination("Wie spät ist es?")
    assert is_goodbye("Tschüss Jarvis!")
    assert not is_goodbye("Tschüss sagt man in Norddeutschland")


# -- model choice -----------------------------------------------------------------------
def test_pick_model_prefers_fast_models():
    installed = ["qwen3.5:2b", "qwen3.8:27b-mlx", "gemma4:12b", "nomic-embed-text:latest"]
    assert pick_model(installed) == "gemma4:12b"
    assert pick_model(installed + ["qwen3.6:35b"]) == "qwen3.6:35b"
    assert pick_model(installed, "qwen3.8") == "qwen3.8:27b-mlx"
    with pytest.raises(OllamaError):
        pick_model(installed, "llama9")
    with pytest.raises(OllamaError):
        pick_model([])


# -- turn detection ---------------------------------------------------------------------
def test_turn_detector_start_end_and_preroll():
    d = TurnDetector(end_silence=0.32, min_speech=0.1, pre_roll=0.1)
    z = np.zeros(CHUNK, np.int16)
    events = []
    for p in [0.0] * 5 + [0.9] * 20 + [0.0] * 20:
        ev = d.feed(p, z)
        if ev:
            events.append(ev)
    assert [e.kind for e in events] == ["start", "end"]
    assert len(events[1].audio) >= 20 * CHUNK


def test_single_click_is_ignored():
    d = TurnDetector(min_speech=0.25)
    z = np.zeros(CHUNK, np.int16)
    assert all(d.feed(p, z) is None for p in [0.9, 0.0, 0.9, 0.0] * 5)


# -- Ollama streaming (fake server) -----------------------------------------------------
class FakeOllama(BaseHTTPRequestHandler):
    tokens = ["Hallo", "! Ich", " bin", " da", ". Wie", " geht's?"]
    reject_think = False
    seen = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        body = json.dumps({"models": [{"name": "gemma4:12b"}]}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.seen.append(payload)
        if FakeOllama.reject_think and "think" in payload:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"model does not support thinking"}')
            return
        self.send_response(200)
        self.end_headers()
        for t in self.tokens:
            self.wfile.write((json.dumps({"message": {"content": t}, "done": False}) + "\n").encode())
            self.wfile.flush()
        self.wfile.write(b'{"message":{"content":""},"done":true}\n')


@pytest.fixture()
def ollama():
    srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    FakeOllama.seen = []
    FakeOllama.reject_think = False
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_ollama_stream_disables_thinking(ollama):
    c = OllamaChat(ollama)
    assert c.list_models() == ["gemma4:12b"]
    assert "".join(c.stream("gemma4:12b", [{"role": "user", "content": "hi"}])) == "Hallo! Ich bin da. Wie geht's?"
    p = FakeOllama.seen[-1]
    assert p["think"] is False and p["stream"] is True and p["keep_alive"]


def test_ollama_retries_without_think(ollama):
    FakeOllama.reject_think = True
    c = OllamaChat(ollama)
    assert "".join(c.stream("x", [])).startswith("Hallo")
    assert "think" not in FakeOllama.seen[-1]


def test_ollama_unreachable():
    with pytest.raises(OllamaError):
        OllamaChat("http://127.0.0.1:9").list_models()


# -- the whole loop with fakes ------------------------------------------------------------
class FakeSTT:
    def __init__(self, text="Wie spät ist es?"):
        self.text = text

    def transcribe(self, audio):
        return self.text


class FakeLLM:
    def __init__(self, tokens, delay=0.0):
        self.tokens, self.delay = tokens, delay

    def stream(self, model, messages, stop=None, tools=None, max_tokens=None, usage=None):
        for t in self.tokens:
            if stop is not None and stop.is_set():
                return
            time.sleep(self.delay)
            yield t


class FakeTTS:
    sample_rate = 16000

    def __init__(self):
        self.spoken = []

    def synth(self, text):
        self.spoken.append(text)
        return np.ones(1600, np.float32)


class FakePlayer:
    def __init__(self):
        self.played, self._busy_until, self.last_sound = [], 0.0, 0.0

    def play(self, audio, on_start=None):
        if on_start:
            on_start()
        self.played.append(audio)
        self._busy_until = time.monotonic() + 0.05

    def stop(self):
        self._busy_until = 0.0

    @property
    def busy(self):
        return time.monotonic() < self._busy_until

    def wait(self, timeout=60):
        while self.busy:
            time.sleep(0.005)


def make_conv(tokens, delay=0.0, text="Wie spät ist es?"):
    out = []
    tts, player = FakeTTS(), FakePlayer()
    conv = Conversation(Settings(model="m", pause=0.3), FakeSTT(text), FakeLLM(tokens, delay), tts,
                        player, out=lambda *x, **k: out.append(" ".join(map(str, x))))
    return conv, tts, player, out


def test_turn_speaks_sentence_by_sentence_and_reports_time():
    conv, tts, player, out = make_conv(["Es ist", " zehn Uhr", ". Schönen", " Abend", "!"])
    conv.handle_audio(np.zeros(16000, np.int16)).join(5)
    assert tts.spoken == ["Es ist zehn Uhr.", "Schönen Abend!"]
    assert conv.history[-1] == {"role": "assistant", "content": "Es ist zehn Uhr. Schönen Abend!"}
    assert any("bis zum ersten Ton" in o for o in out)
    assert not conv.assistant_busy


def test_first_audio_starts_before_answer_finished():
    conv, tts, player, out = make_conv(["Erster Satz.", " "] + [" mehr"] * 20 + ["."], delay=0.02)
    t = conv.handle_text("hallo")
    time.sleep(0.15)
    assert tts.spoken and tts.spoken[0] == "Erster Satz."  # already speaking while still thinking
    assert t.is_alive()
    t.join(5)


def test_barge_in_stops_answer():
    conv, tts, player, out = make_conv(["Satz eins."] + [" bla"] * 200, delay=0.01)
    t = conv.handle_text("erzähl was")
    time.sleep(0.1)
    assert conv.assistant_busy
    z = np.zeros(CHUNK, np.int16)
    for _ in range(15):  # loud, confident speech while Jarvis talks
        conv.on_mic_chunk(z, 0.99)
    t.join(2)
    assert not t.is_alive()
    assert any("Unterbrochen" in o for o in out)
    assert "(unterbrochen)" in conv.history[-1]["content"]


def test_hallucinated_silence_is_ignored():
    conv, tts, player, out = make_conv(["Hallo."], text="Untertitel der Amara.org-Community")
    conv.handle_audio(np.zeros(16000, np.int16)).join(5)
    assert tts.spoken == [] and conv.history == []


def test_goodbye_finishes():
    conv, tts, player, out = make_conv(["Tschüss!"], text="Tschüss Jarvis")
    conv.handle_audio(np.zeros(16000, np.int16)).join(5)
    assert conv.finished.is_set()
