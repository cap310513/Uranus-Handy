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
# materialshapes, asynckivy).
#
# WICHTIG: pycairo UND pillow sind noetig - live auf dem echten Handy per adb
# logcat gefunden: sobald man IRGENDEINEN Knopf/Karte antippt (Hover-/State-
# Layer-Verhalten in fast jedem M3-Widget), laedt KivyMD intern
# kivymd.uix.list -> kivymd.uix.fitimage -> materialshapes nach, das
# zwingend "import cairo" UND "import PIL" braucht - ohne die beiden also ein
# Absturz bei JEDER Beruehrung eines Knopfes. pycairo zieht freetype/
# libcairo/libwebp als Bauregeln nach sich - freetypes Standardquelle
# (download.savannah.gnu.org) ist wiederholt (auch nach mehreren
# automatischen Versuchen) mit HTTP 502/504 ausgefallen. Deshalb eigene
# Bauregel in p4a-recipes/freetype mit SourceForge als Quelle stattdessen
# (siehe p4a.local_recipes unten).
requirements = python3,kivy==2.3.1,https://github.com/kivymd/KivyMD/archive/master.zip,asynckivy,asyncgui,materialyoucolor==3.0.4,materialshapes,pycairo,pillow,requests,python-dotenv

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

# Eigene freetype-Bauregel (siehe oben) statt der eingebauten - identisch,
# nur mit SourceForge statt dem ausfallenden download.savannah.gnu.org.
p4a.local_recipes = p4a-recipes

[buildozer]
log_level = 2
