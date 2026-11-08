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
