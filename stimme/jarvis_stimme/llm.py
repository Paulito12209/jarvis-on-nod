"""Talk to a local Ollama server with token streaming (only the Python standard library)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Iterator

# Fast models first: for voice, time to the first sentence matters most.
# MoE models (only ~3B active parameters) answer much faster than dense models of the same size.
MODEL_PREFERENCE = [
    "qwen3.6:35b",
    "qwen3.6:35b-a3b",
    "qwen3.5:35b",
    "qwen3-30b",
    "qwen3:30b",
    "gemma4:12b",
    "qwen3.6:27b",
    "qwen3.5:27b",
    "qwen3.8:27b",
    "gemma4",
    "qwen3.6",
    "qwen3.5",
    "qwen3",
    "gpt-oss:20b",
]

_SKIP_WORDS = ("embed", "whisper", "vision-only", "tts")


class OllamaError(RuntimeError):
    pass


def pick_model(installed: list[str], wanted: str | None = None) -> str:
    """Choose the model: the one asked for, otherwise the fastest good one that is installed."""
    if not installed:
        raise OllamaError("In Ollama ist noch kein Modell installiert. Beispiel: ollama pull gemma4:12b")
    if wanted:
        if wanted in installed:
            return wanted
        for name in installed:
            if name.startswith(wanted):
                return name
        raise OllamaError(
            f"Modell '{wanted}' ist nicht installiert. Installiert sind: {', '.join(installed)}"
        )
    usable = [m for m in installed if not any(w in m.lower() for w in _SKIP_WORDS)]
    for pref in MODEL_PREFERENCE:
        for name in usable:
            if name == pref or name.startswith(pref):
                return name
    return (usable or installed)[0]


class OllamaChat:
    def __init__(self, base_url: str = "http://localhost:11434", num_ctx: int = 8192,
                 keep_alive: str = "60m", temperature: float = 0.6):
        self.base_url = base_url.rstrip("/")
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self.temperature = temperature
        self._think_supported: dict[str, bool] = {}

    # -- helpers -----------------------------------------------------------------
    def _request(self, path: str, payload: dict | None = None, timeout: float = 600):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base_url + path, data=data,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            raise OllamaError(f"Ollama antwortet mit Fehler {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise OllamaError(
                f"Ollama ist nicht erreichbar unter {self.base_url}. Läuft die Ollama-App?"
            ) from e

    def list_models(self) -> list[str]:
        with self._request("/api/tags", timeout=5) as r:
            return [m["name"] for m in json.load(r).get("models", [])]

    def _payload(self, model: str, messages: list[dict], think: bool | None) -> dict:
        p = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": {"num_ctx": self.num_ctx, "temperature": self.temperature},
        }
        if think is not None:
            p["think"] = think
        return p

    def warmup(self, model: str) -> None:
        """Load the model into memory now, so the first question is fast."""
        for _ in self.stream(model, [{"role": "user", "content": "Hallo"}], max_tokens=1):
            pass

    def stream(self, model: str, messages: list[dict], stop: threading.Event | None = None,
               max_tokens: int | None = None) -> Iterator[str]:
        """Yield answer text piece by piece. Thinking is switched off (it only costs time)."""
        think: bool | None = False if self._think_supported.get(model, True) else None
        payload = self._payload(model, messages, think)
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        try:
            resp = self._request("/api/chat", payload)
        except OllamaError as e:
            if think is not None and "think" in str(e).lower():
                self._think_supported[model] = False
                payload.pop("think", None)
                resp = self._request("/api/chat", payload)
            else:
                raise
        with resp:
            for line in resp:
                if stop is not None and stop.is_set():
                    return
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)
                if msg.get("error"):
                    raise OllamaError(msg["error"])
                piece = msg.get("message", {}).get("content", "")
                if piece:
                    yield piece
                if msg.get("done"):
                    return
