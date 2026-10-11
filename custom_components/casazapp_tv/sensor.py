"""Sensors: who watches, recordings, the library, the disk and the providers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import CasaZappConfigEntry, CasaZappCoordinator
from .entity import CasaZappEntity

Data = dict[str, Any]


def _time(value: str | None) -> datetime | None:
    return dt_util.parse_datetime(value) if value else None


def _watching(data: Data) -> list[Data]:
    """Devices watching; the server's own recordings have their own sensors."""
    return [v for v in data.get("watching", []) if v.get("kind") != "recording"]


def _playing(data: Data) -> str:
    """What plays, in a few words: one stream as "Channel: programme", more as "2 streams"."""
    viewers = _watching(data)
    if not viewers:
        return "Nothing"
    if len(viewers) > 1:
        return f"{len(viewers)} streams"
    viewer = viewers[0]
    channel = (viewer.get("channel") or {}).get("name")
    title = viewer.get("title") or ""
    return f"{channel}: {title}" if channel and title and title != channel else (title or channel or "")


def _playing_attrs(data: Data) -> dict[str, Any]:
    viewers = _watching(data)
    if len(viewers) == 1:
        viewer = viewers[0]
        programme = viewer.get("programme") or {}
        return {
            "device": viewer.get("device"),
            "channel": (viewer.get("channel") or {}).get("name"),
            "title": viewer.get("title"),
            "start": programme.get("start"),
            "stop": programme.get("stop"),
            "since": viewer.get("since"),
            "stream_id": viewer.get("id"),
        }
    return {
        "streams": [
            {
                "device": v.get("device"),
                "channel": (v.get("channel") or {}).get("name"),
                "title": v.get("title"),
                "stream_id": v.get("id"),
            }
            for v in viewers
        ]
    }


@dataclass(frozen=True, kw_only=True)
class CasaZappSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Data], Any]
    attrs_fn: Callable[[Data], dict[str, Any]] | None = None
    # Only with a key whose profile looks after the server (the disk is then in the summary).
    manages: bool = False


SENSORS: tuple[CasaZappSensorDescription, ...] = (
    CasaZappSensorDescription(
        key="now_playing",
        translation_key="now_playing",
        value_fn=_playing,
        attrs_fn=_playing_attrs,
    ),
    CasaZappSensorDescription(
        key="watching",
        translation_key="watching",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(_watching(d)),
        attrs_fn=lambda d: {
            "streams": [
                {
                    "device": v.get("device"),
                    "title": v.get("title"),
                    "channel": (v.get("channel") or {}).get("name"),
                    "since": v.get("since"),
                    "id": v.get("id"),
                }
                for v in _watching(d)
            ]
        },
    ),
    CasaZappSensorDescription(
        key="recording_now",
        translation_key="recording_now",
        value_fn=lambda d: ", ".join(r["title"] for r in d["recordings"]["active"]) or None,
        attrs_fn=lambda d: {"recordings": d["recordings"]["active"]},
    ),
    CasaZappSensorDescription(
        key="next_recording",
        translation_key="next_recording",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _time((d["recordings"]["next"] or {}).get("startAt")),
        attrs_fn=lambda d: dict(d["recordings"]["next"] or {}),
    ),
    CasaZappSensorDescription(
        key="planned",
        translation_key="planned",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["recordings"]["planned"],
    ),
    CasaZappSensorDescription(
        key="recorded",
        translation_key="recorded",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["recordings"]["done"],
    ),
    CasaZappSensorDescription(
        key="last_channel",
        translation_key="last_channel",
        value_fn=lambda d: next((c["name"] for c in d.get("recent", {}).get("channels", [])), None),
        attrs_fn=lambda d: {"channels": [c["name"] for c in d.get("recent", {}).get("channels", [])]},
    ),
    CasaZappSensorDescription(
        key="continue",
        translation_key="continue",
        value_fn=lambda d: next(
            (c["title"] for c in d.get("recent", {}).get("continue", [])), None
        ),
        attrs_fn=lambda d: {"items": d.get("recent", {}).get("continue", [])},
    ),
    CasaZappSensorDescription(
        key="channels",
        translation_key="channels",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["library"]["channels"],
    ),
    CasaZappSensorDescription(
        key="movies",
        translation_key="movies",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["library"]["movies"],
    ),
    CasaZappSensorDescription(
        key="series",
        translation_key="series",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["library"]["series"],
    ),
    CasaZappSensorDescription(
        key="storage_free",
        translation_key="storage_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        manages=True,
        value_fn=lambda d: (d.get("storage") or {}).get("freeBytes"),
        attrs_fn=lambda d: {"total_bytes": (d.get("storage") or {}).get("totalBytes")},
    ),
)


@dataclass(frozen=True, kw_only=True)
class ProviderSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Data], Any]


PROVIDER_SENSORS: tuple[ProviderSensorDescription, ...] = (
    ProviderSensorDescription(
        key="expires",
        translation_key="provider_expires",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda p: _time(p.get("expiresAt")),
    ),
    ProviderSensorDescription(
        key="connections",
        translation_key="provider_connections",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda p: p.get("watching"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CasaZappConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        CasaZappSensor(coordinator, d) for d in SENSORS if coordinator.manages or not d.manages
    ]
    if coordinator.manages:
        entities += [
            ProviderSensor(coordinator, provider, d)
            for provider in coordinator.data.get("providers", [])
            for d in PROVIDER_SENSORS
        ]
    async_add_entities(entities)


class CasaZappSensor(CasaZappEntity, SensorEntity):
    entity_description: CasaZappSensorDescription

    def __init__(self, coordinator: CasaZappCoordinator, description: CasaZappSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn else None


class ProviderSensor(CasaZappEntity, SensorEntity):
    """One provider (a playlist): when it ends, how many watch of how many may."""

    entity_description: ProviderSensorDescription

    def __init__(
        self, coordinator: CasaZappCoordinator, provider: Data, description: ProviderSensorDescription
    ) -> None:
        super().__init__(coordinator, f"provider-{provider['id']}-{description.key}")
        self.entity_description = description
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
    def native_value(self) -> Any:
        provider = self._provider
        return self.entity_description.value_fn(provider) if provider else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        provider = self._provider
        if not provider:
            return None
        return {
            "status": provider.get("status"),
            "limit": provider.get("limit"),
            "last_sync": provider.get("lastSyncAt"),
            "type": provider.get("type"),
        }
