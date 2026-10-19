"""Daten der Bar sammeln: schneller Zustand alle 10 s, Einstellungen jede Minute, Ereignisse per UPnP."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    JBLBarClient,
    JBLBarCommandError,
    JBLBarConnectionError,
    JBLBarError,
    MediaInfo,
    format_stream_info,
    parse_harman_state,
)
from .const import DOMAIN, EQ_CUSTOM_ID, EVENT_TIMEOUT, MAX_MISSES, SCAN_INTERVAL, SLOW_EVERY, SOURCE_ALIASES

_LOGGER = logging.getLogger(__name__)

type JBLBarConfigEntry = ConfigEntry[JBLBarCoordinator]


@dataclass(slots=True)
class EqPreset:
    """Ein EQ-Preset der Bar (`eq_id` "0" = eigenes)."""

    eq_id: str
    name: str
    band: int
    payload: dict[str, Any]

    @property
    def gains(self) -> list[float]:
        return [float(g) for g in self.payload.get("gain", [])]


@dataclass(slots=True)
class JBLBarState:
    """Alles, was die Entitäten zeigen. Felder bleiben None, solange die Bar nichts dazu gesagt hat."""

    power: bool | None = None
    volume: int | None = None
    muted: bool | None = None
    player_status: str | None = None
    source: str | None = None
    streaming: bool | None = None
    atmos_active: bool | None = None
    media: MediaInfo = field(default_factory=MediaInfo)
    eq_presets: dict[str, EqPreset] = field(default_factory=dict)
    eq_active_id: str | None = None
    night_mode: bool | None = None
    smart_mode: bool | None = None
    pure_voice: bool | None = None
    feedback_tone: bool | None = None
    audio_sync: int | None = None
    atmos_level: int | None = None
    rears: dict[str, dict[str, Any]] = field(default_factory=dict)
    rear_volume: int | None = None
    sleep_timer: int | None = None
    sleep_remaining: int | None = None
    audio_format: str | None = None
    stream_info: dict[str, Any] = field(default_factory=dict)

    @property
    def eq_gains(self) -> list[float]:
        """Verstärkung der Bänder des aktiven Presets."""
        preset = self.eq_presets.get(self.eq_active_id or "")
        return preset.gains if preset else []


def _on(value: Any) -> bool:
    return str(value).lower() in ("on", "1", "true")


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _dicts(value: Any) -> list[dict[str, Any]]:
    """Liste aus einer Antwort der Bar; fehlt sie oder enthält sie Fremdes, zählen nur die Objekte darin."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _source(raw: Any) -> str | None:
    if not raw:
        return None
    value = str(raw).upper()
    return SOURCE_ALIASES.get(value, value)


class JBLBarCoordinator(DataUpdateCoordinator[JBLBarState]):
    """Fragt die Bar ab und schickt Änderungen hin."""

    config_entry: JBLBarConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: JBLBarConfigEntry, client: JBLBarClient, device: dict[str, Any]
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            request_refresh_debouncer=Debouncer(hass, _LOGGER, cooldown=1.0, immediate=False),
        )
        self.client = client
        self.device = device
        # Befehle, die diese Bar nicht kennt – werden nicht mehr gefragt, ihre Entitäten nicht angelegt.
        self.unsupported: set[str] = set()
        self._cycle = 0
        self._slow_due = True
        self._standby = False
        self._sid: str | None = None
        self._misses = 0
        # Registry-ID der Bar – die Rear-Speaker hängen daran.
        self.device_id: str | None = None
        # IP-Adressen, von denen NOTIFYs der Bar angenommen werden (der Host kann auch ein Name sein).
        self.host_ips: frozenset[str] = frozenset({client.host})

    @property
    def unique_id(self) -> str:
        return str(self.config_entry.unique_id)

    def supports(self, command: str) -> bool:
        return command not in self.unsupported

    @property
    def events_subscribed(self) -> bool:
        return self._sid is not None

    # ---------- Abfragen ----------

    async def _ask(self, command: str) -> dict[str, Any] | None:
        """Ein Lese-Befehl; None bei unbekanntem Befehl oder kurzem Fehler (alter Wert bleibt dann stehen)."""
        if command in self.unsupported:
            return None
        try:
            return await self.client.command(command)
        except JBLBarCommandError as err:
            if "unknown command" in str(err):
                _LOGGER.debug("%s: Bar kennt %s nicht", self.client.host, command)
                self.unsupported.add(command)
            else:
                _LOGGER.debug("%s", err)
            return None

    async def _async_update_data(self) -> JBLBarState:
        state = replace(self.data) if self.data else JBLBarState()
        slow = self._slow_due or self._cycle % SLOW_EVERY == 0
        self._cycle += 1
        self._slow_due = False
        try:
            power = await self.client.command("getPowerState")
            # Achtung, verdreht: "0" = an, "1" = Standby (an der Bar 1000 ausprobiert, 07.10.2026).
            state.power = str(power.get("power_state")) == "0"
            if not state.power:
                # Standby: keine Wiedergabe abfragen, Einstellungen (u. a. Rear-Akkus) nur im langsamen Takt –
                # sonst bleiben sie nach einem HA-Neustart im Standby „nicht verfügbar“.
                self._misses = 0
                self._standby = True
                if slow:
                    await self._update_settings(state)
                return state
            if self._standby:
                # Gerade eingeschaltet: Einstellungen sofort lesen
                self._standby = False
                slow = True
            player, streaming, selected = await asyncio.gather(
                self.client.command("getPlayerStatus"),
                self._ask("getStreamingStatus"),
                self._ask("getMediaSourceStatus"),
            )
        except JBLBarError as err:
            self._slow_due = self._slow_due or slow
            # Beim Wechsel in den Standby bricht die Bar gern eine Verbindung ab – ein Aussetzer zählt nicht,
            # erst der zweite in Folge macht die Entitäten „nicht verfügbar“.
            if self.data is not None and self._misses < MAX_MISSES:
                self._misses += 1
                _LOGGER.debug("%s: Aussetzer %s – alter Zustand bleibt: %s", self.client.host, self._misses, err)
                return self.data
            key = "unreachable" if isinstance(err, JBLBarConnectionError) else "update_failed"
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key=key, translation_placeholders={"error": str(err)}
            ) from err
        self._misses = 0

        state.volume = _int(player.get("vol"))
        state.muted = _on(player.get("mute"))
        state.player_status = player.get("status")
        if streaming and isinstance(streaming.get("status"), dict):
            info = streaming["status"]
            state.source = _source(info.get("source"))
            state.streaming = _on(info.get("is_streaming"))
            state.atmos_active = _on(info.get("is_atmos"))
        # Gewählter Eingang – auch wenn gerade nichts ankommt (dann meldet getStreamingStatus nur IDLE).
        if selected and selected.get("media_source"):
            state.source = _source(selected["media_source"])
        try:
            state.media = await self.client.media_info()
        except JBLBarError as err:
            _LOGGER.debug("GetInfoEx: %s", err)

        if slow:
            await self._update_settings(state)
        return state

    async def _update_settings(self, state: JBLBarState) -> None:
        commands = (
            "getEQList",
            "getPersonalListeningMode",
            "getSmartMode",
            "getPureVoiceState",
            "getFeedbackToneConfig",
            "getAudioSync",
            "getAtmosLevel",
            "getRearSpeakerStatus",
            "getRearSpeakerVolume",
            "getSleepTimer",
        )
        answers = dict(zip(commands, await asyncio.gather(*(self._ask(c) for c in commands)), strict=True))

        if (eq := answers["getEQList"]) is not None:
            state.eq_presets = {
                str(item.get("eq_id")): EqPreset(
                    eq_id=str(item.get("eq_id")),
                    name=str(item.get("eq_name") or f"Preset {item.get('eq_id')}"),
                    band=_int(item.get("band")) or 7,
                    payload=dict(item["eq_payload"]) if isinstance(item.get("eq_payload"), dict) else {},
                )
                for item in _dicts(eq.get("eq_list"))
                if item.get("eq_id") is not None
            }
            state.eq_active_id = str(eq.get("active_eq_id", EQ_CUSTOM_ID))
        if (night := answers["getPersonalListeningMode"]) is not None:
            state.night_mode = _on(night.get("status"))
        if (smart := answers["getSmartMode"]) is not None:
            state.smart_mode = _on(smart.get("status"))
        if (voice := answers["getPureVoiceState"]) is not None:
            state.pure_voice = _on(voice.get("purevoice_state"))
        if (tone := answers["getFeedbackToneConfig"]) is not None:
            state.feedback_tone = _on(tone.get("status"))
        if (sync := answers["getAudioSync"]) is not None:
            state.audio_sync = _int(sync.get("audio_sync"))
        if (atmos := answers["getAtmosLevel"]) is not None:
            state.atmos_level = _int(atmos.get("atmos_level")) if _on(atmos.get("status")) else 0
        if (rears := answers["getRearSpeakerStatus"]) is not None:
            state.rears = {str(r.get("channel")): r for r in _dicts(rears.get("rears")) if r.get("channel")}
        if (rear_volume := answers["getRearSpeakerVolume"]) is not None:
            state.rear_volume = _int(rear_volume.get("volume"))
        if (sleep := answers["getSleepTimer"]) is not None:
            state.sleep_timer = _int(sleep.get("sleep_timer"))
            state.sleep_remaining = _int(sleep.get("remain_time"))

    # ---------- Schreiben ----------

    async def _write(self, action: Callable[[], Awaitable[Any]], change: Callable[[JBLBarState], None]) -> None:
        """Befehl schicken, Zustand sofort anpassen und gleich danach frisch lesen (inkl. Einstellungen)."""
        await action()
        if self.data is not None:
            state = replace(self.data)
            change(state)
            self.async_set_updated_data(state)
        self._slow_due = True
        await self.async_request_refresh()

    def _set(self, **values: Any) -> Callable[[JBLBarState], None]:
        def apply(state: JBLBarState) -> None:
            for key, value in values.items():
                setattr(state, key, value)

        return apply

    async def async_set_power(self, on: bool) -> None:
        async def action() -> None:
            await self.client.command("setPowerState", {"power_state": "0" if on else "1"})

        await self._write(action, self._set(power=on))

    async def async_set_volume(self, percent: int) -> None:
        await self._write(lambda: self.client.set_volume(percent), self._set(volume=percent))

    async def async_set_mute(self, mute: bool) -> None:
        await self._write(lambda: self.client.set_mute(mute), self._set(muted=mute))

    async def async_set_source(self, source: str) -> None:
        await self._write(
            lambda: self.client.command("setMediaSource", {"media_source": source}), self._set(source=source)
        )

    async def async_press(self, key: str) -> None:
        await self._write(lambda: self.client.key(key), lambda _state: None)

    async def async_set_switch(self, key: str, on: bool) -> None:
        """Nachtmodus, Smart Mode, PureVoice, Bestätigungstöne."""
        commands: dict[str, tuple[str, dict[str, Any]]] = {
            "night_mode": ("setPersonalListeningMode", {"status": "on" if on else "off"}),
            "smart_mode": ("setSmartMode", {"status": "on" if on else "off"}),
            "pure_voice": ("setPureVoiceState", {"purevoice_state": "1" if on else "0"}),
            "feedback_tone": ("setFeedbackToneConfig", {"status": "on" if on else "off"}),
        }
        command, payload = commands[key]
        await self._write(lambda: self.client.command(command, payload), self._set(**{key: on}))

    async def async_set_audio_sync(self, value: int) -> None:
        await self._write(
            lambda: self.client.command("setAudioSync", {"audio_sync": str(value)}), self._set(audio_sync=value)
        )

    async def async_set_rear_volume(self, value: int) -> None:
        await self._write(
            lambda: self.client.command("setRearSpeakerVolume", {"volume": str(value)}),
            self._set(rear_volume=value),
        )

    async def async_set_sleep_timer(self, minutes: int) -> None:
        await self._write(
            lambda: self.client.command("setSleepTimer", {"sleep_timer": minutes * 60}),
            self._set(sleep_timer=minutes * 60, sleep_remaining=minutes * 60),
        )

    async def async_set_eq_preset(self, eq_id: str) -> None:
        preset = self.data.eq_presets.get(eq_id) if self.data else None
        if preset is None:
            raise JBLBarError(f"EQ preset {eq_id} not found on the bar")
        payload = {"active_eq_id": eq_id, "band": preset.band, "eq_payload": preset.payload}
        await self._write(lambda: self.client.command("setActiveEQ", payload), self._set(eq_active_id=eq_id))

    async def async_set_eq_band(self, index: int, gain: float) -> None:
        """Ein Band ändern: übernimmt die Bänder des aktiven Presets ins eigene Preset und setzt es aktiv."""
        if self.data is None:
            return
        source = self.data.eq_presets.get(self.data.eq_active_id or "")
        custom = self.data.eq_presets.get(EQ_CUSTOM_ID)
        base = source or custom
        if base is None:
            raise JBLBarError("the bar reported no EQ data")
        gains = base.gains
        if not 0 <= index < len(gains):
            raise JBLBarError(f"the bar's EQ has {len(gains)} bands, no band {index + 1}")
        gains[index] = gain
        frequencies = list((custom or base).payload.get("fs") or [125, 250, 500, 1000, 2000, 4000, 8000])
        eq_payload = {"fs": [float(f) for f in frequencies], "gain": gains}
        payload = {"active_eq_id": EQ_CUSTOM_ID, "band": len(gains), "eq_payload": eq_payload}

        def change(state: JBLBarState) -> None:
            presets = dict(state.eq_presets)
            name = custom.name if custom else "CUSTOMIZE"
            presets[EQ_CUSTOM_ID] = EqPreset(EQ_CUSTOM_ID, name, len(gains), eq_payload)
            state.eq_presets = presets
            state.eq_active_id = EQ_CUSTOM_ID

        await self._write(lambda: self.client.command("setActiveEQ", payload), change)

    # ---------- Ereignisse (UPnP GENA) ----------

    async def async_run_events(self, callback_url: str) -> None:
        """Abo halten, solange der Eintrag lebt; bei Fehlern alle 5 Min. neu versuchen (Abfrage läuft weiter)."""
        try:
            while True:
                try:
                    if self._sid is None:
                        self._sid, timeout = await self.client.subscribe(callback_url, EVENT_TIMEOUT)
                        _LOGGER.debug("Ereignisse von %s abonniert (%s)", self.client.host, callback_url)
                    else:
                        self._sid, timeout = await self.client.renew(self._sid, EVENT_TIMEOUT)
                except JBLBarError as err:
                    _LOGGER.debug("Ereignis-Abo bei %s: %s", self.client.host, err)
                    self._sid = None
                    timeout = EVENT_TIMEOUT
                await asyncio.sleep(max(30, timeout - 60))
        finally:
            if self._sid:
                sid, self._sid = self._sid, None
                await self.client.unsubscribe(sid)

    def handle_notify(self, body: str) -> None:
        """Ein NOTIFY der Bar: Audioformat übernehmen und den Rest gleich neu lesen."""
        state = parse_harman_state(body)
        if state and isinstance(info := state.get("tv_stream_info"), dict) and self.data is not None:
            data = replace(self.data)
            data.stream_info = info
            data.audio_format = format_stream_info(info)
            self.async_set_updated_data(data)
        self.hass.async_create_task(self.async_request_refresh(), eager_start=True)
