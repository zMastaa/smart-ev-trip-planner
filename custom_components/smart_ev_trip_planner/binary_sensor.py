"""Binary sensor platform for Smart Trip Planner."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_EV_RANGE_KM, KEY_NEEDS_CHARGING, KEY_REQUIRED_RANGE_KM
from .coordinator import SmartTripPlannerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smart Trip Planner binary sensor."""
    coordinator: SmartTripPlannerCoordinator = entry.runtime_data
    async_add_entities([NeedsChargingBinarySensor(coordinator)])


class NeedsChargingBinarySensor(
    CoordinatorEntity[SmartTripPlannerCoordinator], BinarySensorEntity
):
    """Binary sensor that is ON when the EV needs charging for the next trip."""

    _attr_has_entity_name = True
    _attr_name = "Needs Charging"
    _attr_icon = "mdi:ev-station"
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator: SmartTripPlannerCoordinator) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_needs_charging"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Smart Trip Planner",
            "manufacturer": "Community",
            "model": "EV Trip Advisor",
        }

    @property
    def is_on(self) -> bool:
        """Return True when the EV cannot reach the next event on current charge."""
        if self.coordinator.data is None:
            return False
        return bool(self.coordinator.data.get(KEY_NEEDS_CHARGING, False))

    @property
    def extra_state_attributes(self) -> dict:
        """Expose range shortfall so automations can act on it."""
        data = self.coordinator.data or {}
        ev_range = data.get(KEY_EV_RANGE_KM)
        required = data.get(KEY_REQUIRED_RANGE_KM)
        shortfall = None
        if ev_range is not None and required is not None:
            shortfall = round(required - ev_range, 1)
        return {
            "ev_range_km": ev_range,
            "required_range_km": required,
            "shortfall_km": shortfall,
        }
