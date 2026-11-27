"""The terminal interface (like Claude Code): status bar on top, conversation in the middle,
a live activity line with spinner, the input line with a blinking cursor, and shortcuts below.

    ┌──────────────────────────────────────────────────────────────────────┐
    │ 🤖 Jarvis · 🧠 gemma4:12b · 📚 ██░░ 1.734/8.192 · letzte: ⚡0,9 s · 412 Tok │  ← Statusleiste
    │                                                                      │
    │ Du › Wie steht's bei Barça?                                          │  ← Gespräch
    │    💬 Moment, ich schau kurz nach.                                    │
    │    🔎 Suche: FC Barcelona Champions League  ✓ 5 Treffer                │
    │ Jarvis › Barcelona führt 2:1 …                                       │
    │                                                                      │
    │ ⠹ sucht im Web … 1,2 s                                               │  ← Aktivität
    │ › █                                                                  │  ← Eingabe
    │ Enter senden · ^O Mikro · ^B Bild · Esc Stopp · /hilfe · ^C Ende      │  ← Kürzel
    └──────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import threading
import time

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.utils import get_cwidth

from .terminal import fmt_int

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
LEVEL = " ▁▂▃▄▅▆▇█"
MAX_LINES = 3000

STYLE = Style.from_dict({
    "topbar": "bg:#1b2a4a #e8eefc",
    "topbar.name": "bg:#1b2a4a #ffffff bold",
    "topbar.dim": "bg:#1b2a4a #8a94ad",
    "topbar.fast": "bg:#1b2a4a #3ee6a0 bold",
    "topbar.slow": "bg:#1b2a4a #ffcc66 bold",
    "du": "#5aa9ff bold",
    "er": "#e8eefc bold",
    "meta": "#8a94ad",
    "bruecke": "#8a94ad italic",
    "fehler": "#ff6b7a",
    "aktiv": "#a77bff",
    "aktiv.hoert": "#3ee6a0",
    "aktiv.spricht": "#38d6ff",
    "aktiv.sucht": "#ffcc66",
    "prompt": "#5aa9ff bold",
    "hints": "#8a94ad",
    "hints.key": "#e8eefc bold",
})

HELP = """Befehle:
  /hilfe          diese Hilfe
  /bild           Bild auswählen (oder Datei ins Fenster ziehen, oder Strg+B)
  /mikro          Mikrofon an/aus (oder Strg+O)
  /name NAME      Assistent umbenennen, z. B. /name Friday
  /stats          Zeit und Tokens der letzten Antworten
  /neu            Gespräch vergessen und neu anfangen
  /leeren         Bildschirm leeren (oder Strg+L)
  /ende           beenden (oder Strg+C)
Tasten: Enter senden · ↑/↓ frühere Eingaben · Esc Jarvis stoppen · Bild↑/Bild↓ blättern"""


def wrap(text: str, width: int, indent: int) -> list[str]:
    """Word wrap that knows emoji are two cells wide."""
    width = max(20, width)
    out, line, w = [], "", 0
    for word in text.split(" "):
        ww = get_cwidth(word)
        if line and w + 1 + ww > width:
            out.append(line)
            line, w = " " * indent + word, indent + ww
        else:
            line = f"{line} {word}" if line else word
            w = w + 1 + ww if w else ww
        while w > width:  # a single very long word
            out.append(line[:width])
            line = " " * indent + line[width:]
            w = get_cwidth(line)
    out.append(line)
    return out


class _LogLexer(Lexer):
    """Colors each line by its start."""

    def __init__(self, tui: "TerminalUI"):
        self.tui = tui

    def lex_document(self, document):
        lines = document.lines

        def get_line(i):
            line = lines[i]
            kind = self.tui.view_kinds.get(i, "")
            if kind == "du" and " › " in line:
                head, rest = line.split(" › ", 1)
                return [("class:du", head + " › "), ("", rest)]
            if kind == "er" and " › " in line:
                head, rest = line.split(" › ", 1)
                return [("class:er", head + " › "), ("", rest)]
            if kind and kind != "cont":
                return [(f"class:{kind}", line)]
            return [("", line)]

        return get_line


class TerminalUI:
    def __init__(self, conv, info: dict, save_name=None, history_file=None, stats_file=None):
        self.conv = conv
        self.info = info
        self.save_name = save_name
        self.stats_file = stats_file
        self.lines: list[str] = []
        self.kinds: dict[int, str] = {}
        self.view_kinds: dict[int, str] = {}  # kinds per wrapped screen line
        self._width = 0
        self.open_answer = False  # last line is an answer still being written
        self.activity = ""  # "denkt", "sucht", "hoert", "spricht", ""
        self.activity_label = ""
        self.activity_since = time.monotonic()
        self.level = 0.0
        self.context = (0, info.get("kontext_limit", 0))
        self.last = {}  # last answer stats
        self.follow = True  # keep the view at the bottom
        self.lock = threading.Lock()
        self.app: Application | None = None

        history = FileHistory(str(history_file)) if history_file else InMemoryHistory()
        self.input = Buffer(multiline=False, history=history, accept_handler=self._accept)
        self.log = Buffer(read_only=True)
        self.app = self._build()

    # -- layout -------------------------------------------------------------------------
    def _top(self):
        try:
            if self.app and self.app.output.get_size().columns != self._width:
                self._later(self._sync)
        except Exception:
            pass
        c = self.conv
        used, limit = self.context
        pct = 100 * used / limit if limit else 0
        bar = "█" * min(6, round(pct / 100 * 6)) + "░" * (6 - min(6, round(pct / 100 * 6)))
        parts = [("class:topbar.name", f" 🤖 {c.s.name} "),
                 ("class:topbar.dim", "· "), ("class:topbar", f"🧠 {self.info.get('modell', '')} "),
                 ("class:topbar.dim", "· "),
                 ("class:topbar", f"📚 {bar} {fmt_int(used)}/{fmt_int(limit)} ({pct:.0f} %) ")]
        if self.last:
            secs = self.last.get("sekunden", 0)
            style = "class:topbar.fast" if secs <= 1.2 else "class:topbar.slow"
            parts += [("class:topbar.dim", "· letzte: "),
                      (style, f"⚡{secs:.1f} s ".replace(".", ","))]
            if self.last.get("tokens_antwort"):
                parts.append(("class:topbar", f"· {fmt_int(self.last['tokens_antwort'])} Tokens "))
        mic = "🎙️ an" if c.listening and not self.info.get("nur_tippen") else "🔇 aus"
        parts += [("class:topbar.dim", "· "), ("class:topbar", f"{mic} ")]
        if c.attention.quiet:
            parts += [("class:topbar.dim", "· "), ("class:topbar", "🤫 Ruhemodus ")]
        return parts

    def _activity(self):
        now = time.monotonic()
        secs = now - self.activity_since
        spin = SPINNER[int(now * 10) % len(SPINNER)]
        a = self.activity
        if a == "denkt":
            return [("class:aktiv", f" {spin} denkt … {secs:.1f} s".replace(".", ","))]
        if a == "sucht":
            return [("class:aktiv.sucht", f" {spin} sucht im Web: {self.activity_label} … {secs:.1f} s".replace(".", ","))]
        if a == "bild":
            return [("class:aktiv", f" {spin} schaut sich das Bild an … {secs:.1f} s".replace(".", ","))]
        if a == "hoert":
            bars = "".join(LEVEL[min(8, int(self.level * 8 * (0.6 + 0.4 * ((i * 7) % 5) / 4)))] for i in range(12))
            return [("class:aktiv.hoert", f" ● hört zu  {bars}")]
        if a == "spricht":
            wave = "".join(LEVEL[int(4 + 3 * math.sin(now * 9 + i))] for i in range(8))
            return [("class:aktiv.spricht", f" 🔊 spricht {wave}   (Esc = stopp)")]
        if self.conv.attention.quiet:
            return [("class:meta", f" 🤫 still – sag „{self.conv.s.name}“, wenn du mich brauchst")]
        if self.conv.listening and not self.info.get("nur_tippen"):
            if self.conv.s.listen_mode == "name" and not self.conv.attention.in_window():
                return [("class:meta", f" ○ bereit – sag „{self.conv.s.name}, …“ oder tippe")]
            return [("class:meta", " ○ bereit – sprich einfach oder tippe")]
        return [("class:meta", " ○ bereit – tippe deine Nachricht")]

    def _hints(self):
        keys = [("Enter", "senden"), ("^O", "Mikro"), ("^B", "Bild"), ("Esc", "Stopp"),
                ("/hilfe", "Befehle"), ("^C", "Ende")]
        out = [("class:hints", " ")]
        for i, (k, v) in enumerate(keys):
            if i:
                out.append(("class:hints", "  ·  "))
            out += [("class:hints.key", k), ("class:hints", f" {v}")]
        return out

    def _build(self) -> Application:
        kb = KeyBindings()

        @kb.add("c-c")
        @kb.add("c-d", filter=Condition(lambda: not self.input.text))
        def _(event):
            self.conv.finished.set()
            event.app.exit()

        @kb.add("escape", eager=True)
        def _(event):
            if self.conv.assistant_busy:
                self.conv.interrupt()
                self.add("   ✋ gestoppt", "meta")
                self.set_activity("")
            else:
                self.input.reset()

        @kb.add("c-o")
        def _(event):
            self.toggle_mic()

        @kb.add("c-b")
        def _(event):
            self.pick_image()

        @kb.add("c-l")
        def _(event):
            self.clear()

        @kb.add("pageup")
        def _(event):
            self.follow = False
            doc = self.log.document
            row = max(0, doc.cursor_position_row - 15)
            self.log.cursor_position = doc.translate_row_col_to_index(row, 0)

        @kb.add("pagedown")
        def _(event):
            doc = self.log.document
            row = doc.cursor_position_row + 15
            if row >= doc.line_count - 1:
                self.follow = True
                self.log.cursor_position = len(doc.text)
            else:
                self.log.cursor_position = doc.translate_row_col_to_index(row, 0)

        log_window = Window(BufferControl(self.log, lexer=_LogLexer(self), focusable=False),
                            wrap_lines=True, always_hide_cursor=True)
        layout = HSplit([
            Window(FormattedTextControl(self._top), height=1, style="class:topbar"),
            log_window,
            Window(FormattedTextControl(self._activity), height=1),
            Window(BufferControl(self.input, input_processors=[BeforeInput("› ", style="class:prompt")]),
                   height=1, wrap_lines=False),
            Window(FormattedTextControl(self._hints), height=1, style="class:hints"),
        ])
        app = Application(layout=Layout(layout, focused_element=self.input), key_bindings=kb,
                          style=STYLE, full_screen=True, refresh_interval=0.1, mouse_support=False)
        app.ttimeoutlen = 0.05
        return app

    # -- log ----------------------------------------------------------------------------
    def _sync(self) -> None:
        try:
            self._width = self.app.output.get_size().columns if self.app else 100
        except Exception:
            self._width = 100
        view, kinds = [], {}
        for i, line in enumerate(self.lines):
            kind = self.kinds.get(i, "")
            indent = line.index(" › ") + 3 if kind in ("du", "er") and " › " in line else 3
            for j, part in enumerate(wrap(line, self._width - 1, indent)):
                kinds[len(view)] = kind if j == 0 or kind not in ("du", "er") else "cont"
                view.append(part)
        self.view_kinds = kinds
        text = "\n".join(view)
        pos = len(text) if self.follow else min(self.log.cursor_position, len(text))
        self.log.set_document(Document(text, pos), bypass_readonly=True)
        if self.app is not None:
            self.app.invalidate()

    def _later(self, fn, *args) -> None:
        """Run fn on the UI thread (events come from worker threads)."""
        app = self.app
        loop = getattr(app, "loop", None) if app else None
        if loop is not None and app.is_running:
            loop.call_soon_threadsafe(fn, *args)
        else:
            fn(*args)

    def add(self, line: str, kind: str = "") -> None:
        def do():
            with self.lock:
                if self.open_answer:
                    self.open_answer = False
                for part in line.split("\n"):
                    self.lines.append(part)
                    if kind:
                        self.kinds[len(self.lines) - 1] = kind
                self._trim()
                self._sync()
        self._later(do)

    def append_answer(self, text: str) -> None:
        def do():
            with self.lock:
                if not self.open_answer:
                    self.lines.append(f"{self.conv.s.name} › ")
                    self.kinds[len(self.lines) - 1] = "er"
                    self.open_answer = True
                parts = text.split("\n")
                self.lines[-1] += parts[0]
                for extra in parts[1:]:
                    self.lines.append("   " + extra)
                self._sync()
        self._later(do)

    def _trim(self) -> None:
        if len(self.lines) > MAX_LINES:
            cut = len(self.lines) - MAX_LINES
            self.lines = self.lines[cut:]
            self.kinds = {i - cut: k for i, k in self.kinds.items() if i >= cut}

    def clear(self) -> None:
        with self.lock:
            self.lines, self.kinds, self.open_answer = [], {}, False
            self._sync()

    def set_activity(self, what: str, label: str = "") -> None:
        if what != self.activity or label != self.activity_label:
            self.activity_since = time.monotonic()
        self.activity, self.activity_label = what, label
        if self.app is not None:
            self.app.invalidate()

    # -- events from the conversation -----------------------------------------------------
    def on_event(self, ev: dict) -> None:
        t = ev.get("typ")
        if t == "pegel":
            self.level = float(ev.get("wert", 0))
            return
        if t == "status":
            st = ev["status"]
            if st == "bereit":
                self.set_activity("")
            elif st == "denkt" and self.activity in ("sucht", "bild"):
                pass
            else:
                self.set_activity(st)
        elif t == "du":
            self.add("")
            self.add("Du › " + ev["text"], "du")
        elif t == "ignoriert":
            self.add(f"   💤 „{ev['text']}“ – {ev['grund']}", "meta")
        elif t == "bruecke":
            self.add(f"   💬 {ev['text']}", "bruecke")
        elif t == "suche":
            self.add(f"   🔎 Suche: {ev['text']}", "meta")
            self.set_activity("sucht", ev["text"][:50])
        elif t == "suche_fertig":
            n = ev.get("treffer", 0)
            self.add(f"   ✓ {n} Treffer gefunden" if n else "   ✗ keine Treffer", "meta")
            self.set_activity("denkt")
        elif t == "bild":
            self.add(f"   🖼️  Bild: {ev['pfad'].rsplit('/', 1)[-1]}", "meta")
            self.set_activity("bild")
        elif t == "antwort_start":
            if self.activity in ("denkt", "sucht", "bild"):
                self.set_activity("spricht")
            self.append_answer(ev.get("text", ""))
        elif t == "token":
            self.append_answer(ev["text"])
        elif t == "antwort_ende":
            self._later(lambda: setattr(self, "open_answer", False))
        elif t == "unterbrochen":
            self.add("   ✋ unterbrochen – ich höre zu", "meta")
        elif t == "vorschlag":
            self.add("")
            self.add(f"{self.conv.s.name} › 💡 {ev['text']}", "er")
        elif t == "fehler":
            self.add(f"   ⚠️  {ev['text']}", "fehler")
        elif t == "kontext":
            self.context = (ev["benutzt"], ev["limit"] or self.context[1])
        elif t == "statistik":
            self.last = ev
            if self.stats_file:
                try:
                    with open(self.stats_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps({k: v for k, v in ev.items() if k not in ("typ", "zeit")},
                                           ensure_ascii=False) + "\n")
                except OSError:
                    pass
        elif t == "mikro":
            pass
        if self.app is not None:
            self.app.invalidate()

    # -- actions ------------------------------------------------------------------------
    def toggle_mic(self) -> None:
        if self.info.get("nur_tippen"):
            self.add("   🎙️ Mikro ist aus (gestartet mit --tippen)", "meta")
            return
        self.conv.listening = not self.conv.listening
        if not self.conv.listening:
            self.conv.detector.reset()
        self.conv.emit("mikro", an=self.conv.listening)
        self.add("   🎙️ Mikro an" if self.conv.listening else "   🔇 Mikro aus – tippen geht weiter", "meta")

    def pick_image(self) -> None:
        if sys.platform != "darwin" or not shutil.which("osascript"):
            self.add("   🖼️  Zieh ein Bild ins Fenster oder tippe den Pfad, dann Enter.", "meta")
            return

        def work():
            r = subprocess.run(["osascript", "-e", 'POSIX path of (choose file of type {"public.image"} '
                                'with prompt "Bild für Jarvis auswählen")'], capture_output=True, text=True)
            path = r.stdout.strip()
            if path:
                def put():
                    self.input.insert_text(f"'{path}' ")
                    self.app.invalidate()
                self._later(put)

        threading.Thread(target=work, daemon=True).start()

    def _accept(self, buf: Buffer) -> bool:
        text = buf.text.strip()
        if not text:
            return False
        self.follow = True
        if text.startswith("/"):
            self.command(text)
        else:
            self.conv.handle_text(text)
        return False  # clear the line (history is kept)

    def command(self, text: str) -> None:
        cmd, _, arg = text.partition(" ")
        cmd = cmd.lower()
        if cmd in ("/hilfe", "/help", "/?"):
            self.add(HELP, "meta")
        elif cmd == "/bild":
            self.pick_image()
        elif cmd == "/mikro":
            self.toggle_mic()
        elif cmd == "/name":
            new = arg.strip()
            if not new:
                self.add("   So geht's: /name Friday", "meta")
                return
            self.conv.s.name = new
            self.conv.attention.name = new
            if getattr(self.conv, "router", None) is not None:
                self.conv.router.name = new
            if self.save_name:
                self.save_name(new)
            self.add(f"   ✔ Ich heiße jetzt {new}.", "meta")
        elif cmd == "/stats":
            rows = self.conv.stats[-10:]
            if not rows:
                self.add("   Noch keine Antworten.", "meta")
                return
            lines = ["   Uhrzeit   erster Ton  Tokens (Frage/Antwort)  Brücke / Suche"]
            for r in rows:
                extra = " · ".join(x for x in (r.get("bruecke"), "🔎" if r.get("websuche") else "") if x)
                lines.append(f"   {r['uhrzeit']}  {str(r['sekunden']).replace('.', ','):>6} s   "
                             f"{fmt_int(r['tokens_frage']):>6} / {fmt_int(r['tokens_antwort']):<6}       {extra}")
            avg = sum(r["sekunden"] for r in rows) / len(rows)
            lines.append(f"   Schnitt: {avg:.2f} s bis zum ersten Ton".replace(".", ","))
            self.add("\n".join(lines), "meta")
        elif cmd == "/neu":
            self.conv.interrupt()
            self.conv.history.clear()
            self.context = (0, self.context[1])
            self.clear()
            self.add("   ✨ Neues Gespräch.", "meta")
        elif cmd in ("/leeren", "/clear"):
            self.clear()
        elif cmd in ("/ende", "/exit", "/quit"):
            self.conv.finished.set()
            self.app.exit()
        else:
            self.add(f"   Unbekannter Befehl {cmd}. Tippe /hilfe.", "meta")

    def run(self) -> None:
        name = self.conv.s.name
        self.add(f"✨ {name} ist bereit. Sprich los oder tippe. /hilfe zeigt alle Befehle.", "meta")
        if self.conv.s.listen_mode == "name" and not self.info.get("nur_tippen"):
            self.add(f"   Sag „{name}, …“, damit ich weiß, dass du mich meinst. Getipptes geht immer.", "meta")

        def watch():
            self.conv.finished.wait()
            time.sleep(0.3)
            self._later(lambda: self.app.exit() if self.app.is_running else None)

        threading.Thread(target=watch, daemon=True).start()
        self.app.run()
