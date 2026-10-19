"""Einrichtung per IP, per Zeroconf und neue IP-Adresse."""

from __future__ import annotations

from ipaddress import ip_address

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from common import HOST, MAC, FakeBar

DOMAIN = "jbl_bar"


def zeroconf(host: str = HOST, mac: str | None = MAC) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        hostname="jbl.local.",
        name="JBL BAR 1000._jbl-product._tcp.local.",
        port=59152,
        type="_jbl-product._tcp.local.",
        properties={"MAC": mac} if mac else {},
    )


async def test_user(hass: HomeAssistant, bar: FakeBar) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: f" {HOST} "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "JBL BAR 1000"
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == "02:00:00:00:00:01"
    await hass.async_block_till_done()

    # Zweites Mal → schon eingerichtet
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_errors(hass: HomeAssistant, bar: FakeBar) -> None:
    bar.reachable = False
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["errors"] == {"base": "cannot_connect"}

    bar.reachable = True
    bar.unknown.add("getDeviceInfo")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["errors"] == {"base": "not_jbl"}


async def test_zeroconf(hass: HomeAssistant, bar: FakeBar) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zeroconf()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"name": "JBL BAR 1000", "host": HOST}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_zeroconf_updates_host_and_aborts(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zeroconf(host="192.0.2.77")
    )
    assert result["reason"] == "already_configured"
    assert setup.data[CONF_HOST] == "192.0.2.77"


async def test_zeroconf_without_mac_or_offline(hass: HomeAssistant, bar: FakeBar) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zeroconf(mac=None)
    )
    assert result["reason"] == "not_jbl"
    bar.reachable = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zeroconf()
    )
    assert result["reason"] == "cannot_connect"


async def test_reconfigure(hass: HomeAssistant, bar: FakeBar, setup) -> None:
    result = await setup.start_reconfigure_flow(hass)
    bar.reachable = False
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["errors"] == {"base": "cannot_connect"}
    bar.reachable = True
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["reason"] == "reconfigure_successful"
