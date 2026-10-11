"""What every CasaZapp TV entity shares: the server as one device."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CasaZappCoordinator


class CasaZappEntity(CoordinatorEntity[CasaZappCoordinator]):
    """Belongs to the server's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CasaZappCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="CasaZapp TV",
            manufacturer="CasaZapp",
            model="Server",
            sw_version=str(coordinator.data.get("version", "")).removeprefix("v"),
            configuration_url=coordinator.client.url,
        )
