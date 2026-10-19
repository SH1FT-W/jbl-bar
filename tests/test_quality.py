"""Quality Scale: Diagnose, Rears zur Laufzeit, verschwundene Rears löschen, übersetzte Fehler."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from common import HOST, FakeBar
from custom_components.jbl_bar import async_remove_config_entry_device
from custom_components.jbl_bar.const import DOMAIN
from custom_components.jbl_bar.diagnostics import async_get_config_entry_diagnostics

UNIQUE = "02:00:00:00:00:01"


async def test_diagnostics_redacted(hass: HomeAssistant, setup) -> None:
    data = await async_get_config_entry_diagnostics(hass, setup)
    assert data["entry"]["host"] == "**REDACTED**"
    assert data["device"]["wlan0_mac"] == "**REDACTED**"
    assert data["last_update_success"] is True
    assert "getRearSpeakerVolume" in data["unsupported_commands"]
    assert data["state"]["power"] is True
    assert HOST not in str(data)
    assert UNIQUE not in str(data).lower()


async def test_rear_added_later(hass: HomeAssistant, bar: FakeBar) -> None:
    rears = list(bar.rears)
    bar.rears.clear()
    entry = MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE, data={"host": HOST}, title="JBL BAR 1000")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jbl_bar_1000_left_battery") is None
    bar.rears.extend(rears)
    entry.runtime_data._slow_due = True  # Rears stehen in der Einstellungs-Runde
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jbl_bar_1000_left_battery").state == "93"
    assert hass.states.get("binary_sensor.jbl_bar_1000_right_charging").state == "on"


async def test_remove_stale_rear(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    devices = dr.async_get(hass)
    left = devices.async_get_device_by_identifier((DOMAIN, f"{UNIQUE}_rear_left"), setup.entry_id)
    bar_device = devices.async_get_device_by_identifier((DOMAIN, UNIQUE), setup.entry_id)

    # Gemeldete Rears und die Bar selbst lassen sich nicht löschen …
    assert not await async_remove_config_entry_device(hass, setup, left)
    assert not await async_remove_config_entry_device(hass, setup, bar_device)
    # … ein Rear, das die Bar nicht mehr meldet, schon
    bar.rears[:] = [r for r in bar.rears if r["channel"] != "left"]
    setup.runtime_data._slow_due = True
    await setup.runtime_data.async_refresh()
    assert await async_remove_config_entry_device(hass, setup, left)


async def test_not_ready_translated(hass: HomeAssistant, bar: FakeBar) -> None:
    bar.reachable = False
    entry = MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE, data={"host": HOST}, title="JBL BAR 1000")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert HOST in (entry.reason or "")


async def test_update_failed_translated(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    coordinator = setup.runtime_data
    bar.reachable = False
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.last_exception.translation_key == "unreachable"
