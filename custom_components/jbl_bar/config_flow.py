"""Einrichtung: automatisch gefunden (Zeroconf `_jbl-product._tcp`) oder per IP-Adresse."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from .api import JBLBarClient, JBLBarConnectionError, JBLBarError, create_ssl_context
from .const import CONF_ANNOUNCE_VOLUME, CONF_CALLBACK_URL, DOMAIN

CALLBACK_URL_EXAMPLE = "http://192.0.2.20:8080"


def _valid_callback_url(value: str) -> bool:
    """A base URL the bar can call: http or https with a host (and maybe a port), no query or fragment."""
    if any(char.isspace() for char in value):
        return False
    try:
        parts = urlsplit(value)
        _ = parts.port  # raises ValueError for a port that is not a number
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname) and not parts.query and not parts.fragment


class JBLBarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Eine Bar = ein Eintrag, erkannt an der WLAN-MAC."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._name: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return JBLBarOptionsFlow()

    async def _probe(self, host: str) -> dict[str, Any]:
        client = JBLBarClient(
            host,
            async_get_clientsession(self.hass, verify_ssl=False),
            await self.hass.async_add_executor_job(create_ssl_context),
        )
        device: dict[str, Any] = (await client.command("getDeviceInfo")).get("device_info", {})
        return device

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                device = await self._probe(host)
            except JBLBarConnectionError:
                errors["base"] = "cannot_connect"
            except JBLBarError:
                errors["base"] = "not_jbl"
            else:
                if not device.get("wlan0_mac"):
                    errors["base"] = "not_jbl"
                else:
                    await self.async_set_unique_id(format_mac(device["wlan0_mac"]))
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                    return self.async_create_entry(title=device.get("name") or "JBL Bar", data={CONF_HOST: host})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=self._host or ""): str}),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        # Not every bar puts its MAC into the TXT record (BAR 800, issue #2); then it comes from getDeviceInfo.
        mac = discovery_info.properties.get("MAC") or discovery_info.properties.get("mac")
        host = discovery_info.host
        if mac:
            await self.async_set_unique_id(format_mac(mac))
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        try:
            device = await self._probe(host)
        except JBLBarConnectionError:
            return self.async_abort(reason="cannot_connect")
        except JBLBarError:
            return self.async_abort(reason="not_jbl")
        if not mac:
            if not device.get("wlan0_mac"):
                return self.async_abort(reason="not_jbl")
            await self.async_set_unique_id(format_mac(device["wlan0_mac"]))
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._host = host
        self._name = device.get("name") or discovery_info.name.split(".")[0]
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._host is not None
        if user_input is not None:
            return self.async_create_entry(title=self._name or "JBL Bar", data={CONF_HOST: self._host})
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm", description_placeholders={"name": self._name or "JBL Bar", "host": self._host}
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Neue IP-Adresse eintragen (z. B. nach Router-Wechsel)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                device = await self._probe(host)
            except JBLBarConnectionError:
                errors["base"] = "cannot_connect"
            except JBLBarError:
                errors["base"] = "not_jbl"
            else:
                await self.async_set_unique_id(format_mac(device.get("wlan0_mac", "")))
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates={CONF_HOST: host})
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}),
            errors=errors,
        )


class JBLBarOptionsFlow(OptionsFlow):
    """Options: volume for announcements (0 = keep the current volume, read at every announcement, no reload) and the
    callback URL for the audio format events (the subscription carries it: a changed URL reloads the entry)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            callback_url = str(user_input.get(CONF_CALLBACK_URL, "")).strip().rstrip("/")
            if callback_url and not _valid_callback_url(callback_url):
                errors[CONF_CALLBACK_URL] = "invalid_url"
            else:
                options: dict[str, Any] = {CONF_ANNOUNCE_VOLUME: int(user_input[CONF_ANNOUNCE_VOLUME])}
                if callback_url:
                    options[CONF_CALLBACK_URL] = callback_url
                return self.async_create_entry(data=options)
        values: Mapping[str, Any] = user_input if user_input is not None else self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(CONF_ANNOUNCE_VOLUME, default=values.get(CONF_ANNOUNCE_VOLUME, 0)): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=100, step=1, unit_of_measurement="%", mode=NumberSelectorMode.SLIDER
                    )
                ),
                vol.Optional(
                    CONF_CALLBACK_URL, description={"suggested_value": values.get(CONF_CALLBACK_URL, "")}
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={"example": CALLBACK_URL_EXAMPLE},
        )
