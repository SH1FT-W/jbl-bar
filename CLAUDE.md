# JBL Bar – Projektregeln

HA-Integration (`custom_components/jbl_bar`, Domain `jbl_bar`) für Soundbars der JBL-Bar-Reihe mit JBL One,
entwickelt und geprüft an einer Bar 1000 (der Test-Bar).

- Repo ist **öffentlich**: nichts Persönliches ins Repo (keine Namen, echten IPs/MACs/Seriennummern, Heimnetz-Details,
  lokalen Pfade). Testdaten bleiben fiktiv.
- README, CHANGELOG, Release-Notizen, Issue-Texte und Commit-Texte auf Englisch.
- Lokal committen ok, Push und Releases nur nach Rückfrage.

## Protokoll (aus der JBL-One-App 2026-10 ausgelesen, an der Test-Bar geprüft)

- `https://<ip>/httpapi.asp`, POST `command=<name>&payload=<json>`, TLS mit Client-Zertifikat aus `certs/`
  (stammt aus MrBearPresident/JBL_Soundbar, MIT, Lizenztext in `certs/LICENSE` und `NOTICE`). Antwort JSON mit
  `error_code` "0" oder Text `unknown command`.
- **`power_state` ist verdreht: "0" = an, "1" = Standby** (Lesen und `setPowerState`).
- Quelle: `getMediaSourceStatus` = gewählter Eingang (auch im Leerlauf), `getStreamingStatus` = was gerade ankommt
  (+ `is_atmos`). Setzen: `setMediaSource {"media_source": "TV"|"HDMI"|"BT"}`.
- Lautstärke/Stumm/Titel über UPnP (Port 59152, `SetVolume`/`SetMute`/`GetInfoEx`), Lesen schneller über
  `getPlayerStatus` (`vol`, `mute`, `status`).
- Wirken nachweislich: setAudioSync (0–250), setActiveEQ, setPersonalListeningMode, setPureVoiceState, setSmartMode,
  setFeedbackToneConfig, setPowerState, setMediaSource. setSleepTimer (Sekunden) wirkt nur im Betrieb (mit TV geprüft:
  900 → zählt runter), im Standby ignoriert. setRearSpeakerVolume ändert nichts, solange die Rears angedockt sind
  (abgenommen ungetestet) → keine Entität. `setAtmosConfig` ändert nichts → Atmos-Stufe nur per Taste `keyAtmosLevel`.
- Tasten (`sendAppController` `key_pressed`): musicPlayPause, next, prev, keyAtmosLevel, bassboost, smart_triger
  (Moment, so geschrieben), calibration, keyRear, power, mute, volumeUp/Down.
- Volle Befehlsliste der App: `EnumCommandMapping` (164 Befehle) + `d9`-Request-Klassen; die Bar 1000 kennt nur einen
  Teil (`getFeatureSupport`).
- GENA (an der Test-Bar geprüft: „Dolby Atmos / Dolby Mat / 12ch / 48 kHz“): SUBSCRIBE
  `http://<ip>:49152/upnp/event/rendercontrol1`, NOTIFY an `/api/jbl_bar/notify/<entry_id>`
  (nur von der Bar-IP angenommen) → `HarmanBarState.tv_stream_info` = Audioformat. Abo läuft als Hintergrund-Task
  (die alte Integration blockierte damit den HA-Start 5 Min.).

## Aufbau

- `api.py` Client ohne HA (testbar), `coordinator.py` Zustand (`JBLBarState`), alle 10 s schnell, Einstellungen jede
  Minute bzw. direkt nach einer Änderung; unbekannte Befehle landen in `unsupported` und werden nicht mehr gefragt.
- Entity-IDs fest `<plattform>.<gerätename>_<key>` (`JBLBarEntity`), kompatibel zur alten Integration –
  Liste in `tests/test_setup.py::LEGACY_IDS`, nie ändern (bestehende Automationen, Dashboards, Energie-Sensoren).
- Rear-Speaker = eigene Geräte mit `via_device_id` (Bar-Gerät wird in `async_setup_entry` registriert).

## Version
Kalender-Schema **YY.M.N** ohne v (Jahr zweistellig, Monat ohne führende Null, N = laufende Nummer im Monat ab 1;
es zählen nur echte, veröffentlichte GitHub-Releases des Monats, auch alte X.Y.Z; bloße Tags nicht; ohne Release im Monat → .1; neuer Monat → wieder .1).
Jedes Release als GitHub-Release veröffentlichen (Tag + Release-Titel ohne v = genau die manifest-Version), sonst zählt es nicht mit.
Nächste Nummer immer aus `tools/next-version`, nie von Hand hochzählen, keine Patch-/Minor-Unterscheidung
(+ `CHANGELOG.md` `## YY.M.N – DD.MM.YYYY`, englisch). Die Versions-Badge im README liest die manifest.json selbst.

## Prüfen

- `python -m pytest -q -p no:logging` in einer venv mit `requirements_test.txt` (Fake-Bar in `tests/common.py`)
- `uvx ruff check . && uvx ruff format --check .`, `uvx mypy@2.3.1 --python-executable <venv>/bin/python`
- `python tools/pruefe-uebersetzungen.py` (strings.json gegen translations/*.json)
- GitHub Actions `.github/workflows/pruefung.yml`: dasselbe bei Push/PR auf main, montags zusätzlich gegen die neueste
  HA; Abdeckungsgrenze dort 95 % (`--cov-fail-under`, bei Bedarf anheben). `.github/workflows/hacs.yml`: HACS-Validierung.
- Testdaten sind fiktiv (192.0.2.x, 02:00:00:00:00:01); keine echten Werte aus einem Heimnetz in Tests.
- hassfest: `docker run --rm -v "$PWD/custom_components/jbl_bar:/github/workspace/custom_components/jbl_bar" ghcr.io/home-assistant/hassfest`
- Live: in einer Test-HA mit einer echten Bar. Nach Tests die Bar wieder in den Ausgangszustand (meist Standby,
  Quelle TV) setzen.
