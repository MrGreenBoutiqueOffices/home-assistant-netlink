"""Sensor platform for NetLink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import NetlinkDataUpdateCoordinator
from .entity import NetlinkControllerEntity, NetlinkDisplayEntity


@dataclass(kw_only=True)
class NetlinkSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description with value resolver."""

    value_fn: Callable[[object], int | float | str | bool | None]


DESK_SENSORS: list[NetlinkSensorEntityDescription] = [
    NetlinkSensorEntityDescription(
        key="desk_height",
        translation_key="desk_height",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.state.height,
    ),
    NetlinkSensorEntityDescription(
        key="desk_mode",
        translation_key="desk_mode",
        value_fn=lambda data: data.state.mode,
    ),
    NetlinkSensorEntityDescription(
        key="desk_error",
        translation_key="desk_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (data.state.error or "")[:255] or None,
    ),
]


DISPLAY_SENSORS: list[NetlinkSensorEntityDescription] = [
    NetlinkSensorEntityDescription(
        key="brightness",
        translation_key="display_brightness",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.state.brightness,
    ),
    NetlinkSensorEntityDescription(
        key="volume",
        translation_key="display_volume",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.state.volume,
    ),
    NetlinkSensorEntityDescription(
        key="power",
        translation_key="display_power",
        value_fn=lambda data: data.state.power,
    ),
    NetlinkSensorEntityDescription(
        key="source",
        translation_key="display_source",
        value_fn=lambda data: data.state.source,
    ),
    NetlinkSensorEntityDescription(
        key="error",
        translation_key="display_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (data.state.error or "")[:255] or None,
    ),
]


BROWSER_SENSORS: list[NetlinkSensorEntityDescription] = [
    NetlinkSensorEntityDescription(
        key="browser_url",
        translation_key="browser_url",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.url,
    ),
]


ACCESS_CODE_SENSORS: list[NetlinkSensorEntityDescription] = [
    NetlinkSensorEntityDescription(
        key="web_login_access_code",
        translation_key="web_login_access_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.web_login.code,
    ),
    NetlinkSensorEntityDescription(
        key="web_login_access_code_valid_until",
        translation_key="web_login_access_code_valid_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: dt_util.parse_datetime(data.web_login.valid_until),
    ),
    NetlinkSensorEntityDescription(
        key="signing_maintenance_access_code",
        translation_key="signing_maintenance_access_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.signing_maintenance.code,
    ),
    NetlinkSensorEntityDescription(
        key="signing_maintenance_access_code_valid_until",
        translation_key="signing_maintenance_access_code_valid_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: dt_util.parse_datetime(
            data.signing_maintenance.valid_until
        ),
    ),
]


class NetlinkBrowserSensor(NetlinkControllerEntity, SensorEntity):
    """Browser controller sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: NetlinkSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data["browser"]
        return self.entity_description.value_fn(data)


class NetlinkDeskSensor(NetlinkControllerEntity, SensorEntity):
    """Desk sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: NetlinkSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    @property
    def native_value(self) -> int | float | str | bool | None:
        data = self.coordinator.data["desk"]
        return self.entity_description.value_fn(data)


class NetlinkDisplaySensor(NetlinkDisplayEntity, SensorEntity):
    """Display sensor."""

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        bus_id: str,
        description: NetlinkSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry, bus_id)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_display_{bus_id}_{description.key}"

    @property
    def native_value(self) -> int | float | str | bool | None:
        data = self.coordinator.data["displays"][self.bus_id]
        return self.entity_description.value_fn(data)


class NetlinkAccessCodeSensor(NetlinkControllerEntity, SensorEntity):
    """Access code diagnostic sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: NetlinkSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    @property
    def native_value(self) -> int | float | str | bool | None:
        data = self.coordinator.data["access_codes"]
        return self.entity_description.value_fn(data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NetLink sensor entities."""
    coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        NetlinkBrowserSensor(coordinator, entry, description)
        for description in BROWSER_SENSORS
    ]
    entities.extend(
        NetlinkDeskSensor(coordinator, entry, description)
        for description in DESK_SENSORS
    )
    if "access_codes" in coordinator.data:
        entities.extend(
            NetlinkAccessCodeSensor(coordinator, entry, description)
            for description in ACCESS_CODE_SENSORS
        )

    display_bus_ids = set(coordinator.display_info.keys()) | set(
        coordinator.data["displays"].keys()
    )
    for bus_id in sorted(display_bus_ids):
        for description in DISPLAY_SENSORS:
            entities.append(
                NetlinkDisplaySensor(coordinator, entry, bus_id, description)
            )

    async_add_entities(entities)

    def _on_new_display(bus_id: str) -> None:
        async_add_entities(
            [
                NetlinkDisplaySensor(coordinator, entry, bus_id, description)
                for description in DISPLAY_SENSORS
            ]
        )

    coordinator.async_add_new_display_callback(_on_new_display)

    access_code_entities_added = "access_codes" in coordinator.data

    def _on_access_codes_available() -> None:
        nonlocal access_code_entities_added
        if access_code_entities_added:
            return
        access_code_entities_added = True
        async_add_entities(
            [
                NetlinkAccessCodeSensor(coordinator, entry, description)
                for description in ACCESS_CODE_SENSORS
            ]
        )

    coordinator.async_add_access_codes_available_callback(_on_access_codes_available)
