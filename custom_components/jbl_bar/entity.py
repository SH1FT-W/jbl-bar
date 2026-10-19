"""Gemeinsame Basis aller Entitäten."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .api import JBLBarConnectionError, JBLBarError
from .const import DOMAIN, MANUFACTURER
from .coordinator import JBLBarCoordinator


def bar_device_info(coordinator: JBLBarCoordinator) -> DeviceInfo:
    device = coordinator.device
    info = DeviceInfo(
        identifiers={(DOMAIN, coordinator.unique_id)},
        name=device.get("name") or "JBL Bar",
        manufacturer=MANUFACTURER,
        model=device.get("name") or "JBL Bar",
        sw_version=device.get("firmware"),
        serial_number=device.get("serial_number"),
        configuration_url=None,
    )
    if mac := device.get("wlan0_mac"):
        info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(mac))}
    return info


def rear_device_info(coordinator: JBLBarCoordinator, channel: str) -> DeviceInfo:
    side = {"left": "Left", "right": "Right"}.get(channel, channel.title())
    bar = coordinator.device.get("name") or "JBL Bar"
    info = DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.unique_id}_rear_{channel}")},
        name=f"{bar} Rear Speaker {side}",
        manufacturer=MANUFACTURER,
        model=f"{bar} Rear Speaker",
    )
    if coordinator.device_id:
        info["via_device_id"] = coordinator.device_id
    return info


class JBLBarEntity(CoordinatorEntity[JBLBarCoordinator]):
    """Eine Entität der Bar.

    Entity-IDs sind fest `<plattform>.<gerätename>_<key>` (wie bei der alten JBL-Integration), damit Automationen und
    Dashboards den Wechsel überleben – die Anzeigenamen kommen trotzdem übersetzt aus `strings.json`.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: JBLBarCoordinator, key: str, platform: str, object_id: str | None = None) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.unique_id}_{key}"
        self._attr_device_info = bar_device_info(coordinator)
        bar = slugify(coordinator.device.get("name") or "jbl_bar")
        self.entity_id = f"{platform}.{bar}_{object_id or key}"

    async def _run(self, call: Awaitable[None]) -> None:
        """Befehl ausführen; Fehler als verständliche Meldung in der Oberfläche."""
        try:
            await call
        except JBLBarError as err:
            key = "unreachable" if isinstance(err, JBLBarConnectionError) else "command_failed"
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=key, translation_placeholders={"error": str(err)}
            ) from err


def async_track_rears(
    coordinator: JBLBarCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    build: Callable[[str], Iterable[Entity]],
) -> None:
    """Entitäten je Rear-Speaker anlegen – auch für Rears, die erst später auftauchen (z. B. neu gekoppelt)."""
    known: set[str] = set()

    @callback
    def add() -> None:
        fresh = [channel for channel in coordinator.data.rears if channel not in known]
        known.update(fresh)
        entities = [entity for channel in fresh for entity in build(channel)]
        if entities:
            async_add_entities(entities)

    add()
    coordinator.config_entry.async_on_unload(coordinator.async_add_listener(add))
