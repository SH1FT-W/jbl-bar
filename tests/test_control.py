"""Bedienen: jede Aktion schickt den richtigen Befehl und der Zustand stimmt danach."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from common import FakeBar
from custom_components.jbl_bar.api import JBLBarError


async def call(hass: HomeAssistant, domain: str, service: str, entity_id: str, **data) -> None:
    await hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)
    await hass.async_block_till_done()


PLAYER = "media_player.jbl_bar_1000"


async def test_media_player(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    await call(hass, "media_player", "volume_set", PLAYER, volume_level=0.3)
    assert ("soap", "SetVolume") in bar.calls
    assert hass.states.get(PLAYER).attributes["volume_level"] == 0.3
    assert hass.states.get("number.jbl_bar_1000_volume").state == "30"

    await call(hass, "media_player", "volume_mute", PLAYER, is_volume_muted=True)
    assert hass.states.get(PLAYER).attributes["is_volume_muted"] is True

    await call(hass, "media_player", "select_source", PLAYER, source="Bluetooth")
    assert bar.commands("setMediaSource") == [{"media_source": "BT"}]
    assert hass.states.get(PLAYER).attributes["source"] == "Bluetooth"

    await call(hass, "media_player", "turn_off", PLAYER)
    assert bar.commands("setPowerState")[-1] == {"power_state": "1"}
    assert hass.states.get(PLAYER).state == "off"
    assert hass.states.get("switch.jbl_bar_1000_power").state == "off"
    await call(hass, "media_player", "turn_on", PLAYER)
    assert bar.commands("setPowerState")[-1] == {"power_state": "0"}
    assert hass.states.get(PLAYER).state == "playing"

    await call(hass, "media_player", "media_next_track", PLAYER)
    await call(hass, "media_player", "media_previous_track", PLAYER)
    assert bar.commands("sendAppController")[-2:] == [{"key_pressed": "next"}, {"key_pressed": "prev"}]

    # Spielt (TV streamt) → Pause drückt Play/Pause, Play nicht
    await call(hass, "media_player", "media_play", PLAYER)
    assert bar.commands("sendAppController")[-1] == {"key_pressed": "prev"}
    await call(hass, "media_player", "media_pause", PLAYER)
    assert bar.commands("sendAppController")[-1] == {"key_pressed": "musicPlayPause"}


async def test_media_metadata(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    bar.state.update(transport="PLAYING", is_streaming="false", source="IDLE", selected="IDLE")
    await setup.runtime_data.async_refresh()
    player = hass.states.get(PLAYER)
    assert player.state == "playing"
    assert player.attributes["media_title"] == "Song"
    assert player.attributes["media_artist"] == "Testband"
    assert player.attributes["media_album_name"] == "Testalbum"
    assert player.attributes["media_duration"] == 210
    assert player.attributes["entity_picture"]
    assert hass.states.get("sensor.jbl_bar_1000_source").state == "idle"

    # Nichts läuft, TV-Eingang gewählt: Quelle bleibt TV
    bar.state.update(transport="STOPPED", selected="TV")
    await setup.runtime_data.async_refresh()
    assert hass.states.get(PLAYER).state == "idle"
    assert hass.states.get(PLAYER).attributes["source"] == "TV"


async def test_switches(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    await call(hass, "switch", "turn_on", "switch.jbl_bar_1000_nightmode")
    assert bar.commands("setPersonalListeningMode") == [{"status": "on"}]
    assert hass.states.get("switch.jbl_bar_1000_nightmode").state == "on"
    await call(hass, "switch", "turn_on", "switch.jbl_bar_1000_pure_voice")
    assert bar.commands("setPureVoiceState") == [{"purevoice_state": "1"}]
    await call(hass, "switch", "turn_off", "switch.jbl_bar_1000_smart_mode")
    assert bar.commands("setSmartMode") == [{"status": "off"}]
    await call(hass, "switch", "turn_off", "switch.jbl_bar_1000_feedback_tone")
    assert bar.commands("setFeedbackToneConfig") == [{"status": "off"}]
    assert hass.states.get("switch.jbl_bar_1000_feedback_tone").state == "off"
    await call(hass, "switch", "turn_off", "switch.jbl_bar_1000_power")
    assert bar.commands("setPowerState") == [{"power_state": "1"}]


async def test_eq(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    await call(hass, "select", "select_option", "select.jbl_bar_1000_eq_preset", option="VOCAL")
    sent = bar.commands("setActiveEQ")[-1]
    assert sent["active_eq_id"] == "2"
    assert sent["eq_payload"]["gain"] == [-5, 0, 0, 4, -2, 4, 0]
    assert hass.states.get("number.jbl_bar_1000_1000hz").state == "4.0"

    # Band ändern: übernimmt VOCAL ins eigene Preset und aktiviert es
    await call(hass, "number", "set_value", "number.jbl_bar_1000_125hz", value=-7.5)
    sent = bar.commands("setActiveEQ")[-1]
    assert sent["active_eq_id"] == "0"
    assert sent["eq_payload"]["gain"] == [-7.5, 0, 0, 4, -2, 4, 0]
    assert sent["eq_payload"]["fs"] == [125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0]
    assert hass.states.get("select.jbl_bar_1000_eq_preset").state == "CUSTOMIZE"
    assert hass.states.get("number.jbl_bar_1000_125hz").state == "-7.5"
    assert hass.states.get("number.jbl_bar_1000_125hz").attributes["min"] == -9


async def test_settings(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    await call(hass, "number", "set_value", "number.jbl_bar_1000_audio_sync", value=120)
    assert bar.commands("setAudioSync") == [{"audio_sync": "120"}]
    assert hass.states.get("number.jbl_bar_1000_audio_sync").state == "120"

    await call(hass, "select", "select_option", "select.jbl_bar_1000_sleep_timer", option="30")
    assert bar.commands("setSleepTimer") == [{"sleep_timer": 1800}]
    state = hass.states.get("select.jbl_bar_1000_sleep_timer")
    assert state.state == "30"
    assert state.attributes["remaining_minutes"] == 30

    await call(hass, "button", "press", "button.jbl_bar_1000_atmos")
    assert bar.commands("sendAppController")[-1] == {"key_pressed": "keyAtmosLevel"}
    await call(hass, "button", "press", "button.jbl_bar_1000_moment")
    assert bar.commands("sendAppController")[-1] == {"key_pressed": "smart_triger"}


async def test_error_is_readable(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    bar.unknown.add("setPersonalListeningMode")
    with pytest.raises(HomeAssistantError, match="did not accept") as err:
        await call(hass, "switch", "turn_on", "switch.jbl_bar_1000_nightmode")
    assert err.value.translation_key == "command_failed"
    assert hass.states.get("switch.jbl_bar_1000_nightmode").state == "off"


async def test_eq_band_out_of_range(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    """Ein Band, das die Bar nicht hat, darf keinen IndexError werfen."""
    with pytest.raises(JBLBarError, match="no band 8"):
        await setup.runtime_data.async_set_eq_band(7, 1.0)
    with pytest.raises(JBLBarError, match="no band 0"):
        await setup.runtime_data.async_set_eq_band(-1, 1.0)
    assert bar.commands("setActiveEQ") == []


async def test_standby_polls_only_power(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    """Im Standby fragt HA nur noch den Ein/Aus-Zustand; nach dem Einschalten sofort alles inkl. Einstellungen."""
    coordinator = setup.runtime_data
    bar.state["power"] = "1"
    await coordinator.async_refresh()
    assert hass.states.get(PLAYER).state == "off"
    bar.calls.clear()
    await coordinator.async_refresh()
    assert [name for name, _ in bar.calls] == ["getPowerState"]
    bar.state["power"] = "0"
    bar.calls.clear()
    await coordinator.async_refresh()
    names = [name for name, _ in bar.calls]
    assert "getPlayerStatus" in names and ("soap", "GetInfoEx") in bar.calls
    assert "getSmartMode" in names  # Einstellungen gleich mit
    assert hass.states.get(PLAYER).state == "playing"
