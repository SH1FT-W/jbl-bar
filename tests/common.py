"""Fake-Bar für die Tests: antwortet wie eine echte JBL Bar 1000 (Antworten von der echten Bar mitgeschnitten)."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import unquote_plus

from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse

HOST = "192.0.2.76"
MAC = "02:00:00:00:00:01"

DEVICE_INFO = {
    "firmware": "25.52.31.80.00",
    "one_os_ver": "3.0",
    "wlan0_mac": MAC,
    "uuid": "ed464bd4-98e1-3814-8319-e117dd1ba46d",
    "name": "JBL BAR 1000",
    "serial_number": "TL0000-XX0000000",
}

EQ_LIST = [
    {
        "band": 7,
        "eq_id": "1",
        "eq_name": "JBL SIGNATURE",
        "eq_payload": {"fs": [125, 250, 500, 1000, 2000, 4000, 8000], "gain": [0, 0, 0, 0, 0, 0, 0]},
    },
    {
        "band": 7,
        "eq_id": "2",
        "eq_name": "VOCAL",
        "eq_payload": {"fs": [80, 250, 500, 1000, 9000, 4000, 9000], "gain": [-5, 0, 0, 4, -2, 4, 0]},
    },
    {
        "band": 7,
        "eq_id": "0",
        "eq_name": "CUSTOMIZE",
        "eq_payload": {"fs": [125, 250, 500, 1000, 2000, 4000, 8000], "gain": [1, 1, 1, 1, 1, 1, 1]},
    },
]

INFO_EX = """<?xml version="1.0" encoding="UTF-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>
<u:GetInfoExResponse xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
<CurrentTransportState>{state}</CurrentTransportState><PlayMedium>SONGLIST-NETWORK</PlayMedium>
<TrackDuration>0:03:30</TrackDuration><RelTime>0:01:00</RelTime>
<TrackMetaData>{meta}</TrackMetaData></u:GetInfoExResponse></s:Body></s:Envelope>"""

DIDL = (
    '&lt;DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"&gt;&lt;item&gt;&lt;dc:title&gt;Song&lt;/dc:title&gt;'
    "&lt;upnp:artist&gt;Testband&lt;/upnp:artist&gt;&lt;upnp:album&gt;Testalbum&lt;/upnp:album&gt;"
    "&lt;upnp:albumArtURI&gt;http://cover/x.jpg&lt;/upnp:albumArtURI&gt;&lt;/item&gt;&lt;/DIDL-Lite&gt;"
)


class FakeBar:
    """Zustand + Antworten; `calls` sammelt (Befehl, Payload) bzw. ("soap", Aktion, Body)."""

    def __init__(self) -> None:
        self.reachable = True
        self.unknown: set[str] = {"getRearSpeakerVolume"}
        self.rears: list[dict[str, Any]] = [
            {"capicity": 93, "channel": "left", "charging": False, "docked": True, "status": "online"},
            {"capicity": 96, "channel": "right", "charging": True, "docked": False, "status": "offline"},
        ]
        self.calls: list[tuple[str, Any]] = []
        self.state: dict[str, Any] = {
            "power": "0",  # 0 = an
            "vol": 48,
            "mute": "0",
            "status": "stop",
            "source": "TV",
            "selected": "TV",
            "is_streaming": "true",
            "is_atmos": "false",
            "eq_active": "1",
            "night": "off",
            "smart": "on",
            "voice": "0",
            "tone": "on",
            "sync": "0",
            "atmos_level": "3",
            "sleep": "0",
            "transport": "STOPPED",
        }

    def install(self, mock: AiohttpClientMocker, host: str = HOST) -> None:
        mock.post(f"https://{host}/httpapi.asp", side_effect=self._httpapi)
        mock.post(re.compile(rf"http://{re.escape(host)}:59152/upnp/control/.*"), side_effect=self._soap)
        mock.request("subscribe", f"http://{host}:49152/upnp/event/rendercontrol1", side_effect=self._subscribe)
        mock.request("unsubscribe", f"http://{host}:49152/upnp/event/rendercontrol1", text="")

    def commands(self, name: str) -> list[Any]:
        return [payload for command, payload in self.calls if command == name]

    async def _subscribe(self, method: str, url: Any, data: Any) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(method, url, headers={"SID": "uuid:abc", "TIMEOUT": "Second-300"})

    async def _soap(self, method: str, url: Any, data: Any) -> AiohttpClientMockResponse:
        if not self.reachable:
            from aiohttp import ClientConnectionError

            return AiohttpClientMockResponse(method, url, exc=ClientConnectionError("offline"))
        action = re.search(r"<u:(\w+) ", data).group(1)
        self.calls.append(("soap", action))
        if action == "SetVolume":
            self.state["vol"] = int(re.search(r"<DesiredVolume>(\d+)<", data).group(1))
        if action == "SetMute":
            self.state["mute"] = re.search(r"<DesiredMute>(\d)<", data).group(1)
        meta = DIDL if self.state["transport"] == "PLAYING" else ""
        return AiohttpClientMockResponse(method, url, text=INFO_EX.format(state=self.state["transport"], meta=meta))

    async def _httpapi(self, method: str, url: Any, data: Any) -> AiohttpClientMockResponse:
        if not self.reachable:
            from aiohttp import ClientConnectionError

            return AiohttpClientMockResponse(method, url, exc=ClientConnectionError("offline"))
        fields = dict(part.split("=", 1) for part in data.split("&", 1))
        name = fields["command"]
        payload = json.loads(unquote_plus(fields["payload"])) if "payload" in fields else None
        self.calls.append((name, payload))
        if name in self.unknown:
            return AiohttpClientMockResponse(method, url, text="unknown command")
        return AiohttpClientMockResponse(method, url, json=self._answer(name, payload))

    def _answer(self, name: str, payload: Any) -> dict[str, Any]:
        s = self.state
        ok: dict[str, Any] = {"error_code": "0"}
        if name.startswith("set") or name == "sendAppController":
            self._apply(name, payload or {})
            return ok
        answers: dict[str, dict[str, Any]] = {
            "getDeviceInfo": {"device_info": DEVICE_INFO},
            "getPowerState": {"power_state": s["power"]},
            "getPlayerStatus": {"status": s["status"], "vol": str(s["vol"]), "mute": s["mute"]},
            "getStreamingStatus": {
                "status": {"source": s["source"], "is_streaming": s["is_streaming"], "is_atmos": s["is_atmos"]}
            },
            "getMediaSourceStatus": {"media_source": s["selected"], "media_status": "stopped"},
            "getEQList": {"active_eq_id": s["eq_active"], "eq_list": EQ_LIST},
            "getPersonalListeningMode": {"status": s["night"]},
            "getSmartMode": {"status": s["smart"]},
            "getPureVoiceState": {"purevoice_state": s["voice"]},
            "getFeedbackToneConfig": {"status": s["tone"]},
            "getAudioSync": {"audio_sync": s["sync"]},
            "getAtmosLevel": {"atmos_level": s["atmos_level"], "status": "on"},
            "getRearSpeakerStatus": {"rears": self.rears},
            "getSleepTimer": {"sleep_timer": s["sleep"], "remain_time": s["sleep"]},
        }
        return ok | answers.get(name, {})

    def _apply(self, name: str, payload: dict[str, Any]) -> None:
        s = self.state
        match name:
            case "setPowerState":
                s["power"] = payload["power_state"]
            case "setPersonalListeningMode":
                s["night"] = payload["status"]
            case "setSmartMode":
                s["smart"] = payload["status"]
            case "setPureVoiceState":
                s["voice"] = payload["purevoice_state"]
            case "setFeedbackToneConfig":
                s["tone"] = payload["status"]
            case "setAudioSync":
                s["sync"] = payload["audio_sync"]
            case "setSleepTimer":
                s["sleep"] = str(payload["sleep_timer"])
            case "setMediaSource":
                s["source"] = s["selected"] = payload["media_source"]
            case "setActiveEQ":
                s["eq_active"] = payload["active_eq_id"]
                if payload["active_eq_id"] == "0":
                    EQ_LIST[2]["eq_payload"] = payload["eq_payload"]
