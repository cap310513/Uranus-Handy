# -*- coding: utf-8 -*-
"""
Einfaches Konto-System: Registrieren, Anmelden, "Angemeldet bleiben".

Eigenstaendig geschrieben (Regel 5), nach demselben Sicherheitsprinzip wie die
PC-Version (uranus_tools.py, Abschnitt URANUS_ACCOUNTS): Passwoerter werden
NIE im Klartext gespeichert, nur ein PBKDF2-HMAC-SHA256-Hash mit eigenem Salt
pro Nutzer. Fuer "angemeldet bleiben" liegt nur ein Zufallstoken auf dem
Geraet, dessen Pruefsumme beim Konto hinterlegt ist - nicht das Token selbst
und nicht das Passwort.

Nutzt ausschliesslich die Python-Standardbibliothek - keine neue Abhaengigkeit.
"""
import hashlib
import json
import os
import re
import secrets
import time

PBKDF2_ROUNDS = 200_000
_NAME_MUSTER = re.compile(r"^[A-Za-z0-9_.\-äöüÄÖÜß ]{3,24}$")


def _ordner():
    """Schreibbarer App-Datenordner - siehe kern/speicher.py fuer denselben
    Grundsatz (auf Android ist der Projektordner selbst schreibgeschuetzt)."""
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None:
            os.makedirs(app.user_data_dir, exist_ok=True)
            return app.user_data_dir
    except Exception:
        pass
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _konten_datei():
    return os.path.join(_ordner(), "konten.json")


def _sitzung_datei():
    return os.path.join(_ordner(), "sitzung.json")


def _lies_json(pfad, ersatz):
    if os.path.exists(pfad):
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return ersatz


def _schreibe_json(pfad, daten):
    tmp = pfad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)
    os.replace(tmp, pfad)


def _hash_passwort(passwort, salt_hex):
    digest = hashlib.pbkdf2_hmac(
        "sha256", passwort.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ROUNDS
    )
    return digest.hex()


def _fingerabdruck(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def lade_konten():
    return _lies_json(_konten_datei(), {})


def konto_vorhanden():
    """Gibt es ueberhaupt schon ein Konto? (fuer die Startlogik in main.py)"""
    return bool(lade_konten())


def registrieren(name, passwort, passwort_wiederholung):
    """Legt ein neues Konto an. Rueckgabe: (erfolg, meldung)."""
    name = name.strip()
    if not _NAME_MUSTER.match(name):
        return False, "Name: 3-24 Zeichen, Buchstaben/Zahlen/._- erlaubt."
    if len(passwort) < 6:
        return False, "Das Passwort braucht mindestens 6 Zeichen."
    if passwort != passwort_wiederholung:
        return False, "Die beiden Passwörter stimmen nicht überein."

    konten = lade_konten()
    if name.lower() in {k.lower() for k in konten}:
        return False, "Diesen Namen gibt es schon."

    salt = secrets.token_hex(16)
    konten[name] = {
        "salt": salt,
        "hash": _hash_passwort(passwort, salt),
        "erstellt": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _schreibe_json(_konten_datei(), konten)
    return True, f"Konto '{name}' wurde angelegt."


def anmelden(name, passwort):
    """Prueft die Anmeldedaten. Rueckgabe: (erfolg, meldung_oder_name)."""
    konten = lade_konten()
    treffer = next((k for k in konten if k.lower() == name.strip().lower()), None)
    if treffer is None:
        return False, "Diesen Namen gibt es nicht."
    eintrag = konten[treffer]
    try:
        erwartet = eintrag["hash"]
        tatsaechlich = _hash_passwort(passwort, eintrag["salt"])
    except Exception:
        return False, "Das Konto ist beschädigt."
    if not secrets.compare_digest(erwartet, tatsaechlich):
        return False, "Falsches Passwort."
    return True, treffer


def sitzung_merken(name):
    """'Angemeldet bleiben': legt ein Zufallstoken an, dessen Abdruck beim
    Konto hinterlegt wird - das Token selbst liegt nur lokal auf dem Geraet."""
    konten = lade_konten()
    treffer = next((k for k in konten if k.lower() == name.strip().lower()), None)
    if treffer is None:
        return False
    token = secrets.token_hex(32)
    konten[treffer]["merken"] = _fingerabdruck(token)
    _schreibe_json(_konten_datei(), konten)
    _schreibe_json(_sitzung_datei(), {"name": treffer, "token": token})
    return True


def gemerkter_name():
    """Prueft beim Start, ob ein gemerktes Konto vorliegt. Rueckgabe: Name oder None."""
    sitzung = _lies_json(_sitzung_datei(), {})
    name, token = sitzung.get("name"), sitzung.get("token")
    if not name or not token:
        return None
    konten = lade_konten()
    eintrag = konten.get(name)
    if not eintrag or not eintrag.get("merken"):
        sitzung_vergessen()
        return None
    if not secrets.compare_digest(eintrag["merken"], _fingerabdruck(token)):
        sitzung_vergessen()
        return None
    return name


def sitzung_vergessen():
    """Meldet vollstaendig ab: Sitzungsdatei loeschen UND den Abdruck beim
    Konto entfernen, damit ein kopiertes Token danach wertlos ist."""
    sitzung = _lies_json(_sitzung_datei(), {})
    name = sitzung.get("name")
    if name:
        konten = lade_konten()
        if name in konten and "merken" in konten[name]:
            konten[name].pop("merken", None)
            _schreibe_json(_konten_datei(), konten)
    try:
        if os.path.exists(_sitzung_datei()):
            os.remove(_sitzung_datei())
    except Exception:
        pass
