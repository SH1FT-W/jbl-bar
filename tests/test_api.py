"""Client ohne HA: Fehlerfälle, Zeitangaben, Rückruf-Adresse."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from common import HOST
from custom_components.jbl_bar import _callback_url
from custom_components.jbl_bar.api import (
    JBLBarClient,
    JBLBarCommandError,
    _seconds,
    create_ssl_context,
    parse_info_ex,
)

URL = f"https://{HOST}/httpapi.asp"


@pytest.fixture
async def client(hass: HomeAssistant) -> JBLBarClient:
    return JBLBarClient(HOST, async_get_clientsession(hass), await hass.async_add_executor_job(create_ssl_context))


@pytest.mark.parametrize(
    ("text", "status", "message"),
    [
        ("unknown command", 200, "unknown command"),
        ("<html>", 200, "keine JSON-Antwort"),
        ("[1]", 200, "unerwartete Antwort"),
        ('{"error_code":"1"}', 200, "error_code 1"),
        ("", 500, "HTTP 500"),
    ],
)
async def test_command_errors(
    aioclient_mock: AiohttpClientMocker, client: JBLBarClient, text: str, status: int, message: str
) -> None:
    aioclient_mock.post(URL, text=text, status=status)
    with pytest.raises(JBLBarCommandError, match=message):
        await client.command("getX")


async def test_status_without_error_code(aioclient_mock: AiohttpClientMocker, client: JBLBarClient) -> None:
    aioclient_mock.post(URL, text='{"vol":"48"}')
    assert await client.command("getPlayerStatus") == {"vol": "48"}
    assert aioclient_mock.mock_calls[-1][2] == "command=getPlayerStatus"


async def test_subscribe_refused(aioclient_mock: AiohttpClientMocker, client: JBLBarClient) -> None:
    aioclient_mock.request("subscribe", f"http://{HOST}:49152/upnp/event/rendercontrol1", status=412)
    with pytest.raises(JBLBarCommandError, match="412"):
        await client.subscribe("http://x/y", 300)


def test_seconds() -> None:
    assert _seconds("0:03:30") == 210
    assert _seconds("1:00:00.000") == 3600
    assert _seconds("NOT_IMPLEMENTED") is None
    assert _seconds("0:00:00") is None
    assert _seconds("a:b:c") is None


def test_info_ex_without_metadata() -> None:
    info = parse_info_ex("<a><CurrentTransportState>PAUSED_PLAYBACK</CurrentTransportState></a>")
    assert info.transport_state == "PAUSED_PLAYBACK"
    assert info.title is None


class FakeSocket:
    def __init__(self, *args: object) -> None:
        pass

    def __enter__(self) -> FakeSocket:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def connect(self, address: tuple[str, int]) -> None:
        pass

    def getsockname(self) -> tuple[str, int]:
        return ("192.0.2.99", 0)


async def test_callback_url(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("custom_components.jbl_bar.socket.socket", FakeSocket)
    await async_process_ha_core_config(hass, {"internal_url": "http://192.0.2.30:8123"})
    assert await _callback_url(hass, HOST, "abc") == "http://192.0.2.30:8123/api/jbl_bar/notify/abc"
    # Hostname statt IP: die Bar löst kein mDNS auf → eigene IP auf dem Weg zur Bar
    await async_process_ha_core_config(hass, {"internal_url": "http://homeassistant.local:8123"})
    assert (await _callback_url(hass, HOST, "abc")).startswith("http://192.0.2.99:")


def test_ssl_context_is_shared() -> None:
    assert create_ssl_context() is create_ssl_context()


async def test_unsubscribe_releases_response(aioclient_mock: AiohttpClientMocker, client: JBLBarClient) -> None:
    aioclient_mock.request("unsubscribe", f"http://{HOST}:49152/upnp/event/rendercontrol1", text="")
    await client.unsubscribe("uuid:abc")
    assert aioclient_mock.mock_calls[-1][0] == "UNSUBSCRIBE"
    aioclient_mock.clear_requests()
    aioclient_mock.request("unsubscribe", f"http://{HOST}:49152/upnp/event/rendercontrol1", exc=TimeoutError())
    await client.unsubscribe("uuid:abc")  # Fehler egal
    aioclient_mock.clear_requests()
    aioclient_mock.request("unsubscribe", f"http://{HOST}:49152/upnp/event/rendercontrol1", exc=OSError("Netz weg"))
    await client.unsubscribe("uuid:abc")  # auch OSError bleibt still
