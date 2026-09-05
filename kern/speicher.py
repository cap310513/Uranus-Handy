# -*- coding: utf-8 -*-
"""
Einfache lokale Speicherung des Chat-Verlaufs als JSON-Datei.

Nutzt den von Kivy bereitgestellten, garantiert beschreibbaren App-Datenordner
(App.user_data_dir) - der zeigt auf dem PC in einen normalen Ordner, auf
Android auf den privaten, beschreibbaren Speicherbereich der App. Der
Projektordner selbst ist auf Android naemlich schreibgeschuetzt (Teil des
Programmpakets), ein Schreibversuch dorthin waere schlicht wirkungslos.
"""
import json
import os

_DATEINAME = "chat_verlauf.json"


def _datei_pfad():
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None:
            os.makedirs(app.user_data_dir, exist_ok=True)
            return os.path.join(app.user_data_dir, _DATEINAME)
    except Exception:
        pass
    # Fallback (z.B. ausserhalb einer laufenden App, beim Testen): Ordner
    # oberhalb von kern/ - funktioniert auf dem PC, nicht auf Android.
    ordner = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(ordner, _DATEINAME)


def lade_verlauf():
    """Gibt die gespeicherten Nachrichten zurueck, oder eine leere Liste."""
    pfad = _datei_pfad()
    if not os.path.exists(pfad):
        return []
    try:
        with open(pfad, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def speichere_verlauf(nachrichten):
    """Schreibt die komplette Nachrichtenliste [{'rolle', 'text'}, ...] weg."""
    try:
        with open(_datei_pfad(), "w", encoding="utf-8") as f:
            json.dump(nachrichten, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[Speicher] Verlauf konnte nicht gesichert werden: {exc}")
