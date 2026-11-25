# 🎙️ Jarvis Stimme

**Du redest, Jarvis antwortet sofort mit deutscher Stimme. Alles läuft auf deinem eigenen Computer.**

Andere Programme warten, bis die KI ihre ganze Antwort fertig geschrieben hat, und lesen sie erst dann vor. Das fühlt sich langsam an.
Jarvis Stimme fängt schon an zu sprechen, während die KI noch weiterdenkt. Ziel: **die erste Silbe in unter einer Sekunde**, nachdem du aufgehört hast zu reden.

---

## ⚡ Starten (ein Befehl)

Öffne das Programm **Terminal** und füge das ein:

```sh
bash <(curl -fsSL https://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-stimme.sh)
```

Oder, wenn du das Repo schon hast, im Repo-Ordner:

```sh
./scripts/jarvis-stimme.sh
```

Das Skript macht alles allein: Es prüft Ollama, installiert die Programme (nur beim ersten Mal, in `~/.jarvis-stimme`), sucht die deutsche Stimme „Thorsten“ (und lädt sie sonst herunter) und startet. Dann einfach **losreden**. 🗣️

> 💡 Beim allerersten Start lädt Whisper (die „Ohren“, ca. 1,5 GB) einmal herunter. macOS fragt nach dem **Mikrofon** – bitte „Erlauben“ klicken.

**Beenden:** Sag „Tschüss Jarvis“ oder drück `Ctrl + C`.

---

## 🧩 So funktioniert es

```
 🎤 Du redest
   │
   ▼
 👂 Silero VAD merkt: „Jetzt ist Pause, du bist fertig“    (0,6 s Stille)
   │
   ▼
 📝 Whisper (MLX, auf der Grafikeinheit) schreibt mit        (~0,2–0,4 s)
   │
   ▼
 🧠 Ollama-Modell denkt und schickt Wort für Wort            (Denken ist AUS = schneller)
   │   ┌───────────────────────────────────────────────┐
   │   │ Sobald der erste Satzteil fertig ist, geht er  │
   │   │ sofort zur Stimme. Der Rest kommt hinterher.   │
   │   └───────────────────────────────────────────────┘
   ▼
 🔊 Piper „Thorsten“ spricht Satz für Satz                    (~20× schneller als Echtzeit)
   │
   ✋ Du kannst jederzeit dazwischenreden – dann hört Jarvis sofort auf.
```

Nach jeder Antwort siehst du, wie schnell es war, zum Beispiel:

```
⚡ 0,72 s bis zur ersten Silbe  (Hören 0,25 · Denken 0,38 · Stimme 0,09)  + 0,60 s Pause-Erkennung
```

So siehst du genau, welcher Teil am meisten Zeit braucht.

---

## 🛠️ Die Tricks für Tempo

| Trick | Warum es schneller ist |
|---|---|
| **Streaming** | Die KI schickt jedes Wort sofort, nicht erst die ganze Antwort. |
| **Erster Satzteil zuerst** | Schon beim ersten Komma (ab 4 Wörtern) fängt die Stimme an. |
| **Gleichzeitig arbeiten** | Während Satz 1 gesprochen wird, schreibt die KI Satz 2 und die Stimme baut ihn schon. |
| **„Denken“ aus** | Qwen-Modelle denken sonst erst lange still nach. Fürs Reden schalten wir das ab. |
| **Modell bleibt geladen** | Ollama hält das Modell 60 Minuten im Speicher. Kein Neuladen. |
| **Aufwärmen beim Start** | Whisper, Stimme und Modell laufen einmal vorab, damit die erste Frage schnell ist. |
| **Kurzer Notizblock** | 8.000 Tokens Kontext statt 64.000 – reicht fürs Gespräch und ist schneller. |
| **Kurze Antworten** | Jarvis ist angewiesen, wie im Gespräch zu reden: 1–3 Sätze, keine Listen. |
| **Whisper-Unsinn filtern** | Bei Stille erfindet Whisper gern „Untertitel von …“. Das wird ignoriert. |

---

## 🧠 Welches Modell?

Jarvis Stimme sucht sich **automatisch** das schnellste gute Modell aus, das du in Ollama hast. Reihenfolge:

1. `qwen3.6:35b` – „MoE“-Modell: groß und klug, rechnet aber nur mit einem kleinen Teil. **Sehr schnell.** ⭐
2. `gemma4:12b` – klein, schnell, gutes Deutsch.
3. `qwen3.6:27b` / `qwen3.5:27b` – klüger, aber langsamer beim Reden.

Selbst wählen:

```sh
./scripts/jarvis-stimme.sh --modell gemma4:12b
```

Mit `--test` misst Jarvis alles einmal durch und zeigt dir die Zeiten. Probier ruhig mehrere Modelle aus!

---

## 🎛️ Einstellungen

| Option | Was sie macht |
|---|---|
| `--test` | Alles einmal durchmessen (Stimme, Hören, Denken) |
| `--modell NAME` | Bestimmtes Ollama-Modell nehmen |
| `--pause 0.4` | Schneller merken, dass du fertig bist (Standard 0,6 s). Zu klein = Jarvis fällt dir ins Wort. |
| `--tempo 1.15` | Stimme spricht schneller (Standard 1,05) |
| `--ohne-unterbrechen` | Kein Dazwischenreden. **Nimm das, wenn Jarvis sich über die Lautsprecher selbst unterbricht.** |
| `--empfindlichkeit 0.9` | Dazwischenreden muss deutlicher sein (Standard 0,85) |
| `--tippen` | Tippen statt sprechen (Antwort kommt trotzdem als Stimme) |
| `--geraete` | Mikrofone und Lautsprecher anzeigen |
| `--mikro 2` / `--lautsprecher 3` | Bestimmtes Gerät nehmen |
| `--stimme PFAD` | Andere Piper-Stimme (`.onnx`-Datei) |
| `--name Friday` | Anderer Name für den Assistenten |

> 🎧 **Tipp:** Mit Kopfhörern klappt das Dazwischenreden am besten. Über Lautsprecher hört das Mikrofon Jarvis' eigene Stimme. Dafür ist die Empfindlichkeit beim Reden extra hoch eingestellt.

---

## 🆘 Hilfe

| Problem | Lösung |
|---|---|
| „Ollama ist nicht erreichbar“ | Ollama-App starten (Lama-Symbol oben in der Menüleiste). |
| Jarvis hört nichts | Systemeinstellungen → Datenschutz → **Mikrofon** → Terminal erlauben. Mit `--geraete` prüfen, welches Mikro aktiv ist. |
| Jarvis unterbricht sich selbst | `--ohne-unterbrechen` oder Kopfhörer benutzen. |
| Jarvis fällt mir ins Wort | `--pause 0.9` |
| Erste Antwort ist langsam | Normal beim allerersten Mal (Modelle werden geladen). Danach geht es schnell. |
| Antworten sind zu lang/zu kurz | Einfach sagen: „Antworte bitte ausführlicher.“ |

---

## 🧑‍💻 Für Profis

```
stimme/
├── jarvis_stimme/
│   ├── __main__.py   ← Start, Optionen, --test
│   ├── app.py        ← Gesprächs-Schleife: Turn-Logik, Barge-in, Zeitmessung
│   ├── text.py       ← Satz-Zerleger für den Token-Strom, Markdown/Emoji-Filter
│   ├── llm.py        ← Ollama /api/chat Streaming (nur Standardbibliothek), Modellwahl
│   ├── stt.py        ← mlx-whisper (Apple Silicon) oder faster-whisper
│   ├── tts.py        ← Piper, Stimmen-Suche
│   ├── vad.py        ← Silero VAD (pysilero-vad, ohne PyTorch) + Turn-Erkennung
│   └── audio.py      ← Mikrofon und lückenlose Wiedergabe (sounddevice)
└── tests/            ← pytest (ohne Mikrofon und ohne Ollama lauffähig)
```

Tests laufen:

```sh
cd stimme && uv run --with pytest --with-editable . pytest -q
```

Gesucht wird die Stimme in `~/.jarvis-stimme/stimmen`, `~/.openjarvis/voices/piper` und `~/.local/share/piper`.

**Nächste Ideen:** Weckwort („Hey Jarvis“) mit openWakeWord, „Smart Turn“ (erkennt am Satzklang, ob du fertig bist, statt nur Stille), eigene Stimme klonen (Chatterbox / F5-TTS), kleines Web-Fenster mit leuchtender Kugel, Werkzeuge (Uhrzeit, Wetter, Timer).
