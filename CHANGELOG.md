# Changelog

## 26.11.1 – 02.11.2026

- **New: announcements.** The media player can play media now (`media_player.play_media`, media browser for audio
  from media sources), so `tts.speak` and other announcements come out of the bar. With `announce` the bar is woken
  from standby and unmuted if needed, plays the announcement and then gets its source (TV, HDMI, Bluetooth), volume,
  mute and standby back. An own volume for announcements can be set in the integration's options (0 keeps the
  current volume). Playback goes through the bar's UPnP media renderer (AVTransport `SetAVTransportURI` + `Play`).
- **Fix:** If the bar is set up with a host name and its IP address changes (DHCP), its UPnP events (audio format)
  get through again without reloading the integration: an event from an unknown address makes the integration look
  up the name again (at most once a minute). Bars set up with an IP address were already covered (zeroconf updates
  the address and reloads the entry).
- **Fix:** The UPnP event subscription is renewed before the timeout the bar granted runs out, also for short
  timeouts (before, anything under 90 seconds lapsed before the renewal). After a failed subscription the next
  attempt now comes after 5 minutes as documented (was 4).

## 26.10.3 – 19.10.2026

- **Fix:** If Home Assistant starts while the bar is in standby, the settings and the rear speakers (battery, docked, connected) are read right away again instead of staying unavailable until the bar is switched on. In standby the settings are refreshed once a minute; playback is still not polled.

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
