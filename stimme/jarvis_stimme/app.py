"""The voice loop: listen -> understand -> decide -> think (streaming) -> speak sentence by sentence.

Everything runs at the same time:
  * the model is still writing sentence 3 while the voice speaks sentence 1,
  * a bridge phrase ("Mhm.", "Gute Frage …") covers the moment before the answer is ready,
  * a tiny model decides in parallel whether you were even talking to Jarvis,
  * the microphone keeps listening, so you can interrupt (barge-in),
  * when it is quiet, Jarvis thinks ahead about the topic.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from .bilder import find_image_paths, load_image_b64, strip_paths
from .bruecken import classify, strip_leading_filler
from .text import SentenceChunker, clean_for_speech, is_goodbye, looks_like_hallucination
from .vad import CHUNK_SEC, TurnDetector
from .werkzeuge import TOOL_HINT, TOOLS, run_tool
from .zuhoeren import Attention

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def system_prompt(name: str = "Jarvis", tools: bool = False, notes: str = "") -> str:
    now = datetime.now()
    text = (
        f"Du bist {name}, ein freundlicher, kluger Sprachassistent. Alles, was du schreibst, wird "
        "sofort laut vorgelesen. Antworte deshalb immer auf Deutsch, natürlich und locker wie in "
        "einem echten Gespräch, meistens in ein bis drei kurzen Sätzen. Fang direkt mit der Antwort "
        "an, ohne Einleitung. Keine Listen, kein Markdown, keine Emojis, keine Tabellen. Wenn etwas "
        "länger ist, gib zuerst die Kurzfassung und biete an, mehr zu erzählen. Wenn du etwas nicht "
        f"weißt, sag es ehrlich. Heute ist {WEEKDAYS[now.weekday()]}, der {now:%d.%m.%Y}, "
        f"es ist {now:%H:%M} Uhr. Dein eingebautes Wissen ist älter als heute. "
        "Behaupte nie, etwas gesehen, geöffnet, gesucht oder erledigt zu haben, was du nicht "
        "wirklich getan hast. Bilder kannst du nur sehen, wenn sie dir mitgeschickt werden."
    )
    if tools:
        text += " " + TOOL_HINT
    if notes:
        text += ("\n\nDeine vorab gesammelten Notizen zum Thema (nur nutzen, wenn sie passen, "
                 "nicht erwähnen, dass es Notizen sind):\n" + notes[:1200])
    return text


@dataclass
class TurnTimes:
    end_of_speech: float = 0.0
    stt_done: float = 0.0
    first_token: float = 0.0
    first_chunk: float = 0.0
    first_audio: float = 0.0
    filler: str = ""

    def summary(self, pause: float) -> str:
        if not self.first_audio:
            return ""
        total = self.first_audio - self.end_of_speech
        hear = self.stt_done - self.end_of_speech
        think = max(0.0, (self.first_chunk or self.first_audio) - self.stt_done)
        voice = max(0.0, self.first_audio - (self.first_chunk or self.first_audio))
        de = lambda x: f"{x:.2f}".replace(".", ",")  # noqa: E731
        extra = f"  · Brücke: „{self.filler}“" if self.filler else ""
        return (f"⚡ {de(total)} s bis zum ersten Ton  (Hören {de(hear)} · Denken {de(think)} · "
                f"Stimme {de(voice)})  + {de(pause)} s Pause-Erkennung{extra}")


@dataclass
class Settings:
    model: str
    pause: float = 0.6
    barge_in: bool = True
    barge_in_threshold: float = 0.85
    barge_in_min: float = 0.35
    vad_threshold: float = 0.5
    history_turns: int = 12
    name: str = "Jarvis"
    show_times: bool = True
    listen_mode: str = "immer"  # "immer" or "name"
    window: float = 30.0  # seconds after an answer in which no name is needed
    filler_delay: float = 0.35  # play a bridge phrase if the answer is not ready after this
    tools: bool = True
    proactive: bool = True
    proactive_after: float = 40.0  # seconds of silence before an "Übrigens …"
    max_tool_rounds: int = 2
    vision_model: str | None = None


class _Turn:
    """Everything that belongs to one answer."""

    def __init__(self, my_id: int, times: TurnTimes):
        self.id = my_id
        self.times = times
        self.lock = threading.Lock()
        self.spoken_any = False  # a real answer chunk was queued
        self.filler_played = False
        self.decided = threading.Event()
        self.approved = False
        self.pending: list[str] = []


class Conversation:
    def __init__(self, settings: Settings, stt, llm, tts, player, out=print,
                 fillers=None, router=None, thinker=None):
        self.s = settings
        self.stt, self.llm, self.tts, self.player = stt, llm, tts, player
        self.fillers, self.router, self.thinker = fillers, router, thinker
        self.out = out
        self.attention = Attention(settings.name, settings.listen_mode, settings.window)
        self.history: list[dict] = []
        self.turn_id = 0
        self._stop = threading.Event()
        self._generating = threading.Event()
        self._tts_q: queue.Queue = queue.Queue()
        self.finished = threading.Event()
        self.detector = TurnDetector(threshold=settings.vad_threshold, end_silence=settings.pause)
        self._barge_chunks = max(1, round(settings.barge_in_min / CHUNK_SEC))
        self.last_activity = time.monotonic()
        self.last_answer = 0.0
        threading.Thread(target=self._tts_worker, daemon=True).start()

    # -- state -------------------------------------------------------------------------
    @property
    def assistant_busy(self) -> bool:
        return self._generating.is_set() or self.player.busy

    def interrupt(self) -> None:
        """Stop talking and thinking immediately."""
        self.turn_id += 1
        self._stop.set()
        self._generating.clear()
        self.player.stop()
        if self.thinker:
            self.thinker.cancel()
        while True:
            try:
                self._tts_q.get_nowait()
            except queue.Empty:
                break
            self._tts_q.task_done()

    # -- microphone side ---------------------------------------------------------------
    def on_mic_chunk(self, chunk: np.ndarray, prob: float) -> None:
        busy = self.assistant_busy
        if busy and not self.s.barge_in:
            self.detector.reset()
            return
        if busy:
            ev = self.detector.feed(prob, chunk, threshold=self.s.barge_in_threshold,
                                    min_speech_chunks=self._barge_chunks)
        elif time.monotonic() - getattr(self.player, "last_sound", 0.0) < 0.25:
            self.detector.reset()  # echo tail right after the voice stopped
            return
        else:
            ev = self.detector.feed(prob, chunk)
            if ev is None and not self.detector.in_speech:
                self.tick()
        if ev is None:
            return
        self.last_activity = time.monotonic()
        if ev.kind == "start":
            if self.thinker:
                self.thinker.cancel()
            if busy:
                self.interrupt()
                self.out("✋ Unterbrochen – ich höre zu …")
            else:
                self.out("🎤 …")
        elif ev.kind == "end":
            self.handle_audio(ev.audio, end_time=time.monotonic())

    def tick(self, now: float | None = None) -> None:
        """Called while it is quiet: maybe say one proactive sentence."""
        now = now or time.monotonic()
        if not (self.s.proactive and self.thinker and self.thinker.suggestion):
            return
        if self.assistant_busy or self.attention.quiet:
            return
        quiet_for = now - max(self.last_activity, self.last_answer)
        if quiet_for < self.s.proactive_after or now - self.last_answer > 180:
            return
        text = clean_for_speech(self.thinker.take_suggestion())
        if not text:
            return
        if not text.lower().startswith(("übrigens", "ach", "kleiner tipp", "wenn du")):
            text = "Übrigens, " + text[0].lower() + text[1:]
        self.out(f"💡 {self.s.name}: {text}")
        self.history.append({"role": "assistant", "content": text})
        self.attention.open_window()
        self.last_answer = time.monotonic()
        self._tts_q.put((self.turn_id, text, TurnTimes()))

    # -- one turn ----------------------------------------------------------------------
    def handle_audio(self, audio: np.ndarray, end_time: float | None = None) -> threading.Thread:
        return self._start_turn(audio, None, end_time)

    def handle_text(self, text: str) -> threading.Thread:
        """Typed text is always meant for Jarvis – no name needed."""
        return self._start_turn(None, text, None, direct=True)

    def _start_turn(self, audio, text, end_time, direct: bool = False) -> threading.Thread:
        self.interrupt()
        self._stop = threading.Event()
        turn = _Turn(self.turn_id, TurnTimes(end_of_speech=end_time or time.monotonic()))
        self._generating.set()
        t = threading.Thread(target=self._run_turn, args=(turn, audio, text, self._stop, direct), daemon=True)
        t.start()
        return t

    def _current(self, turn: _Turn) -> bool:
        return turn.id == self.turn_id

    def _run_turn(self, turn: _Turn, audio, text, stop: threading.Event, direct: bool = False):
        times = turn.times
        try:
            if text is None:
                text = self.stt.transcribe(audio)
            times.stt_done = time.monotonic()
            if not self._current(turn) or looks_like_hallucination(text):
                return

            decision = self.attention.decide(text)
            if direct and decision.answer in ("nein", "fragen"):
                decision.answer, self.attention.quiet = "ja", False
            if decision.answer == "nein":
                self.out(f"💤 ({decision.reason}) {text}")
                return
            self.out(f"🗣️  Du: {text}")
            if decision.answer == "still":
                self._say_now(turn, "Okay, ich bin still. Sag einfach meinen Namen, wenn du mich brauchst.")
                self._finish(turn)
                return

            kind = classify(text, self.s.name)
            if kind == "hallo" and self.fillers and self.fillers.ready.is_set():
                # Just the name or "Hallo" – answer instantly, no model needed.
                self._approve(turn, True)
                phrase = self._play_filler(turn, "hallo", force=True)
                self.history += [{"role": "user", "content": text},
                                 {"role": "assistant", "content": phrase or "Ja?"}]
                self.attention.open_window()
                self._finish(turn)
                return

            if decision.answer == "fragen" and self.router is not None:
                threading.Thread(target=self._ask_router, args=(turn, text), daemon=True).start()
            else:
                self._approve(turn, True)

            if self.fillers:
                threading.Thread(target=self._filler_timer, args=(turn, kind), daemon=True).start()

            goodbye = is_goodbye(text)
            model, images, user_text = self.s.model, [], text
            paths = find_image_paths(text)
            if paths:
                user_text = strip_paths(text) or "Was ist auf dem Bild? Beschreib es kurz."
                if not self.s.vision_model:
                    self._approve(turn, True)
                    self._say_now(turn, "Ich kann leider keine Bilder ansehen, weil kein Bild-Modell "
                                        "installiert ist. Installier zum Beispiel gemma4:12b, dann klappt das.")
                    self._finish(turn)
                    return
                try:
                    for p in paths[:3]:
                        images.append(load_image_b64(p))
                        self.out(f"🖼️  Bild geladen: {p}")
                except ValueError as e:
                    self._approve(turn, True)
                    self._say_now(turn, str(e))
                    self._finish(turn)
                    return
                model = self.s.vision_model
            names = ", ".join(p.rsplit("/", 1)[-1] for p in paths)
            self.history.append({"role": "user", "content": f"[Bild: {names}] {user_text}" if paths else text})
            self.history = self.history[-2 * self.s.history_turns:]
            notes = self.thinker.take_notes() if self.thinker else ""
            use_tools = self.s.tools
            messages = [{"role": "system", "content": system_prompt(self.s.name, use_tools, notes)}] + self.history
            if images:
                messages[-1] = {"role": "user", "content": user_text, "images": images}

            reply = self._generate(turn, messages, stop, use_tools, model)
            if not turn.approved:
                # The router said: not for me. Forget this sentence.
                if self.history and self.history[-1].get("role") == "user":
                    self.history.pop()
                self.out("💤 (war nicht an mich gerichtet)")
                return
            if reply:
                if not self._current(turn):
                    reply += " … (unterbrochen)"
                self.history.append({"role": "assistant", "content": reply})
            self._finish(turn)
            if self._current(turn):
                self.attention.open_window()
                self.last_answer = time.monotonic()
                if self.s.show_times and times.first_audio:
                    self.out(times.summary(self.s.pause))
                if self.thinker and not goodbye:
                    self.thinker.start(self.history)
                if goodbye:
                    self.finished.set()
        except Exception as e:  # keep the loop alive and say what went wrong
            self.out(f"\n⚠️  Fehler: {e}")
        finally:
            if self._current(turn):
                self._generating.clear()

    def _finish(self, turn: _Turn) -> None:
        """Wait until everything is spoken."""
        self._tts_q.join()
        if self._current(turn):
            self.player.wait()

    def _generate(self, turn: _Turn, messages: list[dict], stop: threading.Event, use_tools: bool,
                  model: str | None = None) -> str:
        """Stream the answer; run tools (web search) if the model asks for them."""
        chunker = SentenceChunker()
        answer: list[str] = []
        printed_header = False
        for _round in range(self.s.max_tool_rounds + 1):
            calls = None
            tools = TOOLS if use_tools and _round < self.s.max_tool_rounds else None
            for piece in self.llm.stream(model or self.s.model, messages, stop=stop, tools=tools):
                if not self._current(turn) or stop.is_set():
                    return "".join(answer).strip()
                if not isinstance(piece, str):
                    calls = piece
                    continue
                if not turn.times.first_token:
                    turn.times.first_token = time.monotonic()
                if not printed_header and turn.approved:
                    self.out(f"🤖 {self.s.name}: ", end="")
                    printed_header = True
                answer.append(piece)
                if printed_header:
                    self.out(piece, end="")
                for chunk in chunker.feed(piece):
                    self._speak(turn, chunk)
                if turn.decided.is_set() and not turn.approved:
                    stop.set()
                    return ""
            if not calls:
                break
            # The model wants to search the web.
            self._wait_decision(turn)
            if not turn.approved:
                return ""
            self._play_filler(turn, "suche", force=True)
            messages = messages + [{"role": "assistant", "content": "".join(answer), "tool_calls": list(calls)}]
            for call in calls:
                fn = call.get("function", {})
                args = fn.get("arguments", {})
                self.out(f"🔎 Suche: {args.get('suchbegriff', args) if isinstance(args, dict) else args}")
                result = run_tool(fn.get("name", ""), args)
                messages.append({"role": "tool", "content": result, "tool_name": fn.get("name", "")})
            if not self._current(turn):
                return "".join(answer).strip()
        for chunk in chunker.flush():
            self._speak(turn, chunk)
        self._wait_decision(turn)
        if turn.approved:
            if not printed_header:
                self.out(f"🤖 {self.s.name}: {''.join(answer).strip()}")
            else:
                self.out("")
        return "".join(answer).strip()

    # -- deciding ----------------------------------------------------------------------
    def _ask_router(self, turn: _Turn, text: str) -> None:
        try:
            ok = self.router.is_for_me(text, self.history[:-1] if self.history else [])
        except Exception as e:  # router broken -> just answer
            self.out(f"\n⚠️  Entscheider-Fehler: {e}")
            ok = True
        self._approve(turn, ok)

    def _approve(self, turn: _Turn, ok: bool) -> None:
        with turn.lock:
            if turn.decided.is_set():
                return
            turn.approved = ok
            turn.decided.set()
            pending, turn.pending = turn.pending, []
            if ok:
                for chunk in pending:
                    self._tts_q.put((turn.id, chunk, turn.times))

    def _wait_decision(self, turn: _Turn, timeout: float = 4.0) -> None:
        if not turn.decided.wait(timeout):
            self._approve(turn, True)

    # -- speaking ----------------------------------------------------------------------
    def _speak(self, turn: _Turn, chunk: str) -> None:
        with turn.lock:
            if not turn.spoken_any and turn.filler_played:
                chunk = strip_leading_filler(chunk)
            if not turn.times.first_chunk:
                turn.times.first_chunk = time.monotonic()
            turn.spoken_any = True
            if not turn.approved:
                turn.pending.append(chunk)
                return
        self._tts_q.put((turn.id, chunk, turn.times))

    def _say_now(self, turn: _Turn, text: str) -> None:
        self._tts_q.put((turn.id, text, turn.times))

    def _filler_timer(self, turn: _Turn, kind: str) -> None:
        self._wait_decision(turn, timeout=3.0)
        if not turn.approved:
            return
        time.sleep(self.s.filler_delay)
        self._play_filler(turn, kind)

    def _play_filler(self, turn: _Turn, kind: str, force: bool = False) -> str:
        """Play a ready-made bridge phrase, unless the answer already started."""
        if not self.fillers or not self._current(turn):
            return ""
        with turn.lock:
            if turn.spoken_any and not force:
                return ""
            if turn.filler_played and not force:
                return ""
            picked = self.fillers.pick(kind)
            if not picked:
                return ""
            phrase, audio = picked
            turn.filler_played = True
            turn.times.filler = turn.times.filler or phrase
            if not turn.times.first_chunk:
                turn.times.first_chunk = time.monotonic()
            breath = self.fillers.maybe_breath() if kind not in ("hallo", "suche") else None
        times = turn.times

        def mark(t=times):
            if not t.first_audio:
                t.first_audio = time.monotonic()

        if breath is not None:
            self.player.play(breath, on_start=mark)
        self.player.play(audio, on_start=mark)
        self.out(f"   💬 {phrase}")
        return phrase

    def _tts_worker(self) -> None:
        while True:
            my_id, chunk, times = self._tts_q.get()
            try:
                if my_id != self.turn_id or not chunk:
                    continue
                audio = self.tts.synth(chunk)
                if my_id != self.turn_id:
                    continue

                def mark(t=times):
                    if not t.first_audio:
                        t.first_audio = time.monotonic()

                self.player.play(audio, on_start=mark)
            except Exception as e:
                self.out(f"\n⚠️  Stimme-Fehler: {e}")
            finally:
                self._tts_q.task_done()
