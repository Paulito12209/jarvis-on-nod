"""Start: python -m jarvis_stimme  (or ./scripts/jarvis-stimme.sh from the repo)."""

from __future__ import annotations

import argparse
import sys
import threading
import time

from . import __version__
from .llm import OllamaChat, OllamaError, pick_model, pick_small_model
from .tts import APP_HOME

CONFIG = APP_HOME / "einstellungen.json"


def load_config() -> dict:
    try:
        import json

        return json.loads(CONFIG.read_text())
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    import json

    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))


def setup(cfg: dict) -> dict:
    """First start: ask for the assistant's name and how it should listen."""
    from .terminal import choose, choose_name

    print("\n✨ Kurze Einrichtung (nur einmal, ändern mit --einrichten)\n")
    name = choose_name(cfg.get("name"))
    print()
    modes = [f"Nur wenn ich „{name}“ sage  (empfohlen)", "Auf alles, was ich sage"]
    i = choose(f"Wann soll {name} antworten?", modes, 0 if cfg.get("zuhoeren", "name") == "name" else 1)
    cfg.update(name=name, zuhoeren="name" if i == 0 else "immer")
    save_config(cfg)
    print(f"  ✔ Gespeichert in {CONFIG}\n")
    return cfg


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="jarvis-stimme",
        description="Jarvis Stimme: schneller, komplett lokaler Sprachassistent auf Deutsch.",
    )
    p.add_argument("--modell", help="Ollama-Modell, z. B. gemma4:12b (Standard: automatisch das schnellste gute)")
    p.add_argument("--stimme", help="Piper-Stimme: Pfad zur .onnx-Datei oder ein Name-Teil wie 'thorsten'")
    p.add_argument("--whisper", help="Whisper-Modell (Standard: large-v3-turbo)")
    p.add_argument("--pause", type=float, default=0.6,
                   help="Sekunden Stille, nach denen du fertig bist (Standard 0.6; kleiner = schneller)")
    p.add_argument("--tempo", type=float, default=1.05, help="Sprechtempo der Stimme (1.0 = normal)")
    p.add_argument("--ohne-unterbrechen", action="store_true",
                   help="Kein Dazwischenreden (nimm das, wenn Jarvis sich über Lautsprecher selbst unterbricht)")
    p.add_argument("--empfindlichkeit", type=float, default=0.85,
                   help="Wie sicher muss Dazwischenreden erkannt werden (0.5–0.95, Standard 0.85)")
    p.add_argument("--gui", "--oberflaeche", dest="gui", action="store_true",
                   help="Mit Fenster starten (Mikro-Knopf, Live-Text, Bilder reinziehen)")
    p.add_argument("--port", type=int, default=8765, help="Port für das Fenster (Standard 8765)")
    p.add_argument("--kein-browser", action="store_true", help="Fenster nicht automatisch öffnen")
    p.add_argument("--tippen", action="store_true", help="Tippen statt Sprechen (Antwort kommt trotzdem als Stimme)")
    p.add_argument("--test", action="store_true", help="Alles einmal durchmessen und Zeiten anzeigen")
    p.add_argument("--geraete", action="store_true", help="Mikrofone und Lautsprecher auflisten")
    p.add_argument("--mikro", help="Mikrofon (Nummer oder Name aus --geraete)")
    p.add_argument("--lautsprecher", help="Lautsprecher (Nummer oder Name aus --geraete)")
    p.add_argument("--ollama", default="http://localhost:11434", help="Adresse von Ollama")
    p.add_argument("--kontext", type=int, default=8192, help="Kontextlänge für das Modell (klein = schneller)")
    p.add_argument("--name", help="Name des Assistenten (Standard: aus der Einrichtung, sonst Jarvis)")
    p.add_argument("--einrichten", action="store_true", help="Name und Zuhör-Art neu festlegen")
    p.add_argument("--zuhoeren", choices=["name", "immer"],
                   help="'name' = nur reagieren, wenn der Name fällt (danach Gesprächsfenster); 'immer' = auf alles")
    p.add_argument("--fenster", type=float, default=30.0,
                   help="Sekunden nach einer Antwort, in denen du den Namen nicht sagen musst (Standard 30)")
    p.add_argument("--entscheider", help="Kleines Modell, das entscheidet ob du mich meinst (Standard: automatisch, 'aus' = keins)")
    p.add_argument("--bildmodell", help="Modell zum Bilder-Ansehen (Standard: automatisch, z. B. gemma4:12b)")
    p.add_argument("--ohne-bruecken", action="store_true", help="Keine Brückensätze wie 'Mhm' oder 'Gute Frage'")
    p.add_argument("--ohne-atmen", action="store_true", help="Kein leises Einatmen vor Antworten")
    p.add_argument("--ohne-websuche", action="store_true", help="Keine Websuche")
    p.add_argument("--ohne-statuszeile", action="store_true", help="Keine Statuszeile oben im Terminal")
    p.add_argument("--einfach", action="store_true",
                   help="Einfache Terminal-Ausgabe statt der Oberfläche mit Statusleiste und Eingabezeile")
    p.add_argument("--nicht-proaktiv", action="store_true", help="Kein Vorausdenken und keine 'Übrigens …'-Vorschläge")
    p.add_argument("--version", action="version", version=f"jarvis-stimme {__version__}")
    return p.parse_args(argv)


def _device(v):
    if v is None:
        return None
    return int(v) if v.isdigit() else v


def step(msg: str):
    print(f"  {msg} …", end=" ", flush=True)
    return time.monotonic()


def done(t0: float, extra: str = ""):
    print(f"fertig ({time.monotonic() - t0:.1f} s){' – ' + extra if extra else ''}", flush=True)


def main(argv=None) -> int:
    a = parse_args(argv)

    if a.geraete:
        import sounddevice as sd

        print(sd.query_devices())
        return 0

    cfg = load_config()
    if (a.einrichten or not cfg) and not a.test and sys.stdin.isatty():
        try:
            cfg = setup(cfg)
        except (EOFError, KeyboardInterrupt):
            pass
    name = a.name or cfg.get("name") or "Jarvis"
    listen_mode = a.zuhoeren or cfg.get("zuhoeren") or "name"
    if a.tippen:
        listen_mode = "immer"

    print(f"\n🤖 {name} – alles läuft lokal auf deinem Computer\n")

    # 1) Brain (Ollama) – start loading first, it takes longest.
    llm = OllamaChat(a.ollama, num_ctx=a.kontext)
    try:
        installed = llm.list_models()
        model = pick_model(installed, a.modell)
    except OllamaError as e:
        print(f"❌ {e}")
        return 2

    warm_err: list[Exception] = []

    def _warm():
        try:
            llm.warmup(model)
        except Exception as e:  # noqa: BLE001
            warm_err.append(e)

    warm_thread = threading.Thread(target=_warm, daemon=True)
    t_warm = time.monotonic()
    warm_thread.start()

    # 2) Voice (Piper)
    from .tts import PiperTTS, find_voice

    voice_path = find_voice(a.stimme)
    if voice_path is None:
        print("❌ Keine deutsche Piper-Stimme gefunden. Starte am besten mit ./scripts/jarvis-stimme.sh,")
        print("   das lädt die Stimme 'Thorsten' automatisch herunter.")
        return 2
    t0 = step(f"Stimme laden ({voice_path.stem})")
    tts = PiperTTS(voice_path, speed=a.tempo)
    tts.synth("Hallo.")
    done(t0)

    # 3) Ears (Whisper + VAD)
    from . import stt as stt_mod
    from .vad import make_vad

    stt_mod.PROMPT = f"Hallo {name}. Das ist ein Gespräch auf Deutsch."
    t0 = step("Ohren laden (Whisper, beim ersten Mal wird es heruntergeladen)")
    stt = stt_mod.make_stt(a.whisper)
    stt_mod.warmup(stt)
    done(t0, stt.name)
    vad, vad_name = make_vad()

    t0 = step(f"Gehirn laden ({model})")
    warm_thread.join()
    if warm_err:
        print(f"\n❌ {warm_err[0]}")
        return 2
    print(f"fertig ({time.monotonic() - t_warm:.1f} s)")

    if a.test:
        return run_test(llm, model, tts, stt)

    from .app import Conversation, Settings
    from .audio import Microphone, Player
    from .bilder import pick_vision_model
    from .bruecken import FillerBank
    from .vorausdenken import Thinker
    from .zuhoeren import Router

    # Helpers: bridge phrases, decision model, vision model, background thinker.
    fillers = None
    if not a.ohne_bruecken:
        fillers = FillerBank(tts, breath_chance=0.0 if a.ohne_atmen else 0.3)
        fillers.prepare(background=True)
    router = None
    if listen_mode == "name" and (a.entscheider or "").lower() != "aus":
        small = a.entscheider or pick_small_model(installed)
        if small:
            router = Router(llm, small, name)
            threading.Thread(target=lambda: llm.warmup(small), daemon=True).start()
    if a.bildmodell:
        vision = pick_model(installed, a.bildmodell)
    else:
        vision = pick_vision_model(llm, installed, model)
    thinker = None if a.nicht_proaktiv else Thinker(llm, model, name)

    player = Player(tts.sample_rate, device=_device(a.lautsprecher))
    settings = Settings(model=model, pause=a.pause, barge_in=not a.ohne_unterbrechen,
                        barge_in_threshold=a.empfindlichkeit, name=name, listen_mode=listen_mode,
                        window=a.fenster, tools=not a.ohne_websuche, proactive=not a.nicht_proaktiv,
                        vision_model=vision)
    conv = Conversation(settings, stt, llm, tts, player, out=lambda *x, **k: print(*x, **k, flush=True),
                        fillers=fillers, router=router, thinker=thinker)

    print(f"\n✅ Bereit!  Modell: {model} · Stimme: {tts.name} · Erkennung: {vad_name}")
    print(f"   Entscheider: {router.model if router else '–'} · Bilder: {vision or '– (kein Bild-Modell)'}"
          f" · Websuche: {'an' if settings.tools else 'aus'} · Brücken: {fillers.count() if fillers else 0}")
    if listen_mode == "name":
        print(f"   👂 Ich reagiere, wenn du „{name}“ sagst. Danach {a.fenster:.0f} s ohne Namen.")
        print(f"      „{name}, sei mal still“ = Ruhe, bis du mich wieder beim Namen rufst.")
    print("   ⌨️  Du kannst auch einfach tippen und Enter drücken. Bilder: Datei ins Fenster ziehen + Enter.")
    print(f"   Sag „Tschüss {name}“ oder drück Ctrl+C zum Beenden.")
    if settings.barge_in:
        print(f"   Du kannst {name} jederzeit unterbrechen, indem du einfach redest.")
    print()

    use_tui = not a.einfach and sys.stdin.isatty() and sys.stdout.isatty()
    if use_tui:
        try:
            from .tui import TerminalUI
        except ImportError:
            use_tui = False

    # Status line at the top of the terminal: model, context tokens, microphone, speed.
    from .terminal import StatusLine, context_text

    status = StatusLine()
    if a.ohne_statuszeile or use_tui:
        status.enabled = False
    status.fields.update(name=f"🤖 {name}", modell=f"🧠 {model}",
                         kontext=context_text(0, llm.num_ctx),
                         mikro="⌨️ nur Tippen" if a.tippen else "🎙️ Mikro an")
    states = {"bereit": "", "hoert": "👂 hört zu", "denkt": "💭 denkt", "spricht": "🔊 spricht"}

    def on_status(ev: dict) -> None:
        t = ev.get("typ")
        if t == "kontext":
            status.set(kontext=context_text(ev["benutzt"], ev["limit"] or llm.num_ctx))
        elif t == "status":
            status.set(zustand=states.get(ev["status"], ""))
        elif t == "zeit":
            status.set(zeit=f"⚡ {str(ev['sekunden']).replace('.', ',')} s")
        elif t == "mikro":
            status.set(mikro="🎙️ Mikro an" if ev["an"] else "🔇 Mikro aus")

    conv.on_event = on_status
    status.start()

    tui = None
    if use_tui:
        def save_name(new: str) -> None:
            cfg["name"] = new
            save_config(cfg)

        tui = TerminalUI(conv, {"modell": model, "kontext_limit": llm.num_ctx, "nur_tippen": a.tippen},
                         save_name=save_name, history_file=APP_HOME / "eingaben.txt",
                         stats_file=APP_HOME / "statistik.jsonl")
        conv.out = lambda *x, **k: None  # everything goes through events into the interface
        conv.on_event = tui.on_event

    if a.gui:
        from .gui import serve

        info = {"modell": model, "bildmodell": vision, "websuche": settings.tools,
                "entscheider": router.model if router else None, "nur_tippen": a.tippen}
        try:
            serve(conv, info, port=a.port, open_browser=not a.kein_browser)
        except OSError as e:
            print(f"⚠️  Fenster ging nicht: {e}")
    gui_on = a.gui or use_tui  # both show the microphone level

    mic = None
    try:
        if not a.tippen:
            mic = Microphone(device=_device(a.mikro))
            mic.start()
            if not use_tui:
                print("🎤 Ich höre zu – sprich einfach los (oder tippe).")

            def listen():
                import numpy as np

                n = 0
                while not conv.finished.is_set():
                    try:
                        chunk = mic.chunks.get(timeout=0.2)
                    except Exception:
                        conv.tick()
                        continue
                    conv.on_mic_chunk(chunk, vad(chunk))
                    n += 1
                    if gui_on and n % 3 == 0:
                        rms = float(np.sqrt(np.mean((chunk.astype(np.float32) / 32768.0) ** 2)))
                        level = min(1.0, rms * 12) if conv.listening else 0.0
                        conv.emit("pegel", wert=round(level, 3))

            threading.Thread(target=listen, daemon=True).start()
        if tui is not None:
            APP_HOME.mkdir(parents=True, exist_ok=True)
            tui.run()  # blocks until Ctrl+C, /ende or "Tschüss"
            conv.finished.set()
        # Keyboard works at the same time as the microphone.
        keyboard_done = threading.Event()

        def keyboard():
            try:
                while not conv.finished.is_set():
                    line = input("").strip() if not a.tippen else input("⌨️  Du: ").strip()
                    if line:
                        t = conv.handle_text(line)
                        if a.tippen:
                            t.join()
            except (EOFError, KeyboardInterrupt):
                pass
            keyboard_done.set()

        if tui is None:
            threading.Thread(target=keyboard, daemon=True).start()
        while not conv.finished.is_set():
            if a.tippen and keyboard_done.is_set():
                break
            conv.finished.wait(0.3)
    except KeyboardInterrupt:
        pass
    finally:
        conv.interrupt()
        status.stop()
        if mic is not None:
            mic.close()
        player.close()
    print("\n👋 Tschüss!")
    return 0


def run_test(llm, model, tts, stt) -> int:
    """Measure every part once – handy to see where time goes."""
    import numpy as np

    from .audio import resample
    from .text import SentenceChunker

    print("\n🔬 Test\n")
    sentence = "Hallo Jarvis, wie wird das Wetter morgen in Berlin?"
    t0 = time.monotonic()
    audio = tts.synth(sentence)
    t_tts = time.monotonic() - t0
    dur = len(audio) / tts.sample_rate
    print(f"  🔊 Stimme:  {t_tts:.2f} s für {dur:.1f} s Sprache ({dur / max(t_tts, 1e-6):.0f}× schneller als Echtzeit)")

    pcm = (np.clip(resample(audio, tts.sample_rate, 16000), -1, 1) * 32767).astype(np.int16)
    t0 = time.monotonic()
    heard = stt.transcribe(pcm)
    print(f"  👂 Hören:   {time.monotonic() - t0:.2f} s  → „{heard}“")

    from .app import system_prompt

    msgs = [{"role": "system", "content": system_prompt()},
            {"role": "user", "content": "Erzähl mir in zwei Sätzen, was du alles kannst."}]
    chunker = SentenceChunker()
    t0 = time.monotonic()
    first_tok = first_chunk = None
    n = 0
    text = []
    for piece in llm.stream(model, msgs):
        n += 1
        text.append(piece)
        first_tok = first_tok or time.monotonic() - t0
        if first_chunk is None and chunker.feed(piece):
            first_chunk = time.monotonic() - t0
    total = time.monotonic() - t0
    first_chunk = first_chunk or total
    print(f"  🧠 Denken:  erstes Wort nach {first_tok or 0:.2f} s, erster Satzteil nach {first_chunk:.2f} s, "
          f"{n / max(total, 1e-6):.0f} Tokens/s")
    print(f"     „{''.join(text).strip()}“")
    est = 0.05 + first_chunk + t_tts * 0.5
    print(f"\n  ⚡ Geschätzt bis zur ersten Silbe: etwa {est:.1f} s nach deiner Pause\n")
    try:
        import sounddevice as sd

        sd.play(tts.synth("Test fertig. Alles funktioniert."), tts.sample_rate)
        sd.wait()
    except Exception as e:  # noqa: BLE001
        print(f"  (Abspielen ging nicht: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
