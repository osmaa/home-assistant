"""Update platform for ESPHome."""
from __future__ import annotations

from typing import cast

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .dashboard import ESPHomeDashboard, async_get_dashboard
from .domain_data import DomainData
from .entry_data import RuntimeEntryData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLED update based on a config entry."""
    dashboard = async_get_dashboard(hass)

    if dashboard is None:
        return

    entry_data = DomainData.get(hass).get_entry_data(entry)
    unsub = None

    async def setup_update_entity() -> None:
        """Set up the update entity."""
        nonlocal unsub

        # Keep listening until device is available
        if not entry_data.available:
            return

        if unsub is not None:
            unsub()  # type: ignore[unreachable]

        assert dashboard is not None
        await dashboard.ensure_data()
        async_add_entities([ESPHomeUpdateEntity(entry_data, dashboard)])

    if entry_data.available:
        await setup_update_entity()
        return

    signal = f"esphome_{entry_data.entry_id}_on_device_update"
    unsub = async_dispatcher_connect(hass, signal, setup_update_entity)


class ESPHomeUpdateEntity(CoordinatorEntity[ESPHomeDashboard], UpdateEntity):
    """Defines an ESPHome update entity."""

    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.SPECIFIC_VERSION
    _attr_title = "ESPHome"
    _attr_name = "Firmware"

    def __init__(
        self, entry_data: RuntimeEntryData, coordinator: ESPHomeDashboard
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator=coordinator)
        self._entry_data = entry_data
        self._attr_unique_id = f"{entry_data.entry_id}_update"
        assert entry_data.device_info
        self._attr_device_info = DeviceInfo(
            connections={
                (dr.CONNECTION_NETWORK_MAC, entry_data.device_info.mac_address)
            }
        )

    @property
    def available(self) -> bool:
        """Return if update is available."""
        return (
            super().available
            and self.coordinator.get_device(self._entry_data) is not None
        )

    @property
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        assert self._entry_data.device_info is not None
        return self._entry_data.device_info.esphome_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        device = self.coordinator.get_device(self._entry_data)
        if device is None:
            return None
        return cast(str, device["current_version"])

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return "https://esphome.io/changelog/"
