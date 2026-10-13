"""Keeps the server's summary up to date: read every minute, and at once when the server says so."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CasaZappAuthError, CasaZappClient, CasaZappError
from .const import DOMAIN, LOGGER, REFRESH_EVENTS, SCAN_INTERVAL

type CasaZappConfigEntry = ConfigEntry[CasaZappCoordinator]


class CasaZappCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The summary of one server (GET /api/integration/status)."""

    config_entry: CasaZappConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: CasaZappConfigEntry, client: CasaZappClient
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.status()
            # The apps it can play on (#256); a read-only key can see them too.
            try:
                data["devices"] = await self.client.devices()
            except CasaZappAuthError:
                raise
            except CasaZappError:
                data["devices"] = []
            return data
        except CasaZappAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CasaZappError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def manages(self) -> bool:
        """The key's profile looks after the server: the disk and the providers are in the summary."""
        return bool(self.data) and self.data.get("storage") is not None

    async def listen(self) -> None:
        """Hear the server's events and read the summary again when something changed."""
        wait = 5
        while True:
            try:
                async for event in self.client.events():
                    wait = 5
                    if event in REFRESH_EVENTS:
                        await self.async_request_refresh()
            except CasaZappAuthError:
                # The coordinator's next read starts the re-authentication.
                await self.async_request_refresh()
                return
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                # Whatever broke the connection (a restart, the network): never stop listening.
                LOGGER.debug("Events from %s stopped: %s", self.client.url, err)
            # Connection lost or server restarted: try again, a little later each time.
            await asyncio.sleep(wait)
            wait = min(wait * 2, 60)
