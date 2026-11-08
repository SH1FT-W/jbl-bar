# JBL Bar – Projektregeln

HA-Integration (`custom_components/jbl_bar`, Domain `jbl_bar`) für Soundbars der JBL-Bar-Reihe mit JBL One,
entwickelt und geprüft an einer Bar 1000 (der Test-Bar).

- Repo ist **öffentlich**: nichts Persönliches ins Repo (keine Namen, echten IPs/MACs/Seriennummern, Heimnetz-Details,
  lokalen Pfade). Testdaten bleiben fiktiv (192.0.2.x, 02:00:00:00:00:01).
- README, CHANGELOG, Release-Notizen, Issue-Texte und Commit-Texte auf Englisch.
- Lokal committen ok, Push und Releases nur nach Rückfrage.

## Protokoll (aus der JBL-One-App 2026-10 ausgelesen, an der Test-Bar geprüft)

- `https://<ip>/httpapi.asp`, POST `command=<name>&payload=<json>`, TLS mit Client-Zertifikat aus
  `custom_components/jbl_bar/certs/` (stammt aus MrBearPresident/JBL_Soundbar, MIT, Lizenztext in `certs/LICENSE` und
  `NOTICE`).
- **`power_state` ist verdreht: "0" = an, "1" = Standby** (Lesen und `setPowerState`).
- Quelle: `getMediaSourceStatus` = gewählter Eingang (auch im Leerlauf), `getStreamingStatus` = was gerade ankommt.
- Wirken nachweislich: setAudioSync (0–250), setActiveEQ, setPersonalListeningMode, setPureVoiceState, setSmartMode,
  setFeedbackToneConfig, setPowerState, setMediaSource. setSleepTimer wirkt nur im Betrieb, im Standby ignoriert.
  setRearSpeakerVolume ändert nichts, solange die Rears angedockt sind → Auswahl nur abgenommen verfügbar. Stufen 0–3 =
  stumm/leise/mittel/laut abgeleitet (App-Menü ist eine Webansicht außerhalb des APK); abgenommen an der Test-Bar
  (OneOS 3.0) in beide Richtungen geprüft: Setzen aus HA wirkt, Änderung in der App erscheint in HA.
  `setAtmosConfig` ändert nichts → Atmos-Stufe nur per Taste `keyAtmosLevel`.
- Volle Befehlsliste der App: `EnumCommandMapping` (164 Befehle) + `d9`-Request-Klassen; die Bar 1000 kennt nur einen
  Teil (`getFeatureSupport`), unbekannte Befehle landen in `coordinator.unsupported` und werden nicht mehr gefragt.
- Wiedergabe von URLs (`media_player.play_media`) über AVTransport: belegt nur aus `description.xml` der Test-Bar
  (nur lesend 2026-11-02). **Wiedergabe selbst an der Test-Bar noch ungeprüft**: ob die Bar aus TV/HDMI auf
  Netzwerk umschaltet, im Standby annimmt, nach dem Ende `STOPPED` meldet und `setMediaSource` danach zurückführt.
- Keep-Alive: httpapi (lighttpd 1.4.69) schließt stille Verbindungen nach ~6 s, HAs Pool nutzt sie bis 15 s →
  jede httpapi-Anfrage mit `Connection: close` (lighttpd antwortet dann selbst mit close). UPnP verträgt gar keine
  zweite Anfrage pro Verbindung → eigene `force_close`-Session. (Gemessen 2026-11-06.)
- Quellwechsel: zwischen TV/HDMI/BT ~0,5 s; aus Netzwerk-Wiedergabe (PlayMedium THIRD-DLNA) erst ~4 s nach
  `setMediaSource`, und dieser Wechsel weckt die Bar aus dem Standby. GetInfoEx `PlayMedium`: TV, HDMI, BLUETOOTH, bei Streams z. B. AIRPLAY, CAST, THIRD-DLNA.
  Auf dem TV-Eingang meldet AVTransport auch ohne Signal `PLAYING`.
- Broadcast (`FlexListening`) und Deep Sleep sind Produkt-Einstellungen: `getProdSetting` je Schlüssel (`{"FlexListening":""}`),
  `setProdSetting` mit `{"FlexListening":"0|1|2"}` (aus/Mono/Stereo) bzw. `{"DeepSleep":"0|1"}`. Die App zeigt sie nur bei
  `feature_support.flex_listening` bzw. `.deep_sleep` mit `support` "true"; modellabhängige Prüfungen gibt es dafür nicht.
  Nur aus der App belegt, die Test-Bar (OneOS 3.0) meldet beides nicht und kennt `getProdSetting` nicht.
- `getProductUsage`: `product_usage.power_on_duration` / `.playback_duration` in Minuten (an der Test-Bar nachgezählt), Feature
  `product_usage_time`. Auracast-Qualität: `getAuracastSQMode` liest an der MK2 (Feature `auracast_sq_mode`), `setAuracastSQMode`
  mit `{"status":"on|off"}` lehnt sie aber mit „unknown command“ ab (in welchem Modus die Bar dabei war, ist offen; die App zeigt das Menü nur im Bluetooth-Modus und schickt beim Einschalten zusätzlich `keepAlive {"interval":3}`). Deshalb keine Entität, erst wieder auf Nutzerwunsch. `getBassLevel` kennen Bar 1000 und MK2 nicht, `getSubwooferState` antwortet leer.
- GENA-Abo (Audioformat vom Fernseher) läuft als Hintergrund-Task: die alte Integration blockierte damit den
  HA-Start 5 Min. NOTIFY nur von der Bar-IP annehmen.

## Regeln

- Entity-IDs fest `<plattform>.<gerätename>_<key>` (`JBLBarEntity`), kompatibel zur alten Integration –
  Liste in `tests/test_setup.py::LEGACY_IDS`, nie ändern (bestehende Automationen, Dashboards, Energie-Sensoren).
- Rear-Speaker = eigene Geräte mit `via_device_id`.

## Version

Versionen über `tools/next-version` (globale Regeln), Tag/Titel ohne v = genau die manifest-Version;
`CHANGELOG.md` `## YY.M.N – DD.MM.YYYY`, englisch. Die Versions-Badge im README liest die manifest.json selbst.

## Prüfen

- `python -m pytest -q -p no:logging` in einer venv mit `requirements_test.txt` (Fake-Bar in `tests/common.py`)
- `uvx ruff@0.16.9 check . && uvx ruff@0.16.9 format --check .`, `uvx mypy@2.3.1 --python-executable <venv>/bin/python`
  (Versionen wie in `.github/workflows/pruefung.yml`)
- `python tools/pruefe-uebersetzungen.py` (strings.json gegen translations/*.json)
- CI `pruefung.yml`: dasselbe bei Push/PR auf main, montags zusätzlich gegen die neueste HA; Abdeckungsgrenze 95 %
  (`--cov-fail-under`, bei Bedarf anheben). `hacs.yml`: HACS-Validierung.
- hassfest: `docker run --rm -v "$PWD/custom_components/jbl_bar:/github/workspace/custom_components/jbl_bar" ghcr.io/home-assistant/hassfest`
- Live: in einer Test-HA mit einer echten Bar. Nach Tests die Bar wieder in den Ausgangszustand (meist Standby,
  Quelle TV) setzen.
