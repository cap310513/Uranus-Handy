# -*- coding: utf-8 -*-
"""
Einstiegspunkt der Uranus-Mobile-App.

Auf dem PC laeuft sie in einem auf Handygroesse verkleinerten Fenster (siehe
README.md, Abschnitt "Meilenstein 1 starten") - auf einem echten Android-Handy
ist sie stattdessen ganz normal im Vollbild, wie jede andere App. Deshalb wird
die feste Fenstergroesse nur auf dem Desktop gesetzt, nie auf Android.
"""
import os
import sys

from kivy.utils import platform

if platform not in ("android", "ios"):
    from kivy.config import Config

    # Muss VOR dem Window-Import passieren, sonst wirkt die Groesse nicht.
    Config.set("graphics", "width", "412")
    Config.set("graphics", "height", "915")
    Config.set("graphics", "resizable", "0")

from kivy.core.window import Window  # noqa: E402
from kivymd.app import MDApp  # noqa: E402
from kivymd.uix.boxlayout import MDBoxLayout  # noqa: E402
from kivymd.uix.navigationbar import (  # noqa: E402
    MDNavigationBar, MDNavigationItem, MDNavigationItemIcon,
    MDNavigationItemLabel,
)
from kivymd.uix.screenmanager import MDScreenManager  # noqa: E402

_PROJEKT_WURZEL = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJEKT_WURZEL not in sys.path:
    sys.path.insert(0, _PROJEKT_WURZEL)

from app.screens.briefing_screen import BriefingScreen  # noqa: E402
from app.screens.chat_screen import ChatScreen  # noqa: E402


class UranusMobileApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Dark"
        if platform not in ("android", "ios"):
            Window.size = (412, 915)

        wurzel = MDBoxLayout(orientation="vertical")

        self.screen_manager = MDScreenManager()
        self.screen_manager.add_widget(BriefingScreen())
        self.screen_manager.add_widget(ChatScreen())
        wurzel.add_widget(self.screen_manager)

        navigation = MDNavigationBar()
        navigation.bind(on_switch_tabs=self._tab_gewechselt)

        briefing_eintrag = MDNavigationItem(active=True)
        briefing_eintrag.add_widget(MDNavigationItemIcon(icon="calendar-today"))
        briefing_eintrag.add_widget(MDNavigationItemLabel(text="Daily Briefing"))
        navigation.add_widget(briefing_eintrag)

        chat_eintrag = MDNavigationItem()
        chat_eintrag.add_widget(MDNavigationItemIcon(icon="chat"))
        chat_eintrag.add_widget(MDNavigationItemLabel(text="Chat"))
        navigation.add_widget(chat_eintrag)

        wurzel.add_widget(navigation)
        return wurzel

    def _tab_gewechselt(self, bar, item, item_icon, item_text):
        ziel = "briefing" if item_text == "Daily Briefing" else "chat"
        self.screen_manager.current = ziel


if __name__ == "__main__":
    UranusMobileApp().run()
