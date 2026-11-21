#!/bin/bash
# =============================================================================
#  Jarvis on Nod – Einrichtungs-Helfer für den Mac
#
#  Was macht dieses Skript?
#    1. Es schaut, wie viel Arbeitsspeicher (RAM) dein Mac hat.
#    2. Es sucht das passende KI-Modell für deinen Mac aus.
#    3. Es prüft, ob Ollama da ist (das "Gehirn"), und hilft beim Installieren.
#    4. Es stellt Ollama so ein, dass Nod genug "Notizblock" (Kontext) hat.
#    5. Es lädt das Modell herunter und testet, ob es Werkzeuge benutzen kann.
#    6. Es hilft dir, die Nod-App zu installieren.
#
#  So startest du es (im Programm "Terminal"):
#    curl -fsSL https://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-mac.sh | bash
#
#  Nur prüfen, ohne etwas zu ändern:
#    curl -fsSL https://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-mac.sh | bash -s -- --check
#
#  Ein bestimmtes Modell erzwingen:
#    ... | bash -s -- --model qwen3.6:27b
# =============================================================================

set -u

# ----- Einstellungen ---------------------------------------------------------
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
CONTEXT_LENGTH="${CONTEXT_LENGTH:-65536}"   # Nod braucht mindestens 64.000 Tokens
MODEL_FAST="qwen3.6:35b"     # Modell 1: schneller Allrounder (Recherche, Schreiben)
MODEL_CODER="qwen3.6:27b"    # Modell 2: gründlicher Bauer (Programmieren, Apps)
MODEL_SMALL="gpt-oss:20b"    # Notlösung für Macs mit 16–32 GB
NOD_INSTALLER="https://raw.githubusercontent.com/n8n-io/nod/main/deployment/n8n/install.sh"

MODE="install"
FORCED_MODEL=""
ASSUME_YES="${JARVIS_YES:-0}"
TEST_MODE="${JARVIS_TEST_MODE:-0}"   # nur für automatische Tests

while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE="check" ;;
    --model) shift; FORCED_MODEL="${1:-}" ;;
    --yes|-y) ASSUME_YES=1 ;;
    --help|-h)
      sed -n '2,22p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'
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

# Fragen funktionieren auch, wenn das Skript über "curl | bash" läuft.
ask_yes() {
  if [ "$ASSUME_YES" = "1" ]; then return 0; fi
  local answer=""
  if [ -r /dev/tty ]; then
    printf '  %s?%s %s [J/n] ' "$Y" "$N" "$1" >/dev/tty
    read -r answer </dev/tty || answer=""
  fi
  case "$answer" in n|N|nein|Nein|no|No) return 1 ;; *) return 0 ;; esac
}
wait_enter() {
  if [ "$ASSUME_YES" = "1" ] || [ ! -r /dev/tty ]; then return 0; fi
  printf '  %s↵%s %s ' "$Y" "$N" "$1" >/dev/tty
  read -r _ </dev/tty || true
}

printf '\n%s──────────────────────────────────────────────%s\n' "$B" "$N"
printf '%s   Jarvis on Nod – dein KI-Helfer, ganz lokal%s\n' "$B" "$N"
printf '%s──────────────────────────────────────────────%s\n' "$B" "$N"
[ "$MODE" = "check" ] && info "Modus: nur prüfen (es wird nichts verändert)"

# ----- 1. Ist das ein Mac? ---------------------------------------------------
step "Schritt 1: Deinen Computer anschauen"
if [ "$TEST_MODE" != "1" ] && [ "$(uname -s)" != "Darwin" ]; then
  bad "Dieses Skript ist für den Mac. Für Windows nimm scripts/jarvis-windows.ps1."
  exit 1
fi

if [ "$TEST_MODE" = "1" ]; then
  RAM_BYTES="${JARVIS_TEST_RAM_BYTES:-68719476736}"
  CHIP="Apple M5 Pro (Test)"
else
  RAM_BYTES="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
  CHIP="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo unbekannt)"
fi
RAM_GB=$(( RAM_BYTES / 1073741824 ))
ok "Chip: $CHIP"
ok "Arbeitsspeicher (RAM): ${RAM_GB} GB"

case "$CHIP" in
  *Apple*) : ;;
  *) warn "Das ist kein Apple-Chip (M1–M5). Lokale Modelle laufen dann sehr langsam."; PROBLEMS=$((PROBLEMS+1)) ;;
esac

# ----- 2. Passendes Modell aussuchen ----------------------------------------
step "Schritt 2: Das passende Gehirn (Modell) aussuchen"
if [ -n "$FORCED_MODEL" ]; then
  MODEL="$FORCED_MODEL"
  ok "Du hast selbst gewählt: $MODEL"
elif [ "$RAM_GB" -ge 44 ]; then
  MODEL="$MODEL_FAST"
  ok "Super! ${RAM_GB} GB reichen für das empfohlene Modell: $MODEL"
  info "Später kannst du auch das Programmier-Modell holen: ollama pull $MODEL_CODER"
elif [ "$RAM_GB" -ge 28 ]; then
  MODEL="$MODEL_SMALL"
  warn "${RAM_GB} GB sind etwas knapp. Wir nehmen das kleinere Modell: $MODEL"
  info "Es funktioniert, macht aber öfter Fehler als die großen Modelle."
elif [ "$RAM_GB" -ge 16 ]; then
  MODEL="$MODEL_SMALL"
  warn "${RAM_GB} GB sind sehr knapp. Wir versuchen das kleinste empfohlene Modell: $MODEL"
  info "Schließe andere Programme, während Jarvis arbeitet."
  PROBLEMS=$((PROBLEMS+1))
else
  bad "Mit ${RAM_GB} GB RAM läuft ein lokales Modell für Nod leider nicht gut."
  info "Tipp: Nod kann auch ein Online-Modell nutzen (siehe README, Abschnitt 'Kein starker Computer?')."
  exit 1
fi

# ----- 3. Ollama -------------------------------------------------------------
step "Schritt 3: Ollama (das Programm für das Gehirn) prüfen"
has_ollama_cli() { command -v ollama >/dev/null 2>&1; }
has_ollama_app() { [ -d "/Applications/Ollama.app" ]; }
server_up() { curl -fsS --max-time 3 "$OLLAMA_URL/api/version" >/dev/null 2>&1; }

if has_ollama_cli || has_ollama_app; then
  ok "Ollama ist installiert."
elif [ "$MODE" = "check" ]; then
  bad "Ollama fehlt. Starte das Skript ohne --check, dann hilft es dir."
  PROBLEMS=$((PROBLEMS+1))
else
  warn "Ollama ist noch nicht installiert."
  if command -v brew >/dev/null 2>&1 && ask_yes "Soll ich Ollama mit Homebrew installieren?"; then
    brew install --cask ollama || bad "Homebrew hat nicht geklappt. Nimm den Download unten."
  fi
  if ! has_ollama_cli && ! has_ollama_app; then
    info "Ich öffne jetzt die Download-Seite: https://ollama.com/download"
    info "1. Klicke auf 'Download for macOS'."
    info "2. Öffne die Datei und ziehe Ollama in den Ordner 'Programme'."
    info "3. Starte Ollama einmal (Lama-Symbol oben in der Menüleiste)."
    open "https://ollama.com/download" 2>/dev/null || true
    wait_enter "Drücke Enter, wenn Ollama installiert ist und läuft …"
  fi
fi

# Ollama-Befehl auch finden, wenn nur die App installiert ist
if ! has_ollama_cli && [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]; then
  PATH="$PATH:/Applications/Ollama.app/Contents/Resources"
fi

# ----- 4. Kontext (Notizblock) groß genug machen -----------------------------
step "Schritt 4: Ollama einen großen Notizblock geben (Kontext = ${CONTEXT_LENGTH})"
if [ "$MODE" = "install" ] && [ "$TEST_MODE" != "1" ]; then
  launchctl setenv OLLAMA_CONTEXT_LENGTH "$CONTEXT_LENGTH" 2>/dev/null || true
  ok "Eingestellt: OLLAMA_CONTEXT_LENGTH=$CONTEXT_LENGTH"
  info "Wichtig: Stell das zusätzlich in der Ollama-App ein, damit es nach einem Neustart bleibt:"
  info "Lama-Symbol oben rechts → Settings → 'Context length' → ganz nach rechts auf 64k."
  # Ollama neu starten, damit die Einstellung greift
  if pgrep -x Ollama >/dev/null 2>&1 || pgrep -x ollama >/dev/null 2>&1; then
    osascript -e 'quit app "Ollama"' >/dev/null 2>&1 || true
    sleep 2
  fi
  open -a Ollama 2>/dev/null || (ollama serve >/dev/null 2>&1 &)
fi

for _ in $(seq 1 30); do server_up && break; sleep 1; done
if server_up; then
  ok "Ollama läuft und antwortet auf $OLLAMA_URL"
else
  bad "Ollama antwortet nicht. Starte die Ollama-App und führe das Skript nochmal aus."
  exit 1
fi

# ----- 5. Modell holen und testen -------------------------------------------
step "Schritt 5: Das Modell $MODEL holen"
model_present() { curl -fsS --max-time 5 "$OLLAMA_URL/api/tags" 2>/dev/null | grep -Eq "\"name\": *\"$1\""; }

if model_present "$MODEL"; then
  ok "$MODEL ist schon heruntergeladen."
elif [ "$MODE" = "check" ]; then
  bad "$MODEL ist noch nicht heruntergeladen (ollama pull $MODEL)."
  PROBLEMS=$((PROBLEMS+1))
else
  info "Das sind mehr als 10 GB. Mit schnellem Internet dauert es 5–20 Minuten."
  info "Du kannst zuschauen – oder einen Kakao trinken gehen."
  if ! ollama pull "$MODEL"; then
    bad "Download hat nicht geklappt. Prüfe dein Internet und starte das Skript neu."
    exit 1
  fi
  ok "$MODEL ist da."
fi

if model_present "$MODEL"; then
  SHOW="$(curl -fsS --max-time 20 "$OLLAMA_URL/api/show" -d "{\"model\":\"$MODEL\"}" 2>/dev/null || true)"
  if printf '%s' "$SHOW" | tr -d ' \n' | grep -q '"capabilities":\[[^]]*"tools"'; then
    ok "Das Modell kann Werkzeuge benutzen (Tool Calling)."
  else
    bad "Ollama meldet für $MODEL kein Tool Calling. Nod braucht das. Nimm ein anderes Modell."
    PROBLEMS=$((PROBLEMS+1))
  fi

  info "Kleiner Probelauf: Kann das Modell ein Werkzeug aufrufen? (dauert beim ersten Mal bis zu 2 Minuten)"
  TEST_BODY='{"model":"'"$MODEL"'","stream":false,"messages":[{"role":"user","content":"Wie spät ist es gerade in Berlin? Benutze das Werkzeug."}],"tools":[{"type":"function","function":{"name":"uhrzeit","description":"Gibt die aktuelle Uhrzeit in einer Stadt zurück","parameters":{"type":"object","properties":{"stadt":{"type":"string","description":"Name der Stadt"}},"required":["stadt"]}}}]}'
  REPLY="$(curl -fsS --max-time 300 "$OLLAMA_URL/v1/chat/completions" -H 'Content-Type: application/json' -d "$TEST_BODY" 2>/dev/null || true)"
  if printf '%s' "$REPLY" | grep -q '"tool_calls"'; then
    ok "Probelauf bestanden: Das Modell hat das Werkzeug 'uhrzeit' aufgerufen."
  elif [ -z "$REPLY" ]; then
    warn "Keine Antwort im Probelauf (vielleicht zu wenig Speicher frei?)."
    PROBLEMS=$((PROBLEMS+1))
  else
    warn "Das Modell hat geantwortet, aber kein Werkzeug benutzt. Das kann passieren – Nod klappt meist trotzdem."
  fi

  PS_OUT="$(ollama ps 2>/dev/null || true)"
  if [ -n "$PS_OUT" ]; then
    info "So ist das Modell gerade geladen:"
    printf '%s\n' "$PS_OUT" | sed 's/^/      /'
    info "In der Spalte CONTEXT sollte 65536 (oder mehr) stehen."
  fi
fi

# ----- 6. Nod ---------------------------------------------------------------
step "Schritt 6: Die Nod-App (die 'Hände' von Jarvis)"
if [ -d "/Applications/Nod.app" ]; then
  ok "Nod ist installiert."
elif [ "$MODE" = "check" ]; then
  bad "Nod ist noch nicht installiert."
  PROBLEMS=$((PROBLEMS+1))
elif [ "$TEST_MODE" = "1" ]; then
  info "(Testmodus: Nod-Installation übersprungen)"
elif ask_yes "Nod ist noch nicht da. Soll ich die offizielle Nod-App jetzt installieren (ca. 1,8 GB)?"; then
  tmp="$(mktemp)"
  if curl -q --proto '=https' --tlsv1.2 -fsSL "$NOD_INSTALLER" -o "$tmp"; then
    /bin/sh "$tmp" || bad "Die Nod-Installation hat nicht geklappt. Lade Nod von https://nod.n8n.io herunter."
  else
    bad "Konnte den Nod-Installer nicht laden. Lade Nod von https://nod.n8n.io herunter."
  fi
  rm -f "$tmp"
else
  info "Okay. Du kannst Nod später hier laden: https://github.com/n8n-io/nod/releases/latest/download/nod-arm64.dmg"
fi

# ----- Fertig ----------------------------------------------------------------
printf '\n%s──────────────────────────────────────────────%s\n' "$B" "$N"
if [ "$PROBLEMS" -eq 0 ]; then
  printf '  %s%s✔ Alles bereit!%s\n' "$B" "$G" "$N"
else
  printf '  %s%s! Fast fertig – bitte %s Punkt(e) oben ansehen (rot oder gelb).%s\n' "$B" "$Y" "$PROBLEMS" "$N"
fi
printf '%s──────────────────────────────────────────────%s\n' "$B" "$N"
cat <<EOF

  So verbindest du Nod mit deinem Gehirn:
    1. Öffne Nod und klicke auf "Get started".
    2. Bei der Frage nach dem Modell: "More providers" → "Your own server".
    3. Server address:  ${B}http://localhost:11434/v1${N}
    4. API key: leer lassen → "Connect".
    5. Modell auswählen: ${B}${MODEL}${N}

  Alles nochmal prüfen (ändert nichts):
    curl -fsSL https://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-mac.sh | bash -s -- --check
  Hilfe bei Problemen:   https://github.com/Paulito12209/jarvis-on-nod#hilfe

EOF
[ "$PROBLEMS" -eq 0 ] || exit 3
exit 0
