"""A newer CasaZapp TV server: shown, not installed (the server doesn't update itself)."""

from __future__ import annotations

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CasaZappConfigEntry, CasaZappCoordinator
from .entity import CasaZappEntity

RELEASES = "https://github.com/QuadNL/CasaZapp-TV-release/releases"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CasaZappConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    # Only a profile that looks after the server hears about updates.
    if entry.runtime_data.manages:
        async_add_entities([CasaZappUpdate(entry.runtime_data)])


class CasaZappUpdate(CasaZappEntity, UpdateEntity):
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_translation_key = "server"
    _attr_title = "CasaZapp TV server"

    def __init__(self, coordinator: CasaZappCoordinator) -> None:
        super().__init__(coordinator, "update")

    @property
    def installed_version(self) -> str | None:
        return str(self.coordinator.data.get("version", "")).removeprefix("v") or None

    @property
    def latest_version(self) -> str | None:
        update = self.coordinator.data.get("update")
        return update["version"] if update else self.installed_version

    @property
    def release_url(self) -> str | None:
        update = self.coordinator.data.get("update")
        return update["url"] if update else RELEASES
