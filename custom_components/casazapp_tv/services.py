"""Actions for automations and dashboards: record, stop or remove a recording, stop a stream."""

from __future__ import annotations

from datetime import datetime

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .api import CasaZappError, CasaZappForbidden
from .const import (
    ATTR_CHANNEL_ID,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_MINUTES,
    ATTR_RECORDING_ID,
    ATTR_START,
    ATTR_STOP,
    ATTR_STREAM_ID,
    ATTR_TAKEOVER,
    ATTR_TITLE,
    DOMAIN,
    SERVICE_DELETE_RECORDING,
    SERVICE_RECORD,
    SERVICE_STOP_RECORDING,
    SERVICE_STOP_STREAM,
)
from .coordinator import CasaZappConfigEntry

ENTRY = {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}

RECORD_SCHEMA = vol.Schema(
    {
        **ENTRY,
        vol.Required(ATTR_CHANNEL_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=1, max=720)),
        vol.Optional(ATTR_START): cv.datetime,
        vol.Optional(ATTR_STOP): cv.datetime,
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_TAKEOVER, default=False): cv.boolean,
    }
)
RECORDING_SCHEMA = vol.Schema(
    {**ENTRY, vol.Required(ATTR_RECORDING_ID): vol.All(vol.Coerce(int), vol.Range(min=1))}
)
STREAM_SCHEMA = vol.Schema({**ENTRY, vol.Required(ATTR_STREAM_ID): cv.string})


def _entry(hass: HomeAssistant, call: ServiceCall) -> CasaZappConfigEntry:
    """The server meant: the one given, or the only one there is."""
    wanted = call.data.get(ATTR_CONFIG_ENTRY_ID)
    entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED and (wanted is None or e.entry_id == wanted)
    ]
    if len(entries) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="which_server" if not wanted else "no_server",
        )
    return entries[0]


async def _run(entry: CasaZappConfigEntry, action) -> object:
    try:
        result = await action(entry.runtime_data.client)
    except CasaZappForbidden as err:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="forbidden") from err
    except CasaZappError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="failed", translation_placeholders={"error": str(err)}
        ) from err
    await entry.runtime_data.async_request_refresh()
    return result


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    def aware(value: datetime | None) -> datetime | None:
        """A time without a zone is Home Assistant's own time."""
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=dt_util.get_default_time_zone())

    async def record(call: ServiceCall) -> ServiceResponse:
        start, stop = aware(call.data.get(ATTR_START)), aware(call.data.get(ATTR_STOP))
        if (start is None) != (stop is None):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="start_and_stop")
        created = await _run(
            _entry(hass, call),
            lambda c: c.record(
                call.data[ATTR_CHANNEL_ID],
                minutes=call.data.get(ATTR_MINUTES),
                start=start,
                stop=stop,
                title=call.data.get(ATTR_TITLE),
                takeover=call.data[ATTR_TAKEOVER],
            ),
        )
        return {"recording": created} if call.return_response else None

    async def stop_recording(call: ServiceCall) -> None:
        await _run(_entry(hass, call), lambda c: c.stop_recording(call.data[ATTR_RECORDING_ID]))

    async def delete_recording(call: ServiceCall) -> None:
        await _run(_entry(hass, call), lambda c: c.delete_recording(call.data[ATTR_RECORDING_ID]))

    async def stop_stream(call: ServiceCall) -> None:
        await _run(_entry(hass, call), lambda c: c.stop_stream(call.data[ATTR_STREAM_ID]))

    hass.services.async_register(
        DOMAIN, SERVICE_RECORD, record, schema=RECORD_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(DOMAIN, SERVICE_STOP_RECORDING, stop_recording, schema=RECORDING_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_RECORDING, delete_recording, schema=RECORDING_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_STOP_STREAM, stop_stream, schema=STREAM_SCHEMA)
