"""UPnP-Ereignisse und Texte aus der Bar lesen."""

from __future__ import annotations

import asyncio
from ipaddress import ip_address
import socket
from types import SimpleNamespace

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from common import FakeBar
from custom_components.jbl_bar import _handle_notify
from custom_components.jbl_bar.api import (
    JBLBarCommandError,
    JBLBarConnectionError,
    format_stream_info,
    parse_didl,
    parse_harman_state,
)
from custom_components.jbl_bar.const import EVENT_RETRY
from custom_components.jbl_bar.coordinator import JBLBarCoordinator

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


class FlakyGena:
    """Stand-in client for the event loop: answers SUBSCRIBE/RENEW from a script of results."""

    host = "192.0.2.76"

    def __init__(self, results: list[tuple[str, int] | Exception]) -> None:
        self.results = results
        self.calls: list[str] = []

    async def _next(self, kind: str) -> tuple[str, int]:
        self.calls.append(kind)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def subscribe(self, callback_url: str, seconds: int) -> tuple[str, int]:
        return await self._next("subscribe")

    async def renew(self, sid: str, seconds: int) -> tuple[str, int]:
        return await self._next("renew")

    async def unsubscribe(self, sid: str) -> None:
        self.calls.append("unsubscribe")


async def _run_events(
    hass: HomeAssistant, client: FlakyGena, monkeypatch: pytest.MonkeyPatch, rounds: int
) -> tuple[JBLBarCoordinator, list[float]]:
    """Run the event loop for a few rounds without real sleeping; returns the requested sleep times."""
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) >= rounds:
            raise asyncio.CancelledError

    # Only the coordinator module sees the fake sleep, HA's own tasks keep the real one
    monkeypatch.setattr(
        "custom_components.jbl_bar.coordinator.asyncio",
        SimpleNamespace(sleep=fake_sleep, gather=asyncio.gather, Lock=asyncio.Lock),
    )
    entry = MockConfigEntry(domain="jbl_bar", unique_id="02:00:00:00:00:01", data={CONF_HOST: client.host})
    entry.add_to_hass(hass)
    coordinator = JBLBarCoordinator(hass, entry, client, {})  # type: ignore[arg-type]
    with pytest.raises(asyncio.CancelledError):
        await coordinator.async_run_events("http://192.0.2.1:8123/x")
    return coordinator, sleeps


async def test_events_retry_after_failed_subscribe(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed SUBSCRIBE is retried after EVENT_RETRY (no subscription exists, its timeout does not apply)."""
    client = FlakyGena([JBLBarConnectionError("offline"), ("uuid:new", 300)])
    _, sleeps = await _run_events(hass, client, monkeypatch, rounds=2)
    assert client.calls == ["subscribe", "subscribe", "unsubscribe"]
    assert sleeps == [EVENT_RETRY, 240]  # then renew a minute before the granted 300 s run out


async def test_events_failed_renew_resubscribes(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch) -> None:
    client = FlakyGena([("uuid:a", 300), JBLBarCommandError("SUBSCRIBE: HTTP 412"), ("uuid:b", 300)])
    coordinator, sleeps = await _run_events(hass, client, monkeypatch, rounds=3)
    assert client.calls == ["subscribe", "renew", "subscribe", "unsubscribe"]
    assert sleeps == [240, EVENT_RETRY, 240]
    assert not coordinator.events_subscribed


async def test_events_short_timeout_renewed_in_time(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the bar grants less than the requested timeout, the renewal must come before it expires."""
    for granted in (20, 60, 90):
        _, sleeps = await _run_events(hass, FlakyGena([("uuid:a", granted)]), monkeypatch, rounds=1)
        assert 0 < sleeps[0] < granted
    # Nonsense from the bar (Second-0, Second--5) must not lead to a renewal every second
    for granted in (0, -5):
        _, sleeps = await _run_events(hass, FlakyGena([("uuid:a", granted)]), monkeypatch, rounds=1)
        assert sleeps == [5]


async def test_notify_after_zeroconf_ip_change(hass: HomeAssistant, bar: FakeBar, setup, aioclient_mock) -> None:
    """IP entry, bar gets a new IP via DHCP: zeroconf updates the host, NOTIFYs from the new IP get through."""
    from homeassistant import config_entries
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

    bar.install(aioclient_mock, host="192.0.2.77")
    info = ZeroconfServiceInfo(
        ip_address=ip_address("192.0.2.77"),
        ip_addresses=[ip_address("192.0.2.77")],
        hostname="bar.local.",
        name="JBL BAR 1000._jbl-product._tcp.local.",
        port=None,
        type="_jbl-product._tcp.local.",
        properties={"MAC": "02:00:00:00:00:01"},
    )
    result = await hass.config_entries.flow.async_init(
        "jbl_bar", context={"source": config_entries.SOURCE_ZEROCONF}, data=info
    )
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()
    assert (await _handle_notify(FakeRequest(hass, setup.entry_id, "192.0.2.77"))).status == 200
    assert (await _handle_notify(FakeRequest(hass, setup.entry_id, "192.0.2.76"))).status == 403


async def test_notify_after_dns_change(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Host name entry, the name now points to a new IP (DHCP): NOTIFYs from it get through without a reload."""
    FakeBar().install(aioclient_mock, host="soundbar.fritz.box")
    current = {"ip": "192.0.2.76"}
    lookups: list[str] = []

    def getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list[tuple]:
        lookups.append(host)
        return [(2, 1, 6, "", (current["ip"], 0))]

    monkeypatch.setattr("custom_components.jbl_bar.socket.getaddrinfo", getaddrinfo)
    entry = MockConfigEntry(domain="jbl_bar", unique_id="02:00:00:00:00:01", data={CONF_HOST: "soundbar.fritz.box"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    lookups.clear()

    current["ip"] = "192.0.2.77"
    # Within a minute of the last lookup an unknown sender does not trigger another one
    assert (await _handle_notify(FakeRequest(hass, entry.entry_id, "192.0.2.77"))).status == 403
    assert lookups == []
    entry.runtime_data.host_ips_resolved -= 61
    assert (await _handle_notify(FakeRequest(hass, entry.entry_id, "192.0.2.77"))).status == 200
    assert entry.runtime_data.host_ips == {"192.0.2.77"}
    # Old IP and strangers are refused; a flood of them does not trigger a lookup each time
    assert (await _handle_notify(FakeRequest(hass, entry.entry_id, "192.0.2.76"))).status == 403
    assert (await _handle_notify(FakeRequest(hass, entry.entry_id, "192.0.2.5"))).status == 403
    assert lookups == ["soundbar.fritz.box"]


async def test_failed_lookup_keeps_known_ips(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DNS hiccup during a lookup triggered by a stranger must not lock out the bar's own events."""
    FakeBar().install(aioclient_mock, host="soundbar.fritz.box")
    dns = {"up": True}

    def getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list[tuple]:
        if not dns["up"]:
            raise socket.gaierror("kein DNS")
        return [(2, 1, 6, "", ("192.0.2.76", 0))]

    monkeypatch.setattr("custom_components.jbl_bar.socket.getaddrinfo", getaddrinfo)
    entry = MockConfigEntry(domain="jbl_bar", unique_id="02:00:00:00:00:01", data={CONF_HOST: "soundbar.fritz.box"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    dns["up"] = False
    entry.runtime_data.host_ips_resolved -= 61
    assert (await _handle_notify(FakeRequest(hass, entry.entry_id, "192.0.2.5"))).status == 403
    assert (await _handle_notify(FakeRequest(hass, entry.entry_id, "192.0.2.76"))).status == 200
