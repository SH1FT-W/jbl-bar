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
| `ConfigEntry.async_create_background_task` blockiert den Start nicht und bricht den Task beim Entladen ab (danach meldet `finally` das GENA-Abo ab) | `__init__.py` `async_setup_entry`, `coordinator.py` `async_run_events` | teilweise: `test_events.py::test_subscribed` (Abo läuft), `test_setup.py::test_unload`; dass beim Entladen wirklich UNSUBSCRIBE gesendet wird, ist **ungetestet** |
| `async_get_clientsession(hass, verify_ssl=False)` plus eigenes SSL-Kontext-Objekt je Request (Client-Zertifikat) | `__init__.py` `async_setup_entry`, `config_flow.py` `_probe` | indirekt über alle Tests mit `AiohttpClientMocker` (die SSL-Übergabe selbst prüft der Mock nicht) |
| Vorab gesetztes `self.entity_id` wird bei neuen Entitäten übernommen (feste IDs wie die alte Integration) | `entity.py` `JBLBarEntity.__init__`, `media_player.py` | `test_setup.py::test_entities_and_ids` (`LEGACY_IDS`) |
| Übersetzte Namen über `has_entity_name` + `translation_key`, Entity-ID bleibt trotzdem fest | `entity.py` | `test_setup.py::test_entities_and_ids`, `::test_media_player_translation_key` |
| `DeviceInfo` kennt `via_device_id` (Gerät-ID statt `via_device`-Tupel; `via_device` ist bis 2027.8 abgekündigt) | `entity.py` `rear_device_info`, `__init__.py` (Bar-Gerät vorab in der Registry, damit die ID feststeht) | `test_setup.py::test_devices` |
| Gerätekennungen je Integration: `async_get_device_by_identifier((DOMAIN, …), entry_id)` | Tests; Code legt nur über `async_get_or_create` an | `test_setup.py::test_devices` |
| `async_remove_config_entry_device(hass, entry, device)` wird für „Gerät löschen“ gefragt | `__init__.py` | `test_quality.py::test_remove_stale_rear` (direkter Aufruf, nicht über die Oberfläche) |
| Zeroconf: `ZeroconfServiceInfo` mit `host`, `name`, `properties` (`MAC`/`mac`) aus `helpers.service_info.zeroconf`; `_abort_if_unique_id_configured(updates=…)` aktualisiert den Host | `config_flow.py` `async_step_zeroconf` | `test_config_flow.py::test_zeroconf`, `::test_zeroconf_updates_host_and_aborts`, `::test_zeroconf_without_mac_or_offline` |
| `manifest.json` `dependencies: ["http"]`: `hass.http` ist beim Einrichten gesetzt | `__init__.py` `async_setup` | indirekt über alle Tests mit `setup` |

## Fremde Integrationen

- Keine: das Repo liest keine Entitäten oder Attribute anderer Integrationen. Es nutzt nur den HA-Kern
  (`http`, `zeroconf`, Device-/Entity-Registry, `helpers.network`).

## Prüfbefehl

Gegen die gepinnte HA (`requirements_test.txt`):

```sh
uv venv --python 3.14 && uv pip install -r requirements_test.txt pytest-cov
LC_ALL=en_US.UTF-8 TZ=UTC .venv/bin/python -m pytest -q -p no:logging
```

Gegen die neueste HA: GitHub-Job „Tests gegen neueste HA (Frühwarnung)“ in `.github/workflows/pruefung.yml`
(montags, ohne Pins).
