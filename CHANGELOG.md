# Changelog

## 26.11.5 – 08.11.2026

- **New (beta): Broadcast for detached rear speakers.** Bars that report the feature (seen in the JBL One app on the
  BAR 1000 MK2 with OneOS 4.0) get `select.jbl_bar_1000_broadcast` with off, mono and stereo (#4).
- **New (beta): Deep sleep switch** on bars that report the feature.
- The diagnostics download lists what the bar reports as supported features.

## 26.11.4 – 07.11.2026

- **Fix:** The battery of a rear speaker no longer shows 255 percent. An empty rear speaker reports 255 when it has
  no reading, which now shows up as "unknown" until the speaker reports a real value again (#3).
- **Fix:** Bars that leave their MAC address out of the network announcement (seen on the BAR 800) are found
  automatically again. The MAC then comes from the bar itself, so these bars show up under discovered devices and
  a new IP address is taken over (#2).

## 26.11.3 – 06.11.2026

- **Fix:** After an announcement from standby the bar stays in standby again. Coming back from network playback,
  the bar switches to the previous input only a few seconds after the command, and that switch woke it again right
  after the restored standby. Standby now waits until the bar shows the input again (at most 15 seconds).

## 26.11.2 – 06.11.2026

- **Fix:** Commands to the bar (for example turning it on) and the restore after an announcement (source, volume,
  standby) no longer fail now and then with "Server disconnected". The bar's web server closes an idle connection
  after about 6 seconds, but Home Assistant's connection pool kept reusing it for up to 15 seconds. Every request
  now asks the bar to close the connection after its answer.
- **Fix:** The audio format (sensor and media player attribute) is empty again when nothing comes in. The bar sends
  the codec as blanks then, which showed up as an empty-looking value instead of "unknown".
- Two pairs of entities had the same name: the new source select is called "Input" ("Eingang") now, next to the
  "Source" sensor, and the Atmos button "Next Atmos level" ("Nächste Atmos-Stufe"), next to the "Atmos level"
  sensor. Entity IDs stay the same.

## 26.11.1 – 06.11.2026

- **New: announcements.** The media player can play media now (`media_player.play_media`, media browser for audio
  from media sources), so `tts.speak` and other announcements come out of the bar. With `announce` the bar is woken
  from standby and unmuted if needed, plays the announcement and then gets its source (TV, HDMI, Bluetooth), volume,
  mute and standby back. An own volume for announcements can be set in the integration's options (0 keeps the
  current volume). Playback goes through the bar's UPnP media renderer (AVTransport `SetAVTransportURI` + `Play`).
  Since 26.11.1b2 the UPnP commands use their own connection each time: the bar drops a second request on a reused
  connection, so in 26.11.1b1 playback and announcements failed with "Server disconnected".
- **New: input as a select.** `select.jbl_bar_1000_source` switches between TV, HDMI and Bluetooth with
  `select.select_option`, the same as `media_player.select_source`, but easier to find in automations and dashboards.
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
