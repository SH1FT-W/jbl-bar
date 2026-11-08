"""Selects: input source, EQ preset, sleep timer, Broadcast and volume of the rear speakers."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BROADCAST_MODES, REAR_VOLUME_LEVELS, SLEEP_OPTIONS, SOURCES
from .coordinator import JBLBarConfigEntry, JBLBarCoordinator
from .entity import JBLBarEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = [JBLBarSource(coordinator)]
    if coordinator.supports("getEQList") and coordinator.data.eq_presets:
        entities.append(JBLBarEqPreset(coordinator))
    if coordinator.supports("getSleepTimer"):
        entities.append(JBLBarSleepTimer(coordinator))
    if coordinator.has_feature("flex_listening"):
        entities.append(JBLBarBroadcast(coordinator))
    if coordinator.supports("getRearSpeakerVolume"):
        entities.append(JBLBarRearVolume(coordinator))
    async_add_entities(entities)


class JBLBarSource(JBLBarEntity, SelectEntity):
    """Selected input, the same as the media player's source (for select.select_option in automations)."""

    def __init__(self, coordinator: JBLBarCoordinator) -> None:
        super().__init__(coordinator, "source", "select")
        # Option keys like the source sensor's states (tv, hdmi, bluetooth); names come from the translations.
        self._attr_options = [name.lower() for name in SOURCES.values()]

    @property
    def current_option(self) -> str | None:
        # Idle or an input without a select option (e.g. network streaming) shows as unknown.
        name = SOURCES.get(self.coordinator.data.source or "")
        return name.lower() if name else None

    async def async_select_option(self, option: str) -> None:
        key = next(key for key, name in SOURCES.items() if name.lower() == option)
        await self._run(self.coordinator.async_set_source(key))


class JBLBarEqPreset(JBLBarEntity, SelectEntity):
    """Presets heißen wie in der JBL-One-App (JBL SIGNATURE, VOCAL, …)."""

    def __init__(self, coordinator: JBLBarCoordinator) -> None:
        super().__init__(coordinator, "eq_preset", "select")

    @property
    def options(self) -> list[str]:
        return [preset.name for preset in self.coordinator.data.eq_presets.values()]

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        preset = data.eq_presets.get(data.eq_active_id or "")
        return preset.name if preset else None

    async def async_select_option(self, option: str) -> None:
        eq_id = next((p.eq_id for p in self.coordinator.data.eq_presets.values() if p.name == option), None)
        if eq_id is not None:
            await self._run(self.coordinator.async_set_eq_preset(eq_id))


class JBLBarSleepTimer(JBLBarEntity, SelectEntity):
    """Ausschalten nach X Minuten; der Rest steht als Attribut dabei."""

    def __init__(self, coordinator: JBLBarCoordinator) -> None:
        super().__init__(coordinator, "sleep_timer", "select")
        self._attr_options = [str(minutes) for minutes in SLEEP_OPTIONS]

    @property
    def current_option(self) -> str | None:
        seconds = self.coordinator.data.sleep_timer
        if seconds is None:
            return None
        minutes = round(seconds / 60)
        # Nach dem Ablauf meldet die Bar wieder 0; ein unbekannter Wert (z. B. aus der App) zeigt den nächsten.
        return str(min(SLEEP_OPTIONS, key=lambda option: abs(option - minutes)))

    @property
    def extra_state_attributes(self) -> dict[str, int | None]:
        remaining = self.coordinator.data.sleep_remaining
        return {"remaining_minutes": None if remaining is None else round(remaining / 60)}

    async def async_select_option(self, option: str) -> None:
        await self._run(self.coordinator.async_set_sleep_timer(int(option)))


class JBLBarBroadcast(JBLBarEntity, SelectEntity):
    """Broadcast of detached rear speakers ("FlexListening" in the app), only on bars that report the feature."""

    def __init__(self, coordinator: JBLBarCoordinator) -> None:
        super().__init__(coordinator, "broadcast", "select")
        self._attr_options = list(BROADCAST_MODES.values())

    @property
    def current_option(self) -> str | None:
        return BROADCAST_MODES.get(self.coordinator.data.broadcast or "")

    async def async_select_option(self, option: str) -> None:
        value = next(value for value, name in BROADCAST_MODES.items() if name == option)
        await self._run(self.coordinator.async_set_broadcast(value))


class JBLBarRearVolume(JBLBarEntity, SelectEntity):
    """Volume of the detached rear speakers; docked the bar ignores it and only remembers the last level."""

    def __init__(self, coordinator: JBLBarCoordinator) -> None:
        super().__init__(coordinator, "rear_volume", "select")
        self._attr_options = list(REAR_VOLUME_LEVELS.values())

    @property
    def available(self) -> bool:
        rears = self.coordinator.data.rears.values()
        return super().available and any(r.get("docked") is False and r.get("status") == "online" for r in rears)

    @property
    def current_option(self) -> str | None:
        volume = self.coordinator.data.rear_volume
        return None if volume is None else REAR_VOLUME_LEVELS.get(volume)

    async def async_select_option(self, option: str) -> None:
        value = next(value for value, name in REAR_VOLUME_LEVELS.items() if name == option)
        await self._run(self.coordinator.async_set_rear_volume(value))
