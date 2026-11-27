import io
import os
import pty
import sys
import time

from jarvis_stimme.terminal import StatusLine, context_text


def _run_in_pty(code: str, keys: bytes) -> str:
    pid, fd = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-c", code])
    time.sleep(0.6)
    os.write(fd, keys)
    out = b""
    end = time.time() + 5
    while time.time() < end:
        try:
            data = os.read(fd, 4096)
        except OSError:
            break
        if not data:
            break
        out += data
        if b"GEWAEHLT" in out and out.rstrip().endswith(b"ENDE"):
            break
    os.waitpid(pid, 0)
    return out.decode(errors="replace")


CODE = ("import sys; sys.path.insert(0, %r); from jarvis_stimme.terminal import choose_name; "
        "print('GEWAEHLT=' + choose_name()); print('ENDE')") % os.path.dirname(os.path.dirname(__file__))


def test_arrow_menu_picks_friday():
    out = _run_in_pty(CODE, b"\x1b[B\r")
    assert "GEWAEHLT=Friday" in out
    assert "Jarvis" in out and "Ultron" in out and "HAL" in out and "Eigenen Namen" in out


def test_arrow_menu_own_name():
    out = _run_in_pty(CODE, b"5" + b"Athena\r")
    assert "GEWAEHLT=Athena" in out


def test_context_text_and_statusline():
    t = context_text(1234, 8192)
    assert "1.234 / 8.192 Tokens (15 %)" in t and "█" in t
    buf = io.StringIO()
    s = StatusLine(out=buf)
    s.enabled = True
    s.set(name="🤖 Jarvis", kontext=t)
    out = buf.getvalue()
    assert "\x1b[1;1H" in out and "1.234 / 8.192" in out
    s.stop()
    assert buf.getvalue().endswith("\x1b[r")
