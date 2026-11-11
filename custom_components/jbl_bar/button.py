"""Tasten der Fernbedienung, die es nicht als Zustand gibt: Atmos-Stufe, Bass, Moment, Kalibrierung, Rears, HDMI."""

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
    # Steps through the HDMI inputs like the remote's HDMI key (setMediaSource "HDMI" only goes to the last one).
    "hdmi": "source-hdmi-switch",
}
# key → input for `setMediaSource`. Not every bar has three HDMI inputs, so these start disabled.
HDMI_INPUTS = {"hdmi_1": "HDMI1", "hdmi_2": "HDMI2", "hdmi_3": "HDMI3"}


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(JBLBarButton(coordinator, key) for key in BUTTONS),
            *(JBLBarHdmiInput(coordinator, key) for key in HDMI_INPUTS),
        ]
    )


class JBLBarButton(JBLBarEntity, ButtonEntity):
    def __init__(self, coordinator: JBLBarCoordinator, key: str) -> None:
        super().__init__(coordinator, key, "button")
        self.entity_description = ButtonEntityDescription(
            key=key, entity_category=EntityCategory.CONFIG if key == "calibration" else None
        )
        self._attr_translation_key = key

    async def async_press(self) -> None:
        await self._run(self.coordinator.async_press(BUTTONS[self.entity_description.key]))


class JBLBarHdmiInput(JBLBarEntity, ButtonEntity):
    """Switches straight to one HDMI input; the source select's "HDMI" goes to the last used one."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: JBLBarCoordinator, key: str) -> None:
        super().__init__(coordinator, key, "button")
        self._input = HDMI_INPUTS[key]

    async def async_press(self) -> None:
        await self._run(self.coordinator.async_set_source(self._input))
