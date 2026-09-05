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
from app.screens.settings_screen import SettingsScreen  # noqa: E402


class UranusMobileApp(MDApp):
    def build(self):
        # Indigo statt Blue als Standard - passt eher zu einem Weltraum-Namen
        # wie "Uranus". In den Einstellungen frei aenderbar.
        # ACHTUNG: "DeepPurple" NICHT verwenden (auch nicht in den
        # Einstellungen anbieten) - live getestet, KivyMDs Farbberechnung
        # stuerzt dabei ab ("invalid literal for int()"), genau wie bei
        # "Amber", "DeepOrange" und "BlueGray". Betrifft offenbar jede
        # Palette, deren erster Buchstabe im internen Farbnamen kollidiert -
        # nicht mein Code, ein Fehler in KivyMD/materialyoucolor selbst.
        self.theme_cls.primary_palette = "Indigo"
        self.theme_cls.theme_style = "Dark"
        if platform not in ("android", "ios"):
            Window.size = (412, 915)
        # Ohne das hier schiebt sich auf dem echten Handy die Bildschirm-
        # tastatur einfach ueber das Eingabefeld (und den ganzen Chatverlauf
        # dahinter) statt die Ansicht hochzuschieben - genau das hat den
        # Nutzer beim ersten echten Geraetetest ausgesperrt. Auf dem PC gibt
        # es keine Bildschirmtastatur, deshalb ist das dort nie aufgefallen.
        Window.softinput_mode = "below_target"

        wurzel = MDBoxLayout(orientation="vertical")

        self.screen_manager = MDScreenManager()
        self.screen_manager.add_widget(BriefingScreen())
        self.screen_manager.add_widget(ChatScreen())
        self.screen_manager.add_widget(SettingsScreen())
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

        einstellungen_eintrag = MDNavigationItem()
        einstellungen_eintrag.add_widget(MDNavigationItemIcon(icon="cog"))
        einstellungen_eintrag.add_widget(MDNavigationItemLabel(text="Einstellungen"))
        navigation.add_widget(einstellungen_eintrag)

        wurzel.add_widget(navigation)
        return wurzel

    _ZIELE = {"Daily Briefing": "briefing", "Chat": "chat",
              "Einstellungen": "settings"}

    def _tab_gewechselt(self, bar, item, item_icon, item_text):
        self.screen_manager.current = self._ZIELE.get(item_text, "briefing")


if __name__ == "__main__":
    UranusMobileApp().run()
