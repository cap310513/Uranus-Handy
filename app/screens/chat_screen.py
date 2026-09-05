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
import re
import threading

from kivy.clock import Clock
from kivy.utils import escape_markup
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

from kern import gemini_verbindung, speicher


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
        sende_knopf = MDIconButton(icon="send")
        sende_knopf.bind(on_release=lambda *_: self._senden())
        zeile.add_widget(self._eingabe)
        zeile.add_widget(sende_knopf)
        wurzel.add_widget(zeile)

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

    def _senden(self):
        text = self._eingabe.text.strip()
        if not text or self._sendet_gerade:
            return
        self._sendet_gerade = True
        self._eingabe.text = ""
        self._anzeigen("user", text)
        self._merken("user", text)

        def im_hintergrund():
            try:
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

    def _merken(self, rolle, text):
        verlauf = speicher.lade_verlauf()
        verlauf.append({"rolle": rolle, "text": text})
        speicher.speichere_verlauf(verlauf)
