"""Tools the model may use. For now: web search (free, no API key).

Search runs through DuckDuckGo & friends via the `ddgs` package, or – if you run your own
search engine – through SearXNG (set JARVIS_SEARXNG=http://localhost:8080).
Only the search words leave your computer; the model and your voice stay local.
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.parse
import urllib.request
from datetime import datetime

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_suche",
            "description": (
                "Sucht im Internet nach aktuellen Informationen: Nachrichten, Sport-Ergebnisse, "
                "Wetter, Preise, Öffnungszeiten, Ereignisse nach deinem Wissensstand und alles, "
                "was sich ändern kann. Nutze es immer, wenn die Frage aktuelle Daten braucht."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "suchbegriff": {"type": "string", "description": "Kurze Suchanfrage, z. B. 'FC Barcelona Champions League Ergebnis heute'"},
                },
                "required": ["suchbegriff"],
            },
        },
    }
]

TOOL_HINT = (
    "Du hast das Werkzeug web_suche. Benutze es sofort und ohne Rückfrage, wenn eine Frage "
    "aktuelle oder neue Informationen braucht (Nachrichten, Spielstände, Wetter, Preise, Termine, "
    "Personen und Ereignisse der letzten Zeit). Sag nie, dass du keinen Internetzugang hast. "
    "Fasse die Suchergebnisse danach kurz und gesprochen zusammen, ohne Links vorzulesen."
)

_NEWSY = re.compile(r"\b(aktuell|heute|gestern|gerade|jetzt|neu(e|ste|igkeit)|news|nachricht|"
                    r"spiel|stand|ergebnis|tabelle|wetter|live|letzte[nr]?)\w*", re.I)


def _searxng(query: str, base: str, n: int) -> list[dict]:
    url = base.rstrip("/") + "/search?" + urllib.parse.urlencode({"q": query, "format": "json", "language": "de"})
    with urllib.request.urlopen(url, timeout=6) as r:
        data = json.load(r)
    return [{"titel": x.get("title", ""), "text": x.get("content", ""), "quelle": x.get("url", ""),
             "datum": x.get("publishedDate") or ""} for x in data.get("results", [])[:n]]


def _ddgs(query: str, n: int, news: bool) -> list[dict]:
    from ddgs import DDGS

    results: list[dict] = []
    errors: list[Exception] = []

    def run_text():
        try:
            for x in DDGS().text(query, region="de-de", max_results=n):
                results.append({"titel": x.get("title", ""), "text": x.get("body", ""),
                                "quelle": x.get("href", ""), "datum": ""})
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def run_news():
        try:
            for x in DDGS().news(query, region="de-de", timelimit="w", max_results=n):
                results.insert(0, {"titel": x.get("title", ""), "text": x.get("body", ""),
                                   "quelle": x.get("source") or x.get("url", ""), "datum": x.get("date", "")})
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=run_text, daemon=True)]
    if news:
        threads.append(threading.Thread(target=run_news, daemon=True))
    for t in threads:
        t.start()
    for t in threads:
        t.join(8)
    if not results and errors:
        raise errors[0]
    return results


def web_search(query: str, n: int = 5) -> str:
    """Return search results as compact text for the model."""
    query = query.strip()[:200]
    if not query:
        return "Leere Suchanfrage."
    try:
        base = os.environ.get("JARVIS_SEARXNG")
        hits = _searxng(query, base, n) if base else _ddgs(query, n, bool(_NEWSY.search(query)))
    except Exception as e:  # noqa: BLE001
        return f"Die Websuche hat nicht geklappt ({type(e).__name__}). Sag das dem Nutzer kurz."
    if not hits:
        return "Keine Treffer gefunden."
    lines = [f"Suchergebnisse für „{query}“ (abgerufen {datetime.now():%d.%m.%Y %H:%M}):"]
    for i, h in enumerate(hits[: n + 3], 1):
        date = f" [{h['datum'][:16]}]" if h.get("datum") else ""
        lines.append(f"{i}. {h['titel']}{date}: {h['text'][:300]} (Quelle: {h['quelle'][:60]})")
    return "\n".join(lines)


def run_tool(name: str, arguments: dict | str) -> str:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            arguments = {"suchbegriff": arguments}
    if name in ("web_suche", "web_search", "suche", "search"):
        q = arguments.get("suchbegriff") or arguments.get("query") or next(iter(arguments.values()), "")
        return web_search(str(q))
    return f"Unbekanntes Werkzeug: {name}"
