"""Konstanten für JBL Bar."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "jbl_bar"
MANUFACTURER: Final = "HARMAN / JBL"

# Alle 10 s Zustand (an/aus, Quelle, Lautstärke, Titel); Einstellungen nur jede Minute oder direkt nach einer Änderung.
SCAN_INTERVAL: Final = timedelta(seconds=10)
SLOW_EVERY: Final = 6
# So viele fehlgeschlagene Abfragen in Folge überbrückt der alte Zustand (Standby-Wechsel trennt kurz).
MAX_MISSES: Final = 1
# GENA-Abo der Bar: 300 s, eine Minute vor Ablauf erneuern.
EVENT_TIMEOUT: Final = 300

# Quellen, die `setMediaSource` annimmt, und ihre Anzeigenamen (auch Rückweg aus `getStreamingStatus`).
SOURCES: Final = {"TV": "TV", "HDMI": "HDMI", "BT": "Bluetooth"}
SOURCE_ALIASES: Final = {"BLUETOOTH": "BT", "HDMI1": "HDMI", "HDMI2": "HDMI", "HDMI3": "HDMI"}

# 7-Band-EQ (JBL One 3.0): Frequenz → Index in `eq_payload.gain`; 125 Hz geht tiefer als die anderen.
EQ_BANDS: Final = (125, 250, 500, 1000, 2000, 4000, 8000)
EQ_CUSTOM_ID: Final = "0"

# Sleep-Timer in Minuten (0 = aus); die Bar will Sekunden.
SLEEP_OPTIONS: Final = (0, 15, 30, 45, 60, 90, 120)

AUDIO_SYNC_MAX: Final = 250
