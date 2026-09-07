# -*- coding: utf-8 -*-
"""
kern/lernen.py - die Lern- und Studien-Engine fuer den "Lernen"-Reiter.

Eigenstaendig fuer die Mobile-Version geschrieben (Regel 5), aber nach dem
Vorbild der PC-Version (uranus_lernen.py) - inhaltlich weitgehend gleich,
technisch bewusst anders an zwei Stellen:

  * Kein lokales Ollama-Modell (auf einem Handy gibt es keinen lokalen
    LLM-Server) - alle Anfragen laufen stattdessen ueber die bereits
    vorhandene Gemini-Anbindung (kern/gemini_verbindung.py), genau wie Chat
    und die Mini-Chats im Daily Briefing.
  * Word-Dateien (.docx) werden vorerst NICHT gelesen - python-docx zieht
    lxml nach, eine kompilierte Abhaengigkeit mit echtem Android-Bau-Risiko
    (siehe buildozer.spec, freetype-Kommentar, fuer ein Beispiel aus genau
    dieser Kategorie). PDF, Text und Markdown gehen sofort.

Vier Werkzeuge auf derselben Grundlage:

  1. MINDMAP      Aus einem Thema oder Dokument wird eine Baumstruktur:
                  Hauptthema in der Mitte, Aeste zu Unterthemen, Blaetter mit
                  den Einzelheiten.
  2. LERNZETTEL   Eine strukturierte Zusammenfassung mit Ueberschriften, fetten
                  Schluesselbegriffen und "Key Takeaways".
  3. KARTEIKARTEN Frage/Antwort-Paare samt Wiederholungsplan nach dem
                  SM-2-Verfahren (dasselbe Prinzip wie Anki).
  4. PRUEFUNG     Fragen, die der Nutzer beantwortet; die Antwort wird bewertet
                  und mit einer Schulnote und konkretem Feedback zurueckgegeben.

Kann das Modell etwas nicht sauber liefern, wird das gesagt - es wird nichts
erfunden und nichts stillschweigend mit Platzhaltern gefuellt.
"""
import json
import os
import re
import time

try:
    from pypdf import PdfReader
    PDF_DA = True
except Exception:                                    # pragma: no cover
    PdfReader = None
    PDF_DA = False

from kern import gemini_verbindung

# .docx/.doc/.rtf bewusst NICHT dabei (siehe Modul-Docstring). Die uebrigen
# Endungen landen alle im Textdatei-Rueckfallpfad von lies_dokument().
LESBARE_TYPEN = (".pdf", ".txt", ".md", ".markdown", ".py", ".csv", ".json")

# Fotos (Handschrift, Arbeitsblaetter, Vokabellisten) - gehen NICHT durch
# lies_dokument(), sondern durch lies_bild() (Gemini Vision statt lokalem
# OCR, siehe dort).
BILD_TYPEN = (".jpg", ".jpeg", ".png", ".webp")

# So viel Text geht hoechstens an das Modell - laengere Dokumente werden gekuerzt.
MAX_KONTEXT = 12000


# ---------------------------------------------------------------- Dokumente

def lies_dokument(pfad, max_zeichen=200_000):
    """
    Text aus PDF, Markdown oder Textdatei.
    (text, meldung) - text ist leer, wenn nichts gelesen werden konnte.
    """
    if not os.path.exists(pfad):
        return "", f"'{os.path.basename(pfad)}' gibt es nicht."
    endung = os.path.splitext(pfad)[1].lower()

    if endung in (".docx", ".doc"):
        return "", "Word-Dateien werden aktuell noch nicht unterstuetzt - bitte als PDF oder Text."

    if endung == ".pdf":
        if not PDF_DA:
            return "", "pypdf fehlt - ohne das kann ich keine PDFs lesen."
        try:
            leser = PdfReader(pfad)
            seiten = []
            for nummer, seite in enumerate(leser.pages, start=1):
                text = (seite.extract_text() or "").strip()
                if text:
                    seiten.append(f"--- Seite {nummer} ---\n{text}")
                if sum(len(s) for s in seiten) > max_zeichen:
                    break
            gesamt = "\n\n".join(seiten)
            if not gesamt.strip():
                return "", ("Diese PDF enthält keinen auslesbaren Text - vermutlich "
                            "ein Scan. Dafür bräuchte es eine Texterkennung.")
            return gesamt, f"{len(leser.pages)} Seiten gelesen ({len(gesamt)} Zeichen)."
        except Exception as fehler:
            return "", f"PDF nicht lesbar: {type(fehler).__name__}: {fehler}"

    try:
        with open(pfad, "r", encoding="utf-8", errors="replace") as datei:
            gesamt = datei.read(max_zeichen)
        if not gesamt.strip():
            return "", "Die Datei ist leer."
        return gesamt, f"{len(gesamt)} Zeichen gelesen."
    except Exception as fehler:
        return "", f"Datei nicht lesbar: {type(fehler).__name__}: {fehler}"


BILD_ERKENNUNG_SYSTEM = (
    "Du liest Fotos von handschriftlichen Notizen, Arbeitsblättern oder "
    "Vokabellisten für Lernende aus. Transkribiere den GESAMTEN lesbaren Text "
    "möglichst genau (auch Handschrift). Erkennst du eine Struktur "
    "(Überschriften, Vokabellisten der Form Fremdsprache = Übersetzung, "
    "Aufzählungen, Rechenaufgaben), gib sie in derselben Struktur als reinen "
    "Text wieder (keine Markdown-Formatierung nötig). Ist ein Teil "
    "unleserlich, kennzeichne genau diese Stelle mit [unleserlich] statt zu "
    "raten. Antworte NUR mit dem transkribierten Text, ohne Einleitung, "
    "Kommentar oder Erklärung."
)


def lies_bild(pfad, melde=None):
    """
    (text, fehler) - laesst Gemini den Bildinhalt (Foto von Handschrift,
    einem Arbeitsblatt oder einer Vokabelliste) auslesen und strukturiert
    als Text wiedergeben. Siehe Modul-Docstring: bewusst kein lokales OCR
    (Android-Bau-Risiko, ausserdem bei Handschrift ungenauer) - stattdessen
    Geminis eigene multimodale Faehigkeit (kern/gemini_verbindung.py,
    frage_mit_bild()).
    """
    melde = melde or (lambda _t: None)
    if not os.path.exists(pfad):
        return "", f"'{os.path.basename(pfad)}' gibt es nicht."
    fehlt = _schluessel_fehler()
    if fehlt:
        return "", fehlt
    melde("Lese Bildinhalt ...")
    try:
        text = gemini_verbindung.frage_mit_bild(pfad, BILD_ERKENNUNG_SYSTEM)
    except Exception as fehler:
        return "", f"Bild nicht lesbar: {type(fehler).__name__}: {fehler}"
    text = text.strip()
    if len(text) < 5:
        return "", "Im Bild konnte kein Text erkannt werden."
    return text, ""


def kuerze(text, grenze=MAX_KONTEXT):
    """Lange Dokumente auf eine Laenge bringen, die das Modell verarbeiten kann."""
    text = (text or "").strip()
    if len(text) <= grenze:
        return text
    # Anfang und Ende behalten - dazwischen steht meist das Gleiche in Variationen.
    kopf = text[:int(grenze * 0.65)]
    schwanz = text[-int(grenze * 0.3):]
    return f"{kopf}\n\n[... {len(text) - len(kopf) - len(schwanz)} Zeichen ausgelassen ...]\n\n{schwanz}"


def _schluessel_fehler():
    """None, wenn ein API-Key hinterlegt ist - sonst eine klare Fehlermeldung,
    statt den Nutzer erst nach einem gescheiterten Netzwerkaufruf im Unklaren
    zu lassen."""
    if not gemini_verbindung.hole_aktiven_schluessel().strip():
        return "Kein Gemini-API-Key hinterlegt (siehe Einstellungen)."
    return None


# ---------------------------------------------------------------- Mindmap

MINDMAP_SYSTEM = (
    "Du baust Mindmaps für Lernende. Antworte AUSSCHLIESSLICH mit JSON, ohne "
    "Erklärung davor oder danach, in genau dieser Form:\n"
    '{"thema": "Hauptthema", "aeste": [{"titel": "Unterthema", '
    '"punkte": ["Detail", "Detail"], "unter": [{"titel": "...", "punkte": [...]}]}]}\n'
    "Regeln: 4 bis 7 Äste. Jeder Ast 2 bis 5 Punkte. Höchstens zwei Ebenen "
    "unterhalb der Äste. Titel maximal 6 Wörter, Punkte maximal 12 Wörter. "
    "Alles auf Deutsch. Nur Inhalte, die im Material stehen oder fachlich "
    "gesichert sind - nichts dazuerfinden."
)


def baue_mindmap(stoff, thema="", melde=None, klassenstufe=None):
    """(mindmap_dict, fehler)"""
    melde = melde or (lambda _t: None)
    fehlt = _schluessel_fehler()
    if fehlt:
        return None, fehlt
    melde("Ordne den Stoff zu einer Mindmap ...")
    frage = _stufen_hinweis(klassenstufe) + \
            (f"Thema: {thema}\n\n" if thema else "") + \
            f"Material:\n{kuerze(stoff, 9000)}\n\nBaue daraus die Mindmap."
    daten = gemini_verbindung.extrahiere_json(frage, MINDMAP_SYSTEM)
    if not isinstance(daten, dict) or not daten.get("aeste"):
        return None, "Das Modell hat keine brauchbare Mindmap geliefert."
    daten.setdefault("thema", thema or "Thema")
    return daten, ""


# ---------------------------------------------------------------- Lernzettel

LERNZETTEL_SYSTEM = (
    "Du schreibst Lernzettel für Prüfungen. Struktur, immer auf Deutsch:\n"
    "# Titel\n"
    "## Überschrift je Abschnitt\n"
    "Fließtext, in dem die **Schlüsselbegriffe fett** stehen.\n"
    "Am Ende ein Abschnitt '## Key Takeaways' mit 4 bis 6 Stichpunkten "
    "(jede Zeile beginnt mit '- ').\n"
    "Regeln: kompakt, keine Wiederholungen, keine Einleitungsfloskeln. "
    "Nur Inhalte aus dem Material oder fachlich gesichertes Wissen."
)


def baue_lernzettel(stoff, thema="", melde=None, klassenstufe=None):
    """(markdown_text, fehler)"""
    melde = melde or (lambda _t: None)
    fehlt = _schluessel_fehler()
    if fehlt:
        return "", fehlt
    melde("Schreibe den Lernzettel ...")
    frage = _stufen_hinweis(klassenstufe) + \
            (f"Thema: {thema}\n\n" if thema else "") + \
            f"Material:\n{kuerze(stoff)}\n\nSchreibe den Lernzettel."
    try:
        text = gemini_verbindung.frage_mit_anweisung(frage, LERNZETTEL_SYSTEM)
    except Exception as fehler:
        return "", str(fehler)
    if len(text) < 80:
        return "", "Der Lernzettel ist zu dünn geraten - versuch es mit mehr Material."
    return text, ""


# ---------------------------------------------------------------- Karteikarten

KARTEN_SYSTEM = (
    "Du erstellst Karteikarten zum aktiven Abfragen. Antworte AUSSCHLIESSLICH "
    "mit JSON in dieser Form:\n"
    '{"karten": [{"frage": "...", "antwort": "...", "thema": "..."}]}\n'
    "Regeln: Die Frage prüft Verständnis, nicht bloßes Auswendiglernen. Eine "
    "Frage pro Karte, keine Sammelfragen. Die Antwort ist vollständig, aber "
    "höchstens drei Sätze. Alles auf Deutsch. Nur Inhalte aus dem Material."
)


def baue_karten(stoff, thema="", anzahl=12, melde=None, klassenstufe=None):
    """(karten_liste, fehler)"""
    melde = melde or (lambda _t: None)
    fehlt = _schluessel_fehler()
    if fehlt:
        return [], fehlt
    melde(f"Erstelle {anzahl} Karteikarten ...")
    frage = _stufen_hinweis(klassenstufe) + \
            (f"Thema: {thema}\n\n" if thema else "") + \
            f"Material:\n{kuerze(stoff)}\n\nErstelle genau {anzahl} Karteikarten."
    daten = gemini_verbindung.extrahiere_json(frage, KARTEN_SYSTEM)
    if isinstance(daten, dict):
        daten = daten.get("karten") or daten.get("cards") or []
    if not isinstance(daten, list) or len(daten) < 3:
        return [], "Das Modell hat keine brauchbaren Karteikarten geliefert."
    karten = []
    for eintrag in daten:
        if not isinstance(eintrag, dict):
            continue
        frage_text = str(eintrag.get("frage") or eintrag.get("question") or "").strip()
        antwort = str(eintrag.get("antwort") or eintrag.get("answer") or "").strip()
        if frage_text and antwort:
            karten.append(neue_karte(frage_text, antwort,
                                     str(eintrag.get("thema") or thema or "").strip()))
    if not karten:
        return [], "Die Karteikarten waren unvollständig."
    return karten, ""


# ------------------------------------------------------- Sprachfach-Vokabeln

# Anhand des Fach-Namens erkannte Sprachfaecher (Substring-Suche, klein
# geschrieben) - loest die automatische Vokabelpruefung aus (siehe
# _QuelleTab in app/screens/lernen_screen.py).
_SPRACHFAECHER = (
    "französisch", "franzosisch", "englisch", "spanisch", "latein",
    "italienisch", "russisch", "türkisch", "turkisch", "arabisch",
    "chinesisch", "japanisch", "niederländisch", "niederlaendisch",
    "portugiesisch", "polnisch", "griechisch", "schwedisch",
)


def erkenne_sprachfach(fach_name):
    """Liefert den erkannten Sprachnamen (klein geschrieben), oder "" wenn
    der Fach-Name keine bekannte Fremdsprache erkennen laesst."""
    name = (fach_name or "").strip().lower()
    for sprache in _SPRACHFAECHER:
        if sprache in name:
            return sprache
    return ""


def _vokabel_pruefung_system(sprache):
    return (
        f"Du bist Sprachlehrer/in für {sprache.capitalize()}. Der Nutzer hat einen Text "
        f"oder eine Vokabelliste eingereicht. Prüfe JEDES enthaltene Wort/jede Phrase in "
        f"der Fremdsprache ({sprache.capitalize()}) auf Rechtschreibung und Grammatik, und "
        "- falls eine deutsche Übersetzung danebensteht - auch auf deren Richtigkeit.\n"
        "Antworte AUSSCHLIESSLICH mit JSON in dieser Form:\n"
        '{"karten": [{"frage": "korrektes fremdsprachiges Wort/Phrase", '
        '"antwort": "korrekte deutsche Übersetzung", "thema": "..."}]}\n'
        "Regeln: Korrigiere Rechtschreib-/Grammatikfehler in der Frage DIREKT (kein "
        "Hinweis nötig, einfach die richtige Schreibweise). War die im Material "
        "angegebene Übersetzung falsch, nimm in der Antwort die RICHTIGE Übersetzung, "
        'ergänze aber in Klammern \'(im Material stand: "<falsche Übersetzung>")\', '
        "damit der Lernende seinen Fehler sieht. Nur echte Vokabeln/kurze Wendungen als "
        "eigene Karte, keine ganzen Fließtext-Sätze wiederholen, keine Duplikate. Alles "
        "auf Deutsch außer der Fremdsprache selbst."
    )


def pruefe_vokabeln(text, sprache, melde=None, klassenstufe=None):
    """
    (karten_liste, fehler) - prueft eine Vokabelliste/einen Text in einer
    Fremdsprache auf Rechtschreibung/Grammatik/Uebersetzung und liefert das
    Ergebnis direkt als Karteikarten-Liste (siehe neue_karte()), bereit zum
    Uebernehmen in fach["karten"].
    """
    melde = melde or (lambda _t: None)
    fehlt = _schluessel_fehler()
    if fehlt:
        return [], fehlt
    melde(f"Prüfe Vokabeln ({sprache}) ...")
    frage = _stufen_hinweis(klassenstufe) + \
            f"Material:\n{kuerze(text)}\n\nPrüfe die Vokabeln."
    daten = gemini_verbindung.extrahiere_json(frage, _vokabel_pruefung_system(sprache))
    if isinstance(daten, dict):
        daten = daten.get("karten") or []
    if not isinstance(daten, list) or not daten:
        return [], "Das Modell hat keine brauchbaren Vokabeln geliefert."
    karten = []
    for eintrag in daten:
        if not isinstance(eintrag, dict):
            continue
        frage_text = str(eintrag.get("frage") or "").strip()
        antwort = str(eintrag.get("antwort") or "").strip()
        if frage_text and antwort:
            karten.append(neue_karte(frage_text, antwort,
                                     str(eintrag.get("thema") or sprache).strip()))
    if not karten:
        return [], "Die Vokabelprüfung ergab keine verwertbaren Karten."
    return karten, ""


# ---------------------------------------------------------------- Lückentext

LUECKENTEXT_SYSTEM = (
    "Du erstellst Lückentexte zum Üben. Antworte AUSSCHLIESSLICH mit JSON in "
    "dieser Form:\n"
    '{"titel": "...", "text": "Ein zusammenhängender Fließtext mit Lücken, '
    'jede Lücke als ___1___, ___2___ usw. durchnummeriert.", '
    '"luecken": {"1": "richtige Lösung", "2": "richtige Lösung"}}\n'
    "Regeln: 8 bis 14 Lücken, immer die wichtigsten Fachbegriffe, Namen oder "
    "Zahlen. Der Text bleibt beim Lesen OHNE Lücken sinnvoll und "
    "zusammenhängend, kein Stichwortstil und keine Aufzählung. Jede Lösung "
    "ist ein einzelnes Wort oder eine kurze Wortgruppe (höchstens 4 Wörter). "
    "Alles auf Deutsch. Nur Inhalte aus dem Material oder fachlich "
    "gesichertes Wissen - nichts dazuerfinden."
)


def baue_luckentext(stoff, thema="", melde=None, klassenstufe=None):
    """(luckentext_dict, fehler) - dict mit 'titel', 'text', 'luecken'."""
    melde = melde or (lambda _t: None)
    fehlt = _schluessel_fehler()
    if fehlt:
        return None, fehlt
    melde("Baue den Lückentext ...")
    frage = _stufen_hinweis(klassenstufe) + \
            (f"Thema: {thema}\n\n" if thema else "") + \
            f"Material:\n{kuerze(stoff)}\n\nErstelle daraus den Lückentext."
    daten = gemini_verbindung.extrahiere_json(frage, LUECKENTEXT_SYSTEM)
    brauchbar = (isinstance(daten, dict) and isinstance(daten.get("text"), str)
                and isinstance(daten.get("luecken"), dict) and len(daten["luecken"]) >= 3
                and "___1___" in daten["text"])
    if not brauchbar:
        return None, "Das Modell hat keinen brauchbaren Lückentext geliefert."
    daten.setdefault("titel", thema or "Lückentext")
    # Schluessel als Text - kommen aus JSON manchmal als Zahl zurueck.
    daten["luecken"] = {str(k): str(v) for k, v in daten["luecken"].items()}
    return daten, ""


# ---------------------------------------------------------------- SM-2

def neue_karte(frage, antwort, thema=""):
    return {"id": f"{int(time.time() * 1000)}-{abs(hash(frage)) % 100000}",
            "frage": frage, "antwort": antwort, "thema": thema,
            "faktor": 2.5, "intervall": 0, "wiederholungen": 0,
            "faellig": time.time(), "zuletzt": 0.0, "richtig": 0, "falsch": 0}


# Bewertung -> Qualitaet nach SM-2 (0..5)
BEWERTUNG = {"leicht": 5, "mittel": 3, "schwer": 1}


def bewerte_karte(karte, bewertung):
    """
    Aktualisiert eine Karte nach dem SM-2-Verfahren.
    "leicht" schiebt sie weit nach hinten, "schwer" holt sie sofort zurueck.
    """
    qualitaet = BEWERTUNG.get(str(bewertung).lower(), 3)
    karte["zuletzt"] = time.time()
    if qualitaet >= 3:
        karte["richtig"] = karte.get("richtig", 0) + 1
        if karte.get("wiederholungen", 0) == 0:
            karte["intervall"] = 1
        elif karte["wiederholungen"] == 1:
            karte["intervall"] = 6
        else:
            karte["intervall"] = max(1, round(karte["intervall"] * karte["faktor"]))
        karte["wiederholungen"] = karte.get("wiederholungen", 0) + 1
    else:
        karte["falsch"] = karte.get("falsch", 0) + 1
        karte["wiederholungen"] = 0
        karte["intervall"] = 0          # noch heute nochmal

    faktor = karte.get("faktor", 2.5) + (0.1 - (5 - qualitaet) * (0.08 + (5 - qualitaet) * 0.02))
    karte["faktor"] = max(1.3, round(faktor, 3))
    karte["faellig"] = time.time() + karte["intervall"] * 86400
    return karte


def faellige_karten(karten, jetzt=None):
    jetzt = jetzt or time.time()
    return [k for k in karten if k.get("faellig", 0) <= jetzt]


def statistik(karten):
    """(gesamt, faellig, gelernt, quote) - fuer die Anzeige."""
    gesamt = len(karten)
    faellig = len(faellige_karten(karten))
    gelernt = sum(1 for k in karten if k.get("wiederholungen", 0) >= 2)
    richtig = sum(k.get("richtig", 0) for k in karten)
    falsch = sum(k.get("falsch", 0) for k in karten)
    quote = round(richtig / (richtig + falsch) * 100) if (richtig + falsch) else 0
    return gesamt, faellig, gelernt, quote


# ---------------------------------------------------------------- Pruefer

PRUEFER_FRAGE_SYSTEM = (
    "Du bist Prüfer in einer mündlichen Prüfung. Stelle GENAU EINE Frage zum "
    "Stoff - offen formuliert, sodass der Prüfling erklären muss, nicht nur ein "
    "Wort nennt. Keine Einleitung, keine Nummerierung, nur die Frage selbst. "
    "Auf Deutsch, höchstens zwei Sätze."
)

PRUEFER_BEWERTUNG_SYSTEM = (
    "Du bewertest die Antwort eines Prüflings in einer mündlichen Prüfung.\n"
    "Vergib zuerst PUNKTE von 0 bis 10:\n"
    "  10 = vollständig und fachlich richtig\n"
    "   7 = im Kern richtig, Einzelheiten fehlen\n"
    "   4 = teilweise richtig oder am Thema vorbei\n"
    "   1 = fast nichts Richtiges\n"
    "   0 = falsch oder keine Antwort\n"
    "Antworte AUSSCHLIESSLICH mit JSON, genau diese Schlüssel:\n"
    '{"punkte": <0-10>, "richtig": [...], "fehlt": [...], "feedback": "...", '
    '"musterantwort": "..."}\n'
    "WICHTIG: Setze überall echte Inhalte ein - schreibe niemals Platzhalter "
    "wie '...' ab.\n"
    "richtig: was der Prüfling tatsächlich korrekt gesagt hat (leer, wenn nichts).\n"
    "fehlt: was zur vollständigen Antwort fehlt.\n"
    "feedback: zwei bis drei Sätze, konstruktiv und konkret.\n"
    "musterantwort: die richtige Antwort in zwei bis drei Sätzen.\n"
    "Alles auf Deutsch."
)

# 10 Punkte = 1,0 ... 0 Punkte = 6,0. Die Note wird aus den Punkten gerechnet,
# weil Modelle die deutsche Skala gern verdrehen (kleine Zahl = gut).
PUNKTE_ZU_NOTE = {10: 1.0, 9: 1.3, 8: 1.7, 7: 2.3, 6: 2.7,
                  5: 3.3, 4: 3.7, 3: 4.3, 2: 4.7, 1: 5.3, 0: 6.0}

_PLATZHALTER = ("was saß", "was sass", "was fehlte", "...", "…", "kurz",
                "zwei bis drei sätze konstruktiv", "string", "text")


def _echte_liste(werte):
    """Platzhalter aus dem Beispielschema aussortieren."""
    sauber = []
    for wert in werte or []:
        text = str(wert).strip()
        if text and text.lower() not in _PLATZHALTER:
            sauber.append(text)
    return sauber


def naechste_frage(stoff, thema="", gestellt=(), melde=None, klassenstufe=None):
    """(frage, fehler)"""
    fehlt = _schluessel_fehler()
    if fehlt:
        return "", fehlt
    bisher = "\n".join(f"- {f}" for f in list(gestellt)[-6:])
    frage = _stufen_hinweis(klassenstufe) + \
            (f"Thema: {thema}\n\n" if thema else "") + \
            f"Stoff:\n{kuerze(stoff, 6000)}\n\n" + \
            (f"Diese Fragen wurden schon gestellt, stelle eine andere:\n{bisher}\n\n"
             if bisher else "") + "Stelle die nächste Prüfungsfrage."
    try:
        text = gemini_verbindung.frage_mit_anweisung(frage, PRUEFER_FRAGE_SYSTEM)
    except Exception as fehler:
        return "", str(fehler)
    text = text.strip().strip('"').split("\n")[0].strip()
    if not text:
        return "", "Das Modell hat keine Frage geliefert."
    return text, ""


def bewerte_antwort(frage, antwort, stoff="", klassenstufe=None):
    """(bewertung_dict, fehler)"""
    fehlt = _schluessel_fehler()
    if fehlt:
        return None, fehlt
    nutzer = _stufen_hinweis(klassenstufe) + \
             (f"Stoff:\n{kuerze(stoff, 5000)}\n\n" if stoff else "") + \
             f"Frage: {frage}\n\nAntwort des Prüflings: {antwort}\n\nBewerte."
    daten = gemini_verbindung.extrahiere_json(nutzer, PRUEFER_BEWERTUNG_SYSTEM)
    if not isinstance(daten, dict) or "punkte" not in daten:
        return None, "Das Modell hat keine brauchbare Bewertung geliefert."
    try:
        daten["punkte"] = max(0, min(10, int(round(float(daten.get("punkte", 5))))))
    except Exception:
        daten["punkte"] = 5

    # Die Note kommt aus den Punkten, nicht aus dem Modell.
    daten["note"] = PUNKTE_ZU_NOTE[daten["punkte"]]

    for feld in ("richtig", "fehlt"):
        wert = daten.get(feld)
        daten[feld] = _echte_liste([wert] if isinstance(wert, str) else wert)
    for feld in ("feedback", "musterantwort"):
        wert = str(daten.get(feld, "")).strip()
        daten[feld] = "" if wert.lower() in _PLATZHALTER else wert
    if not daten["feedback"]:
        daten["feedback"] = ("Das Modell hat kein Feedback geliefert - die Punktzahl "
                             "steht aber.")
    return daten, ""


def notentext(note):
    """1.3 -> 'sehr gut (1,3)'"""
    stufen = ((1.5, "sehr gut"), (2.5, "gut"), (3.5, "befriedigend"),
              (4.5, "ausreichend"), (5.5, "mangelhaft"), (6.1, "ungenügend"))
    for grenze, wort in stufen:
        if note < grenze:
            return f"{wort} ({note:.1f})".replace(".", ",")
    return f"ungenügend ({note:.1f})".replace(".", ",")


# ---------------------------------------------------------------- Ablage

def _lese_json(pfad, standard=None):
    if not os.path.exists(pfad):
        return standard
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            return json.load(datei)
    except Exception:
        return standard


def _schreibe_json(pfad, daten):
    try:
        with open(pfad, "w", encoding="utf-8") as datei:
            json.dump(daten, datei, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[Lernen] Konnte nicht gespeichert werden: {exc}")


def _ordner():
    """Schreibbarer Ort fuer die Kurse/Faecher-Ablage - derselbe App-
    Datenordner wie kern/speicher.py fuer den Chatverlauf."""
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None:
            ordner = os.path.join(app.user_data_dir, "lernen")
            os.makedirs(ordner, exist_ok=True)
            return ordner
    except Exception:
        pass
    return "."


def _kurse_ablage(benutzer):
    sicher = re.sub(r"[^A-Za-z0-9_.-]", "_", benutzer or "gast")
    return os.path.join(_ordner(), f"{sicher}_kurse.json")


def _neue_id(vorsatz):
    return f"{vorsatz}{int(time.time() * 1000)}{os.urandom(2).hex()}"


def neues_fach(name):
    return {"id": _neue_id("f"), "name": (name or "Neues Fach").strip()[:60] or "Neues Fach",
            "erstellt": time.strftime("%Y-%m-%d"), "thema": "", "quellen": [],
            "zusammenfassung": "", "luckentext": None, "mindmap": None, "karten": []}


def neuer_kurs(name, klassenstufe=8):
    return {"id": _neue_id("k"), "name": (name or "Neuer Kurs").strip()[:60] or "Neuer Kurs",
            "erstellt": time.strftime("%Y-%m-%d"), "faecher": [],
            "klassenstufe": max(1, min(12, int(klassenstufe or 8)))}


def effektive_klassenstufe(klassenstufe):
    """
    Berliner Anforderungsniveau: ab Klasse 5 gilt "Uranus Klasse N" fachlich
    als Anforderungsniveau "Klasse N+1" (Berliner Schulsystem-Konvention,
    vom Nutzer so vorgegeben) - alle Aufgaben/Karten/Fragen/Mindmaps sollen
    entsprechend eine Stufe schwerer ausfallen, sobald die gewaehlte
    Klassenstufe 5 oder hoeher ist.
    """
    stufe = max(1, min(12, int(klassenstufe or 8)))
    return stufe + 1 if stufe >= 5 else stufe


def _stufen_hinweis(klassenstufe):
    """Ein Kontextsatz fuers Modell, IMMER genau EINMAL vor Thema/Material
    gestellt - keine eigene System-Anweisung noetig, dieselbe Anweisung
    passt fuer alle vier Werkzeuge (Mindmap/Lernzettel/Karten/Luecken/
    Pruefung)."""
    if not klassenstufe:
        return ""
    effektiv = effektive_klassenstufe(klassenstufe)
    return (f"Zielstufe: Klasse {effektiv} (Anforderungsniveau). Passe Wortwahl, "
            f"Komplexitaet und Aufgabenschwierigkeit GENAU auf dieses Niveau an - "
            f"nicht leichter, nicht schwerer.\n\n")


def lade_kurse(benutzer):
    """{"kurse": [{"id","name","erstellt","faecher": [...]}]}"""
    daten = _lese_json(_kurse_ablage(benutzer), None)
    if not isinstance(daten, dict):
        daten = {}
    daten.setdefault("kurse", [])
    return daten


def speichere_kurse(benutzer, daten):
    _schreibe_json(_kurse_ablage(benutzer), daten)


def kurs_hinzufuegen(benutzer, name, klassenstufe=8):
    daten = lade_kurse(benutzer)
    kurs = neuer_kurs(name, klassenstufe)
    daten["kurse"].append(kurs)
    speichere_kurse(benutzer, daten)
    return kurs


def kurs_loeschen(benutzer, kurs_id):
    daten = lade_kurse(benutzer)
    daten["kurse"] = [k for k in daten["kurse"] if k.get("id") != kurs_id]
    speichere_kurse(benutzer, daten)


def fach_hinzufuegen(benutzer, kurs_id, name):
    daten = lade_kurse(benutzer)
    for kurs in daten["kurse"]:
        if kurs.get("id") == kurs_id:
            fach = neues_fach(name)
            kurs["faecher"].append(fach)
            speichere_kurse(benutzer, daten)
            return fach
    return None


def fach_loeschen(benutzer, kurs_id, fach_id):
    daten = lade_kurse(benutzer)
    for kurs in daten["kurse"]:
        if kurs.get("id") == kurs_id:
            kurs["faecher"] = [f for f in kurs["faecher"] if f.get("id") != fach_id]
    speichere_kurse(benutzer, daten)


def fach_speichern(benutzer, kurs_id, fach):
    """Ein komplettes Fach-Dict ersetzen - nach Quelle hinzufuegen oder Generieren."""
    daten = lade_kurse(benutzer)
    for kurs in daten["kurse"]:
        if kurs.get("id") == kurs_id:
            for index, vorhanden in enumerate(kurs["faecher"]):
                if vorhanden.get("id") == fach.get("id"):
                    kurs["faecher"][index] = fach
                    speichere_kurse(benutzer, daten)
                    return
    speichere_kurse(benutzer, daten)


def finde_fach(kurse_daten, kurs_id, fach_id):
    for kurs in kurse_daten.get("kurse", []):
        if kurs.get("id") == kurs_id:
            for fach in kurs.get("faecher", []):
                if fach.get("id") == fach_id:
                    return kurs, fach
    return None, None


def fach_stoff(fach):
    """Alle Quellen eines Fachs zu einem Text zusammenfuehren, mit Herkunft je Abschnitt."""
    teile = []
    for quelle in (fach or {}).get("quellen", []):
        kopf = f"### Quelle: {quelle.get('name', 'unbenannt')}"
        teile.append(f"{kopf}\n{quelle.get('text', '')}")
    return "\n\n".join(teile).strip()
