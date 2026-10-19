# Changelog

## 26.10.2 – 19.10.2026

- **Fix:** Unknown entries in the bar's lists (EQ presets, rear speakers) no longer cause an error while reading the settings; valid entries are kept.
- UPnP events without a length header are now capped at 64 KB while reading (before, the limit only applied with Content-Length).
- If unsubscribing from the UPnP events fails with a network error while unloading, this now only shows up in the debug output instead of as an error in the log.
- **Fix:** An EQ band the bar does not report now gives an understandable error message instead of a crash.
- **Fix:** The media player's "Audio format" attribute is translated again (the translation key was switched off).
- **Fix:** If the bar is set up with a host name instead of an IP address, its UPnP events now get through (the sender
  check resolves the name on startup).
- In standby Home Assistant only asks for the power state (no playback or stream queries); after switching on,
  playback and settings are read right away.
- The event route checks whether the entry is loaded; finding the own IP address no longer blocks the event loop;
  the SSL context is built once and shared; the UNSUBSCRIBE response is released.
- Tests use fictitious addresses, MAC, serial number and metadata.
- Tooling: GitHub checks (ruff, mypy, translations, pytest with a coverage threshold, hassfest, weekly against
  the latest Home Assistant), `tools/pruefe-uebersetzungen.py`, `tools/next-version` from the shared template; template
  leftovers (ruff `dev/**`, mypy astral, pytest markers) removed.

## 26.10.1 – 16.10.2026

- **New version numbers:** From now on the version counts **year.month.number of the release in that month**: `26.10.1` is the first release in October 2026, next month starts again at `.1` (for example `26.11.1`). The jump from `1.0.1` to `26.10.1` is intentional: Home Assistant recognises `26.10.1` as newer, and the update shows up as usual.

## 1.0.1 – 13.10.2026
- Checked against the Integration Quality Scale (self-assessed platinum, see `quality_scale.yaml`).
- Download diagnostics (without IP address, MAC address and serial number).
- Rear speakers that only show up after startup get their entities without a reload; rears the bar
  no longer reports can be deleted.
- Error messages translated (English and German).
- A single connection dropout no longer makes the entities "unavailable" right away.
- README: troubleshooting, removal, more limitations. Type checking with `mypy --strict`.

## 1.0.0 – 07.10.2026
- First version: a rewrite replacing `jbl_integration` (same entity IDs), media player, true power state,
  audio sync, sleep timer, feedback tones, source, Dolby Atmos sensor, Atmos level; UPnP events in the background.
