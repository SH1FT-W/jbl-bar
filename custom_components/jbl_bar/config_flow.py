"""Einrichtung: automatisch gefunden (Zeroconf `_jbl-product._tcp`) oder per IP-Adresse."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from .api import JBLBarClient, JBLBarConnectionError, JBLBarError, create_ssl_context
from .const import DOMAIN


class JBLBarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Eine Bar = ein Eintrag, erkannt an der WLAN-MAC."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._name: str | None = None

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
        mac = discovery_info.properties.get("MAC") or discovery_info.properties.get("mac")
        host = discovery_info.host
        if not mac:
            return self.async_abort(reason="not_jbl")
        await self.async_set_unique_id(format_mac(mac))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        try:
            device = await self._probe(host)
        except JBLBarError:
            return self.async_abort(reason="cannot_connect")
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
