# -*- coding: utf-8 -*-
"""
Echte Live-Daten fuer den "Daily Briefing"-Reiter: Wetter, Kryptowaehrungen,
eine Aktie, aktuelle Kurznachrichten.

Eigenstaendig geschrieben (siehe Regel 5), aber nach demselben Muster wie die
gleichnamigen Funktionen in der PC-Version (uranus_tools.py) - alles ueber
oeffentliche, kostenlose Schnittstellen ohne eigenen API-Key:
Open-Meteo (Wetter), CoinGecko (Krypto), Yahoo Finance (Aktien), oeffentliche
RSS-Feeds (Nachrichten).
"""
import xml.etree.ElementTree as ET

import requests

_TIMEOUT = 10
_USER_AGENT = "Uranus-Mobile/0.1"


def _leer(titel, fehler):
    return {"ok": False, "titel": titel, "wert": "—", "zeilen": [],
            "fehler": str(fehler)[:120]}


def wetter(ort="Berlin", lat=52.52, lon=13.405):
    """Aktuelles Wetter plus Tageshoechst-/-tiefstwert."""
    WETTERCODES = {
        0: "klar", 1: "überwiegend klar", 2: "teils bewölkt", 3: "bedeckt",
        45: "Nebel", 48: "Reifnebel", 51: "leichter Nieselregen",
        53: "Nieselregen", 61: "leichter Regen", 63: "Regen",
        65: "starker Regen", 71: "leichter Schneefall", 73: "Schneefall",
        80: "Regenschauer", 95: "Gewitter",
    }
    try:
        antwort = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
                "daily": "temperature_2m_max,temperature_2m_min",
                "forecast_days": 1, "timezone": "auto",
            }, timeout=_TIMEOUT)
        antwort.raise_for_status()
        daten = antwort.json()
        jetzt = daten.get("current", {})
        grad = jetzt.get("temperature_2m")
        code = int(jetzt.get("weather_code", 0))
        taeglich = daten.get("daily", {})
        hoch = (taeglich.get("temperature_2m_max") or [None])[0]
        tief = (taeglich.get("temperature_2m_min") or [None])[0]

        zeilen = [
            ("Zustand", WETTERCODES.get(code, f"Code {code}")),
            ("Wind", f"{jetzt.get('wind_speed_10m', 0):.0f} km/h"),
            ("Luftfeuchte", f"{jetzt.get('relative_humidity_2m', 0):.0f} %"),
        ]
        if hoch is not None and tief is not None:
            zeilen.append(("Heute", f"{tief:.0f} bis {hoch:.0f} Grad"))

        return {"ok": True, "titel": f"Wetter {ort}",
                "wert": f"{grad:.1f}°" if grad is not None else "—",
                "zeilen": zeilen, "fehler": ""}
    except Exception as exc:
        return _leer(f"Wetter {ort}", exc)


def krypto(muenzen=("bitcoin", "ethereum"), waehrung="eur"):
    """Aktuelle Kurse samt Tagesveraenderung."""
    try:
        antwort = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ",".join(muenzen), "vs_currencies": waehrung,
                    "include_24hr_change": "true"},
            timeout=_TIMEOUT)
        antwort.raise_for_status()
        daten = antwort.json()

        zeilen = []
        for muenze in muenzen:
            eintrag = daten.get(muenze, {})
            if eintrag.get(waehrung) is None:
                continue
            aenderung = eintrag.get(f"{waehrung}_24h_change") or 0.0
            zeilen.append((
                muenze.title(),
                f"{eintrag[waehrung]:,.0f} {waehrung.upper()} ({aenderung:+.1f} %)"
                .replace(",", "."),
            ))
        haupt = daten.get(muenzen[0], {})
        return {"ok": True, "titel": "Kryptowährungen",
                "wert": f"{haupt.get(waehrung, 0):,.0f} {waehrung.upper()}".replace(",", "."),
                "zeilen": zeilen, "fehler": ""}
    except Exception as exc:
        return _leer("Kryptowährungen", exc)


def aktie(symbol="AAPL", name=None):
    """Aktueller Kurs ueber die oeffentliche Yahoo-Finance-Schnittstelle."""
    try:
        antwort = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range": "5d", "interval": "1d"}, timeout=_TIMEOUT)
        antwort.raise_for_status()
        ergebnis = antwort.json()["chart"]["result"][0]
        meta = ergebnis["meta"]
        preis = meta.get("regularMarketPrice")
        vortag = meta.get("chartPreviousClose") or preis
        waehrung = meta.get("currency", "USD")
        trend = ((preis - vortag) / vortag * 100.0) if vortag else 0.0

        return {"ok": True, "titel": name or f"Aktie {symbol}",
                "wert": f"{preis:.2f} {waehrung}",
                "zeilen": [("Veränderung heute", f"{trend:+.2f} %")],
                "fehler": ""}
    except Exception as exc:
        return _leer(name or f"Aktie {symbol}", exc)


_FEEDS = [
    ("Tagesschau", "https://www.tagesschau.de/xml/rss2/"),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
]


def schlagzeilen(anzahl=4):
    """Die neuesten Meldungen aus oeffentlichen RSS-Feeds - keine Erfindung."""
    eintraege = []
    for quelle, url in _FEEDS:
        try:
            antwort = requests.get(
                url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT)
            antwort.raise_for_status()
            wurzel = ET.fromstring(antwort.content)
            for item in wurzel.iter():
                if not item.tag.endswith("item"):
                    continue
                titel_element = item.find("title")
                titel = (titel_element.text or "").strip() if titel_element is not None else ""
                if titel:
                    eintraege.append((quelle, titel[:90]))
        except Exception:
            continue
        if len(eintraege) >= anzahl:
            break

    if not eintraege:
        return _leer("Weltgeschehen", "Keine Meldungen erreichbar")
    return {"ok": True, "titel": "Weltgeschehen",
            "wert": f"{len(eintraege)} Meldungen", "zeilen": eintraege[:anzahl],
            "fehler": ""}


# ----------------------------------------------------------------------
# Frage-Erkennung fuer den Chat: manche Fragen sollen ECHTE Zahlen bekommen
# statt Gemini raten zu lassen (das Modell hat keinen Internetzugriff und hat
# genau das zugegeben: "dazu habe ich gerade keinen Live-Ticker").
# ----------------------------------------------------------------------
_WELTGESCHEHEN_WOERTER = ("welt", "weltgeschehen", "nachrichten", "news",
                          "schlagzeilen", "was passiert", "aktuelles")
_WETTER_WOERTER = ("wetter", "temperatur", "grad draußen", "regnet", "schneit")
_KRYPTO_WOERTER = ("bitcoin", "ethereum", "krypto", "kryptowährung")


def erkenne_frage(text):
    """
    Erkennt, ob eine Chat-Frage mit echten Live-Daten statt einer Modell-
    Vermutung beantwortet werden sollte. Rueckgabe: eine der obigen
    Funktionen (parameterlos aufrufbar) oder None.
    """
    low = (text or "").lower()
    if any(wort in low for wort in _WELTGESCHEHEN_WOERTER):
        return schlagzeilen
    if any(wort in low for wort in _WETTER_WOERTER):
        return wetter
    if any(wort in low for wort in _KRYPTO_WOERTER):
        return krypto
    return None
