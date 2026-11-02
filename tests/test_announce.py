"""Playing URLs and announcements: AVTransport calls, and source, volume, mute and standby come back afterwards."""

from __future__ import annotations

import asyncio
import html
import re
from unittest.mock import patch

from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.components.media_source import PlayMedia
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from common import FakeBar
from custom_components.jbl_bar import coordinator as coordinator_module
from custom_components.jbl_bar.const import CONF_ANNOUNCE_VOLUME

PLAYER = "media_player.jbl_bar_1000"
URL = "http://192.0.2.10:8123/local/chime.mp3?a=1&b=2"


@pytest.fixture(autouse=True)
def fast_announcements(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(coordinator_module, "ANNOUNCE_POLL", 0)


async def play(hass: HomeAssistant, media_id: str = URL, media_type: str = "music", **data) -> None:
    await hass.services.async_call(
        "media_player",
        "play_media",
        {"entity_id": PLAYER, "media_content_id": media_id, "media_content_type": media_type, **data},
        blocking=True,
    )


def soap_since(bar: FakeBar, start: int) -> list[str]:
    return [entry[1] for entry in bar.calls[start:] if entry[0] == "soap" and entry[1] != "GetInfoEx"]


def sent_uri(bar: FakeBar) -> str:
    return html.unescape(re.search(r"<CurrentURI>(.*)</CurrentURI>", bar.soap_bodies["SetAVTransportURI"]).group(1))


def sent_didl(bar: FakeBar) -> str:
    body = bar.soap_bodies["SetAVTransportURI"]
    return html.unescape(re.search(r"<CurrentURIMetaData>(.*)</CurrentURIMetaData>", body).group(1))


async def settle(hass: HomeAssistant) -> None:
    """Wait for the announcement's background task (the event subscription task never ends, so no
    wait_background_tasks)."""
    coordinator = hass.config_entries.async_entries("jbl_bar")[0].runtime_data
    async with asyncio.timeout(5):
        while coordinator._playback_lock.locked():  # noqa: ASYNC110 - polls state owned by the code under test
            await asyncio.sleep(0.001)
    await hass.async_block_till_done()


async def finish(hass: HomeAssistant, bar: FakeBar, wait: bool = True) -> None:
    """The bar has played the announcement: transport stops, the restore runs.

    Only after the wait loop has seen the bar playing (in reality the announcement takes seconds)."""
    polls = bar.calls.count(("soap", "GetInfoEx"))
    async with asyncio.timeout(5):
        while bar.calls.count(("soap", "GetInfoEx")) == polls:  # noqa: ASYNC110 - polls the fake bar
            await asyncio.sleep(0.001)
    bar.state["transport"] = "STOPPED"
    if wait:
        await settle(hass)


async def test_play_url(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    start = len(bar.calls)
    await play(hass, extra={"title": "Chime <1>"})
    assert soap_since(bar, start) == ["SetAVTransportURI", "Play"]
    # URL and metadata are XML-escaped; the metadata carries title and MIME type (guessed from the file name)
    assert sent_uri(bar) == URL
    didl = sent_didl(bar)
    assert "<dc:title>Chime &lt;1&gt;</dc:title>" in didl
    assert 'protocolInfo="http-get:*:audio/mpeg:*"' in didl
    assert f"<res {didl.split('<res ', 1)[1].split('>', 1)[0]}>{URL.replace('&', '&amp;')}</res>" in didl
    assert "<Speed>1</Speed>" in bar.soap_bodies["Play"]
    # Without announce nothing is put back
    await settle(hass)
    assert bar.commands("setMediaSource") == []
    assert hass.states.get(PLAYER).state == "playing"


@pytest.mark.parametrize(
    ("media_id", "media_type", "mime"),
    [
        ("http://192.0.2.10/x.wav", "music", "audio/x-wav"),
        ("http://192.0.2.10/stream", "music", "audio/mpeg"),
        ("http://192.0.2.10/stream", "audio/flac", "audio/flac"),
    ],
)
async def test_mime_type(
    hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry, media_id: str, media_type: str, mime: str
) -> None:
    await play(hass, media_id, media_type)
    assert f'protocolInfo="http-get:*:{mime}:*"' in sent_didl(bar)
    assert "<dc:title>Home Assistant</dc:title>" in sent_didl(bar)


async def test_announce_restores_source_volume_and_mute(
    hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry
) -> None:
    hass.config_entries.async_update_entry(setup, options={CONF_ANNOUNCE_VOLUME: 30})
    bar.state.update(mute="1", transport="STOPPED")
    await setup.runtime_data.async_refresh()
    start = len(bar.calls)

    await play(hass, announce=True)
    assert soap_since(bar, start) == ["SetMute", "SetVolume", "SetAVTransportURI", "Play"]
    assert "<DesiredMute>0</DesiredMute>" in bar.soap_bodies["SetMute"]
    assert "<DesiredVolume>30</DesiredVolume>" in bar.soap_bodies["SetVolume"]
    assert bar.commands("setMediaSource") == []
    assert setup.runtime_data._playback_lock.locked()

    start = len(bar.calls)
    await finish(hass, bar)
    assert bar.commands("setMediaSource") == [{"media_source": "TV"}]
    assert soap_since(bar, start) == ["SetVolume", "SetMute"]
    assert "<DesiredVolume>48</DesiredVolume>" in bar.soap_bodies["SetVolume"]
    assert "<DesiredMute>1</DesiredMute>" in bar.soap_bodies["SetMute"]
    assert bar.commands("setPowerState") == []
    assert not setup.runtime_data._playback_lock.locked()
    state = hass.states.get(PLAYER)
    assert state.attributes["source"] == "TV"
    assert state.attributes["volume_level"] == 0.48
    assert state.attributes["is_volume_muted"] is True


async def test_announce_keeps_volume_without_option(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    bar.state["transport"] = "STOPPED"
    start = len(bar.calls)
    await play(hass, announce=True)
    await finish(hass, bar)
    # Option 0 (default) and an option equal to the current volume both leave the volume alone
    hass.config_entries.async_update_entry(setup, options={CONF_ANNOUNCE_VOLUME: 48})
    await play(hass, announce=True)
    await finish(hass, bar)
    assert "SetVolume" not in soap_since(bar, start)
    assert "SetMute" not in soap_since(bar, start)
    assert bar.commands("setMediaSource") == [{"media_source": "TV"}] * 2


async def test_announce_from_standby(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    bar.state.update(power="1", transport="STOPPED", selected="HDMI", source="HDMI")
    await setup.runtime_data.async_refresh()
    # In standby the source is not polled; it is read fresh when the announcement starts
    await play(hass, announce=True)
    assert bar.commands("setPowerState") == [{"power_state": "0"}]
    await finish(hass, bar)
    assert bar.commands("setMediaSource") == [{"media_source": "HDMI"}]
    assert bar.commands("setPowerState") == [{"power_state": "0"}, {"power_state": "1"}]
    assert hass.states.get(PLAYER).state == "off"


async def test_announce_from_other_source(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    """Network playback cannot be selected again with setMediaSource: no source is sent back."""
    bar.state.update(selected="WIFI", source="WIFI", transport="STOPPED")
    await setup.runtime_data.async_refresh()
    await play(hass, announce=True)
    await finish(hass, bar)
    assert bar.commands("setMediaSource") == []


async def test_announce_media_source(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    """TTS and other media source items are resolved, relative URLs become signed absolute URLs of HA."""
    await hass.config.async_update(internal_url="http://192.0.2.10:8123")
    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=PlayMedia(url="/media/local/abc.wav", mime_type="audio/mpeg"),
    ) as resolve:
        await play(hass, "media-source://tts/demo?message=Hallo", "music", announce=True)
    assert resolve.call_args.args[1:] == ("media-source://tts/demo?message=Hallo", PLAYER)
    uri = sent_uri(bar)
    assert uri.startswith("http://192.0.2.10:8123/media/local/abc.wav?authSig=")
    # The MIME type of the media source wins over the file name
    assert 'protocolInfo="http-get:*:audio/mpeg:*"' in sent_didl(bar)
    await finish(hass, bar)


async def test_announce_fails(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    """The bar refuses the URL: the error reaches the caller, standby comes back, the next call is not blocked."""
    bar.state["power"] = "1"
    await setup.runtime_data.async_refresh()
    bar.failing_soap.add("SetAVTransportURI")
    with pytest.raises(HomeAssistantError, match="HTTP 500"):
        await play(hass, announce=True)
    assert bar.commands("setPowerState") == [{"power_state": "0"}, {"power_state": "1"}]
    assert not setup.runtime_data._playback_lock.locked()

    bar.failing_soap.clear()
    await play(hass)
    assert bar.soap_bodies["Play"]


async def test_announce_never_starts(
    hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bar never reports PLAYING (and GetInfoEx fails meanwhile): restore after the start timeout."""
    monkeypatch.setattr(coordinator_module, "ANNOUNCE_START_TIMEOUT", 0)
    bar.state["transport"] = "STOPPED"
    await setup.runtime_data.async_refresh()
    bar.failing_soap.add("Play")
    bar.failing_soap.add("GetInfoEx")
    with pytest.raises(HomeAssistantError):
        await play(hass, announce=True)
    bar.failing_soap.discard("Play")
    await play(hass, announce=True)
    await settle(hass)
    # Two restores: the failed call and the timeout
    assert bar.commands("setMediaSource") == [{"media_source": "TV"}] * 2
    assert not setup.runtime_data._playback_lock.locked()


async def test_announce_max_duration(
    hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An endless stream as announcement: the restore comes after ANNOUNCE_MAX anyway."""
    monkeypatch.setattr(coordinator_module, "ANNOUNCE_MAX", 0)
    await play(hass, announce=True)
    await settle(hass)
    assert bar.state["transport"] == "PLAYING"
    assert bar.commands("setMediaSource") == [{"media_source": "TV"}]


async def test_restore_continues_after_failed_step(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    hass.config_entries.async_update_entry(setup, options={CONF_ANNOUNCE_VOLUME: 30})
    bar.state.update(mute="1", transport="STOPPED")
    await setup.runtime_data.async_refresh()
    await play(hass, announce=True)
    bar.failing_soap.add("SetVolume")
    with patch.object(coordinator_module._LOGGER, "warning") as warning:
        await finish(hass, bar)
    assert warning.call_args.args[1:3] == ("volume", "192.0.2.76")
    assert "<DesiredMute>1</DesiredMute>" in bar.soap_bodies["SetMute"]


async def test_second_announcement_waits(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    """A second announcement starts only after the first one is restored, and remembers the restored state."""
    bar.state["transport"] = "STOPPED"
    await play(hass, announce=True)
    # Not tracked by hass: async_block_till_done would wait for it while it waits for the first announcement
    second = asyncio.create_task(play(hass, "http://192.0.2.10/two.mp3", announce=True))
    await asyncio.sleep(0.01)
    assert sent_uri(bar) == URL
    # The lock passes straight on to the second announcement, so wait for that one instead of the lock
    await finish(hass, bar, wait=False)
    async with asyncio.timeout(5):
        await second
    assert sent_uri(bar) == "http://192.0.2.10/two.mp3"
    # The first restore ran before the second announcement started
    first_restore = bar.calls.index(("setMediaSource", {"media_source": "TV"}))
    assert first_restore < max(i for i, call in enumerate(bar.calls) if call == ("soap", "SetAVTransportURI"))
    await finish(hass, bar)
    assert bar.commands("setMediaSource") == [{"media_source": "TV"}] * 2


async def test_browse_media_audio_only(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    root = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="",
        title="Media",
        can_play=False,
        can_expand=True,
    )
    with patch("homeassistant.components.media_source.async_browse_media", return_value=root) as browse:
        player = hass.data["entity_components"]["media_player"].get_entity(PLAYER)
        assert await player.async_browse_media("music", "media-source://media_source") is root
    assert browse.call_args.args[1] == "media-source://media_source"
    content_filter = browse.call_args.kwargs["content_filter"]
    audio = BrowseMedia(
        media_class=MediaClass.MUSIC,
        media_content_id="a",
        media_content_type="audio/mpeg",
        title="a",
        can_play=True,
        can_expand=False,
    )
    video = BrowseMedia(
        media_class=MediaClass.VIDEO,
        media_content_id="v",
        media_content_type="video/mp4",
        title="v",
        can_play=True,
        can_expand=False,
    )
    assert content_filter(audio)
    assert not content_filter(video)


async def test_options_flow(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    coordinator = setup.runtime_data
    result = await hass.config_entries.options.async_init(setup.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_ANNOUNCE_VOLUME: 25.0})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup.options == {CONF_ANNOUNCE_VOLUME: 25}
    # The option is read at every announcement: the entry is not reloaded
    assert hass.config_entries.async_get_entry(setup.entry_id).runtime_data is coordinator


async def test_announce_after_restart_in_standby(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    """After a restart in standby volume and mute were never polled: they are read when the bar wakes up."""
    coordinator = setup.runtime_data
    coordinator.data.power = False
    coordinator.data.volume = coordinator.data.muted = None
    hass.config_entries.async_update_entry(setup, options={CONF_ANNOUNCE_VOLUME: 30})
    bar.state.update(power="1", mute="1", transport="STOPPED")
    start = len(bar.calls)
    await play(hass, announce=True)
    assert soap_since(bar, start) == ["SetMute", "SetVolume", "SetAVTransportURI", "Play"]
    assert "<DesiredVolume>30</DesiredVolume>" in bar.soap_bodies["SetVolume"]
    await finish(hass, bar)
    assert "<DesiredVolume>48</DesiredVolume>" in bar.soap_bodies["SetVolume"]
    assert "<DesiredMute>1</DesiredMute>" in bar.soap_bodies["SetMute"]
    assert bar.commands("setPowerState")[-1] == {"power_state": "1"}


async def test_two_announcements_with_poll_in_between(
    hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry
) -> None:
    """A poll during the first announcement sees it playing; the second one still starts from the restored state."""
    hass.config_entries.async_update_entry(setup, options={CONF_ANNOUNCE_VOLUME: 30})
    bar.state.update(power="1", transport="STOPPED")
    await setup.runtime_data.async_refresh()
    for _ in range(2):
        await play(hass, announce=True)
        # The regular poll during the announcement: bar on, network source, announcement volume
        await setup.runtime_data.async_refresh()
        assert setup.runtime_data.data.source == "WIFI"
        await finish(hass, bar)
    assert bar.commands("setPowerState") == [{"power_state": "0"}, {"power_state": "1"}] * 2
    assert bar.commands("setMediaSource") == [{"media_source": "TV"}] * 2
    assert bar.state["vol"] == 48
    assert hass.states.get(PLAYER).state == "off"


async def test_announce_volume_read_fails(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    """getPlayerStatus fails at the start: the polled volume counts."""
    hass.config_entries.async_update_entry(setup, options={CONF_ANNOUNCE_VOLUME: 30})
    bar.state["transport"] = "STOPPED"
    bar.unknown.add("getPlayerStatus")
    await play(hass, announce=True)
    bar.unknown.discard("getPlayerStatus")
    await finish(hass, bar)
    assert "<DesiredVolume>48</DesiredVolume>" in bar.soap_bodies["SetVolume"]


async def test_announce_unknown_volume_kept(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    """Volume unknown and not readable: the announcement volume is not set, it could not be put back."""
    setup.runtime_data.data.volume = None
    hass.config_entries.async_update_entry(setup, options={CONF_ANNOUNCE_VOLUME: 80})
    bar.state["transport"] = "STOPPED"
    bar.unknown.add("getPlayerStatus")
    start = len(bar.calls)
    await play(hass, announce=True)
    bar.unknown.discard("getPlayerStatus")
    await finish(hass, bar)
    assert "SetVolume" not in soap_since(bar, start)


async def test_announce_state_read_fails(hass: HomeAssistant, bar: FakeBar, setup: MockConfigEntry) -> None:
    """Power and source not readable at the start: the polled state counts."""
    bar.state["transport"] = "STOPPED"
    bar.unknown.update({"getPowerState", "getMediaSourceStatus"})
    await play(hass, announce=True)
    bar.unknown.difference_update({"getPowerState", "getMediaSourceStatus"})
    await finish(hass, bar)
    assert bar.commands("setMediaSource") == [{"media_source": "TV"}]
    assert bar.commands("setPowerState") == []
