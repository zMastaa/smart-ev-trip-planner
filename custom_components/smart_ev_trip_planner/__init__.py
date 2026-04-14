"""Smart Trip Planner integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import SmartTripPlannerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type SmartTripPlannerConfigEntry = ConfigEntry[SmartTripPlannerCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: SmartTripPlannerConfigEntry
) -> bool:
    """Set up Smart Trip Planner from a config entry."""
    coordinator = SmartTripPlannerCoordinator(hass, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as exc:
        raise ConfigEntryNotReady(
            f"Unable to complete first data refresh: {exc}"
        ) from exc

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SmartTripPlannerConfigEntry
) -> bool:
    """Unload Smart Trip Planner config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: SmartTripPlannerCoordinator = entry.runtime_data
        await coordinator.async_shutdown()
    return unload_ok
