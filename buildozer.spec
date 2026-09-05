[app]
title = Uranus
package.name = uranus
package.domain = com.manfredmeier

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,env

version = 0.1

# Bewusst schlank gehalten (nur reines Python) - vermeidet riskante
# Cross-Compile-Schritte fuer kompilierte Abhaengigkeiten beim Android-Bau.
# materialyoucolor fest angegeben: python-for-android baut aktuell zwingend
# gegen Python 3.14 (bekannter, offener Fehler in python-for-android), und
# ohne diese Angabe versucht pip eine Version zu installieren, die es fuer
# 3.14 gar nicht gibt - das liess den vorigen Bau mit "ResolutionImpossible"
# scheitern. 3.0.1 ist laut den p4a-Fehlermeldungen fuer 3.14 tatsaechlich
# verfuegbar.
requirements = python3,kivy,kivymd,materialyoucolor==3.0.1,requests,python-dotenv

orientation = portrait
fullscreen = 0

# INTERNET wird fuer die Gemini-Anfragen gebraucht.
android.permissions = INTERNET

# Ohne das hier zielt Buildozer auf eine veraltete Android-Version - genau das
# hat Google Play Protect als "unsichere App" blockiert ("fuer eine aeltere
# Android-Version entwickelt, bietet keinen aktuellen Datenschutz"). Google
# verlangt seit 2026 mindestens API 35 (Android 15).
android.api = 35
android.sdk = 35
android.minapi = 24

android.archs = arm64-v8a

[buildozer]
log_level = 2
