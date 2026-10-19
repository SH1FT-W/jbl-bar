"""Zahlen: Lautstärke, 7-Band-EQ, Audio-Sync."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AUDIO_SYNC_MAX, EQ_BANDS
from .coordinator import JBLBarConfigEntry, JBLBarCoordinator
from .entity import JBLBarEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [JBLBarVolume(coordinator)]
    if coordinator.supports("getEQList") and coordinator.data.eq_presets:
        entities += [JBLBarEqBand(coordinator, index, hz) for index, hz in enumerate(EQ_BANDS)]
    if coordinator.supports("getAudioSync"):
        entities.append(JBLBarAudioSync(coordinator))
    async_add_entities(entities)


class JBLBarVolume(JBLBarEntity, NumberEntity):
    """Lautstärke als Regler (für Automationen, die eine Zahl setzen wollen)."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 3
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: JBLBarCoordinator) -> None:
        super().__init__(coordinator, "volume", "number")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.volume

    async def async_set_native_value(self, value: float) -> None:
        await self._run(self.coordinator.async_set_volume(round(value)))


class JBLBarEqBand(JBLBarEntity, NumberEntity):
    """Ein EQ-Band. Zeigt das aktive Preset; Ändern legt die Werte ins eigene Preset."""

    _attr_native_max_value = 6
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "dB"
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: JBLBarCoordinator, index: int, hz: int) -> None:
        super().__init__(coordinator, f"eq_{hz}", "number", f"{hz}hz")
        self._index = index
        self._attr_native_min_value = -9 if hz == 125 else -6
        self._attr_translation_placeholders = {"band": f"{hz} Hz" if hz < 1000 else f"{hz // 1000} kHz"}
        self._attr_translation_key = "eq_band"

    @property
    def native_value(self) -> float | None:
        gains = self.coordinator.data.eq_gains
        return gains[self._index] if self._index < len(gains) else None

    async def async_set_native_value(self, value: float) -> None:
        await self._run(self.coordinator.async_set_eq_band(self._index, value))


class JBLBarAudioSync(JBLBarEntity, NumberEntity):
    """Ton verzögern, wenn er dem Bild vorausläuft."""

    _attr_native_min_value = 0
    _attr_native_max_value = AUDIO_SYNC_MAX
    _attr_native_step = 10
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: JBLBarCoordinator) -> None:
        super().__init__(coordinator, "audio_sync", "number")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.audio_sync

    async def async_set_native_value(self, value: float) -> None:
        await self._run(self.coordinator.async_set_audio_sync(round(value)))
