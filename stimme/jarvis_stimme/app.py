"""The voice loop: listen -> understand -> think (streaming) -> speak sentence by sentence.

Everything runs at the same time:
  * the model is still writing sentence 3 while the voice speaks sentence 1,
  * the microphone keeps listening, so you can interrupt (barge-in).
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from .text import SentenceChunker, is_goodbye, looks_like_hallucination
from .vad import CHUNK_SEC, TurnDetector

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def system_prompt(name: str = "Jarvis") -> str:
    now = datetime.now()
    return (
        f"Du bist {name}, ein freundlicher, kluger Sprachassistent. Alles, was du schreibst, wird "
        "sofort laut vorgelesen. Antworte deshalb immer auf Deutsch, natürlich und locker wie in "
        "einem echten Gespräch, meistens in ein bis drei kurzen Sätzen. Fang direkt mit der Antwort "
        "an, ohne Einleitung. Keine Listen, kein Markdown, keine Emojis, keine Tabellen. Wenn etwas "
        "länger ist, gib zuerst die Kurzfassung und biete an, mehr zu erzählen. Wenn du etwas nicht "
        f"weißt, sag es ehrlich. Heute ist {WEEKDAYS[now.weekday()]}, der {now:%d.%m.%Y}, "
        f"es ist {now:%H:%M} Uhr."
    )


@dataclass
class TurnTimes:
    end_of_speech: float = 0.0
    stt_done: float = 0.0
    first_token: float = 0.0
    first_chunk: float = 0.0
    first_audio: float = 0.0

    def summary(self, pause: float) -> str:
        if not self.first_audio:
            return ""
        total = self.first_audio - self.end_of_speech
        hear = self.stt_done - self.end_of_speech
        think = (self.first_chunk or self.first_audio) - self.stt_done
        voice = self.first_audio - (self.first_chunk or self.first_audio)
        de = lambda x: f"{x:.2f}".replace(".", ",")  # noqa: E731
        return (f"⚡ {de(total)} s bis zur ersten Silbe  (Hören {de(hear)} · Denken {de(think)} · "
                f"Stimme {de(voice)})  + {de(pause)} s Pause-Erkennung")


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


class Conversation:
    def __init__(self, settings: Settings, stt, llm, tts, player, out=print):
        self.s = settings
        self.stt, self.llm, self.tts, self.player = stt, llm, tts, player
        self.out = out
        self.history: list[dict] = []
        self.turn_id = 0
        self._stop = threading.Event()
        self._generating = threading.Event()
        self._tts_q: queue.Queue = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self.finished = threading.Event()
        self.detector = TurnDetector(threshold=settings.vad_threshold, end_silence=settings.pause)
        self._barge_chunks = max(1, round(settings.barge_in_min / CHUNK_SEC))
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
            # Echo tail right after the voice stopped – ignore.
            self.detector.reset()
            return
        else:
            ev = self.detector.feed(prob, chunk)
        if ev is None:
            return
        if ev.kind == "start":
            if busy:
                self.interrupt()
                self.out("✋ Unterbrochen – ich höre zu …")
            else:
                self.out("🎤 …")
        elif ev.kind == "end":
            self.handle_audio(ev.audio, end_time=time.monotonic())

    # -- one turn ----------------------------------------------------------------------
    def handle_audio(self, audio: np.ndarray, end_time: float | None = None) -> threading.Thread:
        self.interrupt()
        self._stop = threading.Event()
        my_id = self.turn_id
        times = TurnTimes(end_of_speech=end_time or time.monotonic())
        self._generating.set()
        t = threading.Thread(target=self._run_turn, args=(my_id, audio, None, times, self._stop),
                             daemon=True)
        t.start()
        return t

    def handle_text(self, text: str) -> threading.Thread:
        self.interrupt()
        self._stop = threading.Event()
        my_id = self.turn_id
        times = TurnTimes(end_of_speech=time.monotonic())
        self._generating.set()
        t = threading.Thread(target=self._run_turn, args=(my_id, None, text, times, self._stop),
                             daemon=True)
        t.start()
        return t

    def _run_turn(self, my_id, audio, text, times: TurnTimes, stop: threading.Event):
        try:
            if text is None:
                text = self.stt.transcribe(audio)
            times.stt_done = time.monotonic()
            if my_id != self.turn_id:
                return
            if looks_like_hallucination(text):
                return
            self.out(f"🗣️  Du: {text}")
            goodbye = is_goodbye(text)
            self.history.append({"role": "user", "content": text})
            self.history = self.history[-2 * self.s.history_turns:]
            messages = [{"role": "system", "content": system_prompt(self.s.name)}] + self.history

            chunker = SentenceChunker()
            answer: list[str] = []
            self.out(f"🤖 {self.s.name}: ", end="")
            for piece in self.llm.stream(self.s.model, messages, stop=stop):
                if my_id != self.turn_id or stop.is_set():
                    break
                if not times.first_token:
                    times.first_token = time.monotonic()
                answer.append(piece)
                self.out(piece, end="")
                for chunk in chunker.feed(piece):
                    self._speak(my_id, chunk, times)
            else:
                for chunk in chunker.flush():
                    self._speak(my_id, chunk, times)
            self.out("")
            reply = "".join(answer).strip()
            if reply:
                if my_id != self.turn_id:
                    reply += " … (unterbrochen)"
                self.history.append({"role": "assistant", "content": reply})
            # Wait until the voice has spoken everything, then print the timing.
            self._tts_q.join()
            if my_id == self.turn_id:
                self.player.wait()
                if self.s.show_times and times.first_audio:
                    self.out(times.summary(self.s.pause))
                if goodbye:
                    self.finished.set()
        except Exception as e:  # keep the loop alive and say what went wrong
            self.out(f"\n⚠️  Fehler: {e}")
        finally:
            if my_id == self.turn_id:
                self._generating.clear()

    def _speak(self, my_id: int, chunk: str, times: TurnTimes) -> None:
        if not times.first_chunk:
            times.first_chunk = time.monotonic()
        self._tts_q.put((my_id, chunk, times))

    def _tts_worker(self) -> None:
        while True:
            my_id, chunk, times = self._tts_q.get()
            try:
                if my_id != self.turn_id:
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
