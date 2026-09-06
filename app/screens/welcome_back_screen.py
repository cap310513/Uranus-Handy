# -*- coding: utf-8 -*-
"""
"Willkommen zurück" - Vorbild: WelcomeBackView aus der PC-Version (main.py).
Ein Klick genügt, kein erneutes Passwort noetig (siehe kern/konten.py:
gemerkter_name(), Zufallstoken statt Passwort).
"""
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen

from kern import konten


class WelcomeBackScreen(MDScreen):
    def __init__(self, on_weiter, on_anders, **kwargs):
        super().__init__(**kwargs)
        self.name = "welcome_back"
        self._on_weiter = on_weiter

        wurzel = MDBoxLayout(orientation="vertical", padding="24dp")

        karte = MDCard(
            style="elevated", orientation="vertical", padding="24dp",
            spacing="14dp", size_hint=(1, None), height="220dp",
            pos_hint={"center_y": 0.5},
        )
        karte.add_widget(MDLabel(
            text="Willkommen zurück", font_style="Title", role="medium",
            adaptive_height=True,
        ))
        self._name_label = MDLabel(
            text="", font_style="Headline", role="small", adaptive_height=True,
        )
        karte.add_widget(self._name_label)

        weiter_knopf = MDButton(style="filled")
        weiter_knopf.add_widget(MDButtonText(text="Fortfahren"))
        weiter_knopf.bind(on_release=lambda *_: self._fortfahren())
        karte.add_widget(weiter_knopf)

        anders_knopf = MDButton(style="text")
        anders_knopf.add_widget(MDButtonText(text="Mit anderem Konto anmelden"))
        anders_knopf.bind(on_release=lambda *_: on_anders())
        karte.add_widget(anders_knopf)

        wurzel.add_widget(karte)
        self.add_widget(wurzel)

    def setze_name(self, name):
        self._name = name
        self._name_label.text = name

    def _fortfahren(self):
        self._on_weiter(self._name)
