[app]
title = Uranus
package.name = uranus
package.domain = com.manfredmeier

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,env

version = 0.1

# Bewusst schlank gehalten (nur reines Python) - vermeidet riskante
# Cross-Compile-Schritte fuer kompilierte Abhaengigkeiten beim Android-Bau.
requirements = python3,kivy,kivymd,requests,python-dotenv

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
