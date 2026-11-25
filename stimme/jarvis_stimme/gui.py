"""A small window for Jarvis: runs in your browser, served from your own computer.

Nothing goes to the internet – the page talks only to http://127.0.0.1.
The microphone and speaker stay in Python (fast path); the page shows what happens,
lets you type, drop or paste pictures, and switch the microphone on and off.
"""

from __future__ import annotations

import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

from .tts import APP_HOME

UPLOAD_DIR = APP_HOME / "bilder"
MAX_UPLOAD = 30_000_000
_ALLOWED = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif", ".bmp", ".tif", ".tiff")


class Hub:
    """Fans out events from the conversation to all open pages (Server-Sent Events)."""

    def __init__(self, keep: int = 200):
        self.clients: list[queue.Queue] = []
        self.lock = threading.Lock()
        self.backlog: list[dict] = []
        self.keep = keep
        self.state: dict = {}

    def publish(self, event: dict) -> None:
        event.setdefault("zeit", time.time())
        with self.lock:
            if event["typ"] != "pegel":
                self.backlog = (self.backlog + [event])[-self.keep:]
            for q in list(self.clients):
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self.lock:
            for e in self.backlog:
                q.put_nowait(e)
            self.clients.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)


def _safe_name(name: str) -> str:
    name = Path(name or "bild.jpg").name
    stem = re.sub(r"[^\w.-]", "_", Path(name).stem)[:60] or "bild"
    ext = Path(name).suffix.lower()
    if ext not in _ALLOWED:
        ext = ".jpg"
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{stem}{ext}"


def make_handler(conv, hub: Hub, info: dict):
    page = resources.files("jarvis_stimme").joinpath("gui.html").read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        server_version = "JarvisStimme"

        def log_message(self, *args):
            pass

        def _json(self, data, code=200):
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _local_only(self) -> bool:
            # Block other websites from talking to Jarvis (simple CSRF guard).
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            if origin and not re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origin):
                self._json({"fehler": "nicht erlaubt"}, 403)
                return False
            if not re.match(r"^(127\.0\.0\.1|localhost)(:\d+)?$", host):
                self._json({"fehler": "nicht erlaubt"}, 403)
                return False
            return True

        def do_GET(self):
            if not self._local_only():
                return
            if self.path in ("/", "/index.html"):
                body = page.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/info":
                self._json({**info, "mikro": conv.listening, "name": conv.s.name})
            elif self.path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                q = hub.subscribe()
                try:
                    while True:
                        try:
                            ev = q.get(timeout=15)
                            data = f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                        except queue.Empty:
                            data = ": ping\n\n"
                        self.wfile.write(data.encode())
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    hub.unsubscribe(q)
            else:
                self._json({"fehler": "gibt es nicht"}, 404)

        def _body(self) -> bytes:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_UPLOAD:
                raise ValueError("Datei zu groß (max. 30 MB)")
            return self.rfile.read(n) if n else b""

        def do_POST(self):
            if not self._local_only():
                return
            try:
                if self.path == "/text":
                    data = json.loads(self._body() or b"{}")
                    text = str(data.get("text", "")).strip()
                    paths = [str(p) for p in data.get("bilder", []) if str(p).startswith(str(UPLOAD_DIR))]
                    if paths:
                        text = " ".join(f"'{p}'" for p in paths) + " " + (text or "Was ist auf dem Bild?")
                    if text:
                        conv.handle_text(text)
                    self._json({"ok": True})
                elif self.path == "/bild":
                    body = self._body()
                    if not body:
                        raise ValueError("Leere Datei")
                    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
                    raw_name = urllib.parse.unquote(self.headers.get("X-Dateiname", "bild.jpg"))
                    dst = UPLOAD_DIR / _safe_name(raw_name)
                    dst.write_bytes(body)
                    self._json({"ok": True, "pfad": str(dst)})
                elif self.path == "/mikro":
                    data = json.loads(self._body() or b"{}")
                    conv.listening = bool(data.get("an", not conv.listening))
                    if not conv.listening:
                        conv.detector.reset()
                    hub.publish({"typ": "mikro", "an": conv.listening})
                    self._json({"ok": True, "mikro": conv.listening})
                elif self.path == "/stopp":
                    conv.interrupt()
                    hub.publish({"typ": "status", "status": "bereit"})
                    self._json({"ok": True})
                else:
                    self._json({"fehler": "gibt es nicht"}, 404)
            except (ValueError, json.JSONDecodeError) as e:
                self._json({"fehler": str(e)}, 400)

    return Handler


def open_window(url: str) -> None:
    """Open the page like an app window (Chrome/Edge 'app mode'), else the normal browser."""
    if sys.platform == "darwin":
        for app in ("Google Chrome", "Microsoft Edge", "Brave Browser", "Chromium"):
            if subprocess.run(["open", "-Ra", app], capture_output=True).returncode == 0:
                subprocess.Popen(["open", "-na", app, "--args", f"--app={url}", "--window-size=520,860"])
                return
    else:
        for exe in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
            if shutil.which(exe):
                subprocess.Popen([exe, f"--app={url}", "--window-size=520,860"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    webbrowser.open(url)


def serve(conv, info: dict, port: int = 8765, open_browser: bool = True) -> tuple[ThreadingHTTPServer, Hub]:
    hub = Hub()
    previous = conv.on_event

    def on_event(ev: dict) -> None:
        hub.publish(ev)
        if previous:
            previous(ev)

    conv.on_event = on_event
    server = None
    for p in range(port, port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), make_handler(conv, hub, info))
            break
        except OSError:
            continue
    if server is None:
        raise OSError("Kein freier Port gefunden")
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"🪟 Fenster: {url}")
    if open_browser:
        open_window(url)
    return server, hub
