#!/bin/bash
# =============================================================================
#  Jarvis on Nod – Freihand-Sprechmodus (EXPERIMENTELL)
#
#  Was macht dieses Skript?
#    Es richtet einen Sprechmodus ein, mit dem du frei mit Jarvis redest:
#    Er hört dauerhaft zu, antwortet mit Stimme, und du kannst ihn
#    unterbrechen. Das Gehirn ist dasselbe Ollama-Modell wie in Nod.
#
#    Dafür nutzt es das Open-Source-Projekt "speech-to-speech" von
#    Hugging Face (Apache 2.0): https://github.com/huggingface/speech-to-speech
#      Ohr:    Silero VAD + Parakeet TDT (versteht Deutsch)
#      Gehirn: dein Ollama-Modell (z. B. qwen3.6:35b)
#      Mund:   Qwen3-TTS (spricht Deutsch)
#
#  WICHTIG: Der Sprechmodus hat KEINE Nod-Werkzeuge (keine E-Mails,
#  keine Websuche, keine Termine). Er ist zum Reden und Nachdenken da.
#  Große Aufgaben gibst du weiter an Nod.
#
#  So startest du es (im Programm "Terminal"):
#    curl -fsSL https://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-sprechen.sh | bash
#
#  Optionen:
#    --check          nur prüfen, nichts verändern
#    --start          Sprechmodus direkt starten (nach der Einrichtung)
#    --model NAME     ein bestimmtes Ollama-Modell nehmen
#    --lautsprecher   ohne Kopfhörer: Mikrofon ist stumm, solange Jarvis
#                     spricht (dann kannst du ihn nicht unterbrechen)
#    --yes            alle Fragen mit "Ja" beantworten
# =============================================================================

set -u

# ----- Einstellungen ---------------------------------------------------------
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
HOME_DIR="${JARVIS_SPRECHEN_DIR:-$HOME/.jarvis-sprechen}"
S2S_VERSION="1.1.0"          # genau diese Version wurde geprüft
PYTHON_VERSION="3.12"
PREFERRED_MODELS="qwen3.6:35b gpt-oss:20b qwen3.6:27b"
UV_INSTALLER="https://astral.sh/uv/install.sh"

MODE="install"
FORCED_MODEL=""
SPEAKERS=0
ASSUME_YES="${JARVIS_YES:-0}"
TEST_MODE="${JARVIS_TEST_MODE:-0}"   # nur für automatische Tests

while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE="check" ;;
    --start) MODE="start" ;;
    --model) shift; FORCED_MODEL="${1:-}" ;;
    --lautsprecher|--speakers) SPEAKERS=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --help|-h)
      sed -n '2,31p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) printf 'Unbekannte Option: %s\n' "$1"; exit 2 ;;
  esac
  shift
done

# ----- Hübsche Ausgabe -------------------------------------------------------
if [ -t 1 ]; then
  B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; C=$'\033[36m'; N=$'\033[0m'
else
  B=""; G=""; Y=""; R=""; C=""; N=""
fi
step()  { printf '\n%s%s▶ %s%s\n' "$B" "$C" "$1" "$N"; }
ok()    { printf '  %s✔%s %s\n' "$G" "$N" "$1"; }
warn()  { printf '  %s!%s %s\n' "$Y" "$N" "$1"; }
bad()   { printf '  %s✘%s %s\n' "$R" "$N" "$1"; }
info()  { printf '    %s\n' "$1"; }
PROBLEMS=0

ask_yes() {
  if [ "$ASSUME_YES" = "1" ]; then return 0; fi
  local answer=""
  if [ -r /dev/tty ]; then
    printf '  %s?%s %s [J/n] ' "$Y" "$N" "$1" >/dev/tty
    read -r answer </dev/tty || answer=""
  fi
  case "$answer" in n|N|nein|Nein|no|No) return 1 ;; *) return 0 ;; esac
}

printf '\n%s──────────────────────────────────────────────%s\n' "$B" "$N"
printf '%s   Jarvis on Nod – Freihand-Sprechmodus%s\n' "$B" "$N"
printf '%s   (experimentell)%s\n' "$B" "$N"
printf '%s──────────────────────────────────────────────%s\n' "$B" "$N"
[ "$MODE" = "check" ] && info "Modus: nur prüfen (es wird nichts verändert)"

# ----- Start ohne Einrichtung ------------------------------------------------
if [ "$MODE" = "start" ]; then
  if [ -x "$HOME_DIR/jarvis-sprechen" ]; then
    exec "$HOME_DIR/jarvis-sprechen"
  fi
  bad "Der Sprechmodus ist noch nicht eingerichtet. Starte das Skript ohne --start."
  exit 1
fi

# ----- 1. Mac prüfen ---------------------------------------------------------
step "Schritt 1: Deinen Mac anschauen"
if [ "$TEST_MODE" = "1" ]; then
  OS="Darwin"; ARCH="arm64"
  RAM_BYTES="${JARVIS_TEST_RAM_BYTES:-68719476736}"
else
  OS="$(uname -s)"; ARCH="$(uname -m)"
  RAM_BYTES="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
fi
if [ "$OS" != "Darwin" ] || [ "$ARCH" != "arm64" ]; then
  bad "Der Sprechmodus braucht einen Mac mit Apple-Chip (M1–M5)."
  exit 1
fi
RAM_GB=$(( RAM_BYTES / 1073741824 ))
ok "Mac mit Apple-Chip, ${RAM_GB} GB RAM"
if [ "$RAM_GB" -lt 32 ]; then
  bad "Ohr und Mund brauchen zusätzlich ca. 8 GB. Mit ${RAM_GB} GB wird das zu eng."
  exit 1
elif [ "$RAM_GB" -lt 48 ]; then
  warn "${RAM_GB} GB sind knapp. Schließe große Programme, während du sprichst."
fi

# ----- 2. Ollama und Modell --------------------------------------------------
step "Schritt 2: Das Gehirn (Ollama) prüfen"
server_up() { curl -fsS --max-time 3 "$OLLAMA_URL/api/version" >/dev/null 2>&1; }
TAGS=""
if server_up; then
  ok "Ollama läuft auf $OLLAMA_URL"
  TAGS="$(curl -fsS --max-time 5 "$OLLAMA_URL/api/tags" 2>/dev/null || true)"
else
  bad "Ollama antwortet nicht. Starte zuerst die Ollama-App (Lama-Symbol 🦙)."
  info "Noch gar nicht eingerichtet? Dann zuerst: scripts/jarvis-mac.sh"
  exit 1
fi
model_present() { printf '%s' "$TAGS" | grep -Eq "\"name\": *\"$1\""; }

MODEL=""
if [ -n "$FORCED_MODEL" ]; then
  if model_present "$FORCED_MODEL"; then MODEL="$FORCED_MODEL"
  else bad "$FORCED_MODEL ist nicht in Ollama. Lade es mit: ollama pull $FORCED_MODEL"; exit 1; fi
else
  for m in $PREFERRED_MODELS; do
    if model_present "$m"; then MODEL="$m"; break; fi
  done
fi
if [ -z "$MODEL" ]; then
  bad "Ich finde keins der empfohlenen Modelle ($PREFERRED_MODELS)."
  info "Lade eins mit: ollama pull qwen3.6:35b"
  exit 1
fi
ok "Gehirn für den Sprechmodus: $MODEL"
case "$MODEL" in
  qwen3.6:27b) warn "Das Programmier-Modell ist langsam fürs Reden. Besser: qwen3.6:35b" ;;
esac

# ----- 3. uv (Python-Helfer) -------------------------------------------------
step "Schritt 3: Den Python-Helfer 'uv' prüfen"
UV=""
for c in uv "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv; do
  if command -v "$c" >/dev/null 2>&1; then UV="$(command -v "$c")"; break; fi
done
if [ -n "$UV" ]; then
  ok "uv ist da ($UV)"
elif [ "$MODE" = "check" ]; then
  bad "uv fehlt. Starte das Skript ohne --check, dann installiert es uv."
  PROBLEMS=$((PROBLEMS+1))
elif ask_yes "uv fehlt. Soll ich es installieren? (offizieller Installer von astral.sh, kein Admin-Passwort)"; then
  tmp="$(mktemp)"
  if curl -q --proto '=https' --tlsv1.2 -fsSL "$UV_INSTALLER" -o "$tmp" && sh "$tmp" >/dev/null 2>&1; then
    UV="$HOME/.local/bin/uv"
    ok "uv installiert."
  else
    bad "uv konnte nicht installiert werden. Anleitung: https://docs.astral.sh/uv/"
    rm -f "$tmp"; exit 1
  fi
  rm -f "$tmp"
else
  bad "Ohne uv geht es nicht weiter."; exit 1
fi

# ----- 4. speech-to-speech installieren -------------------------------------
step "Schritt 4: Ohr und Mund installieren (speech-to-speech $S2S_VERSION)"
VENV="$HOME_DIR/venv"
S2S="$VENV/bin/speech-to-speech"
installed_version() { "$VENV/bin/python" -c 'import importlib.metadata as m; print(m.version("speech-to-speech"))' 2>/dev/null; }
if [ -x "$S2S" ] && [ "$(installed_version)" = "$S2S_VERSION" ]; then
  ok "speech-to-speech $S2S_VERSION ist schon installiert."
elif [ "$MODE" = "check" ]; then
  bad "speech-to-speech ist noch nicht installiert."
  PROBLEMS=$((PROBLEMS+1))
else
  info "Das lädt einige GB Programme. Die Sprach-Modelle (mehrere GB) kommen beim ersten Start."
  mkdir -p "$HOME_DIR"
  if "$UV" venv --quiet --python "$PYTHON_VERSION" "$VENV" \
     && "$UV" pip install --quiet --python "$VENV/bin/python" "speech-to-speech==$S2S_VERSION"; then
    ok "speech-to-speech $S2S_VERSION installiert in $VENV"
  else
    bad "Installation hat nicht geklappt. Prüfe dein Internet und starte das Skript neu."
    exit 1
  fi
fi

# ----- 5. Startbefehl schreiben ---------------------------------------------
step "Schritt 5: Startbefehl anlegen"
LAUNCHER="$HOME_DIR/jarvis-sprechen"
PROMPT='Du bist Jarvis, ein freundlicher persönlicher Assistent. Du sprichst mit deinem Besitzer über ein Mikrofon. Antworte immer auf Deutsch, in ein bis drei kurzen Sätzen. Benutze keine Listen, keine Emojis und kein Markdown, denn deine Antwort wird vorgelesen. Du hast in diesem Sprechmodus keine Werkzeuge: Du kannst keine E-Mails schreiben, nicht im Internet suchen und keine Termine eintragen. Wenn jemand so etwas möchte, sag ehrlich, dass er das in der Nod-App schreiben oder als Sprachnachricht schicken soll.'
MIC_FLAG=""
[ "$SPEAKERS" = "1" ] && MIC_FLAG="--local_audio_block_mic_during_playback true"

if [ "$MODE" = "check" ]; then
  if [ -x "$LAUNCHER" ]; then ok "Startbefehl ist da: $LAUNCHER"; else bad "Startbefehl fehlt."; PROBLEMS=$((PROBLEMS+1)); fi
else
  cat > "$LAUNCHER" <<EOF
#!/bin/bash
# Von jarvis-sprechen.sh erzeugt. Zum Beenden: Ctrl + C
echo ""
echo "  🎙️  Jarvis hört zu. Sprich einfach los."
echo "  Beenden: Ctrl + C   ·   Beim ersten Start werden mehrere GB geladen."
echo ""
exec "$S2S" local \\
  --llm_backend chat-completions \\
  --responses_api_base_url "$OLLAMA_URL/v1" \\
  --responses_api_api_key ollama \\
  --responses_api_reasoning_effort none \\
  --model_name "$MODEL" \\
  --qwen3_tts_language german \\
  --enable_lang_prompt true \\
  --init_chat_prompt "$PROMPT" $MIC_FLAG "\$@"
EOF
  chmod +x "$LAUNCHER"
  ok "Startbefehl angelegt: $LAUNCHER"
  DESKTOP_FILE="$HOME/Desktop/Jarvis sprechen.command"
  if [ -d "$HOME/Desktop" ] && [ ! -e "$DESKTOP_FILE" ] && ask_yes "Soll ich ein Symbol 'Jarvis sprechen' auf den Schreibtisch legen?"; then
    printf '#!/bin/bash\nexec "%s"\n' "$LAUNCHER" > "$DESKTOP_FILE"
    chmod +x "$DESKTOP_FILE"
    ok "Schreibtisch-Symbol angelegt. Doppelklick startet den Sprechmodus."
  fi
fi

# ----- Fertig ----------------------------------------------------------------
printf '\n%s──────────────────────────────────────────────%s\n' "$B" "$N"
if [ "$PROBLEMS" -eq 0 ]; then
  printf '  %s%s✔ Sprechmodus bereit!%s\n' "$B" "$G" "$N"
else
  printf '  %s%s! Bitte %s Punkt(e) oben ansehen.%s\n' "$B" "$Y" "$PROBLEMS" "$N"
fi
printf '%s──────────────────────────────────────────────%s\n' "$B" "$N"
cat <<EOF

  Starten:   ${B}$LAUNCHER${N}
             (oder Doppelklick auf "Jarvis sprechen" auf dem Schreibtisch)
  Beenden:   Ctrl + C

  Tipps:
    • Nimm Kopfhörer. Dann kannst du Jarvis mitten im Satz unterbrechen.
    • Beim ersten Start fragt der Mac nach dem Mikrofon: "Erlauben".
    • Der Sprechmodus hat keine Nod-Werkzeuge. Für E-Mails, Suche und
      Termine sprich in Nod mit ⌘ + D oder schick eine Sprachnachricht.

EOF
[ "$PROBLEMS" -eq 0 ] || exit 3
if [ "$MODE" = "install" ] && [ "$TEST_MODE" != "1" ] && ask_yes "Soll ich den Sprechmodus jetzt starten?"; then
  exec "$LAUNCHER"
fi
exit 0
