"""Binary sensor platform for Smart EV Trip Planner."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    KEY_EV_RANGE_KM,
    KEY_NEEDS_CHARGING,
    KEY_REQUIRED_RANGE_KM,
    KEY_TOMORROW_RT_NEEDS_CHARGING,
    KEY_TOMORROW_RT_REQUIRED_KM,
    KEY_TOMORROW_RT_DISTANCE_KM,
    KEY_TOMORROW_SEQ_NEEDS_CHARGING,
    KEY_TOMORROW_SEQ_REQUIRED_KM,
    KEY_TOMORROW_SEQ_DISTANCE_KM,
)
from .coordinator import SmartTripPlannerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smart Trip Planner binary sensors."""
    coordinator: SmartTripPlannerCoordinator = entry.runtime_data
    async_add_entities([
        NeedsChargingBinarySensor(coordinator),
        TomorrowSequentialNeedsChargingBinarySensor(coordinator),
        TomorrowRoundTripNeedsChargingBinarySensor(coordinator),
    ])


class NeedsChargingBinarySensor(
    CoordinatorEntity[SmartTripPlannerCoordinator], BinarySensorEntity
):
    """Binary sensor: ON when the EV needs charging for the next upcoming trip."""

    _attr_has_entity_name = True
    _attr_name = "Needs Charging"
    _attr_icon = "mdi:ev-station"
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator: SmartTripPlannerCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_needs_charging"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Smart EV Trip Planner",
            "model": "EV Trip Advisor",
        }

    @property
    def is_on(self) -> bool:
        if self.coordinator.data is None:
            return False
        return bool(self.coordinator.data.get(KEY_NEEDS_CHARGING, False))

    @property
    def extra_state_attributes(self) -> dict:
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


class TomorrowSequentialNeedsChargingBinarySensor(
    CoordinatorEntity[SmartTripPlannerCoordinator], BinarySensorEntity
):
    """Binary sensor: ON when the EV can't cover tomorrow's sequential route (Home → E1 → E2 → … → Home)."""

    _attr_has_entity_name = True
    _attr_name = "Tomorrow Sequential Needs Charging"
    _attr_icon = "mdi:calendar-alert"
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator: SmartTripPlannerCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_tomorrow_seq_needs_charging"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Smart EV Trip Planner",
            "model": "EV Trip Advisor",
        }

    @property
    def is_on(self) -> bool:
        if self.coordinator.data is None:
            return False
        return bool(self.coordinator.data.get(KEY_TOMORROW_SEQ_NEEDS_CHARGING, False))

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        ev_range = data.get(KEY_EV_RANGE_KM)
        total = data.get(KEY_TOMORROW_SEQ_DISTANCE_KM)
        required = data.get(KEY_TOMORROW_SEQ_REQUIRED_KM)
        shortfall = None
        if ev_range is not None and required is not None:
            shortfall = round(required - ev_range, 1)
        return {
            "ev_range_km": ev_range,
            "total_distance_km": total,
            "required_range_km": required,
            "shortfall_km": shortfall,
            "route": "Home → E1 → E2 → … → EN → Home",
        }


class TomorrowRoundTripNeedsChargingBinarySensor(
    CoordinatorEntity[SmartTripPlannerCoordinator], BinarySensorEntity
):
    """Binary sensor: ON when the EV can't cover tomorrow's per-event round trips (Home → Ei → Home each)."""

    _attr_has_entity_name = True
    _attr_name = "Tomorrow Round Trip Needs Charging"
    _attr_icon = "mdi:calendar-alert"
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator: SmartTripPlannerCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_tomorrow_rt_needs_charging"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Smart EV Trip Planner",
            "model": "EV Trip Advisor",
        }

    @property
    def is_on(self) -> bool:
        if self.coordinator.data is None:
            return False
        return bool(self.coordinator.data.get(KEY_TOMORROW_RT_NEEDS_CHARGING, False))

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        ev_range = data.get(KEY_EV_RANGE_KM)
        total = data.get(KEY_TOMORROW_RT_DISTANCE_KM)
        required = data.get(KEY_TOMORROW_RT_REQUIRED_KM)
        shortfall = None
        if ev_range is not None and required is not None:
            shortfall = round(required - ev_range, 1)
        return {
            "ev_range_km": ev_range,
            "total_distance_km": total,
            "required_range_km": required,
            "shortfall_km": shortfall,
            "route": "Home → E1 → Home, Home → E2 → Home, …",
        }
