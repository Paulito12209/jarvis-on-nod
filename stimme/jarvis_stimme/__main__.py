"""Start: python -m jarvis_stimme  (or ./scripts/jarvis-stimme.sh from the repo)."""

from __future__ import annotations

import argparse
import sys
import time

from . import __version__
from .llm import OllamaChat, OllamaError, pick_model


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
    p.add_argument("--tippen", action="store_true", help="Tippen statt Sprechen (Antwort kommt trotzdem als Stimme)")
    p.add_argument("--test", action="store_true", help="Alles einmal durchmessen und Zeiten anzeigen")
    p.add_argument("--geraete", action="store_true", help="Mikrofone und Lautsprecher auflisten")
    p.add_argument("--mikro", help="Mikrofon (Nummer oder Name aus --geraete)")
    p.add_argument("--lautsprecher", help="Lautsprecher (Nummer oder Name aus --geraete)")
    p.add_argument("--ollama", default="http://localhost:11434", help="Adresse von Ollama")
    p.add_argument("--kontext", type=int, default=8192, help="Kontextlänge für das Modell (klein = schneller)")
    p.add_argument("--name", default="Jarvis", help="Name des Assistenten")
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

    print("\n🤖 Jarvis Stimme – alles läuft lokal auf deinem Computer\n")

    # 1) Brain (Ollama) – start loading first, it takes longest.
    llm = OllamaChat(a.ollama, num_ctx=a.kontext)
    try:
        model = pick_model(llm.list_models(), a.modell)
    except OllamaError as e:
        print(f"❌ {e}")
        return 2

    import threading

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

    player = Player(tts.sample_rate, device=_device(a.lautsprecher))
    settings = Settings(model=model, pause=a.pause, barge_in=not a.ohne_unterbrechen,
                        barge_in_threshold=a.empfindlichkeit, name=a.name)
    conv = Conversation(settings, stt, llm, tts, player,
                        out=lambda *x, **k: print(*x, **k, flush=True))

    print(f"\n✅ Bereit!  Modell: {model} · Stimme: {tts.name} · Erkennung: {vad_name}")
    print("   Sag 'Tschüss Jarvis' oder drück Ctrl+C zum Beenden.")
    if settings.barge_in:
        print("   Du kannst Jarvis jederzeit unterbrechen, indem du einfach redest.")
    print()

    try:
        if a.tippen:
            while not conv.finished.is_set():
                line = input("⌨️  Du: ").strip()
                if line:
                    conv.handle_text(line).join()
        else:
            mic = Microphone(device=_device(a.mikro))
            mic.start()
            print("🎤 Ich höre zu – sprich einfach los.")
            while not conv.finished.is_set():
                try:
                    chunk = mic.chunks.get(timeout=0.2)
                except Exception:
                    continue
                conv.on_mic_chunk(chunk, vad(chunk))
            mic.close()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        conv.interrupt()
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
