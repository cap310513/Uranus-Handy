# -*- coding: utf-8 -*-
"""
Gemeinsame HUD-Kartenfarben fuer Briefing- und Einstellungen-Reiter.

Beide Reiter faerben ihre Karten bewusst NICHT mit KivyMDs eigenen
Standardfarben (surfaceContainer & Co.), sondern mit einem eigenen, festen
HUD-Look: sehr dunkles Navy mit leuchtendem Rand in der Akzentfarbe (Dark),
ein sehr helles Neutral mit demselben Rand in Light.

Weil diese Farbe als fester Python-Wert gesetzt wird (keine KV-Bindung),
zieht sie beim Hell/Dunkel-Umschalten NICHT von selbst mit - anders als
KivyMDs eigene Widgets (MDTextField, Standard-MDCard etc.), die ihre Farben
ueber interne KV-Regeln beziehen und darum automatisch reagieren. Genau das
war der gemeldete Fehler: der Hintergrund blieb beim Wechsel in den hellen
Modus dunkel, nur eingebaute Widgets wurden hell.

Siehe app/main.py (_theme_geaendert) - dort wird nach jedem Themenwechsel
aktualisiere_theme() auf beiden Reitern aufgerufen, die wiederum diese
Funktionen hier neu abfragen.
"""

_HINTERGRUND = {
    "Dark": (0.03, 0.05, 0.09, 1),
    "Light": (0.95, 0.96, 0.99, 1),
}
_SPUR = {
    "Dark": (1, 1, 1, 0.08),
    "Light": (0, 0, 0, 0.08),
}


def hintergrund(theme):
    return _HINTERGRUND[theme.theme_style]


def spur(theme):
    return _SPUR[theme.theme_style]
