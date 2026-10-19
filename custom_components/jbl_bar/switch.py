"""Schalter: Ein/Aus, Nachtmodus, Smart Mode, PureVoice, Bestätigungstöne."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JBLBarConfigEntry, JBLBarCoordinator, JBLBarState
from .entity import JBLBarEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class JBLBarSwitchDescription(SwitchEntityDescription):
    value: Callable[[JBLBarState], bool | None]
    command: str
    object_id: str | None = None


SWITCHES = (
    JBLBarSwitchDescription(key="power", value=lambda s: s.power, command="getPowerState"),
    JBLBarSwitchDescription(
        key="night_mode", value=lambda s: s.night_mode, command="getPersonalListeningMode", object_id="nightmode"
    ),
    JBLBarSwitchDescription(key="smart_mode", value=lambda s: s.smart_mode, command="getSmartMode"),
    JBLBarSwitchDescription(key="pure_voice", value=lambda s: s.pure_voice, command="getPureVoiceState"),
    JBLBarSwitchDescription(
        key="feedback_tone",
        value=lambda s: s.feedback_tone,
        command="getFeedbackToneConfig",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        JBLBarSwitch(coordinator, description) for description in SWITCHES if coordinator.supports(description.command)
    )


class JBLBarSwitch(JBLBarEntity, SwitchEntity):
    entity_description: JBLBarSwitchDescription

    def __init__(self, coordinator: JBLBarCoordinator, description: JBLBarSwitchDescription) -> None:
        super().__init__(coordinator, description.key, "switch", description.object_id)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._switch(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._switch(False)

    async def _switch(self, on: bool) -> None:
        if self.entity_description.key == "power":
            await self._run(self.coordinator.async_set_power(on))
        else:
            await self._run(self.coordinator.async_set_switch(self.entity_description.key, on))
