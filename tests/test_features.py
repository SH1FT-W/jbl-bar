"""Broadcast and Deep Sleep: only on bars that report them, read and written as the JBL One app does."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from common import FakeBar
from custom_components.jbl_bar.coordinator import _prod_value
from custom_components.jbl_bar.diagnostics import async_get_config_entry_diagnostics

BROADCAST = "select.jbl_bar_1000_broadcast"
DEEP_SLEEP = "switch.jbl_bar_1000_deep_sleep"
REAR_VOLUME = "select.jbl_bar_1000_rear_volume"
POWER_ON = "sensor.jbl_bar_1000_power_on_time"
PLAYBACK = "sensor.jbl_bar_1000_playback_time"
AURACAST = "switch.jbl_bar_1000_auracast_quality"


async def call(hass: HomeAssistant, domain: str, service: str, entity_id: str, **data) -> None:
    await hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)
    await hass.async_block_till_done()


@pytest.fixture
def capable_bar(bar: FakeBar) -> FakeBar:
    bar.features |= {"flex_listening": {"support": "true"}, "deep_sleep": {"support": "true"}}
    bar.prod = {"FlexListening": "1", "DeepSleep": "0"}
    return bar


async def test_bar_without_the_features(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    assert hass.states.get(BROADCAST) is None
    assert hass.states.get(DEEP_SLEEP) is None
    assert bar.commands("getProdSetting") == []


@pytest.fixture
def declining_bar(bar: FakeBar) -> FakeBar:
    bar.features["flex_listening"] = {"support": "false"}
    return bar


async def test_feature_reported_as_false(hass: HomeAssistant, declining_bar: FakeBar, setup) -> None:
    assert hass.states.get(BROADCAST) is None


async def test_broadcast(hass: HomeAssistant, capable_bar: FakeBar, setup) -> None:
    assert {"FlexListening": ""} in capable_bar.commands("getProdSetting")
    state = hass.states.get(BROADCAST)
    assert state.state == "mono"
    assert state.attributes["options"] == ["off", "mono", "stereo"]

    await call(hass, "select", "select_option", BROADCAST, option="stereo")
    assert capable_bar.commands("setProdSetting") == [{"FlexListening": "2"}]
    assert hass.states.get(BROADCAST).state == "stereo"


async def test_broadcast_refused_by_the_bar(hass: HomeAssistant, capable_bar: FakeBar, setup, monkeypatch) -> None:
    answer = capable_bar._answer
    monkeypatch.setattr(
        capable_bar,
        "_answer",
        lambda name, payload: {"error_code": "1"} if name == "setProdSetting" else answer(name, payload),
    )
    with pytest.raises(HomeAssistantError):
        await call(hass, "select", "select_option", BROADCAST, option="off")
    assert hass.states.get(BROADCAST).state == "mono"


async def test_deep_sleep(hass: HomeAssistant, capable_bar: FakeBar, setup) -> None:
    assert hass.states.get(DEEP_SLEEP).state == "off"
    await call(hass, "switch", "turn_on", DEEP_SLEEP)
    assert capable_bar.commands("setProdSetting") == [{"DeepSleep": "1"}]
    assert hass.states.get(DEEP_SLEEP).state == "on"


async def test_diagnostics_list_the_features(hass: HomeAssistant, capable_bar: FakeBar, setup) -> None:
    result = await async_get_config_entry_diagnostics(hass, setup)
    assert result["feature_support"]["flex_listening"] == {"support": "true"}


@pytest.fixture
def usage_bar(bar: FakeBar) -> FakeBar:
    bar.features |= {"product_usage_time": {"support": "true"}, "auracast_sq_mode": {"support": "true"}}
    return bar


async def test_usage_and_auracast_absent_without_features(
    hass: HomeAssistant, bar: FakeBar, setup, entity_registry
) -> None:
    assert entity_registry.async_get(POWER_ON) is None
    assert hass.states.get(AURACAST) is None
    assert bar.commands("getProductUsage") == []
    assert bar.commands("getAuracastSQMode") == []


async def test_usage_sensors(hass: HomeAssistant, usage_bar: FakeBar, setup) -> None:
    state = hass.states.get(POWER_ON)
    assert float(state.state) == 10
    assert state.attributes["unit_of_measurement"] == "h"
    assert float(hass.states.get(PLAYBACK).state) == 1.5


async def test_auracast_quality(hass: HomeAssistant, usage_bar: FakeBar, setup) -> None:
    assert hass.states.get(AURACAST).state == "off"
    await call(hass, "switch", "turn_on", AURACAST)
    assert usage_bar.commands("setAuracastSQMode") == [{"status": "on"}]
    assert hass.states.get(AURACAST).state == "on"


@pytest.fixture
def volume_bar(bar: FakeBar) -> FakeBar:
    bar.unknown.discard("getRearSpeakerVolume")
    return bar


@pytest.fixture
def detached_bar(volume_bar: FakeBar) -> FakeBar:
    for rear in volume_bar.rears:
        rear |= {"docked": False, "status": "online"}
    return volume_bar


async def test_rear_volume(hass: HomeAssistant, detached_bar: FakeBar, setup) -> None:
    state = hass.states.get(REAR_VOLUME)
    assert state.state == "high"
    assert state.attributes["options"] == ["muted", "low", "medium", "high"]

    await call(hass, "select", "select_option", REAR_VOLUME, option="low")
    assert detached_bar.commands("setRearSpeakerVolume") == [{"volume": "1"}]
    assert hass.states.get(REAR_VOLUME).state == "low"


async def test_rear_volume_unavailable_while_docked(hass: HomeAssistant, volume_bar: FakeBar, setup) -> None:
    assert hass.states.get(REAR_VOLUME).state == "unavailable"


@pytest.fixture
def odd_volume_bar(detached_bar: FakeBar) -> FakeBar:
    detached_bar.state["rear_volume"] = "7"
    return detached_bar


async def test_rear_volume_unknown_level(hass: HomeAssistant, odd_volume_bar: FakeBar, setup) -> None:
    assert hass.states.get(REAR_VOLUME).state == "unknown"


async def test_no_rear_volume_without_the_command(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    assert hass.states.get(REAR_VOLUME) is None


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ({"error_code": "0", "FlexListening": "2"}, "2"),
        ({"error_code": "0", "FlexListening": 1}, "1"),
        ({"prod_setting": {"FlexListening": "1"}}, "1"),
        ({"error_code": "0", "FlexListening": ""}, None),
        ({"error_code": "0"}, None),
    ],
)
def test_prod_value(answer: dict, expected: str | None) -> None:
    assert _prod_value(answer, "FlexListening") == expected
