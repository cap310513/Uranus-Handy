# -*- coding: utf-8 -*-
"""
Tab 2: Chat - echtes Eingabefeld, echter Verlauf, echte Gemini-Antwort.

Der Netzwerk-Aufruf laeuft in einem Hintergrund-Thread, damit die Oberflaeche
waehrend des Wartens nicht einfriert. Die Rueckmeldung kommt ueber
Clock.schedule_once() zurueck in den Haupt-Thread - das ist bei Kivy dasselbe
Prinzip wie self.after() bei tkinter in der PC-Version: UI-Aenderungen aus
einem Hintergrund-Thread muessen ueber den Haupt-Thread laufen, sonst droht ein
Absturz.
"""
import random
import re
import threading

from kivy.clock import Clock
from kivy.graphics import Color, Point
from kivy.uix.widget import Widget
from kivy.utils import escape_markup
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

from kern import gemini_verbindung, live_daten, speicher, sprache


class _Sternenfeld(Widget):
    """
    Ruhig treibender Punktschwarm hinter dem Chatverlauf, angelehnt an das
    Partikelfeld im Chatbot-Reiter der PC-Version - bewusst als einfache
    Kivy-Grafik statt echtem 3D (siehe uranus-mobile-5-regeln: kein echtes
    3D auf dem Handy). Liegt als erstes Kind unter dem eigentlichen Inhalt,
    scheint also nur durch die Luecken zwischen den Sprechblasen durch.
    """
    _ANZAHL = 50

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        theme = MDApp.get_running_app().theme_cls
        self._punkte = []
        with self.canvas:
            Color(*theme.primaryColor[:3], 0.4)
            self._zeichnung = Point(pointsize=1.4)
        self.bind(pos=self._neu_verteilen, size=self._neu_verteilen)
        Clock.schedule_interval(self._takt, 1 / 12)

    def _neu_verteilen(self, *_args):
        if self.width <= 0 or self.height <= 0:
            return
        self._punkte = [
            [random.uniform(self.x, self.right),
             random.uniform(self.y, self.top),
             random.uniform(-5, 5), random.uniform(-5, 5)]
            for _ in range(self._ANZAHL)
        ]

    def _takt(self, dt):
        if not self._punkte:
            self._neu_verteilen()
            return
        flach = []
        for punkt in self._punkte:
            punkt[0] += punkt[2] * dt
            punkt[1] += punkt[3] * dt
            if punkt[0] < self.x or punkt[0] > self.right:
                punkt[2] *= -1
            if punkt[1] < self.y or punkt[1] > self.top:
                punkt[3] *= -1
            flach.extend([punkt[0], punkt[1]])
        self._zeichnung.points = flach


def _daten_zu_satz(daten):
    """Formt ein live_daten-Ergebnis (Wetter/Krypto/Weltgeschehen) zu einem
    normalen Satz - dieselbe echte Zahl, die auch im Daily Briefing steht."""
    if not daten.get("ok"):
        return f"Dazu konnte ich gerade keine Daten holen ({daten.get('fehler', '')})."
    zeilen = "; ".join(f"{name}: {wert}" for name, wert in daten.get("zeilen", []))
    kopf = f"{daten.get('titel', '')}: {daten.get('wert', '')}."
    return f"{kopf} {zeilen}." if zeilen else kopf


def _markdown_zu_kivy(text):
    """
    Wandelt die haeufigsten Markdown-Zeichen aus Gemini-Antworten
    (**fett**, *kursiv*) in Kivy-Markup um, damit sie im Chat auch wirklich
    fett/kursiv erscheinen statt als rohe Sternchen. Erst escapen, damit
    eckige Klammern im Modelltext kein eigenes Markup vortaeuschen koennen.
    """
    sicher = escape_markup(text)
    sicher = re.sub(r"\*\*(.+?)\*\*", r"[b]\1[/b]", sicher)
    sicher = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"[i]\1[/i]", sicher)
    return sicher


def _zum_vorlesen(text):
    """Entfernt Markdown-Sternchen, bevor der Text an die Sprachausgabe geht -
    sonst wuerde die Stimme "Stern Stern" mitlesen."""
    return re.sub(r"\*+", "", text)


class ChatScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "chat"
        self._chat = None          # wird beim ersten Senden angelegt
        self._sendet_gerade = False

        wurzel = MDBoxLayout(orientation="vertical")

        self._verlauf_liste = MDBoxLayout(
            orientation="vertical", spacing="10dp", padding="12dp",
            size_hint_y=None, adaptive_height=True,
        )
        self._scroll = MDScrollView()
        self._scroll.add_widget(self._verlauf_liste)
        wurzel.add_widget(self._scroll)

        zeile = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height="64dp",
            padding=("12dp", "8dp"), spacing="8dp",
        )
        self._eingabe = MDTextField(
            MDTextFieldHintText(text="Frag Uranus etwas ..."),
            mode="filled", multiline=False,
        )
        self._eingabe.bind(on_text_validate=lambda *_: self._senden())
        mikrofon_knopf = MDIconButton(icon="microphone")
        mikrofon_knopf.bind(on_release=lambda *_: self._diktieren())
        sende_knopf = MDIconButton(icon="send")
        sende_knopf.bind(on_release=lambda *_: self._senden())
        zeile.add_widget(self._eingabe)
        zeile.add_widget(mikrofon_knopf)
        zeile.add_widget(sende_knopf)
        wurzel.add_widget(zeile)

        self.add_widget(_Sternenfeld())
        self.add_widget(wurzel)

        for nachricht in speicher.lade_verlauf():
            self._anzeigen(nachricht["rolle"], nachricht["text"])

    def _anzeigen(self, rolle, text):
        """Baut eine Chat-Sprechblase - rechts/eingefaerbt fuer den Nutzer,
        links/neutral fuer Uranus, statt einer schlichten Textzeile."""
        ist_nutzer = rolle == "user"
        theme = MDApp.get_running_app().theme_cls

        zeile = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, adaptive_height=True,
            padding=("48dp", "2dp", "8dp", "2dp") if ist_nutzer
                    else ("8dp", "2dp", "48dp", "2dp"),
        )
        # Ein Fuellwidget links (Nutzer) bzw. rechts (Uranus) schiebt die
        # Sprechblase an den passenden Bildschirmrand.
        if ist_nutzer:
            zeile.add_widget(MDBoxLayout())

        # adaptive_height NICHT im Konstruktor von MDCard setzen: das stuerzt
        # ab ("FBO Initialization failed"), weil MDCard dabei sofort einen
        # Ripple/Schatten-Fbo mit der (noch kindlosen, also 0-hohen) Groesse
        # anlegt - live getestet, exakt derselbe Fehler wie zuvor bei den
        # Briefing-Karten. Deshalb: Konstruktor ohne adaptive_height, Kind
        # zuerst hinzufuegen, adaptive_height danach setzen.
        blase = MDCard(
            style="elevated", padding="10dp", radius=[16, 16, 16, 16],
            size_hint=(1, None), theme_bg_color="Custom",
            md_bg_color=(theme.primaryContainerColor if ist_nutzer
                        else theme.surfaceContainerHighColor),
        )
        blase.add_widget(MDLabel(
            text=_markdown_zu_kivy(text), markup=True, adaptive_height=True,
        ))
        blase.adaptive_height = True
        zeile.add_widget(blase)

        if not ist_nutzer:
            zeile.add_widget(MDBoxLayout())

        self._verlauf_liste.add_widget(zeile)
        self._scroll.scroll_y = 0

    def _diktieren(self):
        """Startet Androids Diktier-Dialog - auf dem PC kommt sofort eine
        Fehlermeldung im Chat zurueck, da es dort keine Spracherkennung gibt."""

        def erfolg(text):
            Clock.schedule_once(lambda dt: setattr(self._eingabe, "text", text))

        def fehler(meldung):
            Clock.schedule_once(lambda dt: self._anzeigen("model", meldung))

        sprache.diktieren(erfolg, fehler)

    def _senden(self):
        text = self._eingabe.text.strip()
        if not text or self._sendet_gerade:
            return
        self._sendet_gerade = True
        self._eingabe.text = ""
        self._anzeigen("user", text)
        self._merken("user", text)

        # Fragen zu Wetter/Krypto/Weltgeschehen bekommen echte Zahlen statt
        # eine Modell-Vermutung - Gemini hat keinen Internetzugriff und sagt
        # das auch ehrlich ("dazu habe ich keinen Live-Ticker"), was fuer den
        # Nutzer wie ein Fehler aussieht.
        live_funktion = live_daten.erkenne_frage(text)

        def im_hintergrund():
            try:
                if live_funktion is not None:
                    antwort = _daten_zu_satz(live_funktion())
                    fehler = None
                else:
                    if self._chat is None:
                        self._chat = gemini_verbindung.neuer_chat()
                    antwort = gemini_verbindung.frage(self._chat, text)
                    fehler = None
            except gemini_verbindung.KeinApiKey as exc:
                antwort, fehler = "", str(exc)
            except Exception as exc:
                antwort, fehler = "", f"Da ist etwas schiefgelaufen: {exc}"
            Clock.schedule_once(lambda dt: self._antwort_da(antwort, fehler))

        threading.Thread(target=im_hintergrund, daemon=True).start()

    def _antwort_da(self, antwort, fehler):
        self._sendet_gerade = False
        if fehler:
            self._anzeigen("model", fehler)
            return
        self._anzeigen("model", antwort)
        self._merken("model", antwort)
        sprache.vorlesen(_zum_vorlesen(antwort))

    def _merken(self, rolle, text):
        verlauf = speicher.lade_verlauf()
        verlauf.append({"rolle": rolle, "text": text})
        speicher.speichere_verlauf(verlauf)
