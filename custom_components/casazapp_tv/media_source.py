"""CasaZapp TV in Home Assistant's media browser: favourites, own lists, recent channels and
recordings, played on any speaker or player Home Assistant knows.

A speaker fetches the stream itself and can't send the API key, so every play asks the server for
a link of its own (POST /api/cast with the speaker as target): it needs no key, ends by itself
when nothing asks for it, and counts for the provider's connections like anyone watching.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api import CasaZappError
from .const import DOMAIN
from .coordinator import CasaZappConfigEntry

# Players filter the browser on these: a speaker shows only what it plays (a DLNA receiver often only
# audio/mpeg), a Chromecast audio/ and video/. A channel is marked as mp3 so it shows on every
# speaker: a speaker gets only its sound as mp3, a Chromecast the HLS stream with the picture.
CHANNEL_TYPE = "audio/mpeg"
# Players that play HLS with the picture: a Chromecast or Google TV with a screen. A Cast speaker
# (Nest, a speaker group) is a "speaker" and, like every other player, gets the sound as mp3.
HLS_PLATFORMS = {"cast"}
RECORDING_TYPE = "video/x-mpegurl"

FOLDERS = {
    "favorites": "Favourites",
    "lists": "My lists",
    "recent": "Recent channels",
    "playlists": "Playlists",
    "recordings": "Recordings",
}


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    return CasaZappMediaSource(hass)


def _channel(entry_id: str, channel: dict[str, Any]) -> BrowseMediaSource:
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"{entry_id}/live/{channel['id']}",
        media_class=MediaClass.CHANNEL,
        media_content_type=CHANNEL_TYPE,
        title=channel["name"],
        can_play=True,
        can_expand=False,
    )


def _folder(entry_id: str, key: str, title: str, children: list | None = None) -> BrowseMediaSource:
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"{entry_id}/{key}",
        media_class=MediaClass.DIRECTORY,
        media_content_type=MediaType.CHANNELS if key != "recordings" else MediaType.VIDEO,
        children_media_class=MediaClass.CHANNEL if key != "recordings" else MediaClass.VIDEO,
        title=title,
        can_play=False,
        can_expand=True,
        children=children,
    )


def _recording_title(r: dict[str, Any]) -> str:
    """"Pauw & De Wit (NPO 1, 2026-10-07)"; without a programme the channel only once."""
    channel = r.get("channelName") or ""
    day = str(r.get("startAt", ""))[:10]
    if not channel or r["title"] == channel:
        return f"{r['title']} ({day})"
    return f"{r['title']} ({channel}, {day})"


class CasaZappMediaSource(MediaSource):
    """One root; with more than one server, a folder per server."""

    name = "CasaZapp TV"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    def _entries(self) -> list[CasaZappConfigEntry]:
        return [
            e
            for e in self.hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
        ]

    def _entry(self, entry_id: str) -> CasaZappConfigEntry:
        for entry in self._entries():
            if entry.entry_id == entry_id:
                return entry
        raise BrowseError("This CasaZapp TV server isn't loaded")

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """A link of its own for the speaker it plays on."""
        try:
            entry_id, kind, item_id = (item.identifier or "").split("/")
            entry = self._entry(entry_id)
        except (ValueError, BrowseError) as err:
            raise Unresolvable(f"Can't play {item.identifier}") from err
        target = "Home Assistant"
        mp3 = True
        if item.target_media_player:
            state = self.hass.states.get(item.target_media_player)
            if state:
                target = state.name
            registered = er.async_get(self.hass).async_get(item.target_media_player)
            screen = not state or state.attributes.get("device_class") != "speaker"
            mp3 = not (registered and registered.platform in HLS_PLATFORMS and screen)
        try:
            link = await entry.runtime_data.client.cast(kind, int(item_id), target, mp3=mp3)
        except CasaZappError as err:
            raise Unresolvable(f"CasaZapp TV: {err}") from err
        return PlayMedia(link["url"], link.get("contentType") or "application/x-mpegURL")

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        parts = [p for p in (item.identifier or "").split("/") if p]
        entries = self._entries()
        if not parts:
            if len(entries) == 1:
                return await self._server(entries[0], title=self.name)
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=None,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.CHANNELS,
                title=self.name,
                can_play=False,
                can_expand=True,
                children=[
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=e.entry_id,
                        media_class=MediaClass.DIRECTORY,
                        media_content_type=MediaType.CHANNELS,
                        title=e.title,
                        can_play=False,
                        can_expand=True,
                    )
                    for e in entries
                ],
            )
        entry = self._entry(parts[0])
        if len(parts) == 1:
            return await self._server(entry, title=entry.title)
        try:
            return await self._folder_contents(entry, parts[1:])
        except CasaZappError as err:
            raise BrowseError(f"CasaZapp TV: {err}") from err

    async def _server(self, entry: CasaZappConfigEntry, title: str) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=entry.entry_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.CHANNELS,
            title=title,
            can_play=False,
            can_expand=True,
            children=[_folder(entry.entry_id, key, name) for key, name in FOLDERS.items()],
        )

    async def _folder_contents(self, entry: CasaZappConfigEntry, path: list[str]) -> BrowseMediaSource:
        coordinator = entry.runtime_data
        client = coordinator.client
        entry_id = entry.entry_id
        playlists = coordinator.data.get("playlists", [])
        # Favourites and own lists span every playlist; any playlist's id will do in the address.
        any_playlist = playlists[0]["id"] if playlists else 1
        key = path[0]

        if key == "favorites":
            channels = await client.channels(any_playlist, favorites=True)
            return _folder(entry_id, key, FOLDERS[key], [_channel(entry_id, c) for c in channels])

        if key == "lists" and len(path) == 1:
            lists = await client.lists()
            return _folder(
                entry_id,
                key,
                FOLDERS[key],
                [_folder(entry_id, f"list/{lst['id']}", lst["name"]) for lst in lists],
            )

        if key == "list" and len(path) == 2:
            list_id = int(path[1])
            name = next((lst["name"] for lst in await client.lists() if lst["id"] == list_id), "")
            channels = await client.channels(any_playlist, list_id=list_id)
            return _folder(entry_id, f"list/{list_id}", name, [_channel(entry_id, c) for c in channels])

        if key == "playlists" and len(path) == 1:
            return _folder(
                entry_id,
                key,
                FOLDERS[key],
                [_folder(entry_id, f"playlist/{p['id']}", p["name"]) for p in playlists],
            )

        # A playlist as the apps show it: its categories that are on, then their channels.
        if key == "playlist" and len(path) == 2:
            playlist_id = int(path[1])
            name = next((p["name"] for p in playlists if p["id"] == playlist_id), "")
            categories = await client.categories(playlist_id)
            return _folder(
                entry_id,
                f"playlist/{playlist_id}",
                name,
                [
                    _folder(entry_id, f"playlist/{playlist_id}/{c['id']}", c["name"] or "Other")
                    for c in categories
                ],
            )

        if key == "playlist" and len(path) == 3:
            playlist_id, category_id = int(path[1]), int(path[2])
            category = next(
                (c for c in await client.categories(playlist_id) if c["id"] == category_id), None
            )
            channels = await client.channels(playlist_id, category_id=category_id)
            return _folder(
                entry_id,
                f"playlist/{playlist_id}/{category_id}",
                (category or {}).get("name") or "Other",
                [_channel(entry_id, c) for c in channels],
            )

        if key == "recent":
            channels = coordinator.data.get("recent", {}).get("channels", [])
            return _folder(entry_id, key, FOLDERS[key], [_channel(entry_id, c) for c in channels])

        if key == "recordings":
            done = [r for r in await client.recordings() if r.get("status") == "done" and r.get("url")]
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry_id}/recording/{r['id']}",
                    media_class=MediaClass.VIDEO,
                    media_content_type=RECORDING_TYPE,
                    title=_recording_title(r),
                    can_play=True,
                    can_expand=False,
                )
                for r in done
            ]
            return _folder(entry_id, key, FOLDERS[key], children)

        raise BrowseError(f"Unknown folder {'/'.join(path)}")
