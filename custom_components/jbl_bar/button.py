"""Remote buttons, plus legacy one-press controls kept for dashboard compatibility."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JBLBarConfigEntry, JBLBarCoordinator
from .entity import JBLBarEntity

PARALLEL_UPDATES = 0

# Physical remote keys implemented by the integration.
BUTTONS = {
    "atmos": "keyAtmosLevel",
    "bass": "bassboost",
    "moment": "smart_triger",
    "calibration": "calibration",
    "rear": "keyRear",
}

# Discrete actions exposed as buttons by the former JBL integration.
# State-aware controls use the current coordinator state and the new API.
LEGACY_BUTTONS = {
    "power": "Power",
    "mute": "Mute",
    "increase_volume": "Increase Volume",
    "lower_volume": "Lower Volume",
    "play_pause": "Play/Pause",
    "hdmi": "HDMI",
    "bluetooth": "Bluetooth",
    "tv": "TV",
    "smart_mode": "Smart Mode",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    keys = (*BUTTONS, *LEGACY_BUTTONS)
    async_add_entities(JBLBarButton(entry.runtime_data, key) for key in keys)


class JBLBarButton(JBLBarEntity, ButtonEntity):
    def __init__(self, coordinator: JBLBarCoordinator, key: str) -> None:
        super().__init__(coordinator, key, "button")
        self.entity_description = ButtonEntityDescription(
            key=key,
            name=LEGACY_BUTTONS.get(key),
            entity_category=EntityCategory.CONFIG if key == "calibration" else None,
        )
        if key in BUTTONS:
            self._attr_translation_key = key
        else:
            # Keep the old entity IDs and names for dashboards using the legacy buttons.
            self._attr_has_entity_name = False
            self._attr_name = LEGACY_BUTTONS[key]

    async def async_press(self) -> None:
        key = self.entity_description.key
        coordinator = self.coordinator
        state = coordinator.data

        if key in BUTTONS:
            await self._run(coordinator.async_press(BUTTONS[key]))
        elif key == "power":
            await self._run(coordinator.async_set_power(state.power is not True))
        elif key == "mute":
            await self._run(coordinator.async_set_mute(state.muted is not True))
        elif key == "increase_volume":
            if state.volume is not None:
                await self._run(coordinator.async_set_volume(min(100, state.volume + 3)))
        elif key == "lower_volume":
            if state.volume is not None:
                await self._run(coordinator.async_set_volume(max(0, state.volume - 3)))
        elif key == "play_pause":
            await self._run(coordinator.async_press("musicPlayPause"))
        elif key == "hdmi":
            await self._run(coordinator.async_set_source("HDMI"))
        elif key == "bluetooth":
            await self._run(coordinator.async_set_source("BT"))
        elif key == "tv":
            await self._run(coordinator.async_set_source("TV"))
        elif key == "smart_mode":
            await self._run(coordinator.async_set_switch("smart_mode", state.smart_mode is not True))
