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

android.archs = arm64-v8a

[buildozer]
log_level = 2
