"""JBL Bar – Soundbars mit JBL One (Bar 300/500/700/800/1000/1300) lokal steuern."""

from __future__ import annotations

from ipaddress import ip_address
import logging
import socket

from aiohttp import web
from homeassistant.components.http import KEY_HASS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.typing import ConfigType

from .api import UPNP_PORT, JBLBarClient, JBLBarError, create_ssl_context
from .const import DOMAIN
from .coordinator import JBLBarConfigEntry, JBLBarCoordinator
from .entity import bar_device_info

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
NOTIFY_PATH = f"/api/{DOMAIN}/notify/{{entry_id}}"
MAX_NOTIFY_BYTES = 64 * 1024


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """NOTIFY-Route einmal anlegen (UPnP schickt ohne Anmeldung – geprüft wird die Absender-IP)."""
    hass.http.app.router.add_route("NOTIFY", NOTIFY_PATH, _handle_notify)
    return True


async def _handle_notify(request: web.Request) -> web.Response:
    hass = request.app[KEY_HASS]
    entry = hass.config_entries.async_get_entry(request.match_info["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        return web.Response(status=404)
    coordinator: JBLBarCoordinator = entry.runtime_data
    if request.remote not in coordinator.host_ips:
        return web.Response(status=403)
    if (request.content_length or 0) > MAX_NOTIFY_BYTES:
        return web.Response(status=413)
    # Ohne Content-Length (chunked) greift die Prüfung oben nicht: höchstens ein Byte über der Grenze lesen
    body = await request.content.read(MAX_NOTIFY_BYTES + 1)
    if len(body) > MAX_NOTIFY_BYTES:
        return web.Response(status=413)
    coordinator.handle_notify(body.decode(request.charset or "utf-8", errors="replace"))
    return web.Response(status=200)


async def async_setup_entry(hass: HomeAssistant, entry: JBLBarConfigEntry) -> bool:
    """Bar verbinden, erste Abfrage, Plattformen, Ereignis-Abo im Hintergrund."""
    host: str = entry.data[CONF_HOST]
    client = JBLBarClient(
        host,
        async_get_clientsession(hass, verify_ssl=False),
        await hass.async_add_executor_job(create_ssl_context),
    )
    try:
        device = (await client.command("getDeviceInfo")).get("device_info", {})
    except JBLBarError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="not_ready",
            translation_placeholders={"host": host, "error": str(err)},
        ) from err

    coordinator = JBLBarCoordinator(hass, entry, client, device)
    await coordinator.async_config_entry_first_refresh()
    # Ist der Host ein Name statt einer IP, kommen die NOTIFYs trotzdem von einer IP: die merken wir uns
    coordinator.host_ips = await hass.async_add_executor_job(_resolve_ips, host)
    entry.runtime_data = coordinator
    coordinator.device_id = (
        dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, **bar_device_info(coordinator)).id
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Hintergrund-Task: HA wartet beim Start nicht darauf (die alte Integration hing hier 5 Minuten).
    callback_url = await _callback_url(hass, host, entry.entry_id)
    entry.async_create_background_task(hass, coordinator.async_run_events(callback_url), f"{DOMAIN}_events_{host}")
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: JBLBarConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Löschen nur für Rear-Speaker, die die Bar nicht mehr meldet; die Bar selbst geht über den Eintrag."""
    coordinator = entry.runtime_data
    prefix = f"{coordinator.unique_id}_rear_"
    for domain, identifier in device.identifiers:
        if domain == DOMAIN and identifier.startswith(prefix):
            return identifier.removeprefix(prefix) not in coordinator.data.rears
    return False


async def async_unload_entry(hass: HomeAssistant, entry: JBLBarConfigEntry) -> bool:
    """Plattformen abbauen; der Ereignis-Task wird von HA beendet und meldet das Abo ab."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _resolve_ips(host: str) -> frozenset[str]:
    """IP-Adressen des Hosts (blockiert bei Namen: im Executor rufen). Eine IP bleibt, wie sie ist."""
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        return frozenset({host})
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        _LOGGER.warning("%s lässt sich nicht auflösen; Ereignisse der Bar werden abgelehnt, bis das klappt", host)
        return frozenset()
    return frozenset(str(info[4][0]) for info in infos)


def _own_ip(host: str) -> str:
    """Eigene IP auf dem Weg zur Bar (UDP-connect schickt nichts, kann aber blockieren: im Executor rufen)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((host, UPNP_PORT))
            return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"


async def _callback_url(hass: HomeAssistant, host: str, entry_id: str) -> str:
    """Adresse, unter der die Bar HA erreicht: interne URL, sonst die eigene IP auf dem Weg zur Bar."""
    path = NOTIFY_PATH.format(entry_id=entry_id)
    try:
        base = get_url(hass, allow_external=False, allow_cloud=False, prefer_external=False)
        url_host = base.split("://", 1)[1].split(":", 1)[0].split("/", 1)[0]
        ip_address(url_host)
    except (NoURLAvailableError, ValueError, IndexError):
        pass
    else:
        return base.rstrip("/") + path
    own_ip = await hass.async_add_executor_job(_own_ip, host)
    port = getattr(hass.http, "server_port", None) or 8123
    return f"http://{own_ip}:{port}{path}"
