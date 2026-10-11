"""On or off: something records, the disk is full, a provider's sync failed."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CasaZappConfigEntry, CasaZappCoordinator
from .entity import CasaZappEntity

Data = dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class CasaZappBinaryDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[Data], bool]
    manages: bool = False


BINARY_SENSORS: tuple[CasaZappBinaryDescription, ...] = (
    CasaZappBinaryDescription(
        key="recording",
        translation_key="recording",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda d: bool(d["recordings"]["active"]),
    ),
    CasaZappBinaryDescription(
        key="storage_full",
        translation_key="storage_full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        manages=True,
        is_on_fn=lambda d: bool((d.get("storage") or {}).get("full")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CasaZappConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        CasaZappBinarySensor(coordinator, d)
        for d in BINARY_SENSORS
        if coordinator.manages or not d.manages
    ]
    if coordinator.manages:
        entities += [
            ProviderSyncProblem(coordinator, p) for p in coordinator.data.get("providers", [])
        ]
    async_add_entities(entities)


class CasaZappBinarySensor(CasaZappEntity, BinarySensorEntity):
    entity_description: CasaZappBinaryDescription

    def __init__(self, coordinator: CasaZappCoordinator, description: CasaZappBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.coordinator.data)


class ProviderSyncProblem(CasaZappEntity, BinarySensorEntity):
    """A provider's last sync went wrong; the reason is an attribute."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "provider_sync"

    def __init__(self, coordinator: CasaZappCoordinator, provider: Data) -> None:
        super().__init__(coordinator, f"provider-{provider['id']}-sync")
        self._id = provider["id"]
        self._attr_translation_placeholders = {"name": provider["name"]}

    @property
    def _provider(self) -> Data | None:
        return next(
            (p for p in self.coordinator.data.get("providers", []) if p["id"] == self._id), None
        )

    @property
    def available(self) -> bool:
        return super().available and self._provider is not None

    @property
    def is_on(self) -> bool:
        return bool((self._provider or {}).get("syncError"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        provider = self._provider
        return {"error": provider.get("syncError"), "last_sync": provider.get("lastSyncAt")} if provider else None
