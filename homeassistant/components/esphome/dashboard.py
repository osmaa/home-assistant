"""Files to interact with a the ESPHome dashboard."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, TypedDict

import aiohttp
from esphome_dashboard_api import ConfiguredDevice, ESPHomeDashboardAPI

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from .entry_data import RuntimeEntryData

KEY_DASHBOARD = "esphome_dashboard"


class SupervisorServiceDiscovery(TypedDict):
    """ESPHome dashboard discovery."""

    host: str
    port: int


@callback
def async_get_dashboard(hass: HomeAssistant) -> ESPHomeDashboard | None:
    """Get an instance of the dashboard if set."""
    return hass.data.get(KEY_DASHBOARD)


def async_set_dashboard_info(
    hass: HomeAssistant, addon_slug: str, host: str, port: int
) -> None:
    """Set the dashboard info."""
    hass.data[KEY_DASHBOARD] = ESPHomeDashboard(
        hass,
        addon_slug,
        f"http://{host}:{port}",
        async_get_clientsession(hass),
    )


class ESPHomeDashboard(DataUpdateCoordinator[dict[str, ConfiguredDevice]]):
    """Class to interact with the ESPHome dashboard."""

    _first_fetch_lock: asyncio.Lock | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        addon_slug: str,
        url: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name="ESPHome Dashboard",
            update_interval=timedelta(minutes=5),
        )
        self.addon_slug = addon_slug
        self.api = ESPHomeDashboardAPI(url, session)

    async def ensure_data(self) -> None:
        """Ensure the update coorindator has data when this call finishes."""
        if self.data:
            return

        if self._first_fetch_lock is not None:
            async with self._first_fetch_lock:
                # We know the data is fetched when lock is done
                return

        self._first_fetch_lock = asyncio.Lock()

        async with self._first_fetch_lock:
            await self.async_request_refresh()

        self._first_fetch_lock = None

    async def _async_update_data(self) -> dict:
        """Fetch device data."""
        devices = await self.api.get_devices()
        return {dev["name"]: dev for dev in devices["configured"]}

    @callback
    def get_device(self, entry_data: RuntimeEntryData) -> ConfiguredDevice | None:
        """Return a configured device."""
        if not self.data:
            return None

        assert entry_data.device_info

        name = entry_data.device_info.name
        assert name is not None
        return self.data.get(name)
