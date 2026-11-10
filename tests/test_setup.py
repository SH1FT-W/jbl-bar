"""Einrichten, Entitäten und feste Entity-IDs (Kompatibilität zur alten JBL-Integration)."""

from __future__ import annotations

import re
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from common import FakeBar

# Diese IDs benutzen bestehende Automationen und Dashboards, sie dürfen sich nie ändern.
LEGACY_IDS = [
    "switch.jbl_bar_1000_power",
    "switch.jbl_bar_1000_nightmode",
    "switch.jbl_bar_1000_smart_mode",
    "switch.jbl_bar_1000_pure_voice",
    "number.jbl_bar_1000_volume",
    "number.jbl_bar_1000_125hz",
    "number.jbl_bar_1000_250hz",
    "number.jbl_bar_1000_500hz",
    "number.jbl_bar_1000_1000hz",
    "number.jbl_bar_1000_2000hz",
    "number.jbl_bar_1000_4000hz",
    "number.jbl_bar_1000_8000hz",
    "select.jbl_bar_1000_eq_preset",
    "sensor.jbl_bar_1000_left_battery",
    "sensor.jbl_bar_1000_right_battery",
    "sensor.jbl_bar_1000_audio_format",
    "binary_sensor.jbl_bar_1000_left_charging",
    "binary_sensor.jbl_bar_1000_left_docked",
    "binary_sensor.jbl_bar_1000_left_online",
    "binary_sensor.jbl_bar_1000_right_charging",
    "binary_sensor.jbl_bar_1000_right_docked",
    "binary_sensor.jbl_bar_1000_right_online",
    "button.jbl_bar_1000_atmos",
    "button.jbl_bar_1000_bass",
    "button.jbl_bar_1000_moment",
    "button.jbl_bar_1000_calibration",
    "button.jbl_bar_1000_rear",
]
# Disabled by default as in jbl_integration: they have no state until enabled, only a registry entry.
LEGACY_DISABLED_IDS = ["sensor.jbl_bar_1000_play_medium"]


async def test_entities_and_ids(hass: HomeAssistant, setup) -> None:
    assert setup.state is ConfigEntryState.LOADED
    for entity_id in [*LEGACY_IDS, "media_player.jbl_bar_1000", "number.jbl_bar_1000_audio_sync"]:
        assert hass.states.get(entity_id) is not None, entity_id
    registry = er.async_get(hass)
    for entity_id in LEGACY_DISABLED_IDS:
        entry = registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, entity_id
        assert hass.states.get(entity_id) is None, entity_id

    assert hass.states.get("switch.jbl_bar_1000_power").state == "on"
    assert hass.states.get("switch.jbl_bar_1000_smart_mode").state == "on"
    assert hass.states.get("switch.jbl_bar_1000_nightmode").state == "off"
    assert hass.states.get("number.jbl_bar_1000_volume").state == "48"
    assert hass.states.get("select.jbl_bar_1000_eq_preset").state == "JBL SIGNATURE"
    assert hass.states.get("select.jbl_bar_1000_sleep_timer").state == "0"
    assert hass.states.get("sensor.jbl_bar_1000_source").state == "tv"
    assert hass.states.get("sensor.jbl_bar_1000_left_battery").state == "93"
    assert hass.states.get("binary_sensor.jbl_bar_1000_right_charging").state == "on"
    assert hass.states.get("binary_sensor.jbl_bar_1000_right_online").state == "off"
    assert hass.states.get("binary_sensor.jbl_bar_1000_left_docked").state == "on"

    player = hass.states.get("media_player.jbl_bar_1000")
    assert player.state == "playing"  # TV streamt
    assert player.attributes["volume_level"] == 0.48
    assert player.attributes["source"] == "TV"
    assert player.attributes["friendly_name"] == "JBL BAR 1000"
    # Übersetzte Namen, IDs bleiben trotzdem englisch/alt
    assert hass.states.get("switch.jbl_bar_1000_nightmode").attributes["friendly_name"] == "JBL BAR 1000 Nachtmodus"
    assert hass.states.get("number.jbl_bar_1000_1000hz").attributes["friendly_name"] == "JBL BAR 1000 EQ 1000 Hz"


async def test_eq_bands_sort_by_frequency(hass: HomeAssistant, setup) -> None:
    """Home Assistant lists a device's entities by name and compares numbers as numbers (issue #6)."""

    def natural(name: str) -> list[int | str]:
        return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", name)]

    bands = [f"number.jbl_bar_1000_{hz}hz" for hz in (125, 250, 500, 1000, 2000, 4000, 8000)]
    names = [hass.states.get(entity_id).attributes["friendly_name"] for entity_id in bands]
    assert sorted(names, key=natural) == names


async def test_unsupported_command_skips_entity(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    # getRearSpeakerVolume kennt die Fake-Bar nicht → wird nach dem ersten Mal nicht mehr gefragt
    coordinator = setup.runtime_data
    asked = len(bar.commands("getRearSpeakerVolume"))
    settings_before = len(bar.commands("getSmartMode"))
    coordinator._slow_due = True
    await coordinator.async_refresh()
    assert len(bar.commands("getSmartMode")) == settings_before + 1
    assert len(bar.commands("getRearSpeakerVolume")) == asked == 1


async def test_devices(hass: HomeAssistant, setup) -> None:
    devices = dr.async_get(hass)
    bar_device = devices.async_get_device_by_identifier(("jbl_bar", "02:00:00:00:00:01"), setup.entry_id)
    assert bar_device.name == "JBL BAR 1000"
    assert bar_device.sw_version == "25.52.31.80.00"
    left = devices.async_get_device_by_identifier(("jbl_bar", "02:00:00:00:00:01_rear_left"), setup.entry_id)
    assert left.name == "JBL BAR 1000 Rear Speaker Left"
    assert left.via_device_id == bar_device.id
    battery = er.async_get(hass).async_get("sensor.jbl_bar_1000_left_battery")
    assert battery.device_id == left.id


async def test_unavailable_and_back(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    coordinator = setup.runtime_data
    bar.reachable = False
    # Ein Aussetzer wird überbrückt …
    await coordinator.async_refresh()
    assert hass.states.get("media_player.jbl_bar_1000").state == "playing"
    # … erst der zweite in Folge macht nicht verfügbar
    await coordinator.async_refresh()
    assert hass.states.get("media_player.jbl_bar_1000").state == STATE_UNAVAILABLE
    bar.reachable = True
    await coordinator.async_refresh()
    assert coordinator._misses == 0
    assert hass.states.get("media_player.jbl_bar_1000").state == "playing"


async def test_unload(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    assert await hass.config_entries.async_unload(setup.entry_id)
    await hass.async_block_till_done()
    assert setup.state is ConfigEntryState.NOT_LOADED
    assert [session.closed for session in bar.upnp_sessions] == [True]


async def test_httpapi_closes_connections(
    hass: HomeAssistant, bar: FakeBar, aioclient_mock: AiohttpClientMocker, setup
) -> None:
    """Turning on and the restore after an announcement failed now and then with "Server disconnected": the bar's
    web server (lighttpd) closes an idle connection after about 6 seconds, Home Assistant's pooled session reuses
    it for up to 15. Every httpapi request asks the bar to close the connection after its answer."""
    await hass.services.async_call("media_player", "turn_on", {"entity_id": "media_player.jbl_bar_1000"}, blocking=True)
    calls = [call for call in aioclient_mock.mock_calls if str(call[1]).endswith("/httpapi.asp")]
    assert calls
    assert all((call[3] or {}).get("Connection") == "close" for call in calls)


async def test_not_ready(hass: HomeAssistant, bar: FakeBar) -> None:
    from homeassistant.const import CONF_HOST
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    bar.reachable = False
    entry = MockConfigEntry(domain="jbl_bar", unique_id="x", data={CONF_HOST: "192.0.2.76"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    await hass.async_block_till_done()
    assert [session.closed for session in bar.upnp_sessions] == [True]  # own session closed on failed setup too


async def test_media_player_translation_key(hass: HomeAssistant, setup) -> None:
    """Name = Gerätename, aber der translation_key bleibt, damit das Attribut audio_format übersetzt wird."""
    registry = er.async_get(hass).async_get("media_player.jbl_bar_1000")
    assert registry.translation_key == "bar"
    assert hass.states.get("media_player.jbl_bar_1000").attributes["friendly_name"] == "JBL BAR 1000"
    for language in ("de", "en"):
        translations = await async_get_translations(hass, language, "entity", {"jbl_bar"})
        assert "component.jbl_bar.entity.media_player.bar.state_attributes.audio_format.name" in translations


async def test_entity_names_unique(hass: HomeAssistant, setup) -> None:
    """Select and sensor of the source were both called "Quelle", Atmos button and sensor both "Atmos-Stufe"."""
    names = [
        state.attributes.get("friendly_name") for state in hass.states.async_all() if "jbl_bar_1000" in state.entity_id
    ]
    assert len(names) == len(set(names))
    assert hass.states.get("select.jbl_bar_1000_source").attributes["friendly_name"] == "JBL BAR 1000 Eingang"
    assert hass.states.get("sensor.jbl_bar_1000_source").attributes["friendly_name"] == "JBL BAR 1000 Quelle"
    atmos_button = hass.states.get("button.jbl_bar_1000_atmos")
    assert atmos_button.attributes["friendly_name"] == "JBL BAR 1000 Nächste Atmos-Stufe"


async def test_broken_lists_from_bar(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    """Fremde Einträge in den Listen der Bar werden übersprungen, die gültigen bleiben."""
    coordinator = setup.runtime_data
    bar.rears = [None, "kaputt", {"channel": "left", "status": "online"}]  # type: ignore[list-item]
    coordinator._slow_due = True
    with patch(
        "common.EQ_LIST",
        [None, {"eq_id": "1", "eq_name": "Standard", "band": 7, "eq_payload": "kaputt"}],
    ):
        await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert list(coordinator.data.rears) == ["left"]
    assert coordinator.data.eq_presets["1"].payload == {}


async def test_rear_battery_255_is_unknown(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    """An empty rear speaker reports capicity 255 (no reading), not 255 percent (issue #3)."""
    coordinator = setup.runtime_data
    bar.rears = [
        {"capicity": 255, "channel": "left", "charging": False, "docked": False, "status": "offline"},
        {"capicity": 0, "channel": "right", "charging": False, "docked": False, "status": "offline"},
    ]
    coordinator._slow_due = True
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jbl_bar_1000_left_battery").state == "unknown"
    assert hass.states.get("sensor.jbl_bar_1000_right_battery").state == "0"


async def test_play_medium_shows_streams(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    """The input stays TV while AirPlay plays; only PlayMedium shows the stream. Unknown in standby, not stale."""
    # Disabled by default: enable it as a user would, then reload the entry
    er.async_get(hass).async_update_entity("sensor.jbl_bar_1000_play_medium", disabled_by=None)
    assert await hass.config_entries.async_reload(setup.entry_id)
    await hass.async_block_till_done()
    coordinator = setup.runtime_data
    assert hass.states.get("sensor.jbl_bar_1000_play_medium").state == "TV"
    bar.state["medium"] = "AIRPLAY"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jbl_bar_1000_play_medium").state == "AIRPLAY"
    assert hass.states.get("sensor.jbl_bar_1000_source").state == "tv"

    bar.state["power"] = "1"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jbl_bar_1000_play_medium").state == "unknown"
