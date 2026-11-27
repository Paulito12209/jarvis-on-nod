"""Uses the real Piper voice + Silero VAD (skipped if no voice is found)."""
import os
from pathlib import Path

import numpy as np
import pytest

from jarvis_stimme.audio import resample
from jarvis_stimme.tts import find_voice
from jarvis_stimme.vad import CHUNK, SileroVAD, TurnDetector

VOICE = find_voice(os.environ.get("JARVIS_TEST_VOICE"))
pytestmark = pytest.mark.skipif(VOICE is None, reason="keine Piper-Stimme gefunden")


def test_piper_voice_and_silero_detect_a_turn():
    from jarvis_stimme.tts import PiperTTS

    tts = PiperTTS(Path(VOICE))
    speech = tts.synth("Hallo Jarvis, wie wird das Wetter morgen?")
    assert len(speech) > tts.sample_rate  # more than a second of audio
    pcm = (resample(speech, tts.sample_rate, 16000) * 30000).astype(np.int16)
    audio = np.concatenate([np.zeros(8000, np.int16), pcm, np.zeros(16000, np.int16)])

    vad, det = SileroVAD(), TurnDetector(end_silence=0.6)
    kinds = []
    for i in range(0, len(audio) - CHUNK, CHUNK):
        c = audio[i:i + CHUNK]
        ev = det.feed(vad(c), c)
        if ev:
            kinds.append((ev.kind, None if ev.audio is None else len(ev.audio)))
    assert [k for k, _ in kinds] == ["start", "end"]
    assert kinds[1][1] >= len(pcm) * 0.8
