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
from kivy.uix.floatlayout import FloatLayout  # noqa: E402
from kivymd.app import MDApp  # noqa: E402
from kivymd.uix.boxlayout import MDBoxLayout  # noqa: E402
from kivymd.uix.button import MDIconButton  # noqa: E402
from kivymd.uix.navigationbar import (  # noqa: E402
    MDNavigationBar, MDNavigationItem, MDNavigationItemIcon,
    MDNavigationItemLabel,
)
from kivymd.uix.screen import MDScreen  # noqa: E402
from kivymd.uix.screenmanager import MDScreenManager  # noqa: E402
from kivymd.uix.widget import MDWidget  # noqa: E402

_PROJEKT_WURZEL = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJEKT_WURZEL not in sys.path:
    sys.path.insert(0, _PROJEKT_WURZEL)

from app import hud_optik  # noqa: E402
from app.screens.briefing_screen import BriefingScreen  # noqa: E402
from app.screens.chat_screen import ChatScreen  # noqa: E402
from app.screens.lernen_screen import LernenScreen  # noqa: E402
from app.screens.login_screen import LoginScreen  # noqa: E402
from app.screens.mindmap_screen import MindmapScreen  # noqa: E402
from app.screens.settings_screen import SettingsScreen  # noqa: E402
from app.screens.welcome_back_screen import WelcomeBackScreen  # noqa: E402
from kern import konten, system_raender  # noqa: E402


class UranusMobileApp(MDApp):
    aktueller_nutzer = None

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

        self.root_manager = MDScreenManager()
        self.root_manager.add_widget(LoginScreen(on_erfolg=self._angemeldet))
        self.root_manager.add_widget(
            WelcomeBackScreen(on_weiter=self._angemeldet, on_anders=self._zu_login)
        )
        self.root_manager.add_widget(self._baue_hauptbereich())

        # Aeusserer Rahmen um alle Bildschirme (Login/Welcome-Back/Haupt):
        # haelt Androids Status- und System-Navigationsleiste fern (siehe
        # kern/system_raender.py - live auf einem Samsung Galaxy S25 FE als
        # Ueberlappung gemeldet) UND traegt den einzigen App-weiten
        # Hintergrund, der theme_style folgt. Ohne Letzteres blieb der
        # Hintergrund beim Wechsel in den hellen Modus dunkel, waehrend nur
        # einzelne Widgets (Textfelder etc. mit eigener KV-Bindung an die
        # Theme-Farben) hell wurden - live genau so gemeldet.
        self._rahmen = MDBoxLayout(orientation="vertical", theme_bg_color="Custom")
        self._rahmen.md_bg_color = hud_optik.hintergrund_getoent(self.theme_cls)
        # BoxLayout reiht Kinder nur hintereinander - fuer das Tech-Raster als
        # HINTERGRUND-Schicht (siehe unten) braucht es einen echten
        # Ueberlagerungs-Container. Deshalb ein FloatLayout als einziges Kind
        # von _rahmen: _rahmen selbst behaelt sein padding (fuer die
        # Insets, siehe _insets_geaendert - FloatLayout ignoriert padding
        # komplett), waehrend die Schicht darin Raster + Bildschirme
        # uebereinanderlegt.
        self._schicht = FloatLayout()
        self._raster = hud_optik.TechRaster(size_hint=(1, 1))
        self._schicht.add_widget(self._raster)
        self._schicht.add_widget(self.root_manager)
        self._rahmen.add_widget(self._schicht)
        system_raender.registriere(self._insets_geaendert)
        self.theme_cls.bind(theme_style=self._theme_geaendert,
                             primary_palette=self._theme_geaendert)

        gemerkt = konten.gemerkter_name()
        if gemerkt:
            self.root_manager.get_screen("welcome_back").setze_name(gemerkt)
            self.root_manager.current = "welcome_back"
        else:
            self.root_manager.current = "login"

        return self._rahmen

    def _insets_geaendert(self, oben_px, unten_px):
        """Rueckruf aus system_raender.registriere() - oben_px/unten_px sind
        Androids tatsaechliche Status-/Navigationsleisten-Hoehe in Pixeln
        (auf dem PC immer 0)."""
        self._rahmen.padding = [0, oben_px, 0, unten_px]

    def _theme_geaendert(self, *_args):
        """Wird bei jedem Hell/Dunkel- oder Farbwechsel aufgerufen (siehe
        settings_screen.py) - aktualisiert alles, was seine Farbe als festen
        Python-Wert statt als KV-Bindung gesetzt hat und deshalb nicht von
        selbst mitzieht."""
        self._rahmen.md_bg_color = hud_optik.hintergrund_getoent(self.theme_cls)
        self._raster.aktualisiere_theme(self.theme_cls)
        self.root_manager.get_screen("login").aktualisiere_theme()
        self.root_manager.get_screen("welcome_back").aktualisiere_theme()
        self.screen_manager.get_screen("briefing").aktualisiere_theme()
        self.screen_manager.get_screen("chat").aktualisiere_theme()
        self.screen_manager.get_screen("lernen").aktualisiere_theme()
        self.screen_manager.get_screen("mindmap").aktualisiere_theme()
        self.screen_manager.get_screen("settings").aktualisiere_theme()

    def _baue_hauptbereich(self):
        """Die drei Reiter (Daily Briefing/Chat/Lernen) plus Einstellungen -
        Einstellungen ist seit dem Redesign KEIN Reiter der Bottom-Nav mehr,
        sondern ueber das Zahnrad oben rechts erreichbar (mehr Platz fuer die
        drei inhaltlichen Reiter, Einstellungen sind kein taeglicher Reiter)."""
        haupt = MDScreen(name="haupt")
        wurzel = MDBoxLayout(orientation="vertical")

        wurzel.add_widget(self._baue_obere_leiste())

        self.screen_manager = MDScreenManager()
        self.screen_manager.add_widget(BriefingScreen())
        self.screen_manager.add_widget(ChatScreen())
        self.screen_manager.add_widget(LernenScreen())
        self.screen_manager.add_widget(MindmapScreen())
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

        lernen_eintrag = MDNavigationItem()
        lernen_eintrag.add_widget(MDNavigationItemIcon(icon="school"))
        lernen_eintrag.add_widget(MDNavigationItemLabel(text="Lernen"))
        navigation.add_widget(lernen_eintrag)

        wurzel.add_widget(navigation)
        haupt.add_widget(wurzel)
        return haupt

    def _baue_obere_leiste(self):
        """Duenne Kopfzeile ueber allen drei Reitern - traegt nur das
        Zahnrad fuer die Einstellungen. Bewusst ohne eigenen Titeltext: jeder
        Reiter hat schon seine eigene Ueberschrift, eine zweite waere
        redundant."""
        leiste = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height="44dp",
            padding=("4dp", "0dp"),
        )
        leiste.add_widget(MDWidget())  # schiebt das Zahnrad nach rechts
        self._einstellungen_knopf = MDIconButton(
            icon="cog", ripple_canvas_after=False)
        self._einstellungen_knopf.bind(
            on_release=lambda *_: self._einstellungen_umschalten())
        leiste.add_widget(self._einstellungen_knopf)
        return leiste

    def _einstellungen_umschalten(self, *_args):
        """Zahnrad oben rechts: oeffnet die Einstellungen als vierten,
        eigenstaendigen Screen im selben Screen-Manager (nicht ueber die
        Bottom-Nav erreichbar) und wird dabei selbst zum Zurueck-Pfeil."""
        if self.screen_manager.current == "settings":
            self.screen_manager.current = self._letzter_reiter
            self._einstellungen_knopf.icon = "cog"
        else:
            self._letzter_reiter = self.screen_manager.current
            self.screen_manager.current = "settings"
            self._einstellungen_knopf.icon = "arrow-left"

    def _angemeldet(self, name):
        self.aktueller_nutzer = name
        self.root_manager.current = "haupt"

    def _zu_login(self):
        self.root_manager.current = "login"

    _ZIELE = {"Daily Briefing": "briefing", "Chat": "chat", "Lernen": "lernen"}
    _letzter_reiter = "briefing"

    def _tab_gewechselt(self, bar, item, item_icon, item_text):
        self._letzter_reiter = self._ZIELE.get(item_text, "briefing")
        self.screen_manager.current = self._letzter_reiter
        self._einstellungen_knopf.icon = "cog"


if __name__ == "__main__":
    UranusMobileApp().run()
