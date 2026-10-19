"""Tasten der Fernbedienung, die es nicht als Zustand gibt: Atmos-Stufe, Bass, Moment, Kalibrierung, Rears."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JBLBarConfigEntry, JBLBarCoordinator
from .entity import JBLBarEntity

PARALLEL_UPDATES = 0

# key → Taste in `sendAppController` (Namen aus der JBL-One-App).
BUTTONS = {
    "atmos": "keyAtmosLevel",
    "bass": "bassboost",
    "moment": "smart_triger",
    "calibration": "calibration",
    "rear": "keyRear",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(JBLBarButton(entry.runtime_data, key) for key in BUTTONS)


class JBLBarButton(JBLBarEntity, ButtonEntity):
    def __init__(self, coordinator: JBLBarCoordinator, key: str) -> None:
        super().__init__(coordinator, key, "button")
        self.entity_description = ButtonEntityDescription(
            key=key, entity_category=EntityCategory.CONFIG if key == "calibration" else None
        )
        self._attr_translation_key = key

    async def async_press(self) -> None:
        await self._run(self.coordinator.async_press(BUTTONS[self.entity_description.key]))
