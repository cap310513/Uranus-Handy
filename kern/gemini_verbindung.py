# -*- coding: utf-8 -*-
"""
Schlanke Gemini-Anbindung fuer die Mobile-Version.

Eigenstaendig geschrieben, nicht aus dem PC-Ordner importiert (siehe Regel 5).

Bewusst ANDERS als die PC-Version: dort wird das offizielle 'google-genai'-Paket
benutzt, das aber viele Abhaengigkeiten mit kompiliertem Code mitbringt
(pydantic-core, cryptography). Fuer den Android-Build in der Cloud
(python-for-android) ist das ein unnoetiges Risiko - ein einzelner
fehlgeschlagener Cross-Compile wuerde den ganzen Bau-Vorgang zum Absturz
bringen. Deshalb spricht die Mobile-Version die Gemini-API direkt per REST an
(nur 'requests', reines Python, keine Kompilierung noetig) - inhaltlich macht
das keinen Unterschied, ruft dieselbe Gemini-API auf.
"""
import datetime
import os

import requests
from dotenv import load_dotenv

MODELL = "gemini-3.6-flash"


def _system_anweisung():
    """
    Echtes Datum aus der Systemuhr statt Modellwissen (sonst haelt sich Gemini
    gern noch fuer im Trainingsjahr) plus kurze Uranus-Persona.
    """
    jetzt = datetime.datetime.now()
    return (
        "Du bist Uranus, ein persönlicher KI-Assistent auf dem Handy seines "
        "Nutzers - hilfsbereit, direkt, mit einer trockenen, freundlichen Art. "
        "Antworte immer auf Deutsch, kurz und natürlich, ohne lange Aufzählungen.\n\n"
        f"Heute ist der {jetzt.strftime('%d.%m.%Y')}, es ist {jetzt.strftime('%H:%M')} "
        f"Uhr. Das ist die echte Systemzeit - dein eigenes Trainingswissen ist älter "
        f"als das. Verlass dich bei 'heute', 'dieses Jahr' oder aktuellen Ereignissen "
        f"auf diese Angabe, nicht auf dein Bauchgefühl."
    )
_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODELL}:generateContent"
)

load_dotenv()


class KeinApiKey(RuntimeError):
    """Wird geworfen, wenn kein gueltiger Gemini-Schluessel gefunden wurde."""


def _hole_schluessel():
    schluessel = os.environ.get("GEMINI_API_KEY", "").strip()
    if not schluessel or schluessel == "hier_deinen_schluessel_einfuegen":
        raise KeinApiKey(
            "Kein Gemini-API-Key gefunden. Siehe README.md, Abschnitt "
            "'API-Key einrichten', um einen kostenlosen Schluessel einzutragen."
        )
    return schluessel


class Chat:
    """Haelt den Gespraechsverlauf selbst - die REST-API kennt keine Sitzungen."""

    def __init__(self):
        self._verlauf = []   # [{"role": "user"|"model", "parts": [{"text": ...}]}]

    def send_message(self, text):
        self._verlauf.append({"role": "user", "parts": [{"text": text}]})
        antwort_text = _rufe_gemini(self._verlauf)
        self._verlauf.append({"role": "model", "parts": [{"text": antwort_text}]})
        return antwort_text


def _rufe_gemini(verlauf):
    schluessel = _hole_schluessel()
    antwort = requests.post(
        _API_URL,
        params={"key": schluessel},
        json={
            "system_instruction": {"parts": [{"text": _system_anweisung()}]},
            "contents": verlauf,
        },
        timeout=30,
    )
    antwort.raise_for_status()
    daten = antwort.json()
    kandidaten = daten.get("candidates") or []
    if not kandidaten:
        return ""
    teile = kandidaten[0].get("content", {}).get("parts", [])
    return "".join(t.get("text", "") for t in teile).strip()


def neuer_chat():
    """Startet ein neues Gespraech - merkt sich den Verlauf selbst."""
    return Chat()


def frage(chat, text):
    """
    Schickt eine Nachricht an ein laufendes Gespraech (siehe neuer_chat()) und
    gibt die Antwort als Text zurueck. Wirft KeinApiKey oder requests.HTTPError
    weiter - der Aufrufer entscheidet, wie er das im UI zeigt.
    """
    return chat.send_message(text)
