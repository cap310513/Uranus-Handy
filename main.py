# -*- coding: utf-8 -*-
"""
Duenner Einstiegspunkt fuer buildozer/python-for-android.

Der Android-Baumeister erwartet ein 'main.py' direkt im Projekt-Wurzelordner.
Die eigentliche App liegt in app/main.py (siehe dort) - dieses File ruft sie
nur auf, damit die bestehende Ordnerstruktur (kern/, app/) unangetastet bleibt.
"""
from app.main import UranusMobileApp

if __name__ == "__main__":
    UranusMobileApp().run()
