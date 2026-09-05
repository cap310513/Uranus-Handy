# Uranus Mobile — Meilenstein 1

Eigenständiges Projekt für die Android-Version von Uranus. Komplett getrennt vom
PC-Ordner (`Uranus/`) — keine gemeinsamen Dateien, keine Imports zwischen den beiden.

In diesem Meilenstein läuft die App noch **auf dem PC**, in einem auf Handygröße
verkleinerten Fenster (kein Android-Gerät nötig). Der echte Android-Build kommt als
eigener, späterer Meilenstein.

## Was ist schon drin

- Zwei Reiter: **Daily Briefing** (Platzhalter) und **Chat** (voll funktionsfähig, echte
  Gemini-Antworten, Verlauf wird gespeichert)
- Eigene, isolierte Python-Umgebung (`venv/`)

## API-Key einrichten (Schritt für Schritt)

Die App braucht einen Gemini-API-Key, um wirklich antworten zu können. Der ist
**kostenlos** — keine Kreditkarte nötig.

1. Öffne [aistudio.google.com](https://aistudio.google.com) und melde dich mit deinem
   Google-Konto an.
2. Klicke links auf **"Get API key"**.
3. Klicke auf **"Create API key"**.
4. Wähle ein bestehendes Projekt oder lass eines neu anlegen — das ist egal.
5. Kopiere den Schlüssel (beginnt mit `AIza...`).
6. Im Projektordner liegt eine Datei `.env.example`. Mache davon eine Kopie namens
   `.env` (ohne ".example") im selben Ordner.
7. Öffne die neue `.env`-Datei in einem Texteditor und ersetze
   `hier_deinen_schluessel_einfuegen` durch deinen kopierten Schlüssel. Speichern.

Fertig. Die `.env`-Datei wird nie in Git gespeichert (steht in `.gitignore`) und bleibt
nur auf deinem Rechner.

**Kostenloser Tarif**: Aktuell (Stand 2026) erlaubt der kostenlose Tarif ungefähr 10
Anfragen pro Minute und 500 pro Tag für das genutzte Modell (`gemini-3.6-flash`) — für
normales Chatten mehr als genug. Solange du in Google AI Studio keine Bezahlung
aktivierst, kann nichts kosten.

## Meilenstein 1 starten

```bash
venv\Scripts\python.exe app\main.py
```

Es öffnet sich ein Fenster in Handygröße. Im Reiter "Chat" kannst du direkt eine echte
Frage stellen.

## Ordnerübersicht

```
kern/                   <- Logik ohne Oberfläche (Gemini-Anbindung, Speicherung)
app/                    <- Kivy/KivyMD-Oberfläche
  main.py               <- Startpunkt
  screens/               <- Die beiden Reiter
chat_verlauf.json        <- wird automatisch angelegt, Gesprächsverlauf
```

## Was noch fehlt (bewusst spätere Meilensteine)

- Echter Android-Build (braucht WSL2 unter Windows + mehrere GB Downloads —
  eigener Meilenstein mit eigener Erlaubnis-Anfrage)
- Test auf dem echten Samsung-Handy
- Hintergrund-Zugriff auf andere Apps (WhatsApp usw.)
- Echte Inhalte im "Daily Briefing"-Reiter
