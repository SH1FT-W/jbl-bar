"""Die Bar als Mediaplayer: an/aus, Lautstärke, Stumm, Quelle, Wiedergabe mit Titel und Cover."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .const import SOURCES
from .coordinator import JBLBarConfigEntry, JBLBarCoordinator
from .entity import JBLBarEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: JBLBarConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([JBLBarMediaPlayer(entry.runtime_data)])


class JBLBarMediaPlayer(JBLBarEntity, MediaPlayerEntity):
    """Hauptentität ohne eigenen Namen – heißt wie die Bar."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_volume_step = 0.03
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(self, coordinator: JBLBarCoordinator) -> None:
        # translation_key "bar" bleibt: darüber wird das Attribut audio_format übersetzt; den Namen
        # liefert _attr_name = None (Gerätename)
        super().__init__(coordinator, "bar", "media_player")
        self._attr_source_list = list(SOURCES.values())
        self.entity_id = f"media_player.{slugify(coordinator.device.get('name') or 'jbl_bar')}"

    @property
    def state(self) -> MediaPlayerState | None:
        data = self.coordinator.data
        if data.power is False:
            return MediaPlayerState.OFF
        if data.player_status == "play" or data.media.transport_state == "PLAYING" or data.streaming:
            return MediaPlayerState.PLAYING
        if data.player_status == "pause" or data.media.transport_state == "PAUSED_PLAYBACK":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE if data.power else None

    @property
    def volume_level(self) -> float | None:
        volume = self.coordinator.data.volume
        return None if volume is None else volume / 100

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.data.muted

    @property
    def source(self) -> str | None:
        return SOURCES.get(self.coordinator.data.source or "")

    @property
    def media_title(self) -> str | None:
        return self.coordinator.data.media.title

    @property
    def media_artist(self) -> str | None:
        return self.coordinator.data.media.artist

    @property
    def media_album_name(self) -> str | None:
        return self.coordinator.data.media.album

    @property
    def media_image_url(self) -> str | None:
        url = self.coordinator.data.media.image_url
        return url if url and url.startswith("http") else None

    @property
    def media_duration(self) -> int | None:
        return self.coordinator.data.media.duration

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        return {"audio_format": self.coordinator.data.audio_format}

    async def async_turn_on(self) -> None:
        await self._run(self.coordinator.async_set_power(True))

    async def async_turn_off(self) -> None:
        await self._run(self.coordinator.async_set_power(False))

    async def async_set_volume_level(self, volume: float) -> None:
        await self._run(self.coordinator.async_set_volume(round(volume * 100)))

    async def async_mute_volume(self, mute: bool) -> None:
        await self._run(self.coordinator.async_set_mute(mute))

    async def async_select_source(self, source: str) -> None:
        key = next((k for k, name in SOURCES.items() if name == source), source)
        await self._run(self.coordinator.async_set_source(key))

    async def async_media_play(self) -> None:
        if self.state != MediaPlayerState.PLAYING:
            await self._run(self.coordinator.async_press("musicPlayPause"))

    async def async_media_pause(self) -> None:
        if self.state == MediaPlayerState.PLAYING:
            await self._run(self.coordinator.async_press("musicPlayPause"))

    async def async_media_next_track(self) -> None:
        await self._run(self.coordinator.async_press("next"))

    async def async_media_previous_track(self) -> None:
        await self._run(self.coordinator.async_press("prev"))
