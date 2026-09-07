# -*- coding: utf-8 -*-
"""
Gemeinsames "Sci-Fi-HUD"-Design fuer die ganze App: akzentgefaerbter
Hintergrund, leuchtende Kartenraender und ein dezentes Tech-Raster - angelehnt
an das Dashboard-Design der PC-Version (dunkles Panel, Neon-Rand in der
gewaehlten Akzentfarbe).

Farben werden hier bewusst als PYTHON-WERTE berechnet (keine KV-Bindung) -
sie ziehen darum beim Hell/Dunkel- oder Farbwechsel NICHT von selbst mit.
Jeder Bildschirm, der diese Funktionen nutzt, muss darum eine
aktualisiere_theme()-Methode anbieten, die app/main.py (_theme_geaendert)
nach jedem Wechsel aufruft - siehe dort.
"""
from kivy.graphics import Color, Line
from kivy.uix.widget import Widget

# ----------------------------------------------------------------------
# Farben
# ----------------------------------------------------------------------
_BASIS_HINTERGRUND = {"Dark": (0.03, 0.05, 0.08, 1), "Light": (0.97, 0.98, 0.99, 1)}
_BASIS_KARTE = {"Dark": (0.05, 0.07, 0.10, 1), "Light": (0.93, 0.95, 0.96, 1)}
_SPUR = {"Dark": (1, 1, 1, 0.08), "Light": (0, 0, 0, 0.08)}


def _mischen(basis, akzent, anteil):
    return tuple(basis[i] * (1 - anteil) + akzent[i] * anteil for i in range(3)) + (1,)


def hintergrund_getoent(theme, anteil=0.09):
    """App-weiter Hintergrund: sehr dunkles/helles Neutral mit einem leichten
    Stich der gewaehlten Akzentfarbe - wechselt die Akzentfarbe (siehe
    settings_screen.py), zieht der ganze Hintergrund sichtbar mit, statt wie
    zuvor komplett neutral zu bleiben."""
    return _mischen(_BASIS_HINTERGRUND[theme.theme_style], theme.primaryColor, anteil)


def hintergrund(theme, anteil=0.16):
    """Kartenhintergrund - etwas staerker eingefaerbt als der Hintergrund
    dahinter, damit sich Karten sichtbar (aber dezent) davon abheben."""
    return _mischen(_BASIS_KARTE[theme.theme_style], theme.primaryColor, anteil)


def spur(theme):
    return _SPUR[theme.theme_style]


def volle_breite(knopf):
    """
    Laesst einen MDButton die volle Breite seines Containers einnehmen -
    statt KivyMDs eigener automatischer Breitenberechnung zu vertrauen.

    Grund: MDButton berechnet seine Breite passend zum Text erst 0.2s NACH
    dem Erzeugen (Clock.schedule_once(self.adjust_width, 0.2), einmalig).
    Liegt der Knopf zu diesem Zeitpunkt auf einem Bildschirm, der gerade
    NICHT der sichtbare ScreenManager-Reiter ist (z.B. Einstellungen/Login,
    die schon beim App-Start im Hintergrund gebaut werden, aber erst beim
    Reiterwechsel angezeigt werden) - hat sein Text-Label noch keine
    berechnete Groesse (texture_size bleibt (0, 0)), und die Breite friert
    bei einem viel zu kleinen Wert ein (48dp - nur die eingebauten Text-
    Innenabstaende). Der Text ragt danach dauerhaft ueber den sichtbaren
    Knopf hinaus (live so gemeldet: "glitcht"/"wird verdeckt"). Passiert nur
    einmalig, ein spaeterer Bildschirmwechsel repariert das NICHT mehr.

    theme_width="Custom" schaltet KivyMDs eigene Breitenlogik komplett ab,
    size_hint_x=1 laesst den Knopf stattdessen zuverlaessig die Breite
    seines Containers uebernehmen (hier: die ganze Karte) - unabhaengig
    davon, ob/wann der Bildschirm sichtbar wird.
    """
    knopf.theme_width = "Custom"
    knopf.size_hint_x = 1


def glow_anwenden(karte, theme, staerke=3, deckkraft=0.6):
    """
    Legt einen leuchtenden Schatten in der Akzentfarbe um eine Karte -
    Neon-Rand-Optik statt flacher Flaeche.

    WICHTIG: braucht style="elevated" auf der Karte. KivyMDs eigene
    card.kv-Regel setzt shadow_color bei style="filled"/"outlined" HART auf
    theme_cls.transparentColor - "Custom" wird dort ignoriert, das
    "Custom"-Schluesselloch fuer eine eigene Farbe existiert nur bei
    style="elevated" (live erst per Debug-Ausgabe gefunden: shadow_color
    blieb (0,0,0,0), obwohl explizit gesetzt). theme_line_color="Custom"
    ist noetig, weil dieselbe Regel den Kartenrand bei style="elevated"
    sonst ebenfalls auf transparent zwingt.
    """
    karte.theme_line_color = "Custom"
    karte.theme_shadow_color = "Custom"
    karte.shadow_color = (*theme.primaryColor[:3], deckkraft)
    karte.theme_shadow_offset = "Custom"
    karte.shadow_offset = (0, 0)
    karte.theme_shadow_softness = "Custom"
    karte.shadow_softness = 4
    karte.theme_elevation_level = "Custom"
    karte.elevation_level = staerke


# ----------------------------------------------------------------------
# Tech-Raster: dezentes, futuristisches Punktgitter hinter der ganzen App -
# rein dekorativ, wie ein Schaltplan/Radar-Hintergrund. Sitzt als erstes
# (unterstes) Kind im aeusseren Rahmen (siehe app/main.py), scheint also nur
# durch die Luecken der Bildschirme/Karten davor durch.
# ----------------------------------------------------------------------
class TechRaster(Widget):
    _ABSTAND = 40  # px zwischen den Punkten

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._farbe_werte = (1, 1, 1, 0.05)
        self.bind(pos=self._neu_zeichnen, size=self._neu_zeichnen)

    def aktualisiere_theme(self, theme):
        self._farbe_werte = (*theme.primaryColor[:3], 0.07)
        self._neu_zeichnen()

    def _neu_zeichnen(self, *_args):
        self.canvas.remove_group("tech_raster")
        if self.width <= 0 or self.height <= 0:
            return
        with self.canvas:
            Color(*self._farbe_werte, group="tech_raster")
            x = self.x
            while x <= self.right:
                Line(points=[x, self.y, x, self.top], width=0.6, group="tech_raster")
                x += self._ABSTAND
            y = self.y
            while y <= self.top:
                Line(points=[self.x, y, self.right, y], width=0.6, group="tech_raster")
                y += self._ABSTAND
