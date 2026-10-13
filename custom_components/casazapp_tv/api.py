"""Talks to a CasaZapp TV server with an API key (the server's /api/docs lists every route)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import aiohttp


class CasaZappError(Exception):
    """The server can't be reached, or answered with an error."""


class CasaZappAuthError(CasaZappError):
    """The key is unknown or revoked."""


class CasaZappForbidden(CasaZappError):
    """The key, or its profile, may not do this."""


class CasaZappNotFound(CasaZappError):
    """Not there (any more): a stream that already stopped, a recording that's gone."""


def normalize_url(url: str) -> str:
    """The server's address without a trailing slash; http:// when no scheme is given."""
    url = url.strip().rstrip("/")
    if "://" not in url:
        url = f"http://{url}"
    return url


class CasaZappClient:
    """One server, one key."""

    def __init__(self, session: aiohttp.ClientSession, url: str, api_key: str) -> None:
        self._session = session
        self.url = normalize_url(url)
        self._headers = {"Authorization": f"Bearer {api_key.strip()}"}

    async def _request(self, method: str, path: str, json: dict[str, Any] | None = None) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self.url}{path}",
                headers=self._headers,
                json=json,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as res:
                if res.status == 401:
                    raise CasaZappAuthError("The API key is not valid")
                if res.status == 403:
                    raise CasaZappForbidden("The API key may not do this")
                if res.status == 404:
                    raise CasaZappNotFound(f"{method} {path}: not found")
                if res.status >= 400:
                    body = await res.json(content_type=None) if res.content_length else None
                    code = body.get("error") if isinstance(body, dict) else None
                    raise CasaZappError(f"{method} {path}: {res.status} {code or ''}".strip())
                if res.status == 204:
                    return None
                return await res.json(content_type=None)
        except aiohttp.ClientError as err:
            raise CasaZappError(f"Can't reach {self.url}: {err}") from err
        except TimeoutError as err:
            raise CasaZappError(f"No answer from {self.url}") from err

    async def status(self) -> dict[str, Any]:
        """Everything at a glance: GET /api/integration/status."""
        return await self._request("GET", "/api/integration/status")

    async def image(self, path: str) -> tuple[bytes, str] | None:
        """A logo, poster or still the summary points to, fetched with the key."""
        try:
            async with self._session.get(
                f"{self.url}{path}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as res:
                if res.status != 200:
                    return None
                return await res.read(), res.content_type
        except (aiohttp.ClientError, TimeoutError):
            return None

    async def record(
        self,
        channel_id: int,
        *,
        minutes: int | None = None,
        start: datetime | None = None,
        stop: datetime | None = None,
        title: str | None = None,
        takeover: bool = False,
    ) -> dict[str, Any]:
        """Plan a recording: now for some minutes, or from start to stop."""
        body: dict[str, Any] = {"channelId": channel_id}
        if start and stop:
            body["startAt"] = start.isoformat()
            body["stopAt"] = stop.isoformat()
        else:
            body["minutes"] = minutes or 60
        if title:
            body["title"] = title
        if takeover:
            body["takeover"] = True
        return await self._request("POST", "/api/recordings", body)

    async def stop_recording(self, recording_id: int) -> None:
        await self._request("POST", f"/api/recordings/{recording_id}/stop")

    async def delete_recording(self, recording_id: int) -> None:
        await self._request("DELETE", f"/api/recordings/{recording_id}")

    async def devices(self) -> list[dict[str, Any]]:
        """The paired apps: remote control allowed there, and the app open now (server 0.5.8)."""
        try:
            return await self._request("GET", "/api/integration/devices")
        except CasaZappNotFound:
            return []  # An older server: no remote control.

    async def remote_play(self, device_id: int, kind: str, item_id: int) -> None:
        """Play a channel or recording on a CasaZapp TV app with remote control."""
        await self._request(
            "POST", f"/api/integration/devices/{device_id}/play", {"kind": kind, "id": item_id}
        )

    async def remote_stop(self, device_id: int) -> None:
        await self._request("POST", f"/api/integration/devices/{device_id}/stop")

    async def stop_stream(self, stream_id: str) -> None:
        await self._request("POST", f"/api/streams/{stream_id}/stop", {})

    async def lists(self) -> list[dict[str, Any]]:
        """The key's profile's own lists."""
        return await self._request("GET", "/api/lists")

    async def channels(
        self,
        playlist_id: int,
        *,
        favorites: bool = False,
        list_id: int | None = None,
        category_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Favourites or an own list (both span every playlist), or a playlist's channels (the
        ones switched on, in the apps' order)."""
        query = "limit=5000"
        if favorites:
            query += "&favorites=true"
        if list_id:
            query += f"&listId={list_id}"
        if category_id is not None:
            query += f"&categoryId={category_id}"
        page = await self._request("GET", f"/api/playlists/{playlist_id}/channels?{query}")
        return page.get("items", []) if isinstance(page, dict) else []

    async def categories(self, playlist_id: int) -> list[dict[str, Any]]:
        """A playlist's channel categories that are on, in its order, as the apps show them."""
        return await self._request("GET", f"/api/playlists/{playlist_id}/categories?type=live")

    async def recordings(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/recordings")

    async def cast(
        self, kind: str, item_id: int, target: str, *, mp3: bool = False
    ) -> dict[str, Any]:
        """A link a speaker or player fetches itself, one per target; it ends by itself. With mp3
        a channel comes as only its sound, for a speaker that can't play HLS."""
        body: dict[str, Any] = {"kind": kind, "id": item_id, "target": target[:80]}
        if mp3 and kind == "live":
            body["format"] = "mp3"
        return await self._request("POST", "/api/cast", body)

    async def events(self) -> AsyncIterator[str]:
        """The names of the server's events, as they come (Server-Sent Events). A dropped
        connection (the server restarting) ends it with a CasaZappError."""
        try:
            async for event in self._events():
                yield event
        except aiohttp.ClientError as err:
            raise CasaZappError(f"Events from {self.url} stopped: {err}") from err

    async def _events(self) -> AsyncIterator[str]:
        async with self._session.get(
            f"{self.url}/api/events",
            headers={**self._headers, "Accept": "text/event-stream"},
            timeout=aiohttp.ClientTimeout(total=None, sock_read=60),
        ) as res:
            if res.status == 401:
                raise CasaZappAuthError("The API key is not valid")
            if res.status != 200:
                raise CasaZappError(f"Events: {res.status}")
            async for raw in res.content:
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("event:"):
                    yield line[len("event:") :].strip()
