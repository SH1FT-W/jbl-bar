"""UPnP-Ereignisse und Texte aus der Bar lesen."""

from __future__ import annotations

import socket

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from common import FakeBar
from custom_components.jbl_bar import _handle_notify
from custom_components.jbl_bar.api import format_stream_info, parse_didl, parse_harman_state

NOTIFY = (
    '<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0"><e:property><LastChange>'
    "&lt;Event xmlns=&quot;urn:schemas-upnp-org:metadata-1-0/RCS/&quot;&gt;&lt;InstanceID val=&quot;0&quot;&gt;"
    "&lt;HarmanBarState val=&quot;{&amp;quot;tv_stream_info&amp;quot;:{&amp;quot;source&amp;quot;:"
    "&amp;quot;com.harman.HDMI2&amp;quot;,&amp;quot;codec_type&amp;quot;:&amp;quot;DDP&amp;quot;,"
    "&amp;quot;proc_type&amp;quot;:&amp;quot;ATMOS&amp;quot;,&amp;quot;channels&amp;quot;:6,"
    "&amp;quot;sample_rate&amp;quot;:48000}}&quot;/&gt;&lt;/InstanceID&gt;&lt;/Event&gt;"
    "</LastChange></e:property></e:propertyset>"
)


def test_parse_harman_state() -> None:
    state = parse_harman_state(NOTIFY)
    assert state["tv_stream_info"]["codec_type"] == "DDP"
    assert format_stream_info(state["tv_stream_info"]) == "ATMOS / DDP / 6ch / 48 kHz"
    assert parse_harman_state("<kaputt") is None
    assert parse_harman_state("<a><b>nichts</b></a>") is None


def test_format_and_didl_edges() -> None:
    assert format_stream_info({}) is None
    assert format_stream_info({"codec_type": "PCM", "sample_rate": "x"}) == "PCM / x Hz"
    assert parse_didl(None) == {}
    assert parse_didl("<kaputt") == {}
    assert parse_didl('<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"/>') == {}


async def test_notify_updates_audio_format(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    setup.runtime_data.handle_notify(NOTIFY)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jbl_bar_1000_audio_format").state == "ATMOS / DDP / 6ch / 48 kHz"
    assert hass.states.get("media_player.jbl_bar_1000").attributes["audio_format"] == "ATMOS / DDP / 6ch / 48 kHz"


class FakeRequest:
    def __init__(self, hass: HomeAssistant, entry_id: str, remote: str, body: str = NOTIFY, size: int = 10) -> None:
        from homeassistant.components.http import KEY_HASS

        self.app = {KEY_HASS: hass}
        self.match_info = {"entry_id": entry_id}
        self.remote = remote
        self.content_length = size
        self._body = body

        self.charset: str | None = None
        self.content = self

    async def read(self, n: int = -1) -> bytes:
        data = self._body.encode()
        return data if n < 0 else data[:n]


async def test_notify_route_checks_sender(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    assert (await _handle_notify(FakeRequest(hass, "nope", "192.0.2.76"))).status == 404
    assert (await _handle_notify(FakeRequest(hass, setup.entry_id, "192.0.2.5"))).status == 403
    assert (await _handle_notify(FakeRequest(hass, setup.entry_id, "192.0.2.76", size=10**6))).status == 413
    assert (await _handle_notify(FakeRequest(hass, setup.entry_id, "192.0.2.76"))).status == 200
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jbl_bar_1000_audio_format").state.startswith("ATMOS")


async def test_subscribed(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    assert setup.runtime_data._sid == "uuid:abc"


async def test_notify_route_after_unload(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    assert await hass.config_entries.async_unload(setup.entry_id)
    await hass.async_block_till_done()
    assert (await _handle_notify(FakeRequest(hass, setup.entry_id, "192.0.2.76"))).status == 404


async def test_notify_from_hostname_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Host als Name eingerichtet: die NOTIFYs kommen trotzdem von der IP und müssen durchgehen."""
    fake = FakeBar()
    fake.install(aioclient_mock, host="soundbar.fritz.box")

    def getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list[tuple]:
        assert host == "soundbar.fritz.box"
        return [(2, 2, 17, "", ("192.0.2.76", 0)), (2, 1, 6, "", ("192.0.2.76", 0))]

    monkeypatch.setattr("custom_components.jbl_bar.socket.getaddrinfo", getaddrinfo)
    entry = MockConfigEntry(domain="jbl_bar", unique_id="02:00:00:00:00:01", data={CONF_HOST: "soundbar.fritz.box"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.host_ips == {"192.0.2.76"}
    assert (await _handle_notify(FakeRequest(hass, entry.entry_id, "192.0.2.76"))).status == 200
    assert (await _handle_notify(FakeRequest(hass, entry.entry_id, "192.0.2.5"))).status == 403


async def test_unresolvable_hostname_rejects_notify(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeBar()
    fake.install(aioclient_mock, host="nirgendwo.invalid")

    def getaddrinfo(*args: object, **kwargs: object) -> list[tuple]:
        raise socket.gaierror("kein DNS")

    monkeypatch.setattr("custom_components.jbl_bar.socket.getaddrinfo", getaddrinfo)
    entry = MockConfigEntry(domain="jbl_bar", unique_id="02:00:00:00:00:01", data={CONF_HOST: "nirgendwo.invalid"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.host_ips == frozenset()
    assert (await _handle_notify(FakeRequest(hass, entry.entry_id, "192.0.2.76"))).status == 403


async def test_notify_without_length_is_limited(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    """Chunked ohne Content-Length: zu große Ereignisse werden beim Lesen abgewiesen."""
    big = FakeRequest(hass, setup.entry_id, "192.0.2.76", body="x" * (64 * 1024 + 1), size=0)
    big.content_length = None  # type: ignore[assignment]
    assert (await _handle_notify(big)).status == 413
