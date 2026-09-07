# -*- coding: utf-8 -*-
"""
Mindmap-Bildschirm - die interaktive Ansicht zu einer per Gemini erzeugten
Mindmap (siehe kern/lernen.py: baue_mindmap(), sowie _MindmapTab in
lernen_screen.py fuer den Erzeugen-Knopf).

Ersetzt den HTML/SVG/PyWebView-Ansatz der PC-Version (uranus_mindmap.py)
durch eine rein native Kivy-Loesung: Knoten sind kleine anklickbare Widgets
auf einem Scatter (Kivys eingebautes Ziehen/Zoomen per Finger), Kanten sind
Bezier-Linien auf einer eigenen Zeichenflaeche direkt darunter. Tippen auf
einen Ast/Wurzel-Knoten klappt ihn auf/zu, tippen auf einen Punkt-Knoten
(ohne eigene Kinder) zeigt seinen vollen Text unten als Hinweis.

Die radiale Anordnung (_lege_radial/_setze_ast) ist eine woertliche
Portierung der gleichnamigen JavaScript-Funktionen legeRadial()/setzeAst()
aus uranus_mindmap.py - Formel und Konstanten (Radius je Tiefe, Winkel-
Aufteilung nach Blattzahl) unveraendert uebernommen. Einziger Unterschied:
SVG-Koordinaten (y waechst nach unten) werden hier durch Kivy-Koordinaten
(y waechst nach oben) ersetzt - das spiegelt das Bild nur vertikal, aendert
an der Anordnung selbst nichts.
"""
import math

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.label import Label
from kivy.uix.scatter import Scatter
from kivy.uix.stencilview import StencilView
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen

from app import hud_optik

# Radius-Formel (Basis + Tiefe*Schritt) und Container-Groesse sind bewusst in
# denselben Groessenordnungen wie die JS-Vorlage (dort 150 + tiefe*135) -
# nur in dp statt CSS-Pixeln, fuer eine auf jedem Geraet gleich wirkende
# Groesse. Der Container muss gross genug sein, dass auch tief verschachtelte
# Aeste (Wurzel -> Ast -> "unter" -> "unter") noch innerhalb bleiben.
_BASIS_RADIUS = dp(120)
_RADIUS_SCHRITT = dp(105)
_MITTE = dp(1400)
_CONTAINER = _MITTE * 2


# ---------------------------------------------------------------- Baumform

def _in_knoten(mindmap):
    """Wandelt die Gemini-Mindmap-Daten ({"thema", "aeste": [...]}) in einen
    Baum mit eindeutigen IDs - woertliche Portierung von _in_knoten() aus
    uranus_mindmap.py (dort in JavaScript)."""
    zaehler = [0]

    def neu(titel, art, kinder=()):
        zaehler[0] += 1
        return {"id": zaehler[0], "titel": str(titel)[:90], "art": art,
                "kinder": list(kinder), "zu": False, "x": 0.0, "y": 0.0}

    def aus_ast(ast):
        kinder = [neu(p, "punkt") for p in (ast.get("punkte") or [])]
        kinder += [aus_ast(u) for u in (ast.get("unter") or [])]
        return neu(ast.get("titel", "..."), "ast", kinder)

    wurzel = neu(mindmap.get("thema", "Thema"), "wurzel",
                 [aus_ast(a) for a in (mindmap.get("aeste") or [])])
    # Aeste mit eigenen Kindern starten zugeklappt, damit die Karte
    # aufgeraeumt beginnt - identisch zur PC-Version.
    for knoten in _alle_knoten(wurzel):
        if knoten["art"] == "ast" and knoten["kinder"]:
            knoten["zu"] = True
    return wurzel


def _alle_knoten(knoten, liste=None):
    if liste is None:
        liste = []
    liste.append(knoten)
    for kind in knoten["kinder"]:
        _alle_knoten(kind, liste)
    return liste


def _sichtbare_kinder(knoten):
    return [] if knoten["zu"] else knoten["kinder"]


def _zaehle_blaetter(knoten):
    kinder = _sichtbare_kinder(knoten)
    if not kinder:
        return 1
    return sum(_zaehle_blaetter(k) for k in kinder)


def _lege_radial(wurzel, cx, cy):
    wurzel["x"], wurzel["y"] = cx, cy
    aeste = _sichtbare_kinder(wurzel)
    gesamt = max(1, sum(_zaehle_blaetter(a) for a in aeste))
    winkel = -math.pi / 2
    for ast in aeste:
        anteil = _zaehle_blaetter(ast) / gesamt
        mitte = winkel + anteil * math.pi * 2 / 2
        _setze_ast(ast, cx, cy, mitte, 1, anteil * math.pi * 2)
        winkel += anteil * math.pi * 2


def _setze_ast(knoten, cx, cy, winkel, tiefe, spanne):
    radius = _BASIS_RADIUS + tiefe * _RADIUS_SCHRITT
    knoten["x"] = cx + math.cos(winkel) * radius
    knoten["y"] = cy + math.sin(winkel) * radius
    kinder = _sichtbare_kinder(knoten)
    if not kinder:
        return
    gesamt = max(1, sum(_zaehle_blaetter(k) for k in kinder))
    start = winkel - spanne / 2
    for kind in kinder:
        anteil = _zaehle_blaetter(kind) / gesamt
        _setze_ast(kind, cx, cy, start + anteil * spanne / 2, tiefe + 1, anteil * spanne * 0.9)
        start += anteil * spanne


def _sichtbare_inhalte(baum):
    """Liefert (sichtbare_knoten, kanten) in einem Rutsch - ein zugeklappter
    Knoten liefert schlicht keine Kinder (siehe _sichtbare_kinder), darum
    reicht hier eine einzige Traversierung ab der Wurzel statt (wie in der
    JS-Vorlage) ein getrennter istSichtbar()-Check pro Knoten."""
    knoten, kanten = [], []

    def gehe(k):
        knoten.append(k)
        for kind in _sichtbare_kinder(k):
            kanten.append((k, kind))
            gehe(kind)

    gehe(baum)
    return knoten, kanten


# ---------------------------------------------------------------- Farben

def _farben(theme):
    """
    Liefert ausschliesslich UNDURCHSICHTIGE (Alpha=1) Farben.

    Grund: mit Alpha<1 verschwanden auf dem Testgeraet (Xvfb + llvmpipe-
    Softwarerenderer) einzelne Kanten-Linien scheinbar zufaellig (mal 2 von
    5, mal 1 von 5 sichtbar) - live per Screenshot-Vergleich gefunden und
    isoliert: sobald alle Farben hier auf Alpha=1 gezwungen wurden, waren
    ausnahmslos alle Kanten wieder da. Vermutlich ein Blending-/Batching-
    Artefakt des Softwarerenderers bei vielen ueberlappenden halbtrans-
    parenten Formen - undurchsichtige Farben umgehen das Risiko komplett,
    ohne die Optik spuerbar einzuschraenken.
    """
    akzent = theme.primaryColor
    return {
        "kante": (*theme.outlineColor[:3], 1),
        "kante_wurzel": (*akzent[:3], 1),
        "fuellung_wurzel": (*akzent[:3], 1),
        "fuellung_ast": hud_optik.hintergrund(theme, anteil=0.30),
        "fuellung_punkt": hud_optik.hintergrund_getoent(theme, anteil=0.05),
        "rand_wurzel": (*akzent[:3], 1),
        "rand_ast": (*akzent[:3], 1),
        "rand_punkt": (*theme.outlineColor[:3], 1),
        "text": (*theme.onSurfaceColor[:3], 1),
        "textauf": (*theme.onPrimaryColor[:3], 1),
    }


# ---------------------------------------------------------------- Knoten-Widget

class _MindKnoten(ButtonBehavior, Label):
    """Ein einzelner Mindmap-Knoten - Kasten aus Canvas-Instruktionen (statt
    KivyMD-Karte, wegen der individuellen Groesse je Titellaenge) plus Text,
    anklickbar zum Auf-/Zuklappen. Groessenformel identisch zur JS-Vorlage
    (dort SVG rect+text): Breite waechst mit der Titellaenge, Hoehe je nach
    Knotenart (Wurzel/Ast/Punkt)."""

    def __init__(self, knoten, farben, auf_klick, **kwargs):
        art = knoten["art"]
        schrift = sp(16) if art == "wurzel" else (sp(13) if art == "ast" else sp(11.5))
        breite = max(dp(72), len(knoten["titel"]) * schrift * 0.6 + dp(28))
        hoehe = dp(44) if art == "wurzel" else (dp(36) if art == "ast" else dp(30))
        text_farbe = farben["textauf"] if art == "wurzel" else farben["text"]
        super().__init__(
            text=knoten["titel"], font_size=schrift, bold=art != "punkt",
            color=text_farbe, halign="center", valign="middle",
            size_hint=(None, None), size=(breite, hoehe), **kwargs,
        )
        self.text_size = (breite - dp(14), hoehe)
        self.center = (knoten["x"], knoten["y"])
        self._knoten = knoten
        self._auf_klick = auf_klick

        radius = hoehe / 2
        with self.canvas.before:
            Color(*farben[f"fuellung_{art}"])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(*farben[f"rand_{art}"])
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                 width=dp(1.2))

    def on_release(self):
        self._auf_klick(self._knoten)


class _Abzeichen(Label):
    """Kleiner Kreis mit Kinderanzahl oben rechts an einem zugeklappten Ast -
    zeigt auf einen Blick, dass hier noch mehr steckt (identisch zur
    PC-Version, dort ebenfalls nur an zugeklappten Knoten sichtbar)."""

    def __init__(self, knoten_widget, farben, **kwargs):
        anzahl = len(knoten_widget._knoten["kinder"])
        super().__init__(
            text=str(anzahl), font_size=sp(10), bold=True, color=farben["textauf"],
            size_hint=(None, None), size=(dp(20), dp(20)), **kwargs,
        )
        self.center = (knoten_widget.center_x + knoten_widget.width / 2 + dp(9),
                       knoten_widget.center_y)
        with self.canvas.before:
            Color(*farben["fuellung_wurzel"])
            Ellipse(pos=self.pos, size=self.size)


# ---------------------------------------------------------------- Bildschirm

class MindmapScreen(MDScreen):
    """Eigenstaendiger Bildschirm im aeusseren app.screen_manager (dasselbe
    Muster wie der Einstellungen-Bildschirm, siehe app/main.py -
    _einstellungen_umschalten) - erreicht ueber _MindmapTab._anzeigen() in
    lernen_screen.py, "Zurueck" fuehrt immer zum Lernen-Reiter, da das der
    einzige Weg hierher ist."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "mindmap"
        self._baum = None

        wurzel = MDBoxLayout(orientation="vertical")

        kopf = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="48dp",
                           padding=("4dp", "0dp"))
        zurueck = MDIconButton(icon="arrow-left", ripple_canvas_after=False)
        zurueck.bind(on_release=lambda *_: self._zurueck())
        kopf.add_widget(zurueck)
        self._titel = MDLabel(text="Mindmap", font_style="Title", role="medium",
                              adaptive_height=True)
        kopf.add_widget(self._titel)
        zentrieren = MDIconButton(icon="crosshairs-gps", ripple_canvas_after=False)
        zentrieren.bind(on_release=lambda *_: self._zentrieren())
        kopf.add_widget(zentrieren)
        wurzel.add_widget(kopf)

        self._blickfeld = StencilView(size_hint=(1, 1))
        self._scatter = Scatter(
            do_rotation=False, do_translation=True, do_scale=True,
            scale_min=0.3, scale_max=2.5,
            size_hint=(None, None), size=(_CONTAINER, _CONTAINER),
        )
        self._kanten_flaeche = Widget(size_hint=(None, None), size=(_CONTAINER, _CONTAINER))
        self._knoten_schicht = Widget(size_hint=(None, None), size=(_CONTAINER, _CONTAINER))
        self._scatter.add_widget(self._kanten_flaeche)
        self._scatter.add_widget(self._knoten_schicht)
        self._blickfeld.add_widget(self._scatter)
        wurzel.add_widget(self._blickfeld)

        self._hinweis = MDLabel(text="", theme_text_color="Secondary", adaptive_height=True,
                                halign="center", size_hint_y=None, height="26dp")
        wurzel.add_widget(self._hinweis)

        fuss = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="48dp",
                           spacing="16dp", padding=("8dp", "0dp"),
                           pos_hint={"center_x": 0.5})
        fuss.add_widget(Widget())
        alle_auf = MDIconButton(icon="arrow-expand-all", ripple_canvas_after=False)
        alle_auf.bind(on_release=lambda *_: self._alle_umschalten(False))
        fuss.add_widget(alle_auf)
        alle_zu = MDIconButton(icon="arrow-collapse-all", ripple_canvas_after=False)
        alle_zu.bind(on_release=lambda *_: self._alle_umschalten(True))
        fuss.add_widget(alle_zu)
        fuss.add_widget(Widget())
        wurzel.add_widget(fuss)

        self.add_widget(wurzel)

    def zeige(self, daten):
        """Von aussen (lernen_screen.py) aufgerufen: laedt die Mindmap-Daten
        eines Fachs und baut die Ansicht neu auf."""
        self._titel.text = f'"{daten.get("thema", "Mindmap")}"'
        self._baum = _in_knoten(daten)
        self._hinweis.text = ""
        self._neu_aufbauen()
        # Das Blickfeld hat direkt nach dem Bildschirmwechsel noch nicht
        # zwingend seine endgueltige Groesse - einen Frame warten, dann
        # zentrieren/zoomen.
        Clock.schedule_once(lambda _dt: self._zentrieren(), 0.05)

    def _zurueck(self):
        MDApp.get_running_app().screen_manager.current = "lernen"

    def _knoten_angeklickt(self, knoten):
        if knoten["kinder"]:
            knoten["zu"] = not knoten["zu"]
            self._neu_aufbauen()
        else:
            self._hinweis.text = knoten["titel"]
            Clock.unschedule(self._hinweis_verbergen)
            Clock.schedule_once(self._hinweis_verbergen, 4)

    def _hinweis_verbergen(self, *_a):
        self._hinweis.text = ""

    def _alle_umschalten(self, zu):
        if not self._baum:
            return
        for knoten in _alle_knoten(self._baum):
            if knoten["kinder"]:
                knoten["zu"] = zu
        # Die Wurzel selbst bleibt IMMER aufgeklappt - sonst wuerde "Alles
        # zuklappen" die komplette Karte auf einen einzelnen Kreis
        # zusammenschrumpfen (identisch zur PC-Version: dort setzt
        # setzeAlle() aus demselben Grund BAUM.zu explizit auf false zurueck).
        self._baum["zu"] = False
        self._neu_aufbauen()

    def _neu_aufbauen(self):
        self._knoten_schicht.clear_widgets()
        self._kanten_flaeche.canvas.clear()
        if not self._baum:
            return
        _lege_radial(self._baum, _MITTE, _MITTE)
        farben = _farben(MDApp.get_running_app().theme_cls)
        sichtbare, kanten = _sichtbare_inhalte(self._baum)

        with self._kanten_flaeche.canvas:
            for eltern, kind in kanten:
                ist_wurzel = eltern["art"] == "wurzel"
                Color(*(farben["kante_wurzel"] if ist_wurzel else farben["kante"]))
                mx = (eltern["x"] + kind["x"]) / 2
                Line(bezier=[eltern["x"], eltern["y"], mx, eltern["y"],
                             mx, kind["y"], kind["x"], kind["y"]],
                     width=dp(2) if ist_wurzel else dp(1.3), segments=24)

        for knoten in sichtbare:
            widget = _MindKnoten(knoten, farben, self._knoten_angeklickt)
            self._knoten_schicht.add_widget(widget)
            if knoten["kinder"] and knoten["zu"]:
                self._knoten_schicht.add_widget(_Abzeichen(widget, farben))

    def _zentrieren(self, *_a):
        if not self._baum or self._blickfeld.width <= 1:
            return
        sichtbare, _kanten = _sichtbare_inhalte(self._baum)
        xs = [k["x"] for k in sichtbare]
        ys = [k["y"] for k in sichtbare]
        breite = max(xs) - min(xs) + dp(280)
        hoehe = max(ys) - min(ys) + dp(180)
        skala = min(self._blickfeld.width / breite, self._blickfeld.height / hoehe, 1.4)
        skala = max(0.3, skala)
        self._scatter.scale = skala
        mitte_x = (max(xs) + min(xs)) / 2
        mitte_y = (max(ys) + min(ys)) / 2
        self._scatter.pos = (
            self._blickfeld.center_x - mitte_x * skala,
            self._blickfeld.center_y - mitte_y * skala,
        )

    def aktualisiere_theme(self):
        self._titel.theme_text_color = "Primary"
        if self._baum:
            self._neu_aufbauen()
