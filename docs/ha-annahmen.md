# HA-Annahmen

<!-- Vorlage aus repo-vorlagen/vorlagen/ha-annahmen.md. Der HA-Beta-Bericht (repo-vorlagen/ha-beta-bericht.md)
     gleicht diese Liste jeden Monat mit den Neuerungen der HA-Beta ab. Nur festhalten, was bei einer Änderung in HA
     still kaputtginge. -->

Worauf sich dieses Repo bei Home Assistant verlässt. Bei jeder Änderung am Code mitpflegen.

**Getestet mit:** HA 2026.9.3 · **Mindestversion:** 2026.9.0 (`hacs.json`)

## Annahmen

| Annahme | Wo im Code | Abgesichert durch |
|---|---|---|
| `hass.http.app.router.add_route("NOTIFY", …)` nimmt eine Route mit eigener HTTP-Methode an, auch nach dem Start des Servers (HA verhindert das Einfrieren des aiohttp-Routers, `http/server.py` `start()`) | `__init__.py` `async_setup` | teilweise: in jedem Test mit `setup` wird die Route am echten `HomeAssistantHTTP`-App registriert (sonst schlüge das Einrichten fehl); späte Registrierung nach dem Serverstart und ein echter NOTIFY-Request über aiohttp **ungetestet** |
| Ohne Anmeldung erreichbar: eine per `router.add_route` (statt `HomeAssistantView`) angelegte Route unter `/api/…` wird von der Auth-Middleware nicht abgewiesen; geschützt wird nur über die Absender-IP | `__init__.py` `async_setup`, `_handle_notify` | **ungetestet** (Tests rufen `_handle_notify` direkt auf); an der Test-Bar live geprüft |
| `request.app[KEY_HASS]` liefert `hass`; `request.remote` ist die Absender-IP (bei Reverse-Proxy von HAs `forwarded`-Middleware gesetzt) | `__init__.py` `_handle_notify` | teilweise: `test_events.py::test_notify_route_checks_sender`, `::test_notify_from_hostname_entry` mit nachgebautem Request (`FakeRequest`) |
| `get_url(hass, allow_external=False, allow_cloud=False, prefer_external=False)` liefert die interne URL oder wirft `NoURLAvailableError` | `__init__.py` `_callback_url` | `test_api.py::test_callback_url` |
| `hass.http.server_port` ist der Port des HA-Webservers (Rückfall 8123) | `__init__.py` `_callback_url` | teilweise: `test_api.py::test_callback_url` prüft nur den Anfang der URL, der Port ist **ungetestet** |
| `ConfigEntry.async_create_background_task` blockiert den Start nicht und bricht den Task beim Entladen ab (danach meldet `finally` das GENA-Abo ab) | `__init__.py` `async_setup_entry`, `coordinator.py` `async_run_events` | teilweise: `test_events.py::test_subscribed` (Abo läuft), `test_setup.py::test_unload`, `::test_events_retry_after_failed_subscribe` (Abbruch per `CancelledError` → UNSUBSCRIBE); dass HA den Task beim Entladen wirklich abbricht, ist **ungetestet** |
| `async_get_clientsession(hass, verify_ssl=False)` plus eigenes SSL-Kontext-Objekt je Request (Client-Zertifikat). Die Session hält Verbindungen bis 15 s offen, die Bar schließt sie nach etwa 6 s: jede httpapi-Anfrage schickt deshalb `Connection: close`, und aiohttp nimmt die Verbindung nach einer Antwort mit `Connection: close` nicht zurück in den Pool | `__init__.py` `async_setup_entry`, `config_flow.py` `_probe`, `api.py` `command` | indirekt über alle Tests mit `AiohttpClientMocker` (die SSL-Übergabe selbst prüft der Mock nicht); Header: `test_setup.py::test_httpapi_closes_connections`; das Verhalten des Pools nur an der Test-Bar geprüft (2026-11-06, 0 von 40 Fehlern statt 14 von 20) |
| `entry.async_on_unload(…)` läuft beim Entladen **und** wenn das Einrichten scheitert (`ConfigEntryNotReady`), auch mit einer Coroutine-Funktion; damit schließt sich die eigene UPnP-Session (`create_upnp_session`, aiohttp `force_close`, weil die Bar keine Keep-Alive-Verbindungen verträgt) | `__init__.py` `async_setup_entry` | `test_setup.py::test_unload`, `::test_not_ready` (Session danach `closed`) |
| Vorab gesetztes `self.entity_id` wird bei neuen Entitäten übernommen (feste IDs wie die alte Integration) | `entity.py` `JBLBarEntity.__init__`, `media_player.py` | `test_setup.py::test_entities_and_ids` (`LEGACY_IDS`) |
| Übersetzte Namen über `has_entity_name` + `translation_key`, Entity-ID bleibt trotzdem fest | `entity.py` | `test_setup.py::test_entities_and_ids`, `::test_media_player_translation_key` |
| `DeviceInfo` kennt `via_device_id` (Gerät-ID statt `via_device`-Tupel; `via_device` ist bis 2027.8 abgekündigt) | `entity.py` `rear_device_info`, `__init__.py` (Bar-Gerät vorab in der Registry, damit die ID feststeht) | `test_setup.py::test_devices` |
| Gerätekennungen je Integration: `async_get_device_by_identifier((DOMAIN, …), entry_id)` | Tests; Code legt nur über `async_get_or_create` an | `test_setup.py::test_devices` |
| `async_remove_config_entry_device(hass, entry, device)` wird für „Gerät löschen“ gefragt | `__init__.py` | `test_quality.py::test_remove_stale_rear` (direkter Aufruf, nicht über die Oberfläche) |
| Zeroconf: `ZeroconfServiceInfo` mit `host`, `name`, `properties` aus `helpers.service_info.zeroconf`; `MAC`/`mac` im TXT-Eintrag ist **optional** (fehlt bei mindestens einer BAR 800, #2), dann kommt die MAC aus `getDeviceInfo`; `_abort_if_unique_id_configured(updates=…)` aktualisiert den Host | `config_flow.py` `async_step_zeroconf` | `test_config_flow.py::test_zeroconf`, `::test_zeroconf_updates_host_and_aborts`, `::test_zeroconf_without_mac_in_txt`, `::test_zeroconf_not_jbl_or_offline` |
| Neue IP der Bar (DHCP): `_abort_if_unique_id_configured(updates=…)` lädt einen geladenen Eintrag bei geänderten Daten neu (`reload_on_update=True`); erst dadurch bekommen Client und `host_ips` die neue IP (eingerichtet mit Hostname: Nachschlagen beim NOTIFY von unbekannter IP, höchstens einmal je Minute, Fehlschlag behält die bekannten IPs; ohne HA) | `config_flow.py` `async_step_zeroconf`, `__init__.py` `_async_refresh_host_ips` | `test_events.py::test_notify_after_zeroconf_ip_change`, `::test_notify_after_dns_change`, `::test_failed_lookup_keeps_known_ips` |
| `media_player.play_media` übergibt `announce` als Keyword (`ATTR_MEDIA_ANNOUNCE`), Titel in `extra` (`ATTR_MEDIA_EXTRA`); `tts.speak` ruft `play_media` mit `announce: True`, `blocking=True` und einer `media-source://tts/…`-ID; der Dienst verlangt nur `PLAY_MEDIA` | `media_player.py` `async_play_media` | `test_announce.py::test_announce_restores_source_volume_and_mute` (über den echten Dienst), `::test_play_url`; der Weg über `tts.speak` selbst ist **ungetestet** |
| `media_source.is_media_source_id` / `async_resolve_media(hass, id, entity_id)` liefert `PlayMedia` mit `url` (oft relativ) und `mime_type`; `async_browse_media(hass, id, content_filter=…)` mit `BrowseMedia.media_content_type` als MIME-Typ; `manifest.json` `after_dependencies: ["media_source"]` | `media_player.py` `async_play_media`, `async_browse_media` | teilweise: `test_announce.py::test_announce_media_source`, `::test_browse_media_audio_only` (Auflösen und Browsen gemockt, nur Aufruf und Filter geprüft) |
| `async_process_play_media_url(hass, url)` macht relative URLs mit der internen URL absolut und signiert Pfade mit Anmeldung (`authSig`); `/api/tts_proxy/…` bleibt unsigniert (`PATHS_WITHOUT_AUTH`) | `media_player.py` `async_play_media` | `test_announce.py::test_announce_media_source` (signierter `/media/local/…`-Pfad); der unsignierte TTS-Pfad ist **ungetestet** |
| `MediaPlayerEntityFeature.MEDIA_ANNOUNCE` meldet, dass die Entität `announce` selbst behandelt (Rückkehr zur vorherigen Quelle) | `media_player.py` `_attr_supported_features` | indirekt: `test_announce.py` (Ansage über den Dienst) |
| Options-Flow über `async_get_options_flow` + `OptionsFlow` ohne eigenes `__init__` (`self.config_entry` setzt HA); `NumberSelector` liefert eine Zahl (float) | `config_flow.py` `JBLBarOptionsFlow` | `test_announce.py::test_options_flow` |
| `ConfigEntry.async_create_background_task` für die Rückkehr nach einer Ansage (HA bricht den Task beim Entladen ab, das `finally` gibt die Sperre frei). Folge: Neustart, Neuladen oder Entladen während einer Ansage lässt die Bar auf der Ansage stehen (keine Rückkehr, nichts gespeichert) | `coordinator.py` `async_announce` | teilweise: `test_announce.py` (Rückkehr läuft); Abbruch beim Entladen **ungetestet** |
| `manifest.json` `dependencies: ["http"]`: `hass.http` ist beim Einrichten gesetzt | `__init__.py` `async_setup` | indirekt über alle Tests mit `setup` |

## Fremde Integrationen

- Keine: das Repo liest keine Entitäten oder Attribute anderer Integrationen. Es nutzt nur den HA-Kern
  (`http`, `zeroconf`, `media_source`, Device-/Entity-Registry, `helpers.network`).

## Prüfbefehl

Gegen die gepinnte HA (`requirements_test.txt`):

```sh
uv venv --python 3.14 && uv pip install -r requirements_test.txt pytest-cov
LC_ALL=en_US.UTF-8 TZ=UTC .venv/bin/python -m pytest -q -p no:logging
```

Gegen die neueste HA: GitHub-Job „Tests gegen neueste HA (Frühwarnung)“ in `.github/workflows/pruefung.yml`
(montags, ohne Pins).
