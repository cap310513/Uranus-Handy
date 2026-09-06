# -*- coding: utf-8 -*-
"""
Sicherheitsabstaende zu Androids Status- und System-Navigationsleiste.

Seit Android 15 (API 35, siehe buildozer.spec: android.api = 35) zeichnet
jede App zwingend "edge-to-edge" - der Bildschirminhalt reicht dadurch ohne
eigenes Zutun bis unter Status- und System-Navigationsleiste. Ohne diese
Datei hier ueberlappen Kopfzeilen und die App-eigene Navigationsleiste am
unteren Rand mit Androids eigenen Leisten (live auf einem Samsung Galaxy
S25 FE gemeldet: Uhr/Akku oben ueberdeckt den Titel, die App-Navigation
unten ueberlappt mit Android-eigenem Zurueck/Home/Uebersicht).

Auf dem PC (kein Android) meldet alles hier immer (0, 0) - dort gibt es
weder Status- noch System-Navigationsleiste.
"""
from kivy.clock import Clock
from kivy.utils import platform

_ist_android = platform == "android"
_HOERER = None  # muss am Leben bleiben, sonst verliert Android die Rueckruf-Verbindung


def registriere(callback):
    """
    Ruft callback(oben_px, unten_px) mit der Hoehe von Androids Status- und
    System-Navigationsleiste auf - einmal sofort mit (0, 0), und auf Android
    danach erneut, sobald das echte Layout steht (kurz nach dem Start) oder
    sich die Leisten aendern (z.B. beim Wechsel zwischen Gesten- und
    3-Tasten-Navigation). Auf dem PC bleibt es bei der einen (0, 0)-Meldung.
    """
    callback(0, 0)
    if not _ist_android:
        return
    try:
        from android.runnable import run_on_ui_thread
        run_on_ui_thread(lambda: _registrieren_auf_ui_thread(callback))()
    except Exception as exc:
        print(f"[SystemRaender] Registrierung fehlgeschlagen: {exc}")


def _registrieren_auf_ui_thread(callback):
    """
    MUSS auf Androids Haupt-/UI-Thread laufen (siehe kern/sprache.py,
    _tts_erstellen(), fuer denselben Grundsatz bei TextToSpeech) - Kivys
    eigener Python-Thread ist auf Android NICHT der UI-Thread, und das
    Registrieren eines View-Listeners gehoert dorthin.
    """
    global _HOERER
    from jnius import PythonJavaClass, autoclass, java_method

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    decor_view = PythonActivity.mActivity.getWindow().getDecorView()

    def _melden(insets):
        oben, unten = _system_balken_lesen(insets)
        Clock.schedule_once(lambda dt: callback(oben, unten))

    class _EinblendungsHoerer(PythonJavaClass):
        __javainterfaces__ = ["android/view/View$OnApplyWindowInsetsListener"]
        __javacontext__ = "app"

        @java_method(
            "(Landroid/view/View;Landroid/view/WindowInsets;)"
            "Landroid/view/WindowInsets;"
        )
        def onApplyWindowInsets(self, view, insets):
            _melden(insets)
            return insets

    _HOERER = _EinblendungsHoerer()
    decor_view.setOnApplyWindowInsetsListener(_HOERER)

    vorhandene = decor_view.getRootWindowInsets()
    if vorhandene is not None:
        _melden(vorhandene)


def _system_balken_lesen(insets):
    """
    (oben_px, unten_px) ueber die moderne Insets-API (Android 11+/API 30+).
    Fuer Geraete zwischen unserem android.minapi = 24 und API 29 gibt es
    diese API noch nicht - Ruckfall auf die dort verfuegbaren, seit Android 5
    existierenden (wenn auch inzwischen als deprecated markierten) Methoden.
    """
    try:
        from jnius import autoclass
        Type = autoclass("android.view.WindowInsets$Type")
        balken = insets.getInsets(Type.systemBars())
        return balken.top, balken.bottom
    except Exception:
        try:
            return (insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetBottom())
        except Exception:
            return 0, 0
