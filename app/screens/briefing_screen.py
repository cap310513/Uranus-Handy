# -*- coding: utf-8 -*-
"""
Tab 1: Daily Briefing - echte Live-Daten (Wetter, Krypto, Weltgeschehen).

Nach dem Vorbild der Dashboard-Kacheln aus der PC-Version, aber eigenstaendig
geschrieben (Regel 5) und ohne die dortige 3D-Optik - hier reichen einfache
Karten. Jede Karte holt ihre Daten in einem Hintergrund-Thread (siehe
chat_screen.py fuer denselben Clock.schedule_once()-Grundsatz) und aktualisiert
sich jedes Mal, wenn der Reiter geoeffnet wird.

Jede Karte hat ausserdem einen eigenen kleinen Mini-Chat direkt unter ihrem
Inhalt (siehe _DatenKarte) - eine Frage dort bezieht sich NUR auf dieses eine
Widget (z.B. "Und wie ist es in Antalya?" unter der Wetterkarte) und wandelt
die Karte dauerhaft um, statt einmalig zu antworten: die naechste
Aktualisierung (Tab-Wechsel, Aktualisieren-Knopf) fragt wieder denselben Ort
neu ab, bis der Nutzer erneut etwas anderes fragt.
"""
import math
import threading

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.progressindicator import MDLinearProgressIndicator
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

from app import hud_optik
from kern import gemini_verbindung, live_daten, sprache

# ----------------------------------------------------------------------
# Mini-Chat je Widget: Gemini interpretiert die kurze Frage, live_daten
# liefert dazu die echten Zahlen - kein erfundener Wert.
# ----------------------------------------------------------------------
_WETTER_ANWEISUNG = (
    "Der Nutzer schreibt eine kurze Frage zum Wetter-Widget im Daily "
    "Briefing einer App. Erkenne, nach welchem Ort er fragt (Stadt, wenn "
    "moeglich mit Land). Antworte NUR mit einem JSON-Objekt der Form "
    '{"ort": "<Ortsname>"}.'
)
_KRYPTO_ANWEISUNG = (
    "Der Nutzer schreibt eine kurze Frage zum Kryptowaehrungs-Widget im "
    "Daily Briefing einer App. Erkenne, nach welchen Kryptowaehrungen er "
    "fragt, und antworte NUR mit einem JSON-Objekt der Form "
    '{"muenzen": ["<coingecko-id>", ...]} - <coingecko-id> ist die ID, wie '
    'sie die CoinGecko-API verwendet (z.B. "bitcoin", "ethereum", "solana", '
    '"ripple" fuer XRP, "dogecoin", "cardano"). Hoechstens 3 Eintraege.'
)


def _fehler_karte(titel, fehler):
    return {"ok": False, "titel": titel, "wert": "—", "zeilen": [],
            "fehler": fehler, "prozent": 0, "prozent_label": ""}


def _wetter_mini_chat(frage_text):
    """
    Interpretiert eine Mini-Chat-Frage zum Wetter-Widget: Gemini erkennt den
    Ort, live_daten.geokodiere() liefert dazu echte Koordinaten. Gibt
    (daten, neue_auffrisch_funktion) zurueck - Zweiteres ist None, wenn kein
    Ort erkannt wurde (die Karte bleibt dann bei ihrer bisherigen Abfrage).
    """
    info = gemini_verbindung.extrahiere_json(frage_text, _WETTER_ANWEISUNG)
    ort = ((info or {}).get("ort") or "").strip()
    if not ort:
        return _fehler_karte("Wetter", "Ort nicht verstanden."), None
    gefunden = live_daten.geokodiere(ort)
    if gefunden is None:
        return _fehler_karte(f"Wetter {ort}", f"Ort '{ort}' nicht gefunden."), None
    name, lat, lon = gefunden
    neue_funktion = lambda: live_daten.wetter(ort=name, lat=lat, lon=lon)  # noqa: E731
    return neue_funktion(), neue_funktion


def _krypto_mini_chat(frage_text):
    """Wie _wetter_mini_chat(), nur fuer Kryptowaehrungen."""
    info = gemini_verbindung.extrahiere_json(frage_text, _KRYPTO_ANWEISUNG)
    muenzen = tuple((info or {}).get("muenzen") or [])[:3]
    if not muenzen:
        return _fehler_karte("Kryptowährungen", "Keine Kryptowährung erkannt."), None
    neue_funktion = lambda: live_daten.krypto(muenzen=muenzen)  # noqa: E731
    return neue_funktion(), neue_funktion


def _weltgeschehen_mini_chat(frage_text):
    """
    Anders als bei Wetter/Krypto gibt es hier keine Schnittstelle, die
    gezielt nach einem Thema suchen koennte - stattdessen beantwortet Gemini
    die Frage auf Basis der bereits geladenen Schlagzeilen (siehe
    live_daten.schlagzeilen()). neue_auffrisch_funktion fragt bei jeder
    Aktualisierung erneut frische Schlagzeilen ab und stellt dieselbe Frage
    noch einmal - so bleibt die Antwort auf dem laufenden, statt fuer immer
    auf dem allerersten Stand einzufrieren.
    """
    aktuelle = live_daten.schlagzeilen()
    if not aktuelle.get("ok"):
        return aktuelle, None
    kontext = "; ".join(f"{quelle}: {titel}" for quelle, titel in aktuelle["zeilen"])
    try:
        antwort = gemini_verbindung.frage_ohne_verlauf(
            f"Aktuelle Schlagzeilen: {kontext}\n\nFrage dazu: {frage_text}\n\n"
            "Antworte in hoechstens zwei kurzen Saetzen, nur auf Basis dieser "
            "Schlagzeilen. Wenn keine davon passt, sag das ehrlich."
        )
    except gemini_verbindung.KeinApiKey as exc:
        return _fehler_karte("Weltgeschehen", str(exc)), None
    daten = {"ok": True, "titel": "Weltgeschehen", "wert": antwort, "zeilen": [],
             "fehler": "", "prozent": aktuelle.get("prozent", 0),
             "prozent_label": aktuelle.get("prozent_label", "")}
    neue_funktion = lambda: _weltgeschehen_mini_chat(frage_text)[0]  # noqa: E731
    return daten, neue_funktion


# (Anzeigename, Anfangsabfrage, Mini-Chat-Funktion) - in dieser Reihenfolge
# dargestellt.
_QUELLEN = (
    ("Wetter", lambda: live_daten.wetter(), _wetter_mini_chat),
    ("Kryptowährungen", lambda: live_daten.krypto(), _krypto_mini_chat),
    ("Weltgeschehen", lambda: live_daten.schlagzeilen(), _weltgeschehen_mini_chat),
)


class _DatenKarte(MDCard):
    """
    Eine Karte, die 'Lädt ...' zeigt und sich selbst befuellt, sobald die
    Daten da sind. Darunter ein kleiner Mini-Chat: eine Frage dort bezieht
    sich NUR auf dieses eine Widget (siehe _mini_chat_senden()) und ersetzt
    dessen Inhalt dauerhaft, statt im grossen Chat-Tab zu landen.
    """

    def __init__(self, anzeigename, anfangsfunktion, mini_chat_funktion, **kwargs):
        # adaptive_height NICHT im Konstruktor setzen: MDCard baut beim
        # Erzeugen sofort einen Fbo (fuer Ripple/Schatten) auf - bei Groesse
        # (0, 0), die adaptive_height dann liefert (noch keine Kinder da),
        # stuerzt das mit "FBO Initialization failed" ab. Live getestet.
        # Deshalb: erst eine feste Platzhalterhoehe, Kinder hinzufuegen,
        # adaptive_height danach setzen - so passt sich die Karte spaeter
        # wirklich der tatsaechlichen Zeilenzahl an (z.B. 4 Nachrichten
        # brauchen mehr Platz als eine kurze Wetterzeile).
        #
        # padding unten bewusst groesser als an den anderen drei Seiten -
        # zusaetzliche Sicherheitsmarge, weil mehrzeiliger Inhalt (z.B. bei
        # Kryptowaehrungen: Kopfzeile + bis zu 3 Zeilen) live beobachtet
        # knapp am unteren Rand abgeschnitten wurde.
        theme = MDApp.get_running_app().theme_cls
        super().__init__(
            style="elevated", padding=("14dp", "14dp", "14dp", "20dp"),
            spacing="8dp",
            orientation="vertical", size_hint_y=None, height="150dp",
            theme_bg_color="Custom", md_bg_color=hud_optik.hintergrund(theme),
            **kwargs,
        )
        self.line_color = theme.primaryColor
        self.anzeigename = anzeigename
        # Aktuelle Abfrage dieser Karte - anfangs die feste Standardabfrage
        # (z.B. Berlin), nach einer erfolgreichen Mini-Chat-Frage die neue,
        # persoenliche Abfrage (siehe _mini_chat_fertig()).
        self._auffrischen = anfangsfunktion
        self._mini_chat_funktion = mini_chat_funktion
        self._mini_chat_laedt = False

        self._titel = MDLabel(
            text=f"• {anzeigename}", font_style="Title", role="medium",
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
            value=0, indicator_color=theme.primaryColor,
            track_color=hud_optik.spur(theme),
        )
        balken_zeile.add_widget(self._balken_label)
        balken_zeile.add_widget(self._balken)
        self.add_widget(balken_zeile)

        # Abstandshalter vor dem Mini-Chat - zusaetzlich zum normalen
        # spacing="8dp" der Karte, damit die Eingabezeile sichtbar von der
        # Karte darueber getrennt ist (live als "ragt hinein" gemeldet).
        self.add_widget(Widget(size_hint_y=None, height="6dp"))

        # Mini-Chat - siehe Klassen-Docstring. adaptive_height statt einer
        # geratenen festen Zeilenhoehe: MDTextField hat selbst eine feste
        # Eigenhoehe von 56dp (Material-3-Vorgabe fuer ein einzeiliges
        # Feld) - eine kleinere feste Zeilenhoehe (z.B. "40dp") zwingt das
        # Feld NICHT kleiner, es ragt dann einfach ueber den Rand seiner
        # eigenen Zeile hinaus in die Karte darueber hinein (genau der
        # gemeldete Fehler). adaptive_height richtet sich stattdessen nach
        # der tatsaechlich groessten Kindhoehe.
        mini_chat_zeile = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, adaptive_height=True,
            spacing="6dp",
        )
        self._mini_chat_feld = MDTextField(
            MDTextFieldHintText(text="Frage dazu ..."),
            mode="filled", multiline=False,
        )
        self._mini_chat_feld.bind(
            on_text_validate=lambda *_: self._mini_chat_senden())
        mini_chat_knopf = MDIconButton(icon="send", ripple_canvas_after=False)
        mini_chat_knopf.bind(on_release=lambda *_: self._mini_chat_senden())
        mini_chat_zeile.add_widget(self._mini_chat_feld)
        mini_chat_zeile.add_widget(mini_chat_knopf)
        self.add_widget(mini_chat_zeile)

        self.adaptive_height = True
        hud_optik.glow_anwenden(self, theme)

    def zeige(self, daten):
        if not daten.get("ok"):
            self._inhalt.text = f"Nicht erreichbar ({daten.get('fehler', '')})"
            self._balken_label.text = ""
            self._balken.value = 0
            return
        self._titel.text = f"• {daten.get('titel', self.anzeigename)}"
        zeilen = [f"{name}: {wert}" for name, wert in daten.get("zeilen", [])]
        kopf = daten.get("wert", "")
        self._inhalt.text = "\n".join(([kopf] if kopf else []) + zeilen) or "Keine Daten."
        prozent = daten.get("prozent", 0)
        self._balken.value = prozent
        self._balken_label.text = f"{daten.get('prozent_label', '')} {prozent}%"

    def text_zum_vorlesen(self):
        return f"{self._titel.text}: {self._inhalt.text}".replace("\n", ". ").replace("•", "")

    def aktualisiere_theme(self):
        """Siehe app/hud_optik.py - faerbt Hintergrund/Rand/Titel/Balken neu
        ein, weil sie als fester Python-Wert statt als KV-Bindung gesetzt
        wurden und darum beim Hell/Dunkel-Umschalten nicht von selbst
        mitziehen."""
        theme = MDApp.get_running_app().theme_cls
        self.md_bg_color = hud_optik.hintergrund(theme)
        self.line_color = theme.primaryColor
        self._titel.text_color = theme.primaryColor
        self._balken.indicator_color = theme.primaryColor
        self._balken.track_color = hud_optik.spur(theme)
        hud_optik.glow_anwenden(self, theme)

    def _mini_chat_senden(self):
        text = self._mini_chat_feld.text.strip()
        if not text or self._mini_chat_laedt:
            return
        self._mini_chat_laedt = True
        self._mini_chat_feld.text = ""
        self._inhalt.text = "Einen Moment …"

        def im_hintergrund():
            try:
                daten, neue_funktion = self._mini_chat_funktion(text)
            except Exception as exc:
                daten = {"ok": False, "titel": self.anzeigename, "wert": "—",
                         "zeilen": [], "fehler": str(exc)[:120], "prozent": 0,
                         "prozent_label": ""}
                neue_funktion = None
            Clock.schedule_once(
                lambda dt: self._mini_chat_fertig(daten, neue_funktion))

        threading.Thread(target=im_hintergrund, daemon=True).start()

    def _mini_chat_fertig(self, daten, neue_funktion):
        self._mini_chat_laedt = False
        if neue_funktion is not None:
            self._auffrischen = neue_funktion
        self.zeige(daten)


class _LageRadar(Widget):
    """
    Kleine Radar-Grafik mit echtem, rotierendem Suchstrahl - angelehnt an die
    "Lage"-Spalte der PC-Version (dort kreist ein Strahl um die Mitte, die
    Kacheln stehen als feste Punkte drumherum). Rein dekorativ, ohne echtes
    3D (bewusst nicht auf dem Handy - siehe uranus-mobile-5-regeln); die
    tatsaechlichen Werte stehen in der Rangliste direkt darunter.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", ("92dp", "92dp"))
        super().__init__(**kwargs)
        theme = MDApp.get_running_app().theme_cls
        self._winkel = 0.0
        self._mitte = (0, 0)
        self._radius_aussen = 0
        with self.canvas:
            self._farbe_ring = Color(*theme.primaryColor[:3], 0.35)
            self._ring_aussen = Line(width=1.1)
            self._ring_innen = Line(width=1.1)
            self._farbe_punkte = Color(*theme.primaryColor[:3], 0.9)
            self._punkte = [Ellipse(size=(9, 9)) for _ in range(3)]
            self._farbe_strahl = Color(*theme.primaryColor[:3], 0.8)
            self._strahl = Line(width=1.4)
        self.bind(pos=self._neu_zeichnen, size=self._neu_zeichnen)
        Clock.schedule_interval(self._drehen, 1 / 30)

    def _neu_zeichnen(self, *_args):
        cx, cy = self.center
        r_aussen = max(min(self.width, self.height) / 2 - 4, 1)
        self._ring_aussen.circle = (cx, cy, r_aussen)
        self._ring_innen.circle = (cx, cy, r_aussen * 0.55)
        self._radius_aussen = r_aussen
        self._mitte = (cx, cy)
        for i, punkt in enumerate(self._punkte):
            winkel = math.radians(90 + i * 120)
            r = r_aussen * 0.78
            x = cx + math.cos(winkel) * r
            y = cy + math.sin(winkel) * r
            punkt.pos = (x - 4.5, y - 4.5)
        self._strahl_zeichnen()

    def _strahl_zeichnen(self):
        cx, cy = self._mitte
        ex = cx + math.cos(self._winkel) * self._radius_aussen
        ey = cy + math.sin(self._winkel) * self._radius_aussen
        self._strahl.points = [cx, cy, ex, ey]

    def _drehen(self, dt):
        self._winkel += dt * 1.3  # eine volle Umdrehung alle ~4.8s
        self._strahl_zeichnen()

    def aktualisiere_theme(self):
        theme = MDApp.get_running_app().theme_cls
        self._farbe_ring.rgba = (*theme.primaryColor[:3], 0.35)
        self._farbe_punkte.rgba = (*theme.primaryColor[:3], 0.9)
        self._farbe_strahl.rgba = (*theme.primaryColor[:3], 0.8)


class _Rangliste(MDBoxLayout):
    """Rangliste mit Balken - wie die Prioritaetenliste der PC-'Lage'-Spalte,
    absteigend nach der jeweiligen Prozentkennzahl der Quelle sortiert."""

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("spacing", "6dp")
        kwargs.setdefault("size_hint_y", None)
        super().__init__(**kwargs)

    def aktualisieren(self, eintraege):
        self.clear_widgets()
        theme = MDApp.get_running_app().theme_cls
        sortiert = sorted(eintraege, key=lambda e: e[1], reverse=True)
        for rang, (name, prozent) in enumerate(sortiert, start=1):
            zeile = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                height="32dp", spacing="2dp")
            zeile.add_widget(MDLabel(
                text=f"{rang}. {name}", font_style="Label", role="small",
                adaptive_height=True, theme_text_color="Secondary",
            ))
            balken = MDLinearProgressIndicator(
                size_hint_y=None, height="5dp", radius=[2, 2, 2, 2],
                value=prozent, indicator_color=theme.primaryColor,
                track_color=hud_optik.spur(theme),
            )
            zeile.add_widget(balken)
            self.add_widget(zeile)
        self.height = len(sortiert) * 38 - 6 if sortiert else 0


class BriefingScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "briefing"
        self._karten = []
        self._laedt_gerade = False
        self._letzte_rangliste = []

        wurzel = MDBoxLayout(orientation="vertical")

        kopfzeile = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height="56dp",
            padding=("16dp", "0dp"),
        )
        theme = MDApp.get_running_app().theme_cls
        self._kopf_label = MDLabel(
            text="• Daily Briefing", font_style="Headline", role="small",
            adaptive_height=True, theme_text_color="Custom",
            text_color=theme.primaryColor,
        )
        kopfzeile.add_widget(self._kopf_label)
        vorlesen_knopf = MDIconButton(icon="volume-high", ripple_canvas_after=False)
        vorlesen_knopf.bind(on_release=lambda *_: self._vorlesen())
        kopfzeile.add_widget(vorlesen_knopf)
        aktualisieren_knopf = MDIconButton(icon="refresh", ripple_canvas_after=False)
        aktualisieren_knopf.bind(on_release=lambda *_: self.aktualisieren())
        kopfzeile.add_widget(aktualisieren_knopf)
        wurzel.add_widget(kopfzeile)

        liste = MDBoxLayout(
            orientation="vertical", spacing="12dp", padding="16dp",
            size_hint_y=None, adaptive_height=True,
        )

        # "Lage"-Zusammenfassung (Radar + Rangliste) - rein additiv oben
        # drauf, die drei bestehenden Karten darunter bleiben unveraendert.
        # adaptive_height NICHT im Konstruktor (siehe _DatenKarte weiter
        # oben) - erst Kinder hinzufuegen, dann setzen.
        self._lage_karte = MDCard(
            style="elevated", orientation="vertical", padding="14dp",
            spacing="8dp", size_hint_y=None, height="100dp",
            theme_bg_color="Custom", md_bg_color=hud_optik.hintergrund(theme),
        )
        self._lage_karte.line_color = theme.primaryColor
        self._lage_titel = MDLabel(
            text="• Lage", font_style="Title", role="medium",
            adaptive_height=True, theme_text_color="Custom",
            text_color=theme.primaryColor,
        )
        self._lage_karte.add_widget(self._lage_titel)
        # Radar und Rangliste NEBENEINANDER statt gestapelt: das runde Radar
        # ueberschnitt sich als eigene, dekorative Grafik direkt UEBER der
        # Rangliste live sichtbar mit deren Text und Balken. Nebeneinander
        # (Radar in fester, kleiner Groesse rechts, Rangliste nimmt den Rest
        # der Breite links) ist Ueberlappung durch die Anordnung selbst
        # ausgeschlossen, statt sie nur ueber Transparenz zu kaschieren.
        lage_reihe = MDBoxLayout(
            orientation="horizontal", spacing="12dp",
            size_hint_y=None, adaptive_height=True,
        )
        self._rangliste = _Rangliste(size_hint_x=1)
        lage_reihe.add_widget(self._rangliste)
        self._radar = _LageRadar()
        lage_reihe.add_widget(self._radar)
        self._lage_karte.add_widget(lage_reihe)
        self._lage_karte.adaptive_height = True
        hud_optik.glow_anwenden(self._lage_karte, theme)
        liste.add_widget(self._lage_karte)

        for anzeigename, anfangsfunktion, mini_chat_funktion in _QUELLEN:
            karte = _DatenKarte(anzeigename, anfangsfunktion, mini_chat_funktion)
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
            for karte in self._karten:
                try:
                    ergebnisse.append((karte, karte._auffrischen()))
                except Exception as exc:
                    ergebnisse.append((karte, {"ok": False, "fehler": str(exc)}))
            Clock.schedule_once(lambda dt: self._fertig(ergebnisse))

        threading.Thread(target=im_hintergrund, daemon=True).start()

    def _fertig(self, ergebnisse):
        for karte, daten in ergebnisse:
            karte.zeige(daten)
        self._letzte_rangliste = [
            (karte.anzeigename, daten.get("prozent", 0))
            for karte, daten in ergebnisse if daten.get("ok")
        ]
        self._rangliste.aktualisieren(self._letzte_rangliste)
        self._laedt_gerade = False

    def aktualisiere_theme(self):
        """Wird von app/main.py (_theme_geaendert) nach jedem Hell/Dunkel-
        oder Farbwechsel aufgerufen."""
        theme = MDApp.get_running_app().theme_cls
        self._kopf_label.text_color = theme.primaryColor
        self._lage_karte.md_bg_color = hud_optik.hintergrund(theme)
        self._lage_karte.line_color = theme.primaryColor
        self._lage_titel.text_color = theme.primaryColor
        hud_optik.glow_anwenden(self._lage_karte, theme)
        self._radar.aktualisiere_theme()
        self._rangliste.aktualisieren(self._letzte_rangliste)
        for karte in self._karten:
            karte.aktualisiere_theme()
