# -*- coding: utf-8 -*-
"""Tab 1: Daily Briefing - in Meilenstein 1 nur ein Platzhalter."""
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen


class BriefingScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "briefing"

        inhalt = MDBoxLayout(
            orientation="vertical", padding="24dp", spacing="16dp",
        )
        inhalt.add_widget(MDLabel(
            text="Daily Briefing", font_style="Headline", role="small",
            adaptive_height=True,
        ))

        karte = MDCard(
            style="outlined", padding="16dp",
            size_hint_y=None, height="140dp",
        )
        karte.add_widget(MDLabel(
            text="Kommt in einem spaeteren Meilenstein - hier stehen bald "
                 "deine taeglichen Kurzmeldungen.",
            adaptive_height=True,
        ))
        inhalt.add_widget(karte)
        self.add_widget(inhalt)
