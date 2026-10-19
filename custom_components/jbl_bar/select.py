"""Auswahl: EQ-Preset und Sleep-Timer."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SLEEP_OPTIONS
from .coordinator import JBLBarConfigEntry, JBLBarCoordinator
from .entity import JBLBarEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = []
    if coordinator.supports("getEQList") and coordinator.data.eq_presets:
        entities.append(JBLBarEqPreset(coordinator))
    if coordinator.supports("getSleepTimer"):
        entities.append(JBLBarSleepTimer(coordinator))
    async_add_entities(entities)


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
