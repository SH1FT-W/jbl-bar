"""Fixtures: eigene Integrationen erlauben, Fake-Bar ins aiohttp-Mock hängen, Eintrag anlegen."""

from __future__ import annotations

import copy

from aiohttp import ClientSession
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

import common
from common import HOST, FakeBar
from custom_components.jbl_bar.const import DOMAIN

EQ_ORIGINAL = copy.deepcopy(common.EQ_LIST)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    common.EQ_LIST[:] = copy.deepcopy(EQ_ORIGINAL)


@pytest.fixture
def bar(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, monkeypatch: pytest.MonkeyPatch) -> FakeBar:
    fake = FakeBar()
    fake.install(aioclient_mock)
    # The own UPnP session (force_close) goes through the mock as well; kept to check that it gets closed

    def create_upnp_session() -> ClientSession:
        session = aioclient_mock.create_session(hass.loop)
        fake.upnp_sessions.append(session)
        return session

    monkeypatch.setattr("custom_components.jbl_bar.create_upnp_session", create_upnp_session)
    return fake


@pytest.fixture
async def setup(hass: HomeAssistant, bar: FakeBar) -> MockConfigEntry:
    hass.config.language = "de"
    entry = MockConfigEntry(domain=DOMAIN, unique_id="02:00:00:00:00:01", data={CONF_HOST: HOST}, title="JBL BAR 1000")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
