"""Adding a CasaZapp TV server: its address and an API key from Settings → Account → API keys."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import CasaZappAuthError, CasaZappClient, CasaZappError, normalize_url
from .const import DOMAIN, LOGGER


class CasaZappConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per server."""

    VERSION = 1

    def __init__(self) -> None:
        self._url: str | None = None

    async def _check(self, url: str, key: str) -> tuple[dict[str, Any] | None, str | None]:
        """The summary with this key, or what went wrong."""
        client = CasaZappClient(async_get_clientsession(self.hass), url, key)
        try:
            return await client.status(), None
        except CasaZappAuthError:
            return None, "invalid_auth"
        except CasaZappError as err:
            LOGGER.debug("Can't connect to %s: %s", url, err)
            return None, "cannot_connect"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            _, error = await self._check(url, user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="CasaZapp TV",
                    data={CONF_URL: url, CONF_API_KEY: user_input[CONF_API_KEY].strip()},
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default=self._url or "http://"): str,
                vol.Required(CONF_API_KEY): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Found on the network: the address is filled in, the key is still needed."""
        url = discovery_info.properties.get("url") or (
            f"http://{discovery_info.host}:{discovery_info.port}"
        )
        url = normalize_url(url)
        await self.async_set_unique_id(url)
        self._abort_if_unique_id_configured()
        self._url = url
        self.context["title_placeholders"] = {"url": url}
        return await self.async_step_user()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The key was revoked: ask for a new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            _, error = await self._check(entry.data[CONF_URL], user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY].strip()}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={"url": entry.data[CONF_URL]},
        )
