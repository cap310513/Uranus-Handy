# -*- coding: utf-8 -*-
"""
Tab 1: Daily Briefing - echte Live-Daten (Wetter, Krypto, Weltgeschehen).

Nach dem Vorbild der Dashboard-Kacheln aus der PC-Version, aber eigenstaendig
geschrieben (Regel 5) und ohne die dortige 3D-Optik - hier reichen einfache
Karten. Jede Karte holt ihre Daten in einem Hintergrund-Thread (siehe
chat_screen.py fuer denselben Clock.schedule_once()-Grundsatz) und aktualisiert
sich jedes Mal, wenn der Reiter geoeffnet wird.
"""
import threading

from kivy.clock import Clock
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.progressindicator import MDLinearProgressIndicator
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.screen import MDScreen

from kern import live_daten, sprache

# HUD-Optik nach Vorbild der "Lage"-Spalte der PC-Version (uranus_theme.py,
# DEFAULT_PALETTE): sehr dunkles Navy statt KivyMDs neutralem Grau, dazu ein
# duenner, in der Akzentfarbe leuchtender Kartenrand.
_HUD_HINTERGRUND = (0.03, 0.05, 0.09, 1)
_HUD_SPUR = (1, 1, 1, 0.08)

# (Anzeigename, Abrufbare Funktion) - in dieser Reihenfolge dargestellt.
_QUELLEN = (
    ("Wetter", lambda: live_daten.wetter()),
    ("Kryptowährungen", lambda: live_daten.krypto()),
    ("Weltgeschehen", lambda: live_daten.schlagzeilen()),
)


class _DatenKarte(MDCard):
    """Eine Karte, die 'Lädt ...' zeigt und sich selbst befuellt, sobald die
    Daten da sind."""

    def __init__(self, anzeigename, **kwargs):
        # adaptive_height NICHT im Konstruktor setzen: MDCard baut beim
        # Erzeugen sofort einen Fbo (fuer Ripple/Schatten) auf - bei Groesse
        # (0, 0), die adaptive_height dann liefert (noch keine Kinder da),
        # stuerzt das mit "FBO Initialization failed" ab. Live getestet.
        # Deshalb: erst eine feste Platzhalterhoehe, Kinder hinzufuegen,
        # adaptive_height danach setzen - so passt sich die Karte spaeter
        # wirklich der tatsaechlichen Zeilenzahl an (z.B. 4 Nachrichten
        # brauchen mehr Platz als eine kurze Wetterzeile).
        super().__init__(
            style="outlined", padding="14dp", spacing="8dp",
            orientation="vertical", size_hint_y=None, height="150dp",
            theme_bg_color="Custom", md_bg_color=_HUD_HINTERGRUND,
            **kwargs,
        )
        theme = MDApp.get_running_app().theme_cls
        self.line_color = theme.primaryColor
        self.anzeigename = anzeigename
        self._titel = MDLabel(
            text=f"◈ {anzeigename}", font_style="Title", role="medium",
            adaptive_height=True, theme_text_color="Custom",
            text_color=theme.primaryColor,
        )
        self._inhalt = MDLabel(text="Lädt ...", adaptive_height=True)
        # Ohne text_size weiss ein Label nicht, bei welcher Breite es
        # umbrechen soll - der Text wird dann nicht umgebrochen, sondern die
        # Zeilen ueberlagern sich ("Buchstaben stehen uebereinander"). Live
        # auf dem echten Handy gemeldet. Die Breite ist erst nach dem Layout
        # bekannt, deshalb bei jeder Breitenaenderung neu setzen.
        for label in (self._titel, self._inhalt):
            label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        self.add_widget(self._titel)
        self.add_widget(self._inhalt)

        # Prozentanzeige - eine echte Kennzahl aus den Live-Daten (z.B.
        # Luftfeuchte, Kursbewegung, erreichte Quellen), nicht erfunden. Nach
        # dem Vorbild der Balken in der "Lage"-Spalte der PC-Version.
        balken_zeile = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height="18dp",
            spacing="8dp",
        )
        self._balken_label = MDLabel(
            text="", font_style="Label", role="small", adaptive_height=True,
            theme_text_color="Secondary", size_hint_x=None, width="120dp",
        )
        self._balken = MDLinearProgressIndicator(
            size_hint_y=None, height="6dp", radius=[3, 3, 3, 3],
            value=0, indicator_color=theme.primaryColor, track_color=_HUD_SPUR,
        )
        balken_zeile.add_widget(self._balken_label)
        balken_zeile.add_widget(self._balken)
        self.add_widget(balken_zeile)

        self.adaptive_height = True

    def zeige(self, daten):
        if not daten.get("ok"):
            self._inhalt.text = f"Nicht erreichbar ({daten.get('fehler', '')})"
            self._balken_label.text = ""
            self._balken.value = 0
            return
        self._titel.text = f"◈ {daten.get('titel', self.anzeigename)}"
        zeilen = [f"{name}: {wert}" for name, wert in daten.get("zeilen", [])]
        kopf = daten.get("wert", "")
        self._inhalt.text = "\n".join(([kopf] if kopf else []) + zeilen) or "Keine Daten."
        prozent = daten.get("prozent", 0)
        self._balken.value = prozent
        self._balken_label.text = f"{daten.get('prozent_label', '')} {prozent}%"

    def text_zum_vorlesen(self):
        return f"{self._titel.text}: {self._inhalt.text}".replace("\n", ". ").replace("◈", "")


class BriefingScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "briefing"
        self._karten = []
        self._laedt_gerade = False

        wurzel = MDBoxLayout(orientation="vertical")

        kopfzeile = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height="56dp",
            padding=("16dp", "0dp"),
        )
        kopfzeile.add_widget(MDLabel(
            text="◈ Daily Briefing", font_style="Headline", role="small",
            adaptive_height=True, theme_text_color="Custom",
            text_color=MDApp.get_running_app().theme_cls.primaryColor,
        ))
        vorlesen_knopf = MDIconButton(icon="volume-high")
        vorlesen_knopf.bind(on_release=lambda *_: self._vorlesen())
        kopfzeile.add_widget(vorlesen_knopf)
        aktualisieren_knopf = MDIconButton(icon="refresh")
        aktualisieren_knopf.bind(on_release=lambda *_: self.aktualisieren())
        kopfzeile.add_widget(aktualisieren_knopf)
        wurzel.add_widget(kopfzeile)

        liste = MDBoxLayout(
            orientation="vertical", spacing="12dp", padding="16dp",
            size_hint_y=None, adaptive_height=True,
        )
        for anzeigename, _funktion in _QUELLEN:
            karte = _DatenKarte(anzeigename)
            self._karten.append(karte)
            liste.add_widget(karte)

        scroll = MDScrollView()
        scroll.add_widget(liste)
        wurzel.add_widget(scroll)
        self.add_widget(wurzel)

        # on_enter() feuert nur bei einem echten Tab-Wechsel, nicht fuer den
        # Reiter, der beim App-Start schon aktiv ist - deshalb hier zusaetzlich
        # einmal direkt beim Bauen anstossen.
        Clock.schedule_once(lambda dt: self.aktualisieren(), 0.3)

    def _vorlesen(self):
        text = " ".join(karte.text_zum_vorlesen() for karte in self._karten)
        sprache.vorlesen(text)

    def on_enter(self):
        """Wird von Kivy automatisch aufgerufen, sobald dieser Reiter aktiv wird."""
        self.aktualisieren()

    def aktualisieren(self):
        if self._laedt_gerade:
            return
        self._laedt_gerade = True

        def im_hintergrund():
            ergebnisse = []
            for (_, funktion), karte in zip(_QUELLEN, self._karten):
                try:
                    ergebnisse.append((karte, funktion()))
                except Exception as exc:
                    ergebnisse.append((karte, {"ok": False, "fehler": str(exc)}))
            Clock.schedule_once(lambda dt: self._fertig(ergebnisse))

        threading.Thread(target=im_hintergrund, daemon=True).start()

    def _fertig(self, ergebnisse):
        for karte, daten in ergebnisse:
            karte.zeige(daten)
        self._laedt_gerade = False
