# -*- coding: utf-8 -*-
"""
Tab "Lernen" - der neue Lernbereich, nach dem Vorbild der PC-Version
(uranus_lernview.py), aber eigenstaendig fuer Kivy neu gebaut (Regel 5).

Drei Ebenen, wie ein Karteikasten mit Trennblaettern:

    Kurse  --->  Faecher  --->  Fach-Ansicht mit sechs Reitern
                                 Quelle | Karteikarten | Zusammenfassung
                                 Lückentext | Prüfung | Mindmap

Jedes Fach traegt seine eigenen Quellen, seine eigene Zusammenfassung, seinen
eigenen Lückentext, seine eigene Mindmap und seinen eigenen Karteikarten-
Stapel samt SM-2-Wiederholungsplan (kern/lernen.py) - alles dauerhaft
gespeichert.

Die Mindmap-Grafik selbst (Reiter "Mindmap") wird an anderer Stelle nativ in
Kivy gezeichnet (ScatterLayout, siehe app/screens/mindmap_screen.py) - hier
gibt es nur den Auftrag zum Generieren und eine kurze Textvorschau.
"""
import os
import re
import threading

from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.progressindicator import MDLinearProgressIndicator
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

from app import hud_optik
from app.screens.chat_screen import _markdown_zu_kivy
from kern import lernen

try:
    from plyer import filechooser
    FILECHOOSER_DA = True
except Exception:                                    # pragma: no cover
    filechooser = None
    FILECHOOSER_DA = False

TABS = (("quelle", "Quelle"), ("karten", "Karteikarten"), ("zettel", "Notizen"),
        ("luecken", "Lückentext"), ("pruefung", "Prüfung"), ("mindmap", "Mindmap"))


def _bestaetigung(knopf, aktion, symbol_normal="trash-can-outline"):
    """Zwei-Klick-Loeschbestaetigung ohne Dialog: erster Klick faerbt das
    Symbol um und fragt nach, der zweite Klick innerhalb von 2,5s loescht
    wirklich - dasselbe Prinzip wie in der PC-Version (dort per Textlabel)."""
    if getattr(knopf, "_bestaetigt", False):
        knopf._bestaetigt = False
        knopf.icon = symbol_normal
        aktion()
        return
    knopf._bestaetigt = True
    knopf.icon = "close-circle"

    def zuruecksetzen(_dt):
        if getattr(knopf, "_bestaetigt", False):
            knopf._bestaetigt = False
            knopf.icon = symbol_normal
    Clock.schedule_once(zuruecksetzen, 2.5)


class _Zeile(MDCard):
    """Eine anklickbare Liste-Zeile (Kurs oder Fach) mit Loeschen-Symbol -
    nach demselben HUD-Look wie die Karten im Daily Briefing."""

    def __init__(self, titel, untertitel, on_oeffnen, on_loeschen, **kwargs):
        theme = MDApp.get_running_app().theme_cls
        super().__init__(
            style="elevated", orientation="horizontal", padding="14dp",
            spacing="10dp", size_hint_y=None, height="60dp", **kwargs,
        )
        self.bind(on_release=lambda *_: on_oeffnen())
        text_spalte = MDBoxLayout(orientation="vertical")
        text_spalte.add_widget(MDLabel(text=titel, font_style="Title", role="small",
                                       adaptive_height=True))
        text_spalte.add_widget(MDLabel(text=untertitel, font_style="Label", role="small",
                                       theme_text_color="Secondary", adaptive_height=True))
        self.add_widget(text_spalte)
        self._loeschen_knopf = MDIconButton(icon="trash-can-outline",
                                            ripple_canvas_after=False)
        self._loeschen_knopf.bind(
            on_release=lambda *_: _bestaetigung(self._loeschen_knopf, on_loeschen))
        self.add_widget(self._loeschen_knopf)
        hud_optik.glow_anwenden(self, theme, staerke=1, deckkraft=0.35)


class _NeuZeile(MDBoxLayout):
    """Eingabezeile zum Anlegen eines neuen Kurses/Fachs - ersetzt einen
    modalen Dialog (dessen genaues KivyMD-2.0-API hier nicht gebraucht wird)
    durch ein einfaches, immer sichtbares Eingabefeld plus Haken-Knopf."""

    def __init__(self, hinweis, on_anlegen, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height="52dp",
                         spacing="8dp", padding=("16dp", "4dp"), **kwargs)
        self._feld = MDTextField(MDTextFieldHintText(text=hinweis), mode="filled",
                                 multiline=False)
        self._feld.bind(on_text_validate=lambda *_: self._anlegen())
        self._on_anlegen = on_anlegen
        self.add_widget(self._feld)
        knopf = MDIconButton(icon="check", ripple_canvas_after=False)
        knopf.bind(on_release=lambda *_: self._anlegen())
        self.add_widget(knopf)

    def _anlegen(self):
        name = self._feld.text.strip()
        if not name:
            return
        self._feld.text = ""
        self._on_anlegen(name)


class LernenScreen(MDScreen):
    """Der ganze Lern-Reiter - haelt die drei Ebenen in einem eigenen,
    inneren ScreenManager (unabhaengig vom aeusseren Reiter-Wechsel)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "lernen"
        self.benutzer = "gast"
        self.kurs_id = None
        self.fach_id = None

        self._ebenen = MDScreenManager()
        self._kurse_ebene = _KurseEbene(self)
        self._faecher_ebene = _FaecherEbene(self)
        self._fach_ebene = _FachEbene(self)
        self._ebenen.add_widget(self._kurse_ebene)
        self._ebenen.add_widget(self._faecher_ebene)
        self._ebenen.add_widget(self._fach_ebene)
        self.add_widget(self._ebenen)

    def on_pre_enter(self):
        app = MDApp.get_running_app()
        if app.aktueller_nutzer and app.aktueller_nutzer != self.benutzer:
            self.benutzer = app.aktueller_nutzer
            self.kurs_id = None
            self.fach_id = None
        if self._ebenen.current == "kurse":
            self._kurse_ebene.aktualisieren()

    def zeige_kurse(self):
        self._ebenen.current = "kurse"
        self._kurse_ebene.aktualisieren()

    def zeige_faecher(self, kurs_id):
        self.kurs_id = kurs_id
        self._faecher_ebene.aktualisieren()
        self._ebenen.current = "faecher"

    def oeffne_fach(self, fach_id):
        self.fach_id = fach_id
        self._fach_ebene.aktualisieren()
        self._ebenen.current = "fach"

    def aktuelles_fach(self):
        daten = lernen.lade_kurse(self.benutzer)
        _, fach = lernen.finde_fach(daten, self.kurs_id, self.fach_id)
        return fach

    def fach_speichern(self, fach):
        lernen.fach_speichern(self.benutzer, self.kurs_id, fach)

    def aktualisiere_theme(self):
        for ebene in (self._kurse_ebene, self._faecher_ebene, self._fach_ebene):
            ebene.aktualisiere_theme()


class _KurseEbene(MDScreen):
    def __init__(self, eltern, **kwargs):
        super().__init__(**kwargs)
        self.name = "kurse"
        self._eltern = eltern
        theme = MDApp.get_running_app().theme_cls

        wurzel = MDBoxLayout(orientation="vertical")
        kopf = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="56dp",
                           padding=("16dp", "0dp"))
        self._titel = MDLabel(text="• Meine Kurse", font_style="Headline", role="small",
                              adaptive_height=True, theme_text_color="Custom",
                              text_color=theme.primaryColor)
        kopf.add_widget(self._titel)
        neu_knopf = MDIconButton(icon="plus", ripple_canvas_after=False)
        neu_knopf.bind(on_release=lambda *_: self._eingabe_umschalten())
        kopf.add_widget(neu_knopf)
        wurzel.add_widget(kopf)

        self._eingabe = _NeuZeile("Name des neuen Kurses ...", self._kurs_angelegt)
        self._eingabe.height = 0
        self._eingabe.opacity = 0
        wurzel.add_widget(self._eingabe)

        self._liste = MDBoxLayout(orientation="vertical", spacing="10dp", padding="16dp",
                                  size_hint_y=None, adaptive_height=True)
        scroll = MDScrollView()
        scroll.add_widget(self._liste)
        wurzel.add_widget(scroll)
        self.add_widget(wurzel)

    def _eingabe_umschalten(self):
        an = self._eingabe.height == 0
        self._eingabe.height = "52dp" if an else 0
        self._eingabe.opacity = 1 if an else 0

    def _kurs_angelegt(self, name):
        self._eingabe.height = 0
        self._eingabe.opacity = 0
        kurs = lernen.kurs_hinzufuegen(self._eltern.benutzer, name)
        self._eltern.zeige_faecher(kurs["id"])

    def aktualisieren(self):
        self._liste.clear_widgets()
        daten = lernen.lade_kurse(self._eltern.benutzer)
        kurse = daten.get("kurse", [])
        if not kurse:
            self._liste.add_widget(MDLabel(
                text="Noch kein Kurs angelegt - mit + oben rechts den ersten anlegen.",
                theme_text_color="Secondary", adaptive_height=True, halign="center"))
            return
        for kurs in kurse:
            anzahl = len(kurs.get("faecher", []))
            self._liste.add_widget(_Zeile(
                kurs.get("name", "Kurs"),
                f"{anzahl} Fach{'' if anzahl == 1 else 'fächer'} · {kurs.get('erstellt', '')}",
                (lambda k=kurs["id"]: self._eltern.zeige_faecher(k)),
                (lambda k=kurs["id"]: self._kurs_loeschen(k)),
            ))

    def _kurs_loeschen(self, kurs_id):
        lernen.kurs_loeschen(self._eltern.benutzer, kurs_id)
        self.aktualisieren()

    def aktualisiere_theme(self):
        self._titel.text_color = MDApp.get_running_app().theme_cls.primaryColor


class _FaecherEbene(MDScreen):
    def __init__(self, eltern, **kwargs):
        super().__init__(**kwargs)
        self.name = "faecher"
        self._eltern = eltern
        theme = MDApp.get_running_app().theme_cls

        wurzel = MDBoxLayout(orientation="vertical")
        kopf = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="56dp",
                           padding=("4dp", "0dp"))
        zurueck = MDIconButton(icon="arrow-left", ripple_canvas_after=False)
        zurueck.bind(on_release=lambda *_: self._eltern.zeige_kurse())
        kopf.add_widget(zurueck)
        self._titel = MDLabel(text="", font_style="Title", role="medium",
                              adaptive_height=True, theme_text_color="Custom",
                              text_color=theme.primaryColor)
        kopf.add_widget(self._titel)
        neu_knopf = MDIconButton(icon="plus", ripple_canvas_after=False)
        neu_knopf.bind(on_release=lambda *_: self._eingabe_umschalten())
        kopf.add_widget(neu_knopf)
        wurzel.add_widget(kopf)

        self._eingabe = _NeuZeile("Name des neuen Fachs ...", self._fach_angelegt)
        self._eingabe.height = 0
        self._eingabe.opacity = 0
        wurzel.add_widget(self._eingabe)

        self._liste = MDBoxLayout(orientation="vertical", spacing="10dp", padding="16dp",
                                  size_hint_y=None, adaptive_height=True)
        scroll = MDScrollView()
        scroll.add_widget(self._liste)
        wurzel.add_widget(scroll)
        self.add_widget(wurzel)

    def _eingabe_umschalten(self):
        an = self._eingabe.height == 0
        self._eingabe.height = "52dp" if an else 0
        self._eingabe.opacity = 1 if an else 0

    def _aktueller_kurs(self, daten):
        for kurs in daten.get("kurse", []):
            if kurs.get("id") == self._eltern.kurs_id:
                return kurs
        return None

    def _fach_angelegt(self, name):
        self._eingabe.height = 0
        self._eingabe.opacity = 0
        fach = lernen.fach_hinzufuegen(self._eltern.benutzer, self._eltern.kurs_id, name)
        if fach is not None:
            self._eltern.oeffne_fach(fach["id"])

    def aktualisieren(self):
        daten = lernen.lade_kurse(self._eltern.benutzer)
        kurs = self._aktueller_kurs(daten)
        if kurs is None:
            self._eltern.zeige_kurse()
            return
        self._titel.text = kurs.get("name", "Kurs")
        self._liste.clear_widgets()
        faecher = kurs.get("faecher", [])
        if not faecher:
            self._liste.add_widget(MDLabel(
                text="Noch kein Fach in diesem Kurs - mit + das erste anlegen.",
                theme_text_color="Secondary", adaptive_height=True, halign="center"))
            return
        for fach in faecher:
            anzahl = len(fach.get("karten", []))
            self._liste.add_widget(_Zeile(
                fach.get("name", "Fach"),
                f"{anzahl} Karte{'' if anzahl == 1 else 'n'} · "
                f"{len(fach.get('quellen', []))} Quelle(n)",
                (lambda f=fach["id"]: self._eltern.oeffne_fach(f)),
                (lambda f=fach["id"]: self._fach_loeschen(f)),
            ))

    def _fach_loeschen(self, fach_id):
        lernen.fach_loeschen(self._eltern.benutzer, self._eltern.kurs_id, fach_id)
        self.aktualisieren()

    def aktualisiere_theme(self):
        self._titel.text_color = MDApp.get_running_app().theme_cls.primaryColor


class _FachEbene(MDScreen):
    """Die Fach-Ansicht mit der Tab-Leiste - Inhalt der sechs Reiter wird von
    eigenen kleinen Klassen weiter unten gebaut und hier nur eingehaengt."""

    def __init__(self, eltern, **kwargs):
        super().__init__(**kwargs)
        self.name = "fach"
        self._eltern = eltern
        theme = MDApp.get_running_app().theme_cls

        wurzel = MDBoxLayout(orientation="vertical")
        kopf = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="52dp",
                           padding=("4dp", "0dp"))
        zurueck = MDIconButton(icon="arrow-left", ripple_canvas_after=False)
        zurueck.bind(on_release=lambda *_: self._eltern.zeige_faecher(self._eltern.kurs_id))
        kopf.add_widget(zurueck)
        self._titel = MDLabel(text="", font_style="Title", role="medium",
                              adaptive_height=True, theme_text_color="Custom",
                              text_color=theme.primaryColor)
        kopf.add_widget(self._titel)
        wurzel.add_widget(kopf)

        # size_hint=(None, 1) statt nur size_hint_x=None: eine MDScrollView
        # mit do_scroll_y=False braucht fuer ihr Kind eine EXPLIZITE Hoehe
        # relativ zu sich selbst (hier: "fuelle die volle Scrollview-Hoehe"),
        # sonst bleibt die Kindhoehe unbestimmt und die Tab-Leiste ueberlappt
        # die Zeile darunter, statt ihre eigenen 46dp zu belegen (live so
        # gefunden).
        tableiste_scroll = MDScrollView(do_scroll_y=False, size_hint_y=None, height="46dp")
        self._tableiste = MDBoxLayout(orientation="horizontal", spacing="6dp",
                                      padding=("10dp", "4dp"), size_hint=(None, 1),
                                      adaptive_width=True)
        tableiste_scroll.add_widget(self._tableiste)
        wurzel.add_widget(tableiste_scroll)

        self._thema_feld = MDTextField(
            MDTextFieldHintText(text="Thema (hilft beim Generieren) ..."),
            mode="filled", multiline=False,
        )
        self._thema_feld.bind(text=self._thema_geaendert)
        # 60dp statt der Kartenhoehe 56dp: MDTextField hat eine feste
        # Eigenhoehe von 56dp (siehe briefing_screen.py fuer denselben
        # Fund) - etwas Luft, damit nichts abgeschnitten wird.
        thema_zeile = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                                  height="60dp", padding=("12dp", "4dp"))
        thema_zeile.add_widget(self._thema_feld)
        wurzel.add_widget(thema_zeile)

        self._status = MDLabel(text="", theme_text_color="Secondary",
                               adaptive_height=True, padding=("14dp", "0dp"))
        wurzel.add_widget(self._status)

        self._inhalt_bereich = MDBoxLayout(orientation="vertical")
        wurzel.add_widget(self._inhalt_bereich)
        self.add_widget(wurzel)

        self._tab_knoepfe = {}
        self._tab_inhalte = {
            "quelle": _QuelleTab(self),
            "karten": _KartenTab(self),
            "zettel": _ZettelTab(self),
            "luecken": _LueckenTab(self),
            "pruefung": _PruefungTab(self),
            "mindmap": _MindmapTab(self),
        }
        for schluessel, beschriftung in TABS:
            # Feste Breite statt KivyMDs eigener automatischer Breiten-
            # berechnung (MDButton.adjust_width(), 0.2s nach dem Erzeugen) -
            # die Fach-Ansicht wird schon beim App-Start im Hintergrund
            # gebaut, bevor sie sichtbar ist, wodurch diese Berechnung
            # verlaesslich danebengeht (siehe hud_optik.volle_breite() fuer
            # dieselbe Ursache bei anderen Knoepfen). Eine einheitliche
            # Breite fuer alle sechs Reiter sieht ausserdem aufgeraeumter aus
            # als sechs unterschiedlich breite Pillen.
            knopf = MDButton(style="tonal", ripple_canvas_after=False,
                             theme_width="Custom", size_hint_x=None, width="108dp")
            knopf.add_widget(MDButtonText(text=beschriftung, halign="center"))
            knopf.bind(on_release=lambda _w, s=schluessel: self._tab_wechseln(s))
            self._tableiste.add_widget(knopf)
            self._tab_knoepfe[schluessel] = knopf
        self._tab_aktiv = "quelle"

    def _thema_geaendert(self, _feld, _wert):
        fach = self._eltern.aktuelles_fach()
        if fach is None:
            return
        text = self._thema_feld.text.strip()
        if fach.get("thema", "") != text:
            fach["thema"] = text
            self._eltern.fach_speichern(fach)

    def setze_status(self, text, fehler=False):
        theme = MDApp.get_running_app().theme_cls
        self._status.text = text
        self._status.text_color = theme.errorColor if fehler else theme.onSurfaceVariantColor

    def aktualisieren(self):
        fach = self._eltern.aktuelles_fach()
        if fach is None:
            self._eltern.zeige_kurse()
            return
        self._titel.text = fach.get("name", "Fach")
        self._thema_feld.text = fach.get("thema", "")
        self.setze_status("")
        self._tab_wechseln("quelle")

    def _tab_wechseln(self, schluessel):
        self._tab_aktiv = schluessel
        theme = MDApp.get_running_app().theme_cls
        for name, knopf in self._tab_knoepfe.items():
            aktiv = name == schluessel
            knopf.style = "filled" if aktiv else "tonal"
        self._inhalt_bereich.clear_widgets()
        self._inhalt_bereich.add_widget(self._tab_inhalte[schluessel])
        self._tab_inhalte[schluessel].aktualisieren()

    def aktualisiere_theme(self):
        self._titel.text_color = MDApp.get_running_app().theme_cls.primaryColor
        for tab in self._tab_inhalte.values():
            if hasattr(tab, "aktualisiere_theme"):
                tab.aktualisiere_theme()


def _platzhalter(hinweistext, knopftext, befehl):
    """Gemeinsames Muster fuer alle Reiter, solange noch nichts erzeugt
    wurde - Text plus ein Knopf zum Generieren."""
    rahmen = MDBoxLayout(orientation="vertical", padding="24dp", spacing="16dp")
    rahmen.add_widget(Widget())
    rahmen.add_widget(MDLabel(text=hinweistext, theme_text_color="Secondary",
                              adaptive_height=True, halign="center"))
    knopf = MDButton(style="filled", ripple_canvas_after=False)
    knopf.add_widget(MDButtonText(text=knopftext, halign="center"))
    knopf.bind(on_release=lambda *_: befehl())
    hud_optik.volle_breite(knopf)
    rahmen.add_widget(knopf)
    rahmen.add_widget(Widget())
    return rahmen, knopf


def _zettel_markup(text):
    """Wandelt die Lernzettel-Markdown-Struktur (# / ## Ueberschriften, "- "
    Aufzaehlungen, **fett**) in Kivy-Markup um - dieselbe Grundidee wie
    _markdown_zu_kivy() in chat_screen.py, nur um Ueberschriften/Listen
    erweitert, die im Lernzettel-Format vorkommen."""
    zeilen = []
    for zeile in (text or "").splitlines():
        z = zeile.rstrip()
        if z.startswith("```"):
            continue
        if z.startswith("## "):
            zeilen.append(f"[size=18sp][b]{_markdown_zu_kivy(z[3:])}[/b][/size]")
        elif z.startswith("# "):
            zeilen.append(f"[size=22sp][b]{_markdown_zu_kivy(z[2:])}[/b][/size]")
        elif z.startswith(("- ", "* ")):
            zeilen.append("• " + _markdown_zu_kivy(z[2:]))
        else:
            zeilen.append(_markdown_zu_kivy(z))
    return "\n".join(zeilen)


class _TabBasis(MDBoxLayout):
    """Gemeinsame Kleinigkeiten aller sechs Fach-Reiter."""

    def __init__(self, fach_ebene, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.fach_ebene = fach_ebene

    def fach(self):
        return self.fach_ebene._eltern.aktuelles_fach()

    def speichern(self, fach):
        self.fach_ebene._eltern.fach_speichern(fach)

    def status(self, text, fehler=False):
        self.fach_ebene.setze_status(text, fehler)

    def thema(self):
        return self.fach_ebene._thema_feld.text.strip()

    def aktualisieren(self):
        pass

    def aktualisiere_theme(self):
        pass


class _QuelleTab(_TabBasis):
    """Datei-Upload (PDF/Text) + eigener Text + Liste der geladenen Quellen."""

    def __init__(self, fach_ebene, **kwargs):
        super().__init__(fach_ebene, **kwargs)
        oben = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="48dp",
                           spacing="8dp", padding=("12dp", "6dp"))
        hochladen = MDButton(style="tonal", ripple_canvas_after=False)
        hochladen.add_widget(MDButtonText(text="Datei hochladen", halign="center"))
        hochladen.bind(on_release=lambda *_: self._datei_waehlen())
        hud_optik.volle_breite(hochladen)
        oben.add_widget(hochladen)
        self.add_widget(oben)

        eingabe_zeile = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                                    height="52dp", spacing="8dp", padding=("12dp", "0dp"))
        self._text_feld = MDTextField(
            MDTextFieldHintText(text="Eigenen Text oder Thema eintippen ..."),
            mode="filled", multiline=False)
        self._text_feld.bind(on_text_validate=lambda *_: self._text_uebernehmen())
        eingabe_zeile.add_widget(self._text_feld)
        uebernehmen = MDIconButton(icon="check", ripple_canvas_after=False)
        uebernehmen.bind(on_release=lambda *_: self._text_uebernehmen())
        eingabe_zeile.add_widget(uebernehmen)
        self.add_widget(eingabe_zeile)

        kopf = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="28dp",
                           padding=("14dp", "0dp"))
        kopf.add_widget(MDLabel(text="GELADENE QUELLEN", font_style="Label", role="small",
                                theme_text_color="Secondary", adaptive_height=True))
        self._zaehler = MDLabel(text="", font_style="Label", role="small",
                                theme_text_color="Secondary", adaptive_height=True,
                                halign="right")
        kopf.add_widget(self._zaehler)
        self.add_widget(kopf)

        self._liste = MDBoxLayout(orientation="vertical", spacing="6dp",
                                  padding="10dp", size_hint_y=None, adaptive_height=True)
        scroll = MDScrollView()
        scroll.add_widget(self._liste)
        self.add_widget(scroll)

    def _datei_waehlen(self):
        if not FILECHOOSER_DA:
            self.status("Dateiauswahl (plyer) ist auf diesem Gerät nicht verfügbar.", True)
            return
        try:
            filechooser.open_file(
                on_selection=self._datei_gewaehlt,
                filters=[["Dokumente", "*.pdf", "*.txt", "*.md"]],
                multiple=True,
            )
        except Exception as exc:
            self.status(f"Dateiauswahl fehlgeschlagen: {exc}", True)

    def _datei_gewaehlt(self, pfade):
        if not pfade:
            return
        self.status(f"Lese {len(pfade)} Datei(en) ...")
        threading.Thread(target=self._lese_worker, args=(list(pfade),), daemon=True).start()

    def _lese_worker(self, pfade):
        ergebnisse = []
        for pfad in pfade:
            text, meldung = lernen.lies_dokument(pfad)
            ergebnisse.append((os.path.basename(pfad), text, meldung))
        Clock.schedule_once(lambda dt: self._quellen_geladen(ergebnisse))

    def _quellen_geladen(self, ergebnisse):
        fach = self.fach()
        if fach is None:
            return
        hinzugefuegt, fehlgeschlagen = [], []
        for name, text, meldung in ergebnisse:
            if text:
                fach.setdefault("quellen", []).append({"name": name, "text": text})
                hinzugefuegt.append(name)
            else:
                fehlgeschlagen.append(f"{name}: {meldung}")
        self.speichern(fach)
        self.aktualisieren()
        meldung = f"{len(hinzugefuegt)} Quelle(n) hinzugefügt." if hinzugefuegt else ""
        if fehlgeschlagen:
            meldung = (meldung + " " if meldung else "") + "Fehlgeschlagen: " + \
                "; ".join(fehlgeschlagen)
        self.status(meldung or "Keine der Dateien konnte gelesen werden.",
                   bool(fehlgeschlagen) and not hinzugefuegt)

    def _text_uebernehmen(self):
        text = self._text_feld.text.strip()
        if not text:
            return
        self._text_feld.text = ""
        fach = self.fach()
        if fach is None:
            return
        quellen = fach.setdefault("quellen", [])
        quellen.append({"name": f"Eigener Text {len(quellen) + 1}", "text": text})
        self.speichern(fach)
        self.aktualisieren()
        self.status("Text übernommen.")

    def aktualisieren(self):
        self._liste.clear_widgets()
        fach = self.fach()
        quellen = fach.get("quellen", []) if fach else []
        gesamt = len(lernen.fach_stoff(fach)) if fach else 0
        self._zaehler.text = (f"{len(quellen)} Quelle(n) · {gesamt} Zeichen"
                              if quellen else "nichts geladen")
        for index, quelle in enumerate(quellen):
            zeile = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="40dp",
                                spacing="6dp")
            label = MDLabel(text=str(quelle.get("name", "?")), adaptive_height=True)
            zeile.add_widget(label)
            loeschen = MDIconButton(icon="close", ripple_canvas_after=False)
            loeschen.bind(on_release=lambda *_a, i=index: self._quelle_entfernen(i))
            zeile.add_widget(loeschen)
            self._liste.add_widget(zeile)

    def _quelle_entfernen(self, index):
        fach = self.fach()
        if fach is None or not (0 <= index < len(fach.get("quellen", []))):
            return
        fach["quellen"].pop(index)
        self.speichern(fach)
        self.aktualisieren()


class _KartenTab(_TabBasis):
    """Karteikarten-Uebersicht (Statuszeile + Lernen) und Abfrage (Frage/
    Antwort umdrehen, Leicht/Mittel/Schwer bewerten - kern.lernen.bewerte_karte)."""

    def __init__(self, fach_ebene, **kwargs):
        super().__init__(fach_ebene, **kwargs)
        self._leer, _ = _platzhalter(
            "Noch keine Karteikarten für dieses Fach.",
            "Karteikarten generieren", lambda: self._generieren())

        self._uebersicht = MDBoxLayout(orientation="vertical", padding="24dp", spacing="16dp")
        self._stats = MDLabel(text="", theme_text_color="Secondary", adaptive_height=True,
                              halign="center")
        self._uebersicht.add_widget(Widget())
        self._uebersicht.add_widget(self._stats)
        knopfzeile = MDBoxLayout(orientation="horizontal", spacing="10dp", size_hint_y=None,
                                 height="48dp")
        lernen_knopf = MDButton(style="filled", ripple_canvas_after=False)
        lernen_knopf.add_widget(MDButtonText(text="Lernen", halign="center"))
        lernen_knopf.bind(on_release=lambda *_: self._abfrage_starten())
        hud_optik.volle_breite(lernen_knopf)
        knopfzeile.add_widget(lernen_knopf)
        mehr_knopf = MDButton(style="tonal", ripple_canvas_after=False)
        mehr_knopf.add_widget(MDButtonText(text="+ weitere", halign="center"))
        mehr_knopf.bind(on_release=lambda *_: self._generieren())
        hud_optik.volle_breite(mehr_knopf)
        knopfzeile.add_widget(mehr_knopf)
        self._uebersicht.add_widget(knopfzeile)
        self._uebersicht.add_widget(Widget())

        self._abfrage = MDBoxLayout(orientation="vertical", padding="20dp", spacing="12dp")
        self._karte_frage = MDLabel(text="", font_style="Title", role="medium",
                                    adaptive_height=True)
        self._karte_frage.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        self._abfrage.add_widget(self._karte_frage)
        self._karte_antwort = MDLabel(text="", adaptive_height=True)
        self._karte_antwort.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        self._abfrage.add_widget(self._karte_antwort)
        self._umdrehen_knopf = MDButton(style="filled", ripple_canvas_after=False)
        self._umdrehen_text = MDButtonText(text="Antwort zeigen", halign="center")
        self._umdrehen_knopf.add_widget(self._umdrehen_text)
        self._umdrehen_knopf.bind(on_release=lambda *_: self._umdrehen())
        hud_optik.volle_breite(self._umdrehen_knopf)
        self._abfrage.add_widget(self._umdrehen_knopf)
        self._bewertung_zeile = MDBoxLayout(orientation="horizontal", spacing="8dp",
                                            size_hint_y=None, height="44dp")
        for text, wert in (("Schwer", "schwer"), ("Mittel", "mittel"), ("Leicht", "leicht")):
            knopf = MDButton(style="tonal", ripple_canvas_after=False)
            knopf.add_widget(MDButtonText(text=text, halign="center"))
            knopf.bind(on_release=lambda _w, b=wert: self._bewerten(b))
            hud_optik.volle_breite(knopf)
            self._bewertung_zeile.add_widget(knopf)
        self._abfrage.add_widget(self._bewertung_zeile)
        zurueck = MDButton(style="text", ripple_canvas_after=False)
        zurueck.add_widget(MDButtonText(text="← Zur Übersicht", halign="center"))
        zurueck.bind(on_release=lambda *_: self._zeige_uebersicht())
        hud_optik.volle_breite(zurueck)
        self._abfrage.add_widget(zurueck)

        self._karte = None
        self._rueckseite_offen = False

    def aktualisieren(self):
        self.clear_widgets()
        fach = self.fach()
        karten = fach.get("karten", []) if fach else []
        if not karten:
            self.add_widget(self._leer)
        else:
            self._zeige_uebersicht()

    def _zeige_uebersicht(self):
        self.clear_widgets()
        fach = self.fach()
        gesamt, faellig, gelernt, quote = lernen.statistik(
            fach.get("karten", []) if fach else [])
        self._stats.text = (f"{gesamt} Karten · {faellig} fällig · "
                            f"{gelernt} sitzen · {quote}% richtig")
        self.add_widget(self._uebersicht)

    def _generieren(self):
        fach = self.fach()
        stoff = lernen.fach_stoff(fach)
        if not stoff or len(stoff) < 40:
            self.status("Erst Quellen hinzufügen (Reiter 'Quelle').", True)
            return
        self.status("Erstelle Karteikarten ...")
        threading.Thread(target=self._worker, args=(stoff, self.thema()), daemon=True).start()

    def _worker(self, stoff, thema):
        karten, fehler = lernen.baue_karten(stoff, thema)
        Clock.schedule_once(lambda dt: self._fertig(karten, fehler))

    def _fertig(self, karten, fehler):
        if fehler or not karten:
            self.status(fehler or "Keine Karteikarten erhalten.", True)
            return
        fach = self.fach()
        vorhanden = {k.get("frage", "").strip().lower() for k in fach.get("karten", [])}
        neu = [k for k in karten if k.get("frage", "").strip().lower() not in vorhanden]
        fach.setdefault("karten", []).extend(neu)
        self.speichern(fach)
        self.aktualisieren()
        self.status(f"{len(neu)} neue Karte(n).")

    def _abfrage_starten(self):
        fach = self.fach()
        faellig = lernen.faellige_karten(fach.get("karten", []))
        if not faellig:
            self.status("Keine Karte ist gerade fällig.")
            return
        self._karte = faellig[0]
        self._rueckseite_offen = False
        self.clear_widgets()
        self.add_widget(self._abfrage)
        self._zeige_karte()

    def _zeige_karte(self):
        self._karte_frage.text = self._karte["frage"]
        if self._rueckseite_offen:
            self._karte_antwort.text = self._karte["antwort"]
            self._umdrehen_text.text = "Frage zeigen"
            self._bewertung_zeile.opacity = 1
            self._bewertung_zeile.disabled = False
        else:
            self._karte_antwort.text = ""
            self._umdrehen_text.text = "Antwort zeigen"
            self._bewertung_zeile.opacity = 0
            self._bewertung_zeile.disabled = True

    def _umdrehen(self):
        if not self._karte:
            return
        self._rueckseite_offen = not self._rueckseite_offen
        self._zeige_karte()

    def _bewerten(self, bewertung):
        if not self._karte:
            return
        lernen.bewerte_karte(self._karte, bewertung)
        fach = self.fach()
        for index, karte in enumerate(fach["karten"]):
            if karte.get("id") == self._karte.get("id"):
                fach["karten"][index] = self._karte
                break
        self.speichern(fach)
        tage = self._karte["intervall"]
        self.status(f"'{bewertung}' - nächste Wiederholung in " +
                   ("wenigen Minuten" if tage == 0 else f"{tage} Tag(en)") + ".")
        self._abfrage_starten()


class _ZettelTab(_TabBasis):
    """Generierte Zusammenfassung (Markdown -> Kivy-Markup)."""

    def __init__(self, fach_ebene, **kwargs):
        super().__init__(fach_ebene, **kwargs)
        self._leer, _ = _platzhalter(
            "Noch keine Zusammenfassung für dieses Fach.",
            "Zusammenfassung generieren", lambda: self._generieren())

        self._inhalt = MDBoxLayout(orientation="vertical")
        leiste = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="36dp",
                             padding=("8dp", "4dp"))
        leiste.add_widget(Widget())
        neu_knopf = MDIconButton(icon="refresh", ripple_canvas_after=False)
        neu_knopf.bind(on_release=lambda *_: self._generieren())
        leiste.add_widget(neu_knopf)
        self._inhalt.add_widget(leiste)
        self._text_label = MDLabel(text="", markup=True, adaptive_height=True)
        self._text_label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        innen = MDBoxLayout(orientation="vertical", padding="14dp", size_hint_y=None,
                           adaptive_height=True)
        innen.add_widget(self._text_label)
        scroll = MDScrollView()
        scroll.add_widget(innen)
        self._inhalt.add_widget(scroll)

    def aktualisieren(self):
        self.clear_widgets()
        fach = self.fach()
        text = (fach.get("zusammenfassung") or "") if fach else ""
        if not text:
            self.add_widget(self._leer)
        else:
            self._text_label.text = _zettel_markup(text)
            self.add_widget(self._inhalt)

    def _generieren(self):
        fach = self.fach()
        stoff = lernen.fach_stoff(fach)
        if not stoff or len(stoff) < 40:
            self.status("Erst Quellen hinzufügen (Reiter 'Quelle').", True)
            return
        self.status("Schreibe die Zusammenfassung ...")
        threading.Thread(target=self._worker, args=(stoff, self.thema()), daemon=True).start()

    def _worker(self, stoff, thema):
        text, fehler = lernen.baue_lernzettel(stoff, thema)
        Clock.schedule_once(lambda dt: self._fertig(text, fehler))

    def _fertig(self, text, fehler):
        if fehler or not text:
            self.status(fehler or "Zusammenfassung blieb leer.", True)
            return
        fach = self.fach()
        fach["zusammenfassung"] = text
        self.speichern(fach)
        self.aktualisieren()
        self.status(f"Zusammenfassung fertig ({len(text)} Zeichen).")


class _LueckenTab(_TabBasis):
    """Lueckentext: Nummerierte Luecken werden als eigene Eingabefelder unter
    dem Text angezeigt (statt inline wie auf dem PC - in Kivy robuster)."""

    def __init__(self, fach_ebene, **kwargs):
        super().__init__(fach_ebene, **kwargs)
        self._leer, _ = _platzhalter(
            "Noch kein Lückentext für dieses Fach.",
            "Lückentext generieren", lambda: self._generieren())

        self._inhalt = MDBoxLayout(orientation="vertical")
        leiste = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="36dp")
        leiste.add_widget(Widget())
        neu_knopf = MDIconButton(icon="refresh", ripple_canvas_after=False)
        neu_knopf.bind(on_release=lambda *_: self._generieren())
        leiste.add_widget(neu_knopf)
        self._inhalt.add_widget(leiste)

        self._text_label = MDLabel(text="", adaptive_height=True)
        self._text_label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        self._luecken_liste = MDBoxLayout(orientation="vertical", spacing="6dp",
                                          size_hint_y=None, adaptive_height=True)
        auswerten_knopf = MDButton(style="filled", ripple_canvas_after=False)
        auswerten_knopf.add_widget(MDButtonText(text="Auswerten", halign="center"))
        auswerten_knopf.bind(on_release=lambda *_: self._auswerten())
        hud_optik.volle_breite(auswerten_knopf)
        self._ergebnis = MDLabel(text="", theme_text_color="Secondary", adaptive_height=True)
        self._ergebnis.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))

        innen = MDBoxLayout(orientation="vertical", padding="14dp", spacing="12dp",
                           size_hint_y=None, adaptive_height=True)
        innen.add_widget(self._text_label)
        innen.add_widget(self._luecken_liste)
        innen.add_widget(auswerten_knopf)
        innen.add_widget(self._ergebnis)
        scroll = MDScrollView()
        scroll.add_widget(innen)
        self._inhalt.add_widget(scroll)
        self._daten = None
        self._eingaben = {}

    def aktualisieren(self):
        self.clear_widgets()
        fach = self.fach()
        daten = fach.get("luckentext") if fach else None
        if not daten:
            self.add_widget(self._leer)
        else:
            self._rendern(daten)
            self.add_widget(self._inhalt)

    def _rendern(self, daten):
        self._daten = daten
        self._eingaben = {}
        self._ergebnis.text = ""
        self._text_label.text = re.sub(r"___(\d+)___", r"[\1]", daten.get("text", ""))
        self._luecken_liste.clear_widgets()
        for nummer in sorted(daten.get("luecken", {}), key=lambda n: int(n)):
            zeile = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="48dp",
                                spacing="8dp")
            zeile.add_widget(MDLabel(text=f"[{nummer}]", adaptive_height=True,
                                     size_hint_x=None, width="36dp"))
            feld = MDTextField(mode="filled", multiline=False)
            zeile.add_widget(feld)
            self._eingaben[nummer] = feld
            self._luecken_liste.add_widget(zeile)

    def _generieren(self):
        fach = self.fach()
        stoff = lernen.fach_stoff(fach)
        if not stoff or len(stoff) < 40:
            self.status("Erst Quellen hinzufügen (Reiter 'Quelle').", True)
            return
        self.status("Baue den Lückentext ...")
        threading.Thread(target=self._worker, args=(stoff, self.thema()), daemon=True).start()

    def _worker(self, stoff, thema):
        daten, fehler = lernen.baue_luckentext(stoff, thema)
        Clock.schedule_once(lambda dt: self._fertig(daten, fehler))

    def _fertig(self, daten, fehler):
        if fehler or not daten:
            self.status(fehler or "Lückentext blieb leer.", True)
            return
        fach = self.fach()
        fach["luckentext"] = daten
        self.speichern(fach)
        self.aktualisieren()
        self.status(f"Lückentext fertig ({len(daten.get('luecken', {}))} Lücken).")

    def _auswerten(self):
        if not self._daten:
            return
        luecken = self._daten.get("luecken", {})
        richtig = 0
        falsch = []
        for nummer, feld in self._eingaben.items():
            soll = str(luecken.get(nummer, "")).strip().casefold()
            ist = feld.text.strip().casefold()
            if ist and ist == soll:
                richtig += 1
            else:
                falsch.append(f"{nummer}. {luecken.get(nummer, '')}")
        gesamt = len(self._eingaben)
        text = f"{richtig} von {gesamt} richtig."
        if falsch:
            falsch.sort(key=lambda t: int(t.split(".")[0]))
            text += " Richtige Lösungen: " + "; ".join(falsch)
        self._ergebnis.text = text


class _PruefungTab(_TabBasis):
    """KI-Pruefer: eine offene Frage, freie Antwort, Bewertung mit Note und
    Feedback (kern.lernen.naechste_frage/bewerte_antwort)."""

    def __init__(self, fach_ebene, **kwargs):
        super().__init__(fach_ebene, **kwargs)
        self._start, _ = _platzhalter(
            "Der KI-Prüfer stellt offene Fragen zum Stoff dieses Fachs und "
            "bewertet deine Antworten mit Feedback und Schulnote.",
            "Prüfung starten", lambda: self._starten())

        self._aktiv = MDBoxLayout(orientation="vertical", padding="16dp", spacing="10dp")
        self._frage_label = MDLabel(text="", font_style="Title", role="medium",
                                    adaptive_height=True)
        self._frage_label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        self._aktiv.add_widget(self._frage_label)
        self._antwort_feld = MDTextField(
            MDTextFieldHintText(text="Deine Antwort ..."), mode="filled", multiline=True,
            size_hint_y=None, height="100dp")
        self._aktiv.add_widget(self._antwort_feld)
        knopf_zeile = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="44dp",
                                  spacing="8dp")
        abgeben = MDButton(style="filled", ripple_canvas_after=False)
        abgeben.add_widget(MDButtonText(text="Antwort abgeben", halign="center"))
        abgeben.bind(on_release=lambda *_: self._abgeben())
        hud_optik.volle_breite(abgeben)
        knopf_zeile.add_widget(abgeben)
        beenden = MDButton(style="tonal", ripple_canvas_after=False)
        beenden.add_widget(MDButtonText(text="Beenden", halign="center"))
        beenden.bind(on_release=lambda *_: self._beenden())
        hud_optik.volle_breite(beenden)
        knopf_zeile.add_widget(beenden)
        self._aktiv.add_widget(knopf_zeile)
        self._feedback_label = MDLabel(text="", adaptive_height=True)
        self._feedback_label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        scroll = MDScrollView()
        scroll.add_widget(self._feedback_label)
        self._aktiv.add_widget(scroll)

        self._stoff = ""
        self._thema = ""
        self._gestellt = []
        self._noten = []
        self._laeuft = False

    def aktualisieren(self):
        self.clear_widgets()
        self.add_widget(self._start)

    def _starten(self):
        fach = self.fach()
        stoff = lernen.fach_stoff(fach)
        if not stoff or len(stoff) < 40:
            self.status("Erst Quellen hinzufügen (Reiter 'Quelle').", True)
            return
        self._stoff = stoff
        self._thema = self.thema()
        self._gestellt = []
        self._noten = []
        self.status("Stelle die erste Frage ...")
        threading.Thread(target=self._naechste_worker, daemon=True).start()

    def _naechste_worker(self):
        frage, fehler = lernen.naechste_frage(self._stoff, self._thema, self._gestellt)
        Clock.schedule_once(lambda dt: self._frage_da(frage, fehler))

    def _frage_da(self, frage, fehler):
        if fehler or not frage:
            self.status(fehler or "Keine Frage erhalten.", True)
            return
        self._gestellt.append(frage)
        self._frage_label.text = frage
        self._antwort_feld.text = ""
        self._feedback_label.text = ""
        self.clear_widgets()
        self.add_widget(self._aktiv)
        self.status("")

    def _abgeben(self):
        if self._laeuft:
            return
        antwort = self._antwort_feld.text.strip()
        if not antwort:
            self.status("Erst eine Antwort schreiben.", True)
            return
        self._laeuft = True
        self.status("Bewerte deine Antwort ...")
        threading.Thread(target=self._bewerten_worker, args=(antwort,), daemon=True).start()

    def _bewerten_worker(self, antwort):
        bewertung, fehler = lernen.bewerte_antwort(self._gestellt[-1], antwort, self._stoff)
        Clock.schedule_once(lambda dt: self._bewertung_da(bewertung, fehler))

    def _bewertung_da(self, bewertung, fehler):
        self._laeuft = False
        if fehler or not bewertung:
            self.status(fehler or "Keine Bewertung erhalten.", True)
            return
        self._noten.append(bewertung["note"])
        zeilen = [f"{lernen.notentext(bewertung['note'])} · {bewertung['punkte']} von 10 Punkten"]
        for text in bewertung["richtig"]:
            zeilen.append(f"✓ {text}")
        for text in bewertung["fehlt"]:
            zeilen.append(f"✗ {text}")
        zeilen.append("")
        zeilen.append(bewertung["feedback"])
        if bewertung.get("musterantwort"):
            zeilen.append("")
            zeilen.append(f"Musterantwort: {bewertung['musterantwort']}")
        schnitt = sum(self._noten) / len(self._noten)
        zeilen.append("")
        zeilen.append(f"Durchschnitt nach {len(self._noten)} Frage(n): "
                      f"{lernen.notentext(schnitt)}")
        self._feedback_label.text = "\n".join(zeilen)
        self.status("Bereit für die nächste Frage.")
        Clock.schedule_once(lambda dt: self._naechste(), 0.6)

    def _naechste(self):
        threading.Thread(target=self._naechste_worker, daemon=True).start()

    def _beenden(self):
        self.clear_widgets()
        self.add_widget(self._start)
        self.status("")


class _MindmapTab(_TabBasis):
    """Nur die Erzeugung + kurze Vorschau - die eigentliche interaktive
    Grafik wird nativ als eigener Bildschirm gezeichnet (ScatterLayout,
    siehe app/screens/mindmap_screen.py in einer der naechsten Ausbaustufen)."""

    def __init__(self, fach_ebene, **kwargs):
        super().__init__(fach_ebene, **kwargs)
        self._leer, _ = _platzhalter("Noch keine Mindmap für dieses Fach.",
                                     "Mindmap generieren", lambda: self._generieren())
        self._inhalt = MDBoxLayout(orientation="vertical", padding="24dp", spacing="16dp")
        self._info = MDLabel(text="", theme_text_color="Secondary", adaptive_height=True,
                             halign="center")
        self._inhalt.add_widget(Widget())
        self._inhalt.add_widget(self._info)
        knopfzeile = MDBoxLayout(orientation="horizontal", spacing="10dp", size_hint_y=None,
                                 height="48dp", pos_hint={"center_x": 0.5})
        anzeigen = MDButton(style="filled", ripple_canvas_after=False)
        anzeigen.add_widget(MDButtonText(text="Anzeigen", halign="center"))
        anzeigen.bind(on_release=lambda *_: self._anzeigen())
        hud_optik.volle_breite(anzeigen)
        knopfzeile.add_widget(anzeigen)
        neu = MDButton(style="tonal", ripple_canvas_after=False)
        neu.add_widget(MDButtonText(text="Neu generieren", halign="center"))
        neu.bind(on_release=lambda *_: self._generieren())
        hud_optik.volle_breite(neu)
        knopfzeile.add_widget(neu)
        self._inhalt.add_widget(knopfzeile)
        self._inhalt.add_widget(Widget())

    def aktualisieren(self):
        self.clear_widgets()
        fach = self.fach()
        daten = fach.get("mindmap") if fach else None
        if not daten:
            self.add_widget(self._leer)
        else:
            self._info.text = (f'"{daten.get("thema", "Mindmap")}" · '
                               f'{len(daten.get("aeste", []))} Äste')
            self.add_widget(self._inhalt)

    def _generieren(self):
        fach = self.fach()
        stoff = lernen.fach_stoff(fach)
        if not stoff or len(stoff) < 40:
            self.status("Erst Quellen hinzufügen (Reiter 'Quelle').", True)
            return
        self.status("Ordne den Stoff zu einer Mindmap ...")
        threading.Thread(target=self._worker, args=(stoff, self.thema()), daemon=True).start()

    def _worker(self, stoff, thema):
        daten, fehler = lernen.baue_mindmap(stoff, thema)
        Clock.schedule_once(lambda dt: self._fertig(daten, fehler))

    def _fertig(self, daten, fehler):
        if fehler or not daten:
            self.status(fehler or "Mindmap blieb leer.", True)
            return
        fach = self.fach()
        fach["mindmap"] = daten
        self.speichern(fach)
        self.aktualisieren()
        self.status(f"Mindmap mit {len(daten.get('aeste', []))} Ästen.")

    def _anzeigen(self):
        fach = self.fach()
        daten = fach.get("mindmap") if fach else None
        if not daten:
            return
        # Die interaktive Mindmap-Grafik (ScatterLayout-Ansicht) kommt in
        # einer der naechsten Ausbaustufen - bis dahin ehrlich sagen, dass
        # der Knopf noch nichts oeffnet, statt so zu tun als ob.
        self.status("Die interaktive Mindmap-Ansicht folgt im nächsten Schritt.")
