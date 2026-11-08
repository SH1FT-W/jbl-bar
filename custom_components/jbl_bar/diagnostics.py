"""Diagnose-Download: Geräteinfo und Zustand der Bar, ohne Adresse, MAC und Seriennummer."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .api import JBLBarError
from .coordinator import JBLBarConfigEntry, JBLBarCoordinator

TO_REDACT = {CONF_HOST, "wlan0_mac", "eth0_mac", "bt_mac", "mac", "serial_number", "uuid", "ssid", "ip", "ip_address"}
# Read-only commands of the JBL One app without an entity yet: their answers show what a bar offers and in which form.
PROBES = ("getProductUsage", "getAuracastSQMode", "getBassLevel", "getSubwooferState", "getSmartButtonConfig")


async def _probe(coordinator: JBLBarCoordinator) -> dict[str, Any]:
    """Ask once, only for this download; the smart button's music is left out because it names what the user plays."""
    answers: dict[str, Any] = {}
    for command in PROBES:
        try:
            answers[command] = await coordinator.client.command(command)
        except JBLBarError as err:
            answers[command] = str(err)
    return async_redact_data(answers, TO_REDACT | {"music"})


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: JBLBarConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "device": async_redact_data(coordinator.device, TO_REDACT),
        "unsupported_commands": sorted(coordinator.unsupported),
        "feature_support": coordinator.features,
        "probes": await _probe(coordinator),
        "last_update_success": coordinator.last_update_success,
        "events_subscribed": coordinator.events_subscribed,
        "state": async_redact_data(asdict(coordinator.data), TO_REDACT),
    }
