# -*- coding: utf-8 -*-
"""
Spracheingabe (Diktieren) und Sprachausgabe (Vorlesen) - beides ueber
Androids eigene, kostenlose Bordmittel per pyjnius (bereits Teil jedes
Android-Baus, keine neue Abhaengigkeit noetig).

Auf dem PC tun alle Funktionen hier bewusst NICHTS (statt einen Fehler zu
werfen) - Android-Bordmittel wie RecognizerIntent/TextToSpeech gibt es dort
schlicht nicht. So kann derselbe Code ueberall aufgerufen werden, ohne an
jeder Stelle eine Plattform-Abfrage zu brauchen.
"""
import os

from kivy.utils import platform

_TTS_MOTOR = None
_EINSTELLUNG_DATEI_NAME = "vorlesen_an.txt"


def ist_android():
    return platform == "android"


def _einstellung_pfad():
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None:
            os.makedirs(app.user_data_dir, exist_ok=True)
            return os.path.join(app.user_data_dir, _EINSTELLUNG_DATEI_NAME)
    except Exception:
        pass
    return None


def ist_vorlesen_an():
    """Ob Antworten automatisch vorgelesen werden sollen. Standard: an."""
    pfad = _einstellung_pfad()
    if pfad and os.path.exists(pfad):
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                return f.read().strip() != "aus"
        except Exception:
            pass
    return True


def vorlesen_umschalten(an):
    pfad = _einstellung_pfad()
    if not pfad:
        return
    with open(pfad, "w", encoding="utf-8") as f:
        f.write("an" if an else "aus")
    if not an:
        stumm()


# ----------------------------------------------------------------------
# Diktieren (Spracheingabe)
# ----------------------------------------------------------------------

def diktieren(erfolg_callback, fehler_callback=None):
    """
    Startet Androids eigenen Diktier-Dialog (RecognizerIntent) - der Nutzer
    spricht, Android erkennt den Text selbst, wir bekommen nur das fertige
    Ergebnis zurueck. Auf dem PC ruft das sofort fehler_callback() auf.
    """
    if not ist_android():
        if fehler_callback:
            fehler_callback("Spracheingabe funktioniert nur auf dem echten Handy.")
        return
    try:
        from android import activity
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        RecognizerIntent = autoclass("android.speech.RecognizerIntent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "de-DE")
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Sprich jetzt ...")

        anfrage_code = 1001

        def on_activity_result(request_code, result_code, data):
            if request_code != anfrage_code:
                return
            activity.unbind(on_activity_result=on_activity_result)
            ERGEBNIS_OK = -1  # android.app.Activity.RESULT_OK
            try:
                if result_code != ERGEBNIS_OK or data is None:
                    if fehler_callback:
                        fehler_callback("Nichts verstanden.")
                    return
                ergebnisse = data.getStringArrayListExtra(
                    RecognizerIntent.EXTRA_RESULTS)
                if ergebnisse and ergebnisse.size() > 0:
                    erfolg_callback(ergebnisse.get(0))
                elif fehler_callback:
                    fehler_callback("Nichts verstanden.")
            except Exception as exc:
                if fehler_callback:
                    fehler_callback(f"Spracherkennung fehlgeschlagen: {exc}")

        activity.bind(on_activity_result=on_activity_result)
        PythonActivity.mActivity.startActivityForResult(intent, anfrage_code)
    except Exception as exc:
        if fehler_callback:
            fehler_callback(f"Spracherkennung nicht verfügbar: {exc}")


# ----------------------------------------------------------------------
# Vorlesen (Sprachausgabe)
# ----------------------------------------------------------------------
_TTS_WIRD_ERSTELLT = False
_TTS_BEREIT = False
_TTS_FEHLGESCHLAGEN = False


def _tts_erstellen():
    """
    Baut den TextToSpeech-Motor - MUSS auf Androids Haupt-/UI-Thread laufen,
    sonst verweigert Android das mit "Can't create handler inside thread that
    has not called Looper.prepare()" (TextToSpeech braucht intern einen
    Handler/Looper fuer seinen Init-Rueckruf). Kivys eigener Python-Thread ist
    auf Android NICHT der UI-Thread - deshalb @run_on_ui_thread statt eines
    normalen Funktionsaufrufs. Live auf dem Geraet getestet: ohne das hier
    blieb "Vorlesen" wirkungslos, ohne dass ueberhaupt ein Fehler auftauchte
    (der Motor wurde nie fertig, jeder speak()-Aufruf lief ins Leere).

    WICHTIG: TextToSpeech(...) liefert das Motor-Objekt SOFORT zurueck, auch
    wenn die eigentliche Initialisierung noch laeuft - erst der Rueckruf
    onInit(status) sagt verlaesslich, ob der Motor wirklich bereit ist. Ein
    speak()-Aufruf VOR diesem Rueckruf verschluckt sich live beobachtet
    ebenfalls kommentarlos. Deshalb wird _TTS_BEREIT erst dort gesetzt, nicht
    schon direkt nach dem Konstruktor.
    """
    global _TTS_MOTOR, _TTS_BEREIT, _TTS_FEHLGESCHLAGEN, _INIT_HOERER
    try:
        from jnius import PythonJavaClass, autoclass, java_method

        TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Locale = autoclass("java.util.Locale")

        class _InitHoerer(PythonJavaClass):
            __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
            __javacontext__ = "app"

            @java_method("(I)V")
            def onInit(self, status):
                global _TTS_BEREIT, _TTS_FEHLGESCHLAGEN
                if status == TextToSpeech.SUCCESS:
                    _TTS_BEREIT = True
                else:
                    print(f"[Sprache] TextToSpeech-Init fehlgeschlagen (status={status})")
                    _TTS_FEHLGESCHLAGEN = True

        # Der Hoerer muss am Leben bleiben, sonst raeumt Python ihn vorzeitig
        # weg und Android verliert die Rueckruf-Verbindung.
        _INIT_HOERER = _InitHoerer()
        motor = TextToSpeech(PythonActivity.mActivity, _INIT_HOERER)
        motor.setLanguage(Locale.GERMANY)
        _TTS_MOTOR = motor
    except Exception as exc:
        print(f"[Sprache] TextToSpeech konnte nicht gestartet werden: {exc}")
        _TTS_FEHLGESCHLAGEN = True


def vorlesen(text, _versuch=0):
    """Liest den Text laut vor, wenn Vorlesen eingeschaltet ist. Tut auf dem
    PC und bei ausgeschaltetem Vorlesen bewusst nichts."""
    global _TTS_WIRD_ERSTELLT
    if not text or not ist_android() or not ist_vorlesen_an() or _TTS_FEHLGESCHLAGEN:
        return
    try:
        if not _TTS_BEREIT:
            if not _TTS_WIRD_ERSTELLT:
                _TTS_WIRD_ERSTELLT = True
                from android.runnable import run_on_ui_thread
                run_on_ui_thread(_tts_erstellen)()
            # Der Motor braucht (asynchron, auf dem UI-Thread) einen Moment
            # zum Starten - statt den allerersten Vorlesen-Aufruf stumm zu
            # verschlucken, bis zu 10 Sekunden lang geduldig erneut versuchen
            # (ein kalter Start des Sprachmotors kann laenger dauern als die
            # zuvor zu knapp bemessenen 2 Sekunden).
            if _versuch < 20:
                from kivy.clock import Clock
                Clock.schedule_once(
                    lambda dt: vorlesen(text, _versuch + 1), 0.5)
            elif _versuch == 20:
                print("[Sprache] TextToSpeech wurde nach 10s nicht bereit.")
            return
        from jnius import autoclass
        TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
        ergebnis = _TTS_MOTOR.speak(text, TextToSpeech.QUEUE_FLUSH, None, None)
        if ergebnis != TextToSpeech.SUCCESS:
            print(f"[Sprache] speak() meldet Fehler (Rueckgabewert {ergebnis})")
    except Exception as exc:
        print(f"[Sprache] Vorlesen fehlgeschlagen: {exc}")


def stumm():
    """Bricht eine laufende Vorlesung sofort ab."""
    if _TTS_MOTOR is not None:
        try:
            _TTS_MOTOR.stop()
        except Exception:
            pass
