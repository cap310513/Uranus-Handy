# -*- coding: utf-8 -*-
"""
Tab 3: Einstellungen - Design (Farbe/Hell-Dunkel) und der Gemini-API-Key.

Der Key laesst sich hier direkt eintragen und aendern, ohne die App neu zu
bauen - er landet in kern.gemini_verbindung.speichere_api_key(), das ihn im
schreibbaren App-Datenordner ablegt (siehe dort, gleiches Prinzip wie
kern/speicher.py fuer den Chatverlauf).
"""
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

from app import hud_optik
from kern import gemini_verbindung, sprache

# (Anzeigename, Vorschau-Farbe) - die Vorschau ist nur zur Auswahl, KivyMD
# waehlt selbst den passenden vollen Farbsatz zu jedem Palettennamen.
#
# ACHTUNG: Namen wie "DeepPurple", "Amber", "DeepOrange", "BlueGray" bewusst
# NICHT aufnehmen - live getestet, KivyMDs eigene Farbberechnung stuerzt
# dabei ab ("invalid literal for int()"). Ein Fehler in KivyMD selbst, kein
# Tippfehler hier - vor dem Hinzufuegen weiterer Paletten immer erst pruefen.
_PALETTEN = (
    ("Indigo", "3f51b5"), ("Blue", "2196f3"), ("Teal", "009688"),
    ("Green", "4caf50"), ("Orange", "ff9800"), ("Red", "f44336"),
)


def _hud_karte(theme):
    # adaptive_height NICHT im Konstruktor setzen (MDCard-FBO-Absturz bei
    # noch kindloser Karte, siehe briefing_screen.py) - erst Kinder
    # hinzufuegen, dann adaptive_height setzen (siehe SettingsScreen.__init__
    # weiter unten). Vorher stand hier eine feste Hoehe ("190dp"/"120dp"),
    # die fuer Titel + Textfeld (56dp fest) + Knopf (40dp fest) + Statuszeile
    # tatsaechlich zu knapp bemessen war - dadurch ragte z.B. der
    # "Speichern"-Knopf teils aus der Karte heraus und wurde vom Textfeld
    # darueber halb verdeckt (live gemeldet).
    return MDCard(
        style="elevated", orientation="vertical", padding="14dp",
        spacing="10dp", size_hint_y=None, height="10dp",
        theme_bg_color="Custom", md_bg_color=hud_optik.hintergrund(theme),
    )


def _hud_titel(text, theme):
    return MDLabel(
        text=f"• {text}", font_style="Title", role="medium",
        adaptive_height=True, theme_text_color="Custom",
        text_color=theme.primaryColor,
    )


class SettingsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "settings"
        app = MDApp.get_running_app()
        theme = app.theme_cls

        wurzel = MDBoxLayout(orientation="vertical")
        self._headline = MDLabel(
            text="• Einstellungen", font_style="Headline", role="small",
            adaptive_height=True, padding=("16dp", "16dp", "16dp", "0dp"),
            theme_text_color="Custom", text_color=theme.primaryColor,
        )
        wurzel.add_widget(self._headline)

        liste = MDBoxLayout(
            orientation="vertical", spacing="16dp", padding="16dp",
            size_hint_y=None, adaptive_height=True,
        )

        # ---- Design ----
        self._design_karte = _hud_karte(theme)
        self._design_karte.line_color = theme.primaryColor
        self._design_titel = _hud_titel("Design", theme)
        self._design_karte.add_widget(self._design_titel)

        farbreihe = MDBoxLayout(
            orientation="horizontal", spacing="10dp",
            size_hint_y=None, height="44dp",
        )
        for name, hexfarbe in _PALETTEN:
            knopf = MDButton(style="tonal", size_hint=(None, None),
                             size=("40dp", "40dp"), radius=[20, 20, 20, 20],
                             theme_bg_color="Custom", ripple_canvas_after=False)
            knopf.md_bg_color = _hex_zu_rgba(hexfarbe)
            knopf.bind(on_release=lambda _w, n=name: self._farbe_waehlen(n))
            farbreihe.add_widget(knopf)
        self._design_karte.add_widget(farbreihe)

        hell_dunkel_reihe = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height="48dp",
        )
        hell_dunkel_reihe.add_widget(MDLabel(
            text="Dunkles Design", adaptive_height=True,
        ))
        # "active" NICHT als Konstruktor-Argument setzen: das feuert
        # on_active(), bevor der interne "thumb"-Kindwidget existiert, und
        # stuerzt ab ("AttributeError: ... no attribute '__getattr__'") -
        # live getestet. Deshalb Konstruktor leer, Wert danach setzen.
        schalter = MDSwitch()
        schalter.active = (theme.theme_style == "Dark")
        schalter.bind(active=self._hell_dunkel_umschalten)
        hell_dunkel_reihe.add_widget(schalter)
        self._design_karte.add_widget(hell_dunkel_reihe)
        self._design_karte.adaptive_height = True
        hud_optik.glow_anwenden(self._design_karte, theme)
        liste.add_widget(self._design_karte)

        # ---- Sprache ----
        self._sprache_karte = _hud_karte(theme)
        self._sprache_karte.line_color = theme.primaryColor
        self._sprache_titel = _hud_titel("Sprache", theme)
        self._sprache_karte.add_widget(self._sprache_titel)
        vorlesen_reihe = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height="48dp",
        )
        vorlesen_reihe.add_widget(MDLabel(
            text="Antworten laut vorlesen", adaptive_height=True,
        ))
        # Gleiches Muster wie beim Hell/Dunkel-Schalter oben: "active" erst
        # NACH dem Konstruktor setzen, sonst stuerzt es ab (ids.thumb fehlt
        # noch).
        vorlesen_schalter = MDSwitch()
        vorlesen_schalter.active = sprache.ist_vorlesen_an()
        vorlesen_schalter.bind(active=self._vorlesen_umschalten)
        vorlesen_reihe.add_widget(vorlesen_schalter)
        self._sprache_karte.add_widget(vorlesen_reihe)
        self._sprache_karte.adaptive_height = True
        hud_optik.glow_anwenden(self._sprache_karte, theme)
        liste.add_widget(self._sprache_karte)

        # ---- API-Schluessel ----
        self._key_karte = _hud_karte(theme)
        self._key_karte.line_color = theme.primaryColor
        self._key_titel = _hud_titel("Gemini-API-Key", theme)
        self._key_karte.add_widget(self._key_titel)
        self._key_feld = MDTextField(
            MDTextFieldHintText(text="API-Key"),
            mode="filled", multiline=False,
            text=gemini_verbindung.hole_aktiven_schluessel(),
        )
        self._key_karte.add_widget(self._key_feld)

        # Eigener kleiner Abstandshalter vor dem Knopf - zusaetzlich zum
        # normalen spacing="10dp" der Karte, damit "Speichern" sichtbar Luft
        # zum Textfeld darueber hat (live als "verdeckt sich" gemeldet).
        self._key_karte.add_widget(Widget(size_hint_y=None, height="6dp"))

        speichern_knopf = MDButton(style="filled", ripple_canvas_after=False)
        speichern_knopf.add_widget(MDButtonText(text="Speichern"))
        speichern_knopf.bind(on_release=lambda *_: self._key_speichern())
        hud_optik.volle_breite(speichern_knopf)
        self._key_karte.add_widget(speichern_knopf)

        self._key_status = MDLabel(text="", adaptive_height=True)
        self._key_karte.add_widget(self._key_status)
        self._key_karte.adaptive_height = True
        hud_optik.glow_anwenden(self._key_karte, theme)
        liste.add_widget(self._key_karte)

        scroll = MDScrollView()
        scroll.add_widget(liste)
        wurzel.add_widget(scroll)
        self.add_widget(wurzel)

    def _farbe_waehlen(self, name):
        MDApp.get_running_app().theme_cls.primary_palette = name

    def _hell_dunkel_umschalten(self, _schalter, aktiv):
        MDApp.get_running_app().theme_cls.theme_style = "Dark" if aktiv else "Light"

    def _vorlesen_umschalten(self, _schalter, aktiv):
        sprache.vorlesen_umschalten(aktiv)

    def _key_speichern(self):
        try:
            gemini_verbindung.speichere_api_key(self._key_feld.text)
            self._key_status.text = "Gespeichert."
        except Exception as exc:
            self._key_status.text = f"Konnte nicht gespeichert werden: {exc}"

    def aktualisiere_theme(self):
        """Wird von app/main.py (_theme_geaendert) nach jedem Hell/Dunkel-
        oder Farbwechsel aufgerufen - faerbt alles neu ein, was oben als
        fester Python-Wert gesetzt wurde und darum nicht von selbst mitzieht."""
        theme = MDApp.get_running_app().theme_cls
        hg = hud_optik.hintergrund(theme)
        self._headline.text_color = theme.primaryColor
        for karte, titel in (
            (self._design_karte, self._design_titel),
            (self._sprache_karte, self._sprache_titel),
            (self._key_karte, self._key_titel),
        ):
            karte.md_bg_color = hg
            karte.line_color = theme.primaryColor
            titel.text_color = theme.primaryColor
            hud_optik.glow_anwenden(karte, theme)


def _hex_zu_rgba(hexfarbe):
    hexfarbe = hexfarbe.lstrip("#")
    r, g, b = (int(hexfarbe[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return [r, g, b, 1]
