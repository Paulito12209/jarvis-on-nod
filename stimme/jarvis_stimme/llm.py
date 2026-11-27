"""Talk to a local Ollama server with token streaming (only the Python standard library)."""

from __future__ import annotations

import json
import re
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
        self._tools_supported: dict[str, bool] = {}
        self._caps: dict[str, list[str]] = {}

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

    def _payload(self, model: str, messages: list[dict], think: bool | None, stream: bool = True) -> dict:
        p = {
            "model": model,
            "messages": messages,
            "stream": stream,
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

    def _post_chat(self, model: str, payload: dict):
        """POST /api/chat; if the model refuses 'think' or 'tools', retry without it."""
        for _ in range(3):
            try:
                return self._request("/api/chat", payload)
            except OllamaError as e:
                err = str(e).lower()
                if "think" in payload and "think" in err:
                    self._think_supported[model] = False
                    payload.pop("think")
                elif "tools" in payload and "tool" in err:
                    self._tools_supported[model] = False
                    payload.pop("tools")
                else:
                    raise
        return self._request("/api/chat", payload)

    def capabilities(self, model: str) -> list[str]:
        """What a model can do, e.g. ["completion", "tools", "vision", "thinking"]."""
        if model not in self._caps:
            try:
                with self._request("/api/show", {"model": model}, timeout=10) as r:
                    self._caps[model] = list(json.load(r).get("capabilities") or [])
            except (OllamaError, ValueError, OSError):
                self._caps[model] = []
        return self._caps[model]

    def supports_tools(self, model: str) -> bool:
        if model in self._tools_supported:
            return self._tools_supported[model]
        caps = self.capabilities(model)
        return "tools" in caps if caps else True

    def stream(self, model: str, messages: list[dict], stop: threading.Event | None = None,
               max_tokens: int | None = None, tools: list[dict] | None = None,
               usage: dict | None = None) -> Iterator[str | ToolCalls]:
        """Yield answer text piece by piece (or a ToolCalls object if the model wants a tool).
        Thinking is switched off – it only costs time when talking."""
        think: bool | None = False if self._think_supported.get(model, True) else None
        payload = self._payload(model, messages, think)
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if tools and self.supports_tools(model):
            payload["tools"] = tools
        resp = self._post_chat(model, payload)
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
                m = msg.get("message", {})
                if m.get("tool_calls"):
                    yield ToolCalls(m["tool_calls"])
                piece = m.get("content", "")
                if piece:
                    yield piece
                if msg.get("done"):
                    if usage is not None:
                        usage["prompt"] = int(msg.get("prompt_eval_count") or 0)
                        usage["antwort"] = int(msg.get("eval_count") or 0)
                    return

    def complete(self, model: str, messages: list[dict], format: dict | str | None = None,
                 max_tokens: int | None = None) -> str:
        """One answer in one go (for small helper jobs like the router)."""
        think: bool | None = False if self._think_supported.get(model, True) else None
        payload = self._payload(model, messages, think, stream=False)
        payload["options"]["temperature"] = 0.0
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if format is not None:
            payload["format"] = format
        with self._post_chat(model, payload) as r:
            return json.load(r).get("message", {}).get("content", "")


class ToolCalls(list):
    """The model asked to use one or more tools: [{"function": {"name": ..., "arguments": {...}}}]."""


SMALL_PREFERENCE = ["qwen3.5:2b", "qwen3:1.7b", "qwen3.5:0.8b", "gemma4:1b", "gemma3:1b",
                    "llama3.2:1b", "qwen3.5:4b", "qwen3:4b", "gemma4:4b", "llama3.2:3b", "gemma3:4b"]


def pick_small_model(installed: list[str]) -> str | None:
    """A tiny model (<= 4B) for quick decisions, or None if there is none."""
    for pref in SMALL_PREFERENCE:
        for name in installed:
            if name == pref or name.startswith(pref):
                return name
    sized = []
    for name in installed:
        m = re.search(r":(\d+(?:\.\d+)?)b\b", name)
        if m and float(m.group(1)) <= 4 and not any(w in name for w in _SKIP_WORDS):
            sized.append((float(m.group(1)), name))
    return min(sized)[1] if sized else None
