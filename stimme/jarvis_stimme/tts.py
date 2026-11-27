"""Text to speech with Piper (fast German voice 'Thorsten', runs on the CPU in a few milliseconds)."""

from __future__ import annotations

import os
from pathlib import Path

import logging

import numpy as np

logging.getLogger("piper").setLevel(logging.ERROR)

HOME = Path.home()
APP_HOME = Path(os.environ.get("JARVIS_STIMME_HOME", HOME / ".jarvis-stimme")).expanduser()
VOICE_DIRS = [
    APP_HOME / "stimmen",
    HOME / ".openjarvis" / "voices" / "piper",
    HOME / ".openjarvis" / "voices",
    HOME / ".local" / "share" / "piper",
    HOME / ".local" / "share" / "piper-voices",
]
DEFAULT_VOICE = "de_DE-thorsten-high"


def _rank(path: Path) -> tuple[int, str]:
    n = path.name.lower()
    score = 50
    if "thorsten" in n:
        score -= 20
        if "emotional" in n:
            score += 5
    if "high" in n:
        score -= 3
    elif "medium" in n:
        score -= 2
    if not (n.startswith("de") or "de_" in n or "-de-" in n):
        score += 40
    return score, n


def find_voice(wanted: str | None = None, dirs: list[Path] | None = None) -> Path | None:
    """Return the best Piper voice (.onnx with its .json) we can find, or None."""
    if wanted:
        p = Path(os.path.expanduser(wanted))
        if p.is_file():
            return p
    candidates: list[Path] = []
    for d in dirs or VOICE_DIRS:
        if d.is_dir():
            for f in d.rglob("*.onnx"):
                if Path(str(f) + ".json").is_file() or f.with_suffix(".json").is_file():
                    candidates.append(f)
    if wanted:
        candidates = [c for c in candidates if wanted.lower() in c.name.lower()]
    if not candidates:
        return None
    return sorted(candidates, key=_rank)[0]


class PiperTTS:
    def __init__(self, voice_path: Path, speed: float = 1.0):
        from piper import PiperVoice

        cfg = Path(str(voice_path) + ".json")
        if not cfg.is_file():
            cfg = voice_path.with_suffix(".json")
        self.voice = PiperVoice.load(str(voice_path), config_path=str(cfg))
        self.sample_rate = int(self.voice.config.sample_rate)
        self.name = voice_path.stem
        self._syn = None
        try:
            from piper.config import SynthesisConfig

            # length_scale < 1 = faster speech. speed 1.1 -> ~10 % faster.
            self._syn = SynthesisConfig(length_scale=1.0 / max(0.5, speed))
        except Exception:  # pragma: no cover - older piper
            self._syn = None

    def synth(self, text: str) -> np.ndarray:
        """Return float32 audio for the text (one chunk – we already split sentences)."""
        parts = [c.audio_float_array for c in self.voice.synthesize(text, syn_config=self._syn)]
        if not parts:
            return np.zeros(0, np.float32)
        return np.concatenate(parts).astype(np.float32)
