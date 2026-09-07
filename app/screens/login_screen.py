# -*- coding: utf-8 -*-
"""
Konto erstellen oder anmelden - Vorbild: LoginView aus der PC-Version
(main.py), eigenstaendig neu gebaut (Regel 5).
"""
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

from app import hud_optik
from kern import konten


class LoginScreen(MDScreen):
    def __init__(self, on_erfolg, **kwargs):
        super().__init__(**kwargs)
        self.name = "login"
        self._on_erfolg = on_erfolg
        self._modus = "registrieren"
        theme = MDApp.get_running_app().theme_cls

        wurzel = MDBoxLayout(orientation="vertical", padding="24dp")

        # adaptive_height NICHT im Konstruktor setzen (MDCard-FBO-Absturz bei
        # noch kindloser Karte, siehe briefing_screen.py) - erst Kinder
        # hinzufuegen, danach adaptive_height setzen. Vorher stand hier eine
        # feste Hoehe ("360dp"), die fuer Titel + 3 Textfelder (je 56dp fest,
        # siehe MDTextField) + Fehlertext + 2 Knoepfe tatsaechlich zu knapp
        # bemessen war.
        self._karte = MDCard(
            style="elevated", orientation="vertical", padding="20dp",
            spacing="12dp", size_hint=(1, None), height="10dp",
            pos_hint={"center_y": 0.5},
        )

        self._titel = MDLabel(
            text="Konto erstellen", font_style="Headline", role="small",
            adaptive_height=True,
        )
        self._karte.add_widget(self._titel)

        self._name_feld = MDTextField(
            MDTextFieldHintText(text="Name"), mode="filled", multiline=False,
        )
        self._passwort_feld = MDTextField(
            MDTextFieldHintText(text="Passwort"), mode="filled",
            multiline=False, password=True,
        )
        self._wiederholung_feld = MDTextField(
            MDTextFieldHintText(text="Passwort bestätigen"), mode="filled",
            multiline=False, password=True,
        )
        self._karte.add_widget(self._name_feld)
        self._karte.add_widget(self._passwort_feld)
        self._karte.add_widget(self._wiederholung_feld)

        self._fehler = MDLabel(text="", adaptive_height=True)
        self._karte.add_widget(self._fehler)

        # ripple_canvas_after=False: siehe welcome_back_screen.py - haelt den
        # Ripple-Kreis hinter dem Knopftext statt sichtbar darueber.
        absenden = MDButton(style="filled", ripple_canvas_after=False)
        self._absenden_text = MDButtonText(text="Konto erstellen")
        absenden.add_widget(self._absenden_text)
        absenden.bind(on_release=lambda *_: self._absenden())
        hud_optik.volle_breite(absenden)
        self._karte.add_widget(absenden)

        umschalten = MDButton(style="text", ripple_canvas_after=False)
        self._umschalten_text = MDButtonText(
            text="Schon ein Konto? Hier anmelden",
        )
        umschalten.add_widget(self._umschalten_text)
        umschalten.bind(on_release=lambda *_: self._modus_umschalten())
        hud_optik.volle_breite(umschalten)
        self._karte.add_widget(umschalten)

        self._karte.adaptive_height = True
        hud_optik.glow_anwenden(self._karte, theme)
        wurzel.add_widget(self._karte)
        self.add_widget(wurzel)

        # Gibt es noch gar kein Konto, macht "Anmelden" als Startmodus keinen
        # Sinn - dann direkt im Registrieren-Modus starten (schon Standard).
        if konten.konto_vorhanden():
            self._modus_umschalten()

    def _modus_umschalten(self):
        if self._modus == "registrieren":
            self._modus = "anmelden"
            self._titel.text = "Anmelden"
            self._wiederholung_feld.opacity = 0
            self._wiederholung_feld.disabled = True
            self._wiederholung_feld.size_hint_y = None
            self._wiederholung_feld.height = 0
            self._absenden_text.text = "Anmelden"
            self._umschalten_text.text = "Noch kein Konto? Hier erstellen"
        else:
            self._modus = "registrieren"
            self._titel.text = "Konto erstellen"
            self._wiederholung_feld.opacity = 1
            self._wiederholung_feld.disabled = False
            self._wiederholung_feld.size_hint_y = None
            self._wiederholung_feld.height = "56dp"
            self._absenden_text.text = "Konto erstellen"
            self._umschalten_text.text = "Schon ein Konto? Hier anmelden"
        self._fehler.text = ""

    def _absenden(self):
        name = self._name_feld.text.strip()
        passwort = self._passwort_feld.text

        if self._modus == "registrieren":
            erfolg, meldung = konten.registrieren(
                name, passwort, self._wiederholung_feld.text,
            )
        else:
            erfolg, meldung = konten.anmelden(name, passwort)

        if not erfolg:
            self._fehler.text = meldung
            return

        self._fehler.text = ""
        self._passwort_feld.text = ""
        self._wiederholung_feld.text = ""
        konten.sitzung_merken(meldung if self._modus == "anmelden" else name)
        self._on_erfolg(meldung if self._modus == "anmelden" else name)

    def aktualisiere_theme(self):
        hud_optik.glow_anwenden(self._karte, MDApp.get_running_app().theme_cls)
