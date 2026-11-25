"""Text helpers: clean LLM output for speech and cut a token stream into speakable chunks.

The chunker is the heart of the low latency: instead of waiting for the full answer,
we hand the first short phrase to the voice as soon as it is complete.
"""

from __future__ import annotations

import re

# Abbreviations that end with a dot but do not end a sentence.
_ABBREVIATIONS = {
    "z.b", "u.a", "d.h", "bzw", "ca", "dr", "prof", "nr", "str", "usw", "evtl", "ggf",
    "inkl", "vgl", "etc", "mio", "mrd", "min", "max", "std", "sek", "bsp", "jh", "st",
    "hr", "fr", "z.t", "o.ä", "u.ä", "s", "co", "tel", "abs", "art", "mr", "mrs",
}

_SENTENCE_END = re.compile(r"([.!?…]+[\"»“”')\]]*)\s+")
_CLAUSE_END = re.compile(r"([,;:–—])\s+")

_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF‍️]+"
)
_URL = re.compile(r"https?://\S+")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S)


def clean_for_speech(text: str) -> str:
    """Remove things a voice should not read aloud (markdown, emoji, links)."""
    text = _THINK_BLOCK.sub(" ", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _URL.sub(" Link ", text)
    text = _EMOJI.sub(" ", text)
    text = re.sub(r"`{1,3}", "", text)
    text = re.sub(r"(\*\*|__|\*|~~)", "", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)  # headings
    text = re.sub(r"^\s*[-•*+]\s+", "", text, flags=re.M)  # bullets
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.M)  # numbered lists
    text = text.replace("&", " und ").replace("%", " Prozent")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_real_sentence_end(buf: str, dot_pos: int) -> bool:
    """False for 'z.B.', 'Dr.', '3.' (ordinal) and similar."""
    if buf[dot_pos] != ".":
        return True
    before = buf[:dot_pos]
    word = re.split(r"\s", before)[-1].lower().strip("(\"'„»")
    if not word:
        return True
    if word.rstrip(".") in _ABBREVIATIONS:
        return False
    if word.isdigit():  # "am 3. Mai" – ordinal number
        return False
    if len(word) == 1 and word.isalpha():  # initials like "A."
        return False
    return True


class SentenceChunker:
    """Feed streamed tokens, get back chunks that are ready to be spoken.

    - The first chunk may end at a comma once it has a few words, so the
      voice can start as early as possible.
    - Later chunks end at sentence boundaries (longer chunks sound more natural).
    - Very long chunks are cut at a comma or space as a safety net.
    """

    def __init__(self, first_min_words: int = 4, first_max_chars: int = 90, max_chars: int = 220):
        self.first_min_words = first_min_words
        self.first_max_chars = first_max_chars
        self.max_chars = max_chars
        self._buf = ""
        self._emitted = 0
        self._in_think = False

    def _strip_think(self, token: str) -> str:
        out = []
        while token:
            if self._in_think:
                end = token.find("</think>")
                if end == -1:
                    return "".join(out)
                token = token[end + len("</think>"):]
                self._in_think = False
            else:
                start = token.find("<think>")
                if start == -1:
                    out.append(token)
                    break
                out.append(token[:start])
                token = token[start + len("<think>"):]
                self._in_think = True
        return "".join(out)

    def feed(self, token: str) -> list[str]:
        self._buf += self._strip_think(token)
        ready: list[str] = []
        while True:
            chunk = self._take_chunk()
            if chunk is None:
                break
            ready.append(chunk)
        return ready

    def flush(self) -> list[str]:
        rest = clean_for_speech(self._buf)
        self._buf = ""
        if rest:
            self._emitted += 1
            return [rest]
        return []

    def _emit(self, end: int) -> str | None:
        piece, self._buf = self._buf[:end], self._buf[end:]
        piece = clean_for_speech(piece)
        if not piece:
            return ""
        self._emitted += 1
        return piece

    def _take_chunk(self) -> str | None:
        buf = self._buf
        for m in _SENTENCE_END.finditer(buf):
            if _is_real_sentence_end(buf, m.start(1)):
                piece = self._emit(m.end())
                return piece if piece else self._take_chunk_or_none()
        if self._emitted == 0:
            for m in _CLAUSE_END.finditer(buf):
                if len(buf[: m.start()].split()) >= self.first_min_words:
                    return self._emit(m.end()) or self._take_chunk_or_none()
            if len(buf) > self.first_max_chars:
                cut = buf.rfind(" ", 0, self.first_max_chars)
                if cut > 0:
                    return self._emit(cut + 1) or self._take_chunk_or_none()
        if len(buf) > self.max_chars:
            cut = max(buf.rfind(", ", 0, self.max_chars), buf.rfind(" ", 0, self.max_chars))
            if cut > 0:
                return self._emit(cut + 1) or self._take_chunk_or_none()
        return None

    def _take_chunk_or_none(self) -> str | None:
        # An empty piece (e.g. only markdown) was dropped; look for the next one.
        return self._take_chunk()


# Phrases Whisper likes to invent on silence or noise (well known for German).
_HALLUCINATIONS = [
    "untertitel", "amara.org", "vielen dank fürs zuschauen", "vielen dank für's zuschauen",
    "danke fürs zuschauen", "bis zum nächsten mal", "swr", "zdf", "copyright",
    "abonniert", "tschüss und bis bald",
]


def looks_like_hallucination(text: str) -> bool:
    t = text.lower().strip()
    if not t or not re.search(r"\w", t):
        return True
    if len(t) < 2:
        return True
    return any(h in t for h in _HALLUCINATIONS) and len(t.split()) <= 8


_GOODBYE = re.compile(r"\b(tschüss|tschüs|auf wiedersehen|bis später|ciao)\b.*\bjarvis\b|\bjarvis\b.*\b(tschüss|aus|beenden|schlafen)\b", re.I)


def is_goodbye(text: str) -> bool:
    return bool(_GOODBYE.search(text))
