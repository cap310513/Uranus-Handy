# -*- coding: utf-8 -*-
"""
Tab 3: Einstellungen - Design (Farbe/Hell-Dunkel) und der Gemini-API-Key.

Der Key laesst sich hier direkt eintragen und aendern, ohne die App neu zu
bauen - er landet in kern.gemini_verbindung.speichere_api_key(), das ihn im
schreibbaren App-Datenordner ablegt (siehe dort, gleiches Prinzip wie
kern/speicher.py fuer den Chatverlauf).
"""
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

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

# HUD-Optik wie im Daily Briefing (briefing_screen.py) - sehr dunkles Navy
# statt KivyMDs neutralem Grau, dazu ein duenner, leuchtender Kartenrand in
# der jeweils gewaehlten Akzentfarbe.
_HUD_HINTERGRUND = (0.03, 0.05, 0.09, 1)


def _hud_karte(hoehe):
    return MDCard(
        style="outlined", orientation="vertical", padding="14dp",
        spacing="10dp", size_hint_y=None, height=hoehe,
        theme_bg_color="Custom", md_bg_color=_HUD_HINTERGRUND,
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

        wurzel = MDBoxLayout(orientation="vertical")
        wurzel.add_widget(MDLabel(
            text="• Einstellungen", font_style="Headline", role="small",
            adaptive_height=True, padding=("16dp", "16dp", "16dp", "0dp"),
            theme_text_color="Custom", text_color=app.theme_cls.primaryColor,
        ))

        liste = MDBoxLayout(
            orientation="vertical", spacing="16dp", padding="16dp",
            size_hint_y=None, adaptive_height=True,
        )

        # ---- Design ----
        design_karte = _hud_karte("190dp")
        design_karte.line_color = app.theme_cls.primaryColor
        design_karte.add_widget(_hud_titel("Design", app.theme_cls))

        farbreihe = MDBoxLayout(
            orientation="horizontal", spacing="10dp",
            size_hint_y=None, height="44dp",
        )
        for name, hexfarbe in _PALETTEN:
            knopf = MDButton(style="tonal", size_hint=(None, None),
                             size=("40dp", "40dp"), radius=[20, 20, 20, 20],
                             theme_bg_color="Custom")
            knopf.md_bg_color = _hex_zu_rgba(hexfarbe)
            knopf.bind(on_release=lambda _w, n=name: self._farbe_waehlen(n))
            farbreihe.add_widget(knopf)
        design_karte.add_widget(farbreihe)

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
        schalter.active = (app.theme_cls.theme_style == "Dark")
        schalter.bind(active=self._hell_dunkel_umschalten)
        hell_dunkel_reihe.add_widget(schalter)
        design_karte.add_widget(hell_dunkel_reihe)
        liste.add_widget(design_karte)

        # ---- Sprache ----
        sprache_karte = _hud_karte("120dp")
        sprache_karte.line_color = app.theme_cls.primaryColor
        sprache_karte.add_widget(_hud_titel("Sprache", app.theme_cls))
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
        sprache_karte.add_widget(vorlesen_reihe)
        liste.add_widget(sprache_karte)

        # ---- API-Schluessel ----
        key_karte = _hud_karte("190dp")
        key_karte.line_color = app.theme_cls.primaryColor
        key_karte.add_widget(_hud_titel("Gemini-API-Key", app.theme_cls))
        self._key_feld = MDTextField(
            MDTextFieldHintText(text="API-Key"),
            mode="filled", multiline=False,
            text=gemini_verbindung.hole_aktiven_schluessel(),
        )
        key_karte.add_widget(self._key_feld)

        speichern_knopf = MDButton(style="filled")
        speichern_knopf.add_widget(MDButtonText(text="Speichern"))
        speichern_knopf.bind(on_release=lambda *_: self._key_speichern())
        key_karte.add_widget(speichern_knopf)

        self._key_status = MDLabel(text="", adaptive_height=True)
        key_karte.add_widget(self._key_status)
        liste.add_widget(key_karte)

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


def _hex_zu_rgba(hexfarbe):
    hexfarbe = hexfarbe.lstrip("#")
    r, g, b = (int(hexfarbe[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return [r, g, b, 1]
