"""Binärsensoren: Dolby Atmos aktiv, Rear-Speaker lädt/angedockt/verbunden."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JBLBarConfigEntry, JBLBarCoordinator
from .entity import JBLBarEntity, async_track_rears, rear_device_info

PARALLEL_UPDATES = 0

REAR_FIELDS = {
    "charging": BinarySensorDeviceClass.BATTERY_CHARGING,
    "docked": BinarySensorDeviceClass.PLUG,
    "online": BinarySensorDeviceClass.CONNECTIVITY,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    if coordinator.supports("getStreamingStatus"):
        entities.append(JBLBarAtmos(coordinator))
    async_add_entities(entities)
    async_track_rears(
        coordinator,
        async_add_entities,
        lambda channel: [JBLBarRearBinary(coordinator, channel, field) for field in REAR_FIELDS],
    )


class JBLBarAtmos(JBLBarEntity, BinarySensorEntity):
    """An, solange gerade Dolby Atmos ankommt."""

    def __init__(self, coordinator: JBLBarCoordinator) -> None:
        super().__init__(coordinator, "atmos_active", "binary_sensor")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.atmos_active


class JBLBarRearBinary(JBLBarEntity, BinarySensorEntity):
    def __init__(self, coordinator: JBLBarCoordinator, channel: str, field: str) -> None:
        super().__init__(coordinator, f"{channel}_{field}", "binary_sensor")
        self._channel = channel
        self._field = field
        self._attr_translation_key = f"rear_{field}"
        self._attr_device_class = REAR_FIELDS[field]
        self._attr_device_info = rear_device_info(coordinator, channel)

    @property
    def is_on(self) -> bool | None:
        rear = self.coordinator.data.rears.get(self._channel)
        if rear is None:
            return None
        value = rear.get("status") if self._field == "online" else rear.get(self._field)
        if self._field == "online":
            return value == "online"
        return bool(value) if value is not None else None
