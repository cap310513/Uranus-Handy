# -*- coding: utf-8 -*-
"""
"Willkommen zurück" - Vorbild: WelcomeBackView aus der PC-Version (main.py).
Ein Klick genügt, kein erneutes Passwort noetig (siehe kern/konten.py:
gemerkter_name(), Zufallstoken statt Passwort).
"""
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen

from app import hud_optik
from kern import konten


class WelcomeBackScreen(MDScreen):
    def __init__(self, on_weiter, on_anders, **kwargs):
        super().__init__(**kwargs)
        self.name = "welcome_back"
        self._on_weiter = on_weiter
        theme = MDApp.get_running_app().theme_cls

        wurzel = MDBoxLayout(orientation="vertical", padding="24dp")

        # adaptive_height NICHT im Konstruktor setzen (MDCard-FBO-Absturz bei
        # noch kindloser Karte, siehe briefing_screen.py) - erst Kinder
        # hinzufuegen, danach adaptive_height setzen. Vorher war hier eine
        # feste Hoehe ("220dp") eingetragen, die fuer Titel + Name + zwei
        # Knoepfe tatsaechlich zu knapp bemessen war - dadurch ragte der
        # "Fortfahren"-Knopf teils aus der Karte heraus, was zusammen mit dem
        # Ripple-Glitch (siehe unten) wie ein "kaputter" Klick aussah.
        self._karte = MDCard(
            style="elevated", orientation="vertical", padding="24dp",
            spacing="14dp", size_hint=(1, None), height="10dp",
            pos_hint={"center_y": 0.5},
        )
        self._karte.add_widget(MDLabel(
            text="Willkommen zurück", font_style="Title", role="medium",
            adaptive_height=True,
        ))
        self._name_label = MDLabel(
            text="", font_style="Headline", role="small", adaptive_height=True,
        )
        self._karte.add_widget(self._name_label)

        # ripple_canvas_after=False: KivyMDs Ripple-Effekt zeichnet
        # standardmaessig NACH den Kindwidgets (canvas.after) - der farbige
        # Ripple-Kreis lief beim Antippen also sichtbar UEBER dem Knopftext,
        # statt dahinter zu bleiben (live als "glitcht ueber den Text"
        # gemeldet). False zeichnet ihn stattdessen in canvas.before, klar
        # hinter dem Text.
        weiter_knopf = MDButton(style="filled", ripple_canvas_after=False)
        weiter_knopf.add_widget(MDButtonText(text="Fortfahren"))
        weiter_knopf.bind(on_release=lambda *_: self._fortfahren())
        hud_optik.volle_breite(weiter_knopf)
        self._karte.add_widget(weiter_knopf)

        anders_knopf = MDButton(style="text", ripple_canvas_after=False)
        anders_knopf.add_widget(MDButtonText(text="Mit anderem Konto anmelden"))
        anders_knopf.bind(on_release=lambda *_: on_anders())
        hud_optik.volle_breite(anders_knopf)
        self._karte.add_widget(anders_knopf)

        self._karte.adaptive_height = True
        hud_optik.glow_anwenden(self._karte, theme)
        wurzel.add_widget(self._karte)
        self.add_widget(wurzel)

    def setze_name(self, name):
        self._name = name
        self._name_label.text = name

    def _fortfahren(self):
        self._on_weiter(self._name)

    def aktualisiere_theme(self):
        hud_optik.glow_anwenden(self._karte, MDApp.get_running_app().theme_cls)
