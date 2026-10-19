"""Sensoren: Akku der Rear-Speaker, Quelle, Audioformat, Atmos-Stufe."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SOURCES
from .coordinator import JBLBarConfigEntry, JBLBarCoordinator, JBLBarState
from .entity import JBLBarEntity, async_track_rears, rear_device_info

PARALLEL_UPDATES = 0


def _source_state(source: str | None) -> str | None:
    if source is None:
        return None
    if source in SOURCES:
        return SOURCES[source].lower()
    return "idle" if source == "IDLE" else "other"


@dataclass(frozen=True, kw_only=True)
class JBLBarSensorDescription(SensorEntityDescription):
    value: Callable[[JBLBarState], str | int | None]
    command: str


SENSORS = (
    JBLBarSensorDescription(
        key="source",
        device_class=SensorDeviceClass.ENUM,
        options=["tv", "hdmi", "bluetooth", "idle", "other"],
        value=lambda s: _source_state(s.source),
        command="getStreamingStatus",
    ),
    JBLBarSensorDescription(key="audio_format", value=lambda s: s.audio_format, command="getStreamingStatus"),
    JBLBarSensorDescription(
        key="atmos_level",
        value=lambda s: s.atmos_level,
        command="getAtmosLevel",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        JBLBarSensor(coordinator, description) for description in SENSORS if coordinator.supports(description.command)
    ]
    async_add_entities(entities)
    async_track_rears(coordinator, async_add_entities, lambda channel: [JBLBarRearBattery(coordinator, channel)])


class JBLBarSensor(JBLBarEntity, SensorEntity):
    entity_description: JBLBarSensorDescription

    def __init__(self, coordinator: JBLBarCoordinator, description: JBLBarSensorDescription) -> None:
        super().__init__(coordinator, description.key, "sensor")
        self.entity_description = description

    @property
    def native_value(self) -> str | int | None:
        return self.entity_description.value(self.coordinator.data)


class JBLBarRearBattery(JBLBarEntity, SensorEntity):
    """Akku eines abnehmbaren Rear-Speakers (eigenes Gerät, hängt an der Bar)."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: JBLBarCoordinator, channel: str) -> None:
        super().__init__(coordinator, f"{channel}_battery", "sensor")
        self._channel = channel
        self._attr_translation_key = "rear_battery"
        self._attr_device_info = rear_device_info(coordinator, channel)

    @property
    def native_value(self) -> int | None:
        rear = self.coordinator.data.rears.get(self._channel)
        # Die Bar schreibt das Feld „capicity“.
        value = rear.get("capicity", rear.get("capacity")) if rear else None
        return int(value) if value is not None else None
