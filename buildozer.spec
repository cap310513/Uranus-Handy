[app]
title = Uranus
package.name = uranus
package.domain = com.manfredmeier

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,env

version = 0.1

# kivymd kommt bewusst als Quellcode-Archiv (GitHub-Zip), nicht als PyPI-Paket:
# Kivy selbst wird aus dem Quellcode gebaut (keine PyPI-Pakete dafuer
# vorhanden), aber die normale kivymd-Installation verlangt trotzdem eine
# PyPI-Version von Kivy - das schlug bisher mit "ResolutionImpossible" fehl.
# Die Einzelabhaengigkeiten von kivymd stehen deshalb einzeln hier (siehe
# kivymd 2.0.0 requires_dist auf PyPI: kivy, pillow, materialyoucolor,
# materialshapes, asynckivy). pycairo war ein Fehlgriff von mir (aus einem
# fremden Beispielprojekt kopiert) - kivymd braucht das gar nicht, es hat nur
# eine anfaellige, unnoetige Bibliothekskette (freetype/cairo/webp)
# nachgezogen, an der ein fremder Server wiederholt mit 502 scheiterte.
requirements = python3,kivy==2.3.1,https://github.com/kivymd/KivyMD/archive/master.zip,asynckivy,asyncgui,materialyoucolor==3.0.4,materialshapes,requests,python-dotenv

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

# Die stabile python-for-android-Version kennt die noetigen Korrekturen fuer
# das (sehr neue) Python 3.14 noch nicht - der develop-Zweig schon, nach dem
# Vorbild desselben funktionierenden Beispielprojekts.
p4a.branch = develop

[buildozer]
log_level = 2
