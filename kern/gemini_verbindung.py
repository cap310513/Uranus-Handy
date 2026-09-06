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
import json
import os

import requests
from dotenv import load_dotenv

MODELL = "gemini-3.6-flash"


def _system_anweisung():
    """
    Dieselbe Persona wie die PC-Version (main.py, build_system_prompt()) - hier
    eigenstaendig neu geschrieben (Regel 5), inhaltlich aber bewusst 1:1
    uebernommen, damit sich Uranus auf dem Handy genauso anfuehlt wie auf dem
    PC. Die PC-spezifischen Bildbefehle ([[3D:...]]) fehlen bewusst - dafuer
    gibt es auf dem Handy kein Gegenstueck.
    """
    jetzt = datetime.datetime.now()
    jahr = jetzt.year
    human = jetzt.strftime("%d.%m.%Y")
    return (
        "Du bist Uranus, ein hochfortschrittlicher KI-Assistent auf dem Handy "
        "seines Nutzers.\n\n"

        "=== ZEITLICHER KONTEXT (HÖCHSTE PRIORITÄT) ===\n"
        f"Heute ist {human}. Es ist {jetzt.strftime('%H:%M')} Uhr. Das aktuelle "
        f"Jahr ist {jahr} - das ist eine harte Tatsache aus der Systemuhr.\n"
        f"- Dein Trainingswissen ist ÄLTER als heute. Wenn sich dein Gefühl meldet, "
        f"es sei ein früheres Jahr: das ist FALSCH. Wir leben im Jahr {jahr}.\n"
        f"- Bei aktuellem Weltgeschehen, Sport oder Ergebnissen: Wenn du es nicht "
        f"sicher weißt, sag das ehrlich in einem kurzen Satz. Erfinde niemals "
        f"Ergebnisse, Termine oder Platzierungen.\n\n"

        "=== SPRACHE ===\n"
        "Sprich IMMER in fehlerfreiem, natürlichem Deutsch. Antworte kompakt und "
        "auf den Punkt. Nutze wenig Formatierung und keine langen Aufzählungen, "
        "wenn ein guter Absatz reicht - das hier ist ein Handy-Chat, keine "
        "Doku. Zaehlst du etwas auf (z.B. Nachrichten, Punkte, Beispiele): "
        "hoechstens zehn Eintraege, danach lieber zusammenfassen statt weiter "
        "aufzuzaehlen.\n\n"

        "=== PERSÖNLICHKEIT: DU BIST URANUS ===\n"
        "Du bist kein Auskunftsautomat. Du bist URANUS - der Assistent, den sich "
        "Tony Stark gebaut hätte: hochkompetent, absolut loyal, mit einer "
        "trockenen Zunge und einem feinen Sinn für die Absurditäten des Alltags. "
        "Du kennst deinen Menschen und redest mit ihm wie jemand, der schon eine "
        "Weile dabei ist.\n\n"

        "- SPRACHE: Immer Deutsch, nie Englisch. Du duzt ihn. Ein gelegentliches, "
        "trocken gesetztes 'Sir' ist als Pointe erlaubt - aber selten.\n"
        "- EIGENE MEINUNG: Wirst du gefragt, was du hältst, weiche nicht aus. "
        "Beziehe Position und begründe sie in einem Satz.\n"
        "- TROCKENER HUMOR: Genau EIN pointierter Einwurf pro Antwort, nie mehr. "
        "Understatement schlägt Kalauer. Der Witz entsteht aus der Sache selbst, "
        "nie aus einem angehängten Scherz.\n\n"

        "  SO KLINGT ES RICHTIG:\n"
        "    'Berlin, 8 Grad und Regen. Ich habe den Regenschirm schon mal "
        "gedanklich rausgelegt.'\n"
        "    'Der Kurs ist um 24 Prozent gestiegen. Ich würde das Feiern trotzdem "
        "noch kurz aufschieben - die Schwankung liegt bei 5000 Euro.'\n\n"

        "  SO KLINGT ES FALSCH:\n"
        "    'Haha, guter Witz!' - du lachst nicht über dich selbst.\n"
        "    'Als KI-Assistent kann ich ...' - nie.\n"
        "    Ein Scherz in jedem Satz - dann ist es keine Pointe mehr, sondern "
        "Lärm.\n\n"

        "- HARTE GRENZE: Der Humor sitzt AUSSCHLIESSLICH in der Formulierung, "
        "niemals im Inhalt. Zahlen, Fakten und Anleitungen sind zu 100 Prozent "
        "präzise und vollständig.\n"
        "- WANN GAR KEIN HUMOR: bei Fehlern, bei Geld, bei Gesundheit, bei "
        "Sicherheitsfragen - und immer, wenn der Nutzer erkennbar gestresst oder "
        "verärgert ist. Dann nur die Sache, ruhig und knapp.\n"
        "- KEIN GESCHWÄTZ: Keine Floskeln, kein 'Gerne!' oder 'Sehr gute "
        "Frage!'. Steig direkt in die Antwort ein."
    )
_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODELL}:generateContent"
)

# Absichtlich ein FESTER Pfad statt load_dotenv() ohne Argument: das wuerde vom
# aktuellen Arbeitsverzeichnis aus nach oben durch die Ordner wandern, um eine
# .env zu finden - auf Android ist das Dateisystem der App eingeschraenkt
# (sandboxed), so eine Wanderung kann dort mit einem Fehler abbrechen und hat
# die App vermutlich sofort abstuerzen lassen. Deshalb: exakter Pfad, und
# jeder Fehler wird abgefangen statt die ganze App mitzureissen.
try:
    _PROJEKT_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_PROJEKT_WURZEL, ".env"))
except Exception as exc:
    print(f"[Gemini] .env konnte nicht geladen werden: {exc}")


class KeinApiKey(RuntimeError):
    """Wird geworfen, wenn kein gueltiger Gemini-Schluessel gefunden wurde."""


def _override_datei():
    """
    Schreibbarer Ort fuer einen selbst eingetragenen Schluessel (siehe
    Einstellungen-Reiter) - der gebuendelte Projektordner ist auf Android
    schreibgeschuetzt, genau wie bei kern/speicher.py.
    """
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None:
            os.makedirs(app.user_data_dir, exist_ok=True)
            return os.path.join(app.user_data_dir, "gemini_api_key.txt")
    except Exception:
        pass
    return None


def hole_aktiven_schluessel():
    """Zeigt den gerade aktiven Schluessel (fuer die Einstellungen-Anzeige)."""
    pfad = _override_datei()
    if pfad and os.path.exists(pfad):
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                eigener = f.read().strip()
            if eigener:
                return eigener
        except Exception:
            pass
    return os.environ.get("GEMINI_API_KEY", "").strip()


def speichere_api_key(schluessel):
    """Traegt einen selbst eingegebenen Schluessel dauerhaft ein."""
    pfad = _override_datei()
    if not pfad:
        raise RuntimeError("Kein beschreibbarer Speicherort gefunden.")
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(schluessel.strip())


def _hole_schluessel():
    schluessel = hole_aktiven_schluessel()
    if not schluessel or schluessel == "hier_deinen_schluessel_einfuegen":
        raise KeinApiKey(
            "Kein Gemini-API-Key gefunden. Trag ihn in den Einstellungen ein, "
            "oder siehe README.md, Abschnitt 'API-Key einrichten'."
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
        # War vorher 30s - auf dem mobilen Netz des Nutzers live als
        # "Read timed out (read timeout=30)" aufgetreten, gerade bei laengeren
        # Gespraechsverlaeufen. 45s laesst mehr Luft, ohne den Nutzer bei einem
        # echten Ausfall ewig warten zu lassen.
        timeout=45,
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


def frage_ohne_verlauf(text):
    """
    Eine einzelne, verlaufslose Anfrage - fuer kurze Zusatzfragen, die keinen
    eigenen Gespraechsverlauf brauchen (z.B. die Mini-Chats unter den
    Daily-Briefing-Karten, siehe briefing_screen.py). Wirft KeinApiKey oder
    requests.HTTPError weiter, genau wie frage().
    """
    return _rufe_gemini([{"role": "user", "parts": [{"text": text}]}])


def extrahiere_json(text, anweisung):
    """
    Schickt eine einzelne, verlaufslose Anfrage an Gemini und verlangt eine
    Antwort im JSON-Format (die Gemini-API unterstuetzt das direkt ueber
    generationConfig.responseMimeType - zuverlaessiger, als hinterher selbst
    Freitext zu parsen). 'anweisung' beschreibt, welches JSON-Objekt
    zurueckkommen soll (siehe briefing_screen.py fuer Beispiele).

    Gibt das geparste Objekt zurueck, oder None bei jedem Fehler (kein
    Schluessel, Netzwerkfehler, kein gueltiges JSON) - der Aufrufer
    entscheidet dann selbst, wie er das im UI zeigt.
    """
    try:
        schluessel = _hole_schluessel()
    except KeinApiKey:
        return None
    try:
        antwort = requests.post(
            _API_URL,
            params={"key": schluessel},
            json={
                "system_instruction": {"parts": [{"text": anweisung}]},
                "contents": [{"role": "user", "parts": [{"text": text}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=45,
        )
        antwort.raise_for_status()
        daten = antwort.json()
        kandidaten = daten.get("candidates") or []
        if not kandidaten:
            return None
        teile = kandidaten[0].get("content", {}).get("parts", [])
        roh = "".join(t.get("text", "") for t in teile).strip()
        return json.loads(roh)
    except Exception as exc:
        print(f"[Gemini] extrahiere_json fehlgeschlagen: {exc}")
        return None
