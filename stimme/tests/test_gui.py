import json
import threading
import time
import urllib.request

import pytest

from jarvis_stimme import gui
from test_natuerlich import ScriptLLM, conv_with


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(gui, "UPLOAD_DIR", tmp_path / "bilder")
    llm = ScriptLLM([["Hallo", " Paulito", "!"], ["Ein", " Foto."]])
    c, tts, player, out = conv_with(llm, vision_model="gemma4:12b")
    srv, hub = gui.serve(c, {"modell": "m", "bildmodell": "gemma4:12b", "websuche": True}, port=18765, open_browser=False)
    yield f"http://127.0.0.1:{srv.server_port}", c, llm, hub
    srv.shutdown()


def post(url, data=None, raw=None, headers=None):
    body = raw if raw is not None else json.dumps(data or {}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers=headers or {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def test_page_and_info(server):
    base, c, llm, hub = server
    html = urllib.request.urlopen(base + "/").read().decode()
    assert "<title>Jarvis Stimme</title>" in html and "EventSource" in html
    info = json.load(urllib.request.urlopen(base + "/info"))
    assert info["modell"] == "m" and info["mikro"] is True and info["name"] == "Jarvis"


def test_text_streams_events(server):
    base, c, llm, hub = server
    q = hub.subscribe()
    post(base + "/text", {"text": "Hallo!"})
    events, end = [], time.time() + 5
    while time.time() < end:
        try:
            ev = q.get(timeout=0.5)
        except Exception:
            continue
        events.append(ev)
        if ev["typ"] == "antwort_ende":
            break
    kinds = [e["typ"] for e in events]
    assert "du" in kinds and "antwort_start" in kinds and "antwort_ende" in kinds
    text = "".join(e.get("text", "") for e in events if e["typ"] in ("antwort_start", "token"))
    assert text == "Hallo Paulito!"


def test_upload_then_ask_about_image(server):
    base, c, llm, hub = server
    post(base + "/text", {"text": "Hi"})
    time.sleep(0.3)
    d = post(base + "/bild", raw=b"\x89PNG\r\n\x1a\nxx", headers={"X-Dateiname": "Mein%20Foto.png"})
    assert d["pfad"].endswith("Mein_Foto.png")
    post(base + "/text", {"text": "Was ist das?", "bilder": [d["pfad"], "/etc/passwd"]})
    for _ in range(50):
        if len(llm.calls) >= 2:
            break
        time.sleep(0.05)
    msg = llm.calls[-1]["messages"][-1]
    assert llm.calls[-1]["model"] == "gemma4:12b" and len(msg["images"]) == 1


def test_mikro_toggle_and_origin_block(server):
    base, c, llm, hub = server
    assert post(base + "/mikro", {"an": False})["mikro"] is False and c.listening is False
    req = urllib.request.Request(base + "/text", data=b'{"text":"x"}', method="POST",
                                 headers={"Content-Type": "application/json", "Origin": "https://evil.example"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code == 403
