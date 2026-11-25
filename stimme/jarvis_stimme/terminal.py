"""Terminal helpers: an arrow-key menu and a fixed status line at the top."""

from __future__ import annotations

import os
import shutil
import signal
import sys
import threading

NAMES = [
    ("Jarvis", "der Klassiker aus Iron Man"),
    ("Friday", "Tony Starks Assistentin nach Jarvis"),
    ("Ultron", "etwas düsterer"),
    ("HAL", "aus 2001: Odyssee im Weltraum"),
]
OWN_NAME = "✏️  Eigenen Namen eingeben"


def _read_key(fd: int) -> str:
    ch = os.read(fd, 1)
    if ch == b"\x1b":
        seq = os.read(fd, 2)
        return {b"[A": "up", b"[B": "down", b"OA": "up", b"OB": "down"}.get(seq, "esc")
    if ch in (b"\r", b"\n"):
        return "enter"
    if ch == b"\x03":
        raise KeyboardInterrupt
    if ch in (b"k", b"w"):
        return "up"
    if ch in (b"j", b"s"):
        return "down"
    if ch.isdigit():
        return ch.decode()
    return ""


def choose(title: str, options: list[str], default: int = 0, out=sys.stdout) -> int:
    """Let the user pick with ↑/↓ and Enter (or a number). Falls back to typing a number."""
    if not (sys.stdin.isatty() and out.isatty()):
        for i, o in enumerate(options, 1):
            print(f"  {i}) {o}")
        ans = input(f"  {title} [{default + 1}] ").strip()
        return int(ans) - 1 if ans.isdigit() and 1 <= int(ans) <= len(options) else default

    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    idx = default

    def draw(first: bool = False):
        if not first:
            out.write(f"\x1b[{len(options)}A")
        for i, o in enumerate(options):
            mark = "\x1b[36m❯ \x1b[1m" if i == idx else "  \x1b[2m"
            out.write(f"\r\x1b[2K  {mark}{o}\x1b[0m\n")
        out.flush()

    out.write(f"  {title}  \x1b[2m(↑/↓ und Enter)\x1b[0m\n\x1b[?25l")
    draw(first=True)
    try:
        tty.setcbreak(fd)
        while True:
            key = _read_key(fd)
            if key == "up":
                idx = (idx - 1) % len(options)
            elif key == "down":
                idx = (idx + 1) % len(options)
            elif key.isdigit() and 1 <= int(key) <= len(options):
                idx = int(key) - 1
                draw()
                break
            elif key == "enter":
                break
            draw()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        out.write("\x1b[?25h")
        out.flush()
    return idx


def choose_name(current: str | None = None) -> str:
    labels = [f"{n:<8} \x1b[2m{d}\x1b[0m" if sys.stdout.isatty() else f"{n} – {d}" for n, d in NAMES] + [OWN_NAME]
    names = [n for n, _ in NAMES]
    default = names.index(current) if current in names else (len(names) if current else 0)
    i = choose("Wie soll dein Assistent heißen?", labels, default)
    if i < len(names):
        return names[i]
    own = input(f"  Name eingeben{f' [{current}]' if current else ''}: ").strip()
    return own or current or "Jarvis"


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


class StatusLine:
    """Keeps one line at the very top of the terminal; normal output scrolls below it.

    Uses a scroll region (DECSTBM), which works in macOS Terminal, iTerm2 and most Linux terminals.
    """

    def __init__(self, out=sys.stdout):
        self.out = out
        self.enabled = out.isatty() and os.environ.get("TERM", "") not in ("", "dumb")
        self.fields: dict[str, str] = {}
        self.order = ["name", "modell", "kontext", "mikro", "zeit", "zustand"]
        self.lock = threading.Lock()
        self._rows = 0

    def start(self) -> None:
        if not self.enabled:
            return
        self._setup()
        try:
            signal.signal(signal.SIGWINCH, lambda *_: self._setup())
        except (ValueError, AttributeError):
            pass  # not in main thread / not available

    def _setup(self) -> None:
        with self.lock:
            cols, rows = shutil.get_terminal_size((80, 24))
            self._rows = rows
            # Reserve line 1, let lines 2..rows scroll; then go to the bottom.
            self.out.write(f"\x1b[2;{rows}r\x1b[{rows};1H")
            self.out.flush()
        self.render()

    def set(self, **fields: str) -> None:
        for k, v in fields.items():
            if v is None:
                self.fields.pop(k, None)
            else:
                self.fields[k] = v
        self.render()

    def text(self) -> str:
        parts = [self.fields[k] for k in self.order if self.fields.get(k)]
        return "  ·  ".join(parts)

    def render(self) -> None:
        if not self.enabled:
            return
        with self.lock:
            cols = shutil.get_terminal_size((80, 24)).columns
            line = (" " + self.text())[: max(10, cols - 1)]
            # save cursor, jump to line 1, inverted bar, restore cursor
            self.out.write(f"\x1b7\x1b[1;1H\x1b[2K\x1b[7m{line.ljust(cols - 1)}\x1b[0m\x1b8")
            self.out.flush()

    def stop(self) -> None:
        if not self.enabled:
            return
        with self.lock:
            self.out.write("\x1b7\x1b[1;1H\x1b[2K\x1b8\x1b[r")
            self.out.flush()
        self.enabled = False


def context_text(used: int, limit: int) -> str:
    pct = 100 * used / limit if limit else 0
    bar_len = 10
    filled = min(bar_len, round(pct / 100 * bar_len))
    bar = "█" * filled + "░" * (bar_len - filled)
    return f"Kontext {bar} {fmt_int(used)} / {fmt_int(limit)} Tokens ({pct:.0f} %)"
