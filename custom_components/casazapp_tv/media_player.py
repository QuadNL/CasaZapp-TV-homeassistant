"""A media player per device that watches: what it plays, the channel's logo, and stop."""

from __future__ import annotations

import hashlib
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import CasaZappNotFound
from .coordinator import CasaZappConfigEntry, CasaZappCoordinator
from .entity import CasaZappEntity

Data = dict[str, Any]


def _key(device: str) -> str:
    """A device's name as the server shows it ("Living room TV · Admin"), as a stable id."""
    return "player-" + hashlib.sha1(device.encode()).hexdigest()[:12]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CasaZappConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    # The devices seen before, also when nobody watches now: their players come back idle.
    registry = er.async_get(hass)
    restored: list[CasaZappPlayer] = []
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        if item.domain == "media_player" and item.original_name:
            known.add(item.original_name)
            restored.append(CasaZappPlayer(coordinator, item.original_name))
    async_add_entities(restored)

    @callback
    def add_new() -> None:
        new = [
            v["device"]
            for v in coordinator.data.get("watching", [])
            if v.get("kind") != "recording" and v.get("device") and v["device"] not in known
        ]
        for device in new:
            known.add(device)
        if new:
            async_add_entities([CasaZappPlayer(coordinator, device) for device in dict.fromkeys(new)])

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class CasaZappPlayer(CasaZappEntity, MediaPlayerEntity):
    """One device; playing while it watches, idle otherwise."""

    _attr_has_entity_name = False
    _attr_media_image_remotely_accessible = False

    def __init__(self, coordinator: CasaZappCoordinator, device: str) -> None:
        super().__init__(coordinator, _key(device))
        self._device = device
        self._attr_name = device

    @property
    def _viewer(self) -> Data | None:
        return next(
            (
                v
                for v in self.coordinator.data.get("watching", [])
                if v.get("device") == self._device and v.get("kind") != "recording"
            ),
            None,
        )

    @property
    def state(self) -> MediaPlayerState:
        return MediaPlayerState.PLAYING if self._viewer else MediaPlayerState.IDLE

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        return MediaPlayerEntityFeature.STOP if self._viewer else MediaPlayerEntityFeature(0)

    @property
    def app_name(self) -> str:
        return "CasaZapp TV"

    @property
    def media_content_type(self) -> MediaType | None:
        viewer = self._viewer
        if not viewer:
            return None
        return MediaType.CHANNEL if viewer.get("kind") == "channel" else MediaType.VIDEO

    @property
    def media_title(self) -> str | None:
        viewer = self._viewer
        return viewer.get("title") if viewer else None

    @property
    def media_channel(self) -> str | None:
        viewer = self._viewer
        return ((viewer or {}).get("channel") or {}).get("name")

    @property
    def media_series_title(self) -> str | None:
        # A programme on a channel: the channel, so a card shows both.
        return self.media_channel

    @property
    def media_position(self) -> int | None:
        programme = (self._viewer or {}).get("programme")
        start = dt_util.parse_datetime(programme["start"]) if programme else None
        return int((dt_util.utcnow() - start).total_seconds()) if start else None

    @property
    def media_duration(self) -> int | None:
        programme = (self._viewer or {}).get("programme")
        if not programme:
            return None
        start = dt_util.parse_datetime(programme["start"])
        stop = dt_util.parse_datetime(programme["stop"])
        return int((stop - start).total_seconds()) if start and stop else None

    @property
    def media_position_updated_at(self):
        return dt_util.utcnow() if self._viewer and self._viewer.get("programme") else None

    @property
    def media_image_url(self) -> str | None:
        viewer = self._viewer
        return viewer.get("image") if viewer else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        viewer = self._viewer
        if not viewer:
            return None
        return {"since": viewer.get("since"), "stream_id": viewer.get("id")}

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """The logo from the server, with the key: Home Assistant shows it through its own proxy."""
        url = self.media_image_url
        if not url:
            return None, None
        found = await self.coordinator.client.image(url)
        return found if found else (None, None)

    async def async_media_stop(self) -> None:
        viewer = self._viewer
        if viewer:
            try:
                await self.coordinator.client.stop_stream(viewer["id"])
            except CasaZappNotFound:
                pass  # Stopped already: nothing to do.
            await self.coordinator.async_request_refresh()
