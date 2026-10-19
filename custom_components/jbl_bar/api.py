"""Verbindung zur Soundbar – ohne Home Assistant, damit sie für sich testbar bleibt.

Die Bar spricht zwei Wege:
- `https://<ip>/httpapi.asp` (JBL One): POST `command=<name>&payload=<json>`, nur mit dem Client-Zertifikat
  der JBL-One-App (`certs/`). Antworten sind JSON mit `error_code` ("0" = ok) oder der Text `unknown command`.
- UPnP (Port 59152): AVTransport `GetInfoEx` (Titel, Cover), RenderingControl `SetVolume`/`SetMute` und
  GENA-Events auf Port 49152 (`HarmanBarState` mit dem Audioformat vom Fernseher).
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import functools
import html
import json
import logging
from pathlib import Path
import ssl
from typing import Any
from xml.etree import ElementTree as ET

import aiohttp

_LOGGER = logging.getLogger(__name__)

CERT_DIR = Path(__file__).parent / "certs"
UPNP_PORT = 59152
EVENT_PORT = 49152
REQUEST_TIMEOUT = 8
# Die Bar beantwortet viele gleichzeitige HTTPS-Anfragen schlecht – höchstens drei auf einmal.
MAX_PARALLEL = 3

SOAP_ENVELOPE = (
    '<?xml version="1.0" encoding="utf-8" standalone="yes"?>'
    '<s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" '
    'xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
    '<u:{action} xmlns:u="urn:schemas-upnp-org:service:{service}:1">'
    "<InstanceID>0</InstanceID>{args}</u:{action}></s:Body></s:Envelope>"
)
SOAP_CONTROL = {"AVTransport": "rendertransport1", "RenderingControl": "rendercontrol1"}
DIDL_NS = {
    "didl": "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "upnp": "urn:schemas-upnp-org:metadata-1-0/upnp/",
}


class JBLBarError(Exception):
    """Allgemeiner Fehler beim Sprechen mit der Bar."""


class JBLBarConnectionError(JBLBarError):
    """Bar nicht erreichbar (Netz, Zeitüberschreitung, TLS)."""


class JBLBarCommandError(JBLBarError):
    """Bar kennt den Befehl nicht oder meldet einen Fehlercode."""


@functools.cache
def create_ssl_context() -> ssl.SSLContext:
    """TLS mit dem App-Zertifikat; die Bar hat ein selbst signiertes Zertifikat.

    Liest Dateien, also im Executor rufen. Einmal gebaut und dann geteilt: der Kontext ist für alle Bars gleich,
    jede Einrichtungs-Probe und jeder Eintrag bekommt dieselbe Instanz.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.load_cert_chain(CERT_DIR / "cert.pem", CERT_DIR / "key.pem")
    return context


@dataclass(slots=True)
class MediaInfo:
    """Was AVTransport `GetInfoEx` über die laufende Wiedergabe sagt."""

    transport_state: str | None = None
    play_medium: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    image_url: str | None = None
    duration: int | None = None
    position: int | None = None


def _seconds(value: str | None) -> int | None:
    """`H:MM:SS` → Sekunden; leere oder `NOT_IMPLEMENTED`-Werte → None."""
    if not value or ":" not in value:
        return None
    try:
        hours, minutes, seconds = (int(float(part)) for part in value.split(":"))
    except ValueError:
        return None
    total = hours * 3600 + minutes * 60 + seconds
    return total or None


def parse_didl(metadata: str | None) -> dict[str, str]:
    """Titel, Interpret, Album und Cover aus DIDL-Lite (manchmal doppelt escaped)."""
    if not metadata:
        return {}
    text = metadata if metadata.lstrip().startswith("<") else html.unescape(metadata)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    item = root.find("didl:item", DIDL_NS)
    if item is None:
        return {}
    result: dict[str, str] = {}
    for key, path in (
        ("title", "dc:title"),
        ("artist", "upnp:artist"),
        ("album", "upnp:album"),
        ("image_url", "upnp:albumArtURI"),
    ):
        node = item.find(path, DIDL_NS)
        value = (node.text or "").strip() if node is not None else ""
        if value and value.lower() not in ("unknown", "un_known", "null"):
            result[key] = value
    return result


def parse_info_ex(xml_text: str) -> MediaInfo:
    """Antwort von `GetInfoEx` lesen (Namensräume der Felder sind leer)."""
    root = ET.fromstring(xml_text)
    fields: dict[str, str | None] = {}
    for element in root.iter():
        tag = element.tag.split("}")[-1]
        if tag in (
            "CurrentTransportState",
            "PlayMedium",
            "TrackMetaData",
            "TrackDuration",
            "RelTime",
        ):
            fields[tag] = element.text
    meta = parse_didl(fields.get("TrackMetaData"))
    return MediaInfo(
        transport_state=fields.get("CurrentTransportState"),
        play_medium=fields.get("PlayMedium"),
        title=meta.get("title"),
        artist=meta.get("artist"),
        album=meta.get("album"),
        image_url=meta.get("image_url"),
        duration=_seconds(fields.get("TrackDuration")),
        position=_seconds(fields.get("RelTime")),
    )


def parse_harman_state(body: str) -> dict[str, Any] | None:
    """`HarmanBarState` aus einem GENA-NOTIFY holen (LastChange ist XML im XML, Werte HTML-escaped)."""
    candidates = [body]
    with contextlib.suppress(ET.ParseError):
        for element in ET.fromstring(body).iter():
            if element.text and "HarmanBarState" in element.text:
                # Je nach Firmware einfach oder doppelt escaped – beide Fassungen probieren.
                candidates += [element.text, html.unescape(element.text)]
    for candidate in candidates:
        try:
            root = ET.fromstring(candidate)
        except ET.ParseError:
            continue
        for element in root.iter():
            if element.tag.split("}")[-1] != "HarmanBarState":
                continue
            raw = element.attrib.get("val")
            if not raw:
                continue
            try:
                state = json.loads(html.unescape(raw))
            except ValueError:
                continue
            if isinstance(state, dict):
                return state
    return None


def format_stream_info(info: dict[str, Any]) -> str | None:
    """`{"codec_type":"PCM","channels":2,"sample_rate":48000}` → `PCM / 2ch / 48 kHz`."""
    parts: list[str] = []
    proc = info.get("proc_type")
    codec = info.get("codec_type")
    if proc:
        parts.append(str(proc))
    if codec and codec != proc:
        parts.append(str(codec))
    if info.get("channels"):
        parts.append(f"{info['channels']}ch")
    rate = info.get("sample_rate")
    if rate:
        try:
            parts.append(f"{int(rate) / 1000:g} kHz")
        except (TypeError, ValueError):
            parts.append(f"{rate} Hz")
    return " / ".join(parts) or None


class JBLBarClient:
    """Befehle an eine Bar. Die aiohttp-Session gehört Home Assistant."""

    def __init__(self, host: str, session: aiohttp.ClientSession, ssl_context: ssl.SSLContext) -> None:
        self.host = host
        self._session = session
        self._ssl = ssl_context
        self._limit = asyncio.Semaphore(MAX_PARALLEL)

    async def command(self, name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Einen httpapi-Befehl schicken und die JSON-Antwort zurückgeben."""
        body = f"command={name}"
        if payload is not None:
            body += "&payload=" + json.dumps(payload, separators=(",", ":"))
        text = await self._request(
            "POST",
            f"https://{self.host}/httpapi.asp",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            ssl=self._ssl,
        )
        if "unknown command" in text:
            raise JBLBarCommandError(f"{name}: unknown command")
        try:
            result = json.loads(text)
        except ValueError as err:
            raise JBLBarCommandError(f"{name}: keine JSON-Antwort: {text[:80]!r}") from err
        if not isinstance(result, dict):
            raise JBLBarCommandError(f"{name}: unerwartete Antwort {text[:80]!r}")
        code = result.get("error_code")
        if code is not None and str(code) != "0":
            raise JBLBarCommandError(f"{name}: error_code {code}")
        return result

    async def key(self, key: str) -> None:
        """Eine Taste der Fernbedienung drücken (`sendAppController`)."""
        await self.command("sendAppController", {"key_pressed": key})

    async def soap(self, service: str, action: str, args: str = "") -> str:
        """Eine UPnP-Aktion aufrufen und den XML-Text zurückgeben."""
        return await self._request(
            "POST",
            f"http://{self.host}:{UPNP_PORT}/upnp/control/{SOAP_CONTROL[service]}",
            data=SOAP_ENVELOPE.format(action=action, service=service, args=args),
            headers={
                "Content-Type": 'text/xml; charset="utf-8"',
                "SOAPAction": f'"urn:schemas-upnp-org:service:{service}:1#{action}"',
            },
        )

    async def media_info(self) -> MediaInfo:
        """Laufende Wiedergabe (Titel, Cover, Zustand)."""
        text = await self.soap("AVTransport", "GetInfoEx")
        try:
            return parse_info_ex(text)
        except ET.ParseError as err:
            raise JBLBarCommandError("GetInfoEx: kein XML") from err

    async def set_volume(self, percent: int) -> None:
        """Lautstärke 0–100 (die Bar rundet auf ihre 3-%-Stufen)."""
        await self.soap(
            "RenderingControl",
            "SetVolume",
            f"<Channel>Master</Channel><DesiredVolume>{max(0, min(100, percent))}</DesiredVolume>",
        )

    async def set_mute(self, mute: bool) -> None:
        """Stumm schalten."""
        await self.soap(
            "RenderingControl", "SetMute", f"<Channel>Master</Channel><DesiredMute>{int(mute)}</DesiredMute>"
        )

    async def subscribe(self, callback_url: str, seconds: int) -> tuple[str, int]:
        """GENA-Abo für RenderingControl; gibt SID und die zugesagte Laufzeit zurück."""
        return await self._gena(
            {"CALLBACK": f"<{callback_url}>", "NT": "upnp:event", "TIMEOUT": f"Second-{seconds}"}, seconds
        )

    async def renew(self, sid: str, seconds: int) -> tuple[str, int]:
        """Abo verlängern."""
        return await self._gena({"SID": sid, "TIMEOUT": f"Second-{seconds}"}, seconds)

    async def unsubscribe(self, sid: str) -> None:
        """Abo beenden (Fehler egal – die Bar vergisst es sonst nach Ablauf)."""
        try:
            async with asyncio.timeout(5), self._session.request("UNSUBSCRIBE", self._event_url, headers={"SID": sid}):
                pass
        except (TimeoutError, aiohttp.ClientError, OSError):
            # OSError wie bei den anderen Anfragen (z. B. Netz weg beim Entladen), sonst landete er als Fehler im Log
            _LOGGER.debug("Abo %s ließ sich nicht abmelden", sid)

    @property
    def _event_url(self) -> str:
        return f"http://{self.host}:{EVENT_PORT}/upnp/event/rendercontrol1"

    async def _gena(self, headers: dict[str, str], seconds: int) -> tuple[str, int]:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.request("SUBSCRIBE", self._event_url, headers=headers)
                response.release()
        except (TimeoutError, aiohttp.ClientError, OSError) as err:
            raise JBLBarConnectionError(f"SUBSCRIBE: {err}") from err
        sid = response.headers.get("SID")
        if response.status not in (200, 202) or not sid:
            raise JBLBarCommandError(f"SUBSCRIBE: HTTP {response.status}")
        granted = response.headers.get("TIMEOUT", "")
        with contextlib.suppress(IndexError, ValueError):
            seconds = int(granted.split("-", 1)[1])
        return sid, seconds

    async def _request(self, method: str, url: str, **kwargs: Any) -> str:
        async with self._limit:
            try:
                async with asyncio.timeout(REQUEST_TIMEOUT), self._session.request(method, url, **kwargs) as response:
                    text = await response.text(errors="replace")
            except (TimeoutError, aiohttp.ClientError, OSError) as err:
                raise JBLBarConnectionError(f"{url}: {err or type(err).__name__}") from err
        if response.status != 200:
            raise JBLBarCommandError(f"{url}: HTTP {response.status}")
        return text
