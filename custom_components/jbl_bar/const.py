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
# Without a subscription (bar unreachable, SUBSCRIBE refused) try again after 5 minutes; polling keeps running.
EVENT_RETRY: Final = 300

# Quellen, die `setMediaSource` annimmt, und ihre Anzeigenamen (auch Rückweg aus `getStreamingStatus`).
SOURCES: Final = {"TV": "TV", "HDMI": "HDMI", "BT": "Bluetooth"}
SOURCE_ALIASES: Final = {"BLUETOOTH": "BT", "HDMI1": "HDMI", "HDMI2": "HDMI", "HDMI3": "HDMI"}

# 7-Band-EQ (JBL One 3.0): Frequenz → Index in `eq_payload.gain`; 125 Hz geht tiefer als die anderen.
EQ_BANDS: Final = (125, 250, 500, 1000, 2000, 4000, 8000)
EQ_CUSTOM_ID: Final = "0"

# Sleep-Timer in Minuten (0 = aus); die Bar will Sekunden.
SLEEP_OPTIONS: Final = (0, 15, 30, 45, 60, 90, 120)
# Values of the product setting "FlexListening" (rear speakers detached, called Broadcast in the app)
BROADCAST_MODES: Final = {"0": "off", "1": "mono", "2": "stereo"}
# Levels of detached rear speakers. The app menu is a web view outside the APK, so the numbers are inferred.
REAR_VOLUME_LEVELS: Final = {0: "muted", 1: "low", 2: "medium", 3: "high"}

AUDIO_SYNC_MAX: Final = 250

# Announcements (media_player.play_media with announce): option for an own volume, 0 = keep the current volume.
CONF_ANNOUNCE_VOLUME: Final = "announce_volume"
# Wait this long for the bar to start playing, then at most this long for the end; checked every ANNOUNCE_POLL s.
ANNOUNCE_START_TIMEOUT: Final = 15.0
ANNOUNCE_MAX: Final = 600.0
ANNOUNCE_POLL: Final = 1.0
# After an announcement the bar switches back from network playback only seconds after setMediaSource (test bar:
# about 4 s), and that switch wakes it: standby waits until AVTransport's PlayMedium shows the input, at most this long.
ANNOUNCE_SOURCE_TIMEOUT: Final = 15.0
PLAY_MEDIUM: Final = {"TV": "TV", "HDMI": "HDMI", "BT": "BLUETOOTH"}
