#!/bin/bash
# =============================================================================
#  Jarvis Stimme – schneller Sprachassistent auf Deutsch, komplett lokal
#
#  Was macht dieses Skript?
#    1. Es prüft, ob Ollama läuft (das "Gehirn"), und startet es notfalls.
#    2. Es installiert beim ersten Mal alles Nötige in ~/.jarvis-stimme
#       (dein restlicher Computer bleibt unberührt).
#    3. Es sucht die deutsche Stimme "Thorsten" und lädt sie sonst herunter.
#    4. Es startet Jarvis Stimme. Dann einfach losreden!
#
#  So startest du es (im Programm "Terminal"):
#    bash <(curl -fsSL https://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-stimme.sh)
#  oder im Repo-Ordner:
#    ./scripts/jarvis-stimme.sh
#
#  Nützliche Extras (einfach hinten anhängen):
#    --test                 alles einmal durchmessen
#    --modell gemma4:12b    ein bestimmtes Modell nehmen
#    --pause 0.4            schneller "fertig" erkennen (Standard 0.6 Sekunden)
#    --ohne-unterbrechen    wenn Jarvis sich über die Lautsprecher selbst unterbricht
#    --tippen               tippen statt sprechen
#    --geraete              Mikrofone und Lautsprecher anzeigen
#    --hilfe                alle Optionen
# =============================================================================

set -u

HOME_DIR="${JARVIS_STIMME_HOME:-$HOME/.jarvis-stimme}"
VENV="$HOME_DIR/venv"
VOICE_DIR="$HOME_DIR/stimmen"
VOICE_NAME="${JARVIS_STIMME_VOICE:-de_DE-thorsten-high}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
REPO_URL="https://github.com/Paulito12209/jarvis-on-nod.git"
PY_VERSION="3.12"

if [ -t 1 ]; then
  B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; C=$'\033[36m'; N=$'\033[0m'
else
  B=""; G=""; Y=""; R=""; C=""; N=""
fi
step() { printf '%s%s▶ %s%s\n' "$B" "$C" "$1" "$N"; }
ok()   { printf '  %s✔%s %s\n' "$G" "$N" "$1"; }
warn() { printf '  %s!%s %s\n' "$Y" "$N" "$1"; }
bad()  { printf '  %s✘%s %s\n' "$R" "$N" "$1"; }

ARGS=()
for a in "$@"; do
  case "$a" in
    --hilfe|-h|--help) ARGS+=("--help") ;;
    *) ARGS+=("$a") ;;
  esac
done

# ----- Wo liegt der Code? ----------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/../stimme/pyproject.toml" ]; then
  APP_DIR="$(cd "$SCRIPT_DIR/../stimme" && pwd)"
else
  # Gestartet über curl: Repo nach ~/.jarvis-stimme/repo holen bzw. aktualisieren.
  step "Hole den aktuellen Code"
  mkdir -p "$HOME_DIR"
  if [ -d "$HOME_DIR/repo/.git" ]; then
    git -C "$HOME_DIR/repo" pull --ff-only -q || warn "Aktualisieren ging nicht, nehme die vorhandene Version."
  else
    git clone -q --depth 1 "$REPO_URL" "$HOME_DIR/repo" || { bad "Konnte $REPO_URL nicht laden."; exit 1; }
  fi
  APP_DIR="$HOME_DIR/repo/stimme"
  ok "Code liegt in $HOME_DIR/repo"
fi

# ----- 1) Computer prüfen ----------------------------------------------------
if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
  ok "Mac mit Apple-Chip – perfekt (Whisper läuft über MLX auf der Grafikeinheit)"
else
  warn "Kein Mac mit Apple-Chip. Es klappt trotzdem, nur das Hören ist etwas langsamer."
fi

# ----- 2) Ollama -------------------------------------------------------------
step "Prüfe Ollama (das Gehirn)"
ollama_up() { curl -fsS -m 2 "$OLLAMA_URL/api/tags" >/dev/null 2>&1; }
if ! ollama_up; then
  if [ "$(uname -s)" = "Darwin" ] && open -Ra Ollama 2>/dev/null; then
    open -a Ollama
    for _ in $(seq 1 30); do ollama_up && break; sleep 1; done
  elif command -v ollama >/dev/null 2>&1; then
    (ollama serve >/dev/null 2>&1 &)
    for _ in $(seq 1 30); do ollama_up && break; sleep 1; done
  fi
fi
if ollama_up; then
  ok "Ollama läuft"
else
  bad "Ollama läuft nicht. Installiere es von https://ollama.com und starte die App."
  exit 1
fi

# ----- 3) Programme installieren (nur beim ersten Mal oder nach Updates) ----
step "Prüfe die Programme"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  warn "Installiere 'uv' (ein schneller Python-Helfer) …"
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null || { bad "uv-Installation fehlgeschlagen"; exit 1; }
  export PATH="$HOME/.local/bin:$PATH"
fi
PY="$VENV/bin/python"
STAMP="$HOME_DIR/.installiert"
WANT="$( (shasum < "$APP_DIR/pyproject.toml" 2>/dev/null || cksum < "$APP_DIR/pyproject.toml") | cut -c1-16)"
if [ ! -x "$PY" ] || [ "$(cat "$STAMP" 2>/dev/null)" != "$WANT" ]; then
  warn "Installiere Jarvis Stimme (beim ersten Mal 1–3 Minuten) …"
  mkdir -p "$HOME_DIR"
  [ -x "$PY" ] || uv venv -q --python "$PY_VERSION" "$VENV" || { bad "Python-Umgebung ging nicht"; exit 1; }
  uv pip install -q --python "$PY" -e "$APP_DIR" || { bad "Installation fehlgeschlagen"; exit 1; }
  echo "$WANT" > "$STAMP"
fi
ok "Programme bereit"

# ----- 4) Deutsche Stimme ----------------------------------------------------
step "Prüfe die deutsche Stimme"
if JARVIS_WANT="${JARVIS_STIMME_VOICE:-thorsten}" "$PY" -c "
import os, sys
from jarvis_stimme.tts import find_voice
v = find_voice(os.environ['JARVIS_WANT'])
print(v or '')
sys.exit(0 if v else 1)" > "$HOME_DIR/.stimme" 2>/dev/null; then
  ok "Stimme gefunden: $(cat "$HOME_DIR/.stimme")"
else
  warn "Lade die Stimme $VOICE_NAME (ca. 110 MB) …"
  "$PY" -m piper.download_voices "$VOICE_NAME" --download-dir "$VOICE_DIR" >/dev/null 2>&1 \
    || { bad "Download der Stimme ging nicht. Internet an?"; exit 1; }
  ok "Stimme geladen"
fi

# ----- 5) Los geht's ---------------------------------------------------------
echo
printf '%sTipp:%s Beim allerersten Start lädt Whisper (die "Ohren", ca. 1,5 GB) einmal herunter.\n' "$B" "$N"
printf '      macOS fragt evtl. nach dem Mikrofon – bitte "Erlauben" klicken.\n'
cd "$APP_DIR" || exit 1
if [ -e /dev/tty ] && [ ! -t 0 ]; then
  exec "$PY" -m jarvis_stimme ${ARGS[@]+"${ARGS[@]}"} < /dev/tty
fi
exec "$PY" -m jarvis_stimme ${ARGS[@]+"${ARGS[@]}"}
