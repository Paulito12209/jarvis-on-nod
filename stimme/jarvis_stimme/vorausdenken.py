"""Thinking ahead: while you are quiet, Jarvis prepares notes on the current topic.

The notes go into the next answer (so it is richer and faster to the point), and
can be turned into one short, friendly suggestion ("Übrigens …") if you stay quiet.
Everything stops the moment you start talking again.
"""

from __future__ import annotations

import re
import threading
import time

PROMPT = (
    "Du bist der stille Hintergrund-Denker eines Sprachassistenten namens {name}. Lies das Gespräch. "
    "Schreib kurze Notizen auf Deutsch, die {name} gleich helfen: höchstens 5 Zeilen mit "
    "wahrscheinlichen Anschlussfragen und hilfreichen Fakten dazu. "
    "Schreib danach genau eine Zeile, die mit 'VORSCHLAG:' beginnt: ein kurzer, freundlicher Satz, "
    "den {name} von sich aus sagen könnte, um weiterzuhelfen (ein Angebot oder ein Tipp, keine Frage nach dem Befinden). "
    "Wenn es nichts Sinnvolles gibt, schreib 'VORSCHLAG: -'."
)


class Thinker:
    def __init__(self, llm, model: str, name: str = "Jarvis", delay: float = 3.0):
        self.llm, self.model, self.name, self.delay = llm, model, name, delay
        self.notes = ""
        self.suggestion = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._version = 0

    def cancel(self) -> None:
        self._stop.set()
        self._version += 1

    def start(self, history: list[dict]) -> None:
        """Start thinking about the conversation after a short quiet moment."""
        self.cancel()
        self._stop = threading.Event()
        version = self._version
        snapshot = list(history[-8:])
        self._thread = threading.Thread(target=self._run, args=(snapshot, self._stop, version), daemon=True)
        self._thread.start()

    def _run(self, history: list[dict], stop: threading.Event, version: int) -> None:
        if stop.wait(self.delay):
            return
        convo = "\n".join(
            f"{'Person' if m['role'] == 'user' else self.name}: {m['content'][:400]}"
            for m in history if m["role"] in ("user", "assistant")
        )
        if not convo:
            return
        messages = [{"role": "system", "content": PROMPT.format(name=self.name)},
                    {"role": "user", "content": convo}]
        parts: list[str] = []
        try:
            for piece in self.llm.stream(self.model, messages, stop=stop, max_tokens=220):
                if isinstance(piece, str):
                    parts.append(piece)
        except Exception:
            return
        if stop.is_set() or version != self._version:
            return
        text = re.sub(r"<think>.*?</think>", "", "".join(parts), flags=re.S).strip()
        m = re.search(r"VORSCHLAG:\s*(.+)", text)
        suggestion = m.group(1).strip() if m else ""
        self.suggestion = "" if suggestion in ("-", "–", "") else suggestion
        self.notes = text[: m.start()].strip() if m else text
        self.notes_time = time.monotonic()

    def take_notes(self) -> str:
        notes, self.notes = self.notes, ""
        return notes

    def take_suggestion(self) -> str:
        s, self.suggestion = self.suggestion, ""
        return s
