"""CasaZapp TV for Home Assistant: what plays, recordings and the server, from a CasaZapp TV server."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import CasaZappClient
from .const import DOMAIN
from .coordinator import CasaZappConfigEntry, CasaZappCoordinator
from .services import async_setup_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.UPDATE,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """The actions (record, stop) exist once, for every server."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: CasaZappConfigEntry) -> bool:
    """Connect to one server."""
    client = CasaZappClient(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_API_KEY]
    )
    coordinator = CasaZappCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # The server's events: what plays changes at once instead of after a minute.
    entry.async_create_background_task(hass, coordinator.listen(), f"{DOMAIN} events")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CasaZappConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
