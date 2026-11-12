"""Sensoren: Akku der Rear-Speaker, Quelle, Wiedergabeweg (PlayMedium), Audioformat, Atmos-Stufe, Betriebszeiten."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SOURCES
from .coordinator import JBLBarConfigEntry, JBLBarCoordinator, JBLBarState, _int
from .entity import JBLBarEntity, async_track_rears, rear_device_info

PARALLEL_UPDATES = 0


def _source_state(source: str | None, hdmi_input: int | None = None) -> str | None:
    if source is None:
        return None
    if source == "HDMI" and hdmi_input:
        return f"hdmi_{hdmi_input}"
    if source in SOURCES:
        return SOURCES[source].lower()
    return "idle" if source == "IDLE" else "other"


def _play_medium(state: JBLBarState) -> str | None:
    """AVTransport's PlayMedium as the bar reports it (TV, HDMI, BLUETOOTH, AIRPLAY, CAST, THIRD-DLNA, …).

    Unlike `source` it also shows network streams. Not asked in standby, so the last value would be stale there.
    """
    if not state.power:
        return None
    return state.media.play_medium or None


@dataclass(frozen=True, kw_only=True)
class JBLBarSensorDescription(SensorEntityDescription):
    value: Callable[[JBLBarState], str | int | None]
    # httpapi command the value comes from; None = AVTransport (UPnP), asked on every bar
    command: str | None
    # Only on bars that list this feature in getFeatureSupport
    feature: str | None = None


SENSORS = (
    JBLBarSensorDescription(
        key="source",
        device_class=SensorDeviceClass.ENUM,
        # "hdmi" when the bar does not name the input
        options=["tv", "hdmi", "hdmi_1", "hdmi_2", "hdmi_3", "bluetooth", "idle", "other"],
        value=lambda s: _source_state(s.source, s.hdmi_input),
        command="getStreamingStatus",
    ),
    # Same ID as the "Play Medium" sensor of jbl_integration, disabled by default like there. Free text, the set of
    # values is open (streaming services).
    JBLBarSensorDescription(key="play_medium", value=_play_medium, command=None, entity_registry_enabled_default=False),
    JBLBarSensorDescription(key="audio_format", value=lambda s: s.audio_format, command="getStreamingStatus"),
    JBLBarSensorDescription(
        key="atmos_level",
        value=lambda s: s.atmos_level,
        command="getAtmosLevel",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Lifetime counters of the bar in minutes (a running bar counted one per minute)
    JBLBarSensorDescription(
        key="power_on_time",
        value=lambda s: s.power_on_minutes,
        command="getProductUsage",
        feature="product_usage_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JBLBarSensorDescription(
        key="playback_time",
        value=lambda s: s.playback_minutes,
        command="getProductUsage",
        feature="product_usage_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        JBLBarSensor(coordinator, description)
        for description in SENSORS
        if (description.command is None or coordinator.supports(description.command))
        and (description.feature is None or coordinator.has_feature(description.feature))
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
        value = _int(rear.get("capicity", rear.get("capacity"))) if rear else None
        # An empty rear speaker reports 255 (no reading) instead of 0..100 (issue #3).
        return value if value is not None and 0 <= value <= 100 else None
