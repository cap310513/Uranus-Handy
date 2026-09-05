# -*- coding: utf-8 -*-
"""
Einfache lokale Speicherung des Chat-Verlaufs als JSON-Datei.

Bewusst schlicht gehalten fuer Meilenstein 1 (nur PC-Test). Wenn die App
spaeter wirklich auf dem Handy laeuft, zieht der Speicherort auf den
Android-eigenen App-Datenordner um - das ist aber ein spaeterer Schritt.
"""
import json
import os

_ORDNER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATEI = os.path.join(_ORDNER, "chat_verlauf.json")


def lade_verlauf():
    """Gibt die gespeicherten Nachrichten zurueck, oder eine leere Liste."""
    if not os.path.exists(_DATEI):
        return []
    try:
        with open(_DATEI, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def speichere_verlauf(nachrichten):
    """Schreibt die komplette Nachrichtenliste [{'rolle', 'text'}, ...] weg."""
    try:
        with open(_DATEI, "w", encoding="utf-8") as f:
            json.dump(nachrichten, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[Speicher] Verlauf konnte nicht gesichert werden: {exc}")