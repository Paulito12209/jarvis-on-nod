# =============================================================================
#  Jarvis on Nod – Einrichtungs-Helfer für Windows 11
#
#  So startest du es (Start-Menü → "PowerShell" öffnen, NICHT als Administrator):
#    irm https://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-windows.ps1 | iex
#
#  Hinweis: Nod für Windows ist noch eine Vorschau-Version ("preview").
#  Es braucht Windows 11, WSL 2 und mindestens 20 GB freien Speicherplatz.
# =============================================================================

$ErrorActionPreference = 'Continue'
$OllamaUrl     = 'http://localhost:11434'
$ContextLength = 65536
$ModelFast     = 'qwen3.6:35b'
$ModelSmall    = 'gpt-oss:20b'
$Problems      = 0

function Step($t) { Write-Host "`n> $t" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "  [OK] $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  [!]  $t" -ForegroundColor Yellow }
function Bad($t)  { Write-Host "  [X]  $t" -ForegroundColor Red }
function Info($t) { Write-Host "       $t" }

Write-Host "`n   Jarvis on Nod - dein KI-Helfer, ganz lokal`n" -ForegroundColor White

# --- 1. Computer anschauen ---------------------------------------------------
Step 'Schritt 1: Deinen Computer anschauen'
$ramGb = [math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
Ok "Arbeitsspeicher (RAM): $ramGb GB"
$gpu = (Get-CimInstance Win32_VideoController | Select-Object -First 1).Name
Ok "Grafikkarte: $gpu"
Info 'Wichtig auf Windows: Am schnellsten ist es mit einer NVIDIA-Grafikkarte mit viel Grafikspeicher (VRAM).'

# --- 2. Modell aussuchen -----------------------------------------------------
Step 'Schritt 2: Das passende Gehirn (Modell) aussuchen'
if ($ramGb -ge 44)      { $Model = $ModelFast;  Ok "Empfohlen für dich: $Model" }
elseif ($ramGb -ge 16)  { $Model = $ModelSmall; Warn "Dein Speicher ist knapp. Wir nehmen das kleinere Modell: $Model" }
else { Bad "Mit $ramGb GB RAM läuft ein lokales Modell für Nod leider nicht gut."; exit 1 }

# --- 3. Ollama ---------------------------------------------------------------
Step 'Schritt 3: Ollama (das Programm für das Gehirn) prüfen'
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Warn 'Ollama ist noch nicht installiert.'
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Info 'Ich installiere Ollama mit winget ...'
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
  } else {
    Start-Process 'https://ollama.com/download'
    Read-Host '  Lade Ollama herunter, installiere es und drücke dann Enter'
  }
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}
if (Get-Command ollama -ErrorAction SilentlyContinue) { Ok 'Ollama ist installiert.' } else { Bad 'Ollama nicht gefunden. Bitte neu starten und das Skript nochmal ausführen.'; exit 1 }

# --- 4. Kontext --------------------------------------------------------------
Step "Schritt 4: Ollama einen großen Notizblock geben (Kontext = $ContextLength)"
[Environment]::SetEnvironmentVariable('OLLAMA_CONTEXT_LENGTH', "$ContextLength", 'User')
$env:OLLAMA_CONTEXT_LENGTH = "$ContextLength"
Ok "Eingestellt: OLLAMA_CONTEXT_LENGTH=$ContextLength (bleibt auch nach Neustart)"
Info 'Ollama wird jetzt neu gestartet, damit die Einstellung greift.'
Get-Process -Name 'ollama*' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$app = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe'
if (Test-Path $app) { Start-Process $app } else { Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden }

$up = $false
for ($i = 0; $i -lt 30; $i++) {
  try { Invoke-RestMethod "$OllamaUrl/api/version" -TimeoutSec 3 | Out-Null; $up = $true; break } catch { Start-Sleep 1 }
}
if ($up) { Ok "Ollama läuft auf $OllamaUrl" } else { Bad 'Ollama antwortet nicht. Starte Ollama aus dem Start-Menü und versuche es nochmal.'; exit 1 }

# --- 5. Modell holen ---------------------------------------------------------
Step "Schritt 5: Das Modell $Model holen"
$tags = (Invoke-RestMethod "$OllamaUrl/api/tags").models.name
if ($tags -contains $Model) { Ok "$Model ist schon da." }
else {
  Info 'Das sind mehr als 10 GB. Das kann 5-20 Minuten dauern.'
  ollama pull $Model
  if ($LASTEXITCODE -ne 0) { Bad 'Download hat nicht geklappt.'; exit 1 }
  Ok "$Model ist da."
}

$show = Invoke-RestMethod "$OllamaUrl/api/show" -Method Post -Body (@{ model = $Model } | ConvertTo-Json) -ContentType 'application/json'
if ($show.capabilities -contains 'tools') { Ok 'Das Modell kann Werkzeuge benutzen (Tool Calling).' }
else { Bad 'Dieses Modell kann keine Werkzeuge benutzen. Nod braucht das.'; $Problems++ }

Info 'Kleiner Probelauf mit einem Werkzeug (beim ersten Mal bis zu 2 Minuten) ...'
$body = @{
  model = $Model; stream = $false
  messages = @(@{ role = 'user'; content = 'Wie spät ist es gerade in Berlin? Benutze das Werkzeug.' })
  tools = @(@{ type = 'function'; function = @{ name = 'uhrzeit'; description = 'Gibt die aktuelle Uhrzeit in einer Stadt zurück'
    parameters = @{ type = 'object'; properties = @{ stadt = @{ type = 'string' } }; required = @('stadt') } } })
} | ConvertTo-Json -Depth 10
try {
  $r = Invoke-RestMethod "$OllamaUrl/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 300
  if ($r.choices[0].message.tool_calls) { Ok "Probelauf bestanden: Das Modell hat das Werkzeug 'uhrzeit' aufgerufen." }
  else { Warn 'Das Modell hat ohne Werkzeug geantwortet. Nod klappt meist trotzdem.' }
} catch { Warn 'Keine Antwort im Probelauf (zu wenig Speicher frei?).'; $Problems++ }

# --- 6. Nod ------------------------------------------------------------------
Step "Schritt 6: Die Nod-App (die 'Hände' von Jarvis)"
$nodInstalled = Test-Path (Join-Path $env:LOCALAPPDATA 'Programs\nod')
if ($nodInstalled) { Ok 'Nod scheint installiert zu sein.' }
else {
  $a = Read-Host '  Nod ist noch nicht da. Jetzt die offizielle Nod-App installieren? [J/n]'
  if ($a -notmatch '^(n|nein|no)$') {
    Invoke-RestMethod 'https://raw.githubusercontent.com/n8n-io/nod/main/deployment/n8n/install.ps1' | Invoke-Expression
  } else {
    Info 'Okay. Download später hier: https://github.com/n8n-io/nod/releases/latest/download/nod-Setup-x64.exe'
  }
}

# --- Fertig ------------------------------------------------------------------
Write-Host ''
if ($Problems -eq 0) { Write-Host '  Alles bereit!' -ForegroundColor Green }
else { Write-Host "  Fast fertig - bitte $Problems Punkt(e) oben ansehen." -ForegroundColor Yellow }
Write-Host @"

  So verbindest du Nod mit deinem Gehirn:
    1. Öffne Nod und klicke auf "Get started".
    2. Bei der Frage nach dem Modell: "More providers" -> "Your own server".
    3. Server address:  http://localhost:11434/v1
    4. API key: leer lassen -> "Connect".
    5. Modell auswählen: $Model

"@
