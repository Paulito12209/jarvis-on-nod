"""Who is being talked to? Name detection, conversation window, quiet mode and a small
"decision model" (router) that tells: is this sentence meant for me or for someone else?
"""

from __future__ import annotations

import difflib
import json
import re
import time
from dataclasses import dataclass

# Ways Whisper may write a name it did not hear clearly.
_KNOWN_ALIASES = {
    "jarvis": ["jarvis", "javis", "jarwis", "jarvi", "dschawis", "tschawis", "dschärwis", "jervis",
               "charvis", "jarvys", "jarviss", "jahrvis", "jarviz"],
}

_QUIET = re.compile(
    r"\b(sei (mal )?(still|ruhig|leise)|ruhe( bitte)?|pause|psst|halt (mal )?die klappe|"
    r"nicht (zu|dazwischen)hören|hör (mal )?(kurz )?weg|ich (telefonier|rede|sprech|schreib|diktier)\w*|"
    r"bin (gleich|kurz) (beschäftigt|weg))\b",
    re.I,
)
_WAKE_ONLY = re.compile(r"^\W*(hey|hallo|hi|ok|okay|na)?\W*$", re.I)


def _norm(word: str) -> str:
    return re.sub(r"[^\wäöüß]", "", word.lower())


def name_variants(name: str) -> list[str]:
    n = _norm(name)
    return sorted(set([n] + _KNOWN_ALIASES.get(n, [])))


def mentions_name(text: str, name: str) -> bool:
    """True if the text contains the name (or something that sounds very close)."""
    variants = name_variants(name)
    for w in text.split():
        w = _norm(w)
        if len(w) < 3:
            continue
        if w in variants:
            return True
        if any(difflib.SequenceMatcher(None, w, v).ratio() >= 0.8 for v in variants):
            return True
    return False


def remove_name(text: str, name: str) -> str:
    variants = name_variants(name)
    words = [w for w in text.split() if _norm(w) not in variants]
    return " ".join(words).strip(" ,.!?")


@dataclass
class Decision:
    answer: str  # "ja", "nein", "fragen" (ask router), "still" (enter quiet mode)
    reason: str = ""


class Attention:
    """Decides quickly – without any model – whether to answer.

    modes:
      "immer" – answer everything (old behaviour)
      "name"  – only when the name was said; afterwards a conversation window stays open
                in which a small model decides if a sentence is for me.
    """

    def __init__(self, name: str, mode: str = "name", window: float = 30.0):
        self.name = name
        self.mode = mode
        self.window = window
        self.window_until = 0.0
        self.quiet = False

    def open_window(self, now: float | None = None) -> None:
        self.window_until = (now or time.monotonic()) + self.window

    def in_window(self, now: float | None = None) -> bool:
        return (now or time.monotonic()) < self.window_until

    def decide(self, text: str, now: float | None = None) -> Decision:
        now = now or time.monotonic()
        named = mentions_name(text, self.name)
        if named and _QUIET.search(text):
            self.quiet = True
            self.window_until = 0.0
            return Decision("still", "soll still sein")
        if self.mode == "immer":
            if _QUIET.search(text) and len(text.split()) <= 6:
                self.quiet = True
                return Decision("still", "soll still sein")
            if self.quiet and not named:
                return Decision("nein", "Ruhemodus")
            self.quiet = False
            return Decision("ja", "immer")
        if named:
            self.quiet = False
            return Decision("ja", "Name gehört")
        if self.quiet:
            return Decision("nein", "Ruhemodus – sag meinen Namen")
        if self.in_window(now):
            return Decision("fragen", "im Gespräch")
        return Decision("nein", "nicht angesprochen")


ROUTER_PROMPT = """Du bist der Türsteher eines Sprachassistenten namens {name}. Ein Mikrofon hört alles im Raum.
Entscheide NUR, ob der letzte Satz an {name} gerichtet ist.

Antworte "ja", wenn der Satz eine Frage, Bitte oder Antwort an {name} ist und zum laufenden Gespräch passt.
Antworte "nein", wenn die Person
- mit jemand anderem redet oder telefoniert,
- eine Nachricht diktiert (z. B. WhatsApp: "schreib Tom, ich komme später" ohne {name} – das ist eine Nachricht an Tom),
- etwas vorliest, laut nachdenkt, flucht oder Selbstgespräche führt,
- wenn es nach Fernseher, Radio oder Hintergrund klingt.
Im Zweifel bei einer direkten Frage im laufenden Gespräch: "ja"."""

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {"an_mich": {"type": "string", "enum": ["ja", "nein"]}},
    "required": ["an_mich"],
}


class Router:
    """Small, fast local model (e.g. qwen3.5:2b) that decides: for me or not?"""

    def __init__(self, llm, model: str, name: str):
        self.llm, self.model, self.name = llm, model, name

    def is_for_me(self, text: str, history: list[dict]) -> bool:
        recent = history[-4:]
        convo = "\n".join(
            f"{'Person' if m['role'] == 'user' else self.name}: {m['content'][:200]}" for m in recent
        ) or "(noch nichts)"
        messages = [
            {"role": "system", "content": ROUTER_PROMPT.format(name=self.name)},
            {"role": "user", "content": f"Bisheriges Gespräch:\n{convo}\n\nLetzter Satz: \"{text}\"\n\nIst der letzte Satz an {self.name} gerichtet?"},
        ]
        raw = self.llm.complete(self.model, messages, format=ROUTER_SCHEMA, max_tokens=20)
        try:
            return json.loads(raw).get("an_mich", "ja") != "nein"
        except (ValueError, AttributeError):
            return "nein" not in raw.lower()
