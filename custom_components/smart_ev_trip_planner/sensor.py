"""Sensor platform for Smart EV Trip Planner."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    KEY_EV_BATTERY_PERCENT,
    KEY_EV_RANGE_KM,
    KEY_NEXT_EVENT_LOCATION,
    KEY_NEXT_EVENT_START,
    KEY_NEXT_EVENT_SUMMARY,
    KEY_REQUIRED_RANGE_KM,
    KEY_TODAY_EVENT_COUNT,
    KEY_TODAY_EVENTS,
    KEY_TODAY_RT_DISTANCE_KM,
    KEY_TODAY_RT_DURATION_MIN,
    KEY_TODAY_RT_REQUIRED_KM,
    KEY_TODAY_SEQ_DISTANCE_KM,
    KEY_TODAY_SEQ_DURATION_MIN,
    KEY_TODAY_SEQ_REQUIRED_KM,
    KEY_TOMORROW_EVENT_COUNT,
    KEY_TOMORROW_EVENTS,
    KEY_TOMORROW_RT_DISTANCE_KM,
    KEY_TOMORROW_RT_DURATION_MIN,
    KEY_TOMORROW_RT_REQUIRED_KM,
    KEY_TOMORROW_SEQ_DISTANCE_KM,
    KEY_TOMORROW_SEQ_DURATION_MIN,
    KEY_TOMORROW_SEQ_REQUIRED_KM,
    KEY_TRIP_DISTANCE_KM,
    KEY_TRIP_DURATION_MIN,
)
from .coordinator import SmartTripPlannerCoordinator


@dataclass(frozen=True, kw_only=True)
class TripSensorEntityDescription(SensorEntityDescription):
    """Sensor description with a value extractor function."""

    value_fn: Any = None
    extra_attr_fn: Any = None


def _format_event_start(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


SENSOR_DESCRIPTIONS: tuple[TripSensorEntityDescription, ...] = (
    # ── Next event ────────────────────────────────────────────────────
    TripSensorEntityDescription(
        key="next_event",
        name="Next Trip Event",
        icon="mdi:calendar-clock",
        value_fn=lambda d: d.get(KEY_NEXT_EVENT_SUMMARY),
        extra_attr_fn=lambda d: {
            "location": d.get(KEY_NEXT_EVENT_LOCATION),
            "departure": _format_event_start(d.get(KEY_NEXT_EVENT_START)),
        },
    ),
    TripSensorEntityDescription(
        key="trip_distance",
        name="Trip Distance",
        icon="mdi:map-marker-distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TRIP_DISTANCE_KM),
    ),
    TripSensorEntityDescription(
        key="trip_duration",
        name="Driving Duration",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TRIP_DURATION_MIN),
    ),
    TripSensorEntityDescription(
        key="required_range",
        name="Required Range",
        icon="mdi:map-check",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_REQUIRED_RANGE_KM),
    ),
    TripSensorEntityDescription(
        key="ev_range",
        name="EV Current Range",
        icon="mdi:battery-charging",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_EV_RANGE_KM),
    ),
    TripSensorEntityDescription(
        key="ev_battery",
        name="EV Battery Level",
        icon="mdi:battery",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_EV_BATTERY_PERCENT),
    ),
    # ── Today — remaining events ──────────────────────────────────────
    TripSensorEntityDescription(
        key="today_events",
        name="Today's Remaining Events with Location",
        icon="mdi:calendar-today",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TODAY_EVENT_COUNT, 0),
        extra_attr_fn=lambda d: {"events": d.get(KEY_TODAY_EVENTS, [])},
    ),
    # ── Today — sequential (Home → E1 → E2 → … → EN → Home) ──────────
    TripSensorEntityDescription(
        key="today_seq_distance",
        name="Today Sequential Distance",
        icon="mdi:map-marker-path",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TODAY_SEQ_DISTANCE_KM),
        extra_attr_fn=lambda d: {
            "required_range_km": d.get(KEY_TODAY_SEQ_REQUIRED_KM),
            "route": "Home → E1 → E2 → … → EN → Home",
        },
    ),
    TripSensorEntityDescription(
        key="today_seq_duration",
        name="Today Sequential Duration",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TODAY_SEQ_DURATION_MIN),
    ),
    # ── Today — round-trip (Home → Ei → Home per event) ───────────────
    TripSensorEntityDescription(
        key="today_rt_distance",
        name="Today Round Trip Distance",
        icon="mdi:map-marker-path",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TODAY_RT_DISTANCE_KM),
        extra_attr_fn=lambda d: {
            "required_range_km": d.get(KEY_TODAY_RT_REQUIRED_KM),
            "route": "Home → E1 → Home, Home → E2 → Home, …",
        },
    ),
    TripSensorEntityDescription(
        key="today_rt_duration",
        name="Today Round Trip Duration",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TODAY_RT_DURATION_MIN),
    ),
    # ── Tomorrow — shared ─────────────────────────────────────────────
    TripSensorEntityDescription(
        key="tomorrow_events",
        name="Tomorrow's Events with Location",
        icon="mdi:calendar-multiple",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TOMORROW_EVENT_COUNT, 0),
        extra_attr_fn=lambda d: {"events": d.get(KEY_TOMORROW_EVENTS, [])},
    ),
    # ── Tomorrow — sequential (Home → E1 → E2 → … → EN → Home) ───────
    TripSensorEntityDescription(
        key="tomorrow_seq_distance",
        name="Tomorrow Sequential Distance",
        icon="mdi:map-marker-path",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TOMORROW_SEQ_DISTANCE_KM),
        extra_attr_fn=lambda d: {
            "required_range_km": d.get(KEY_TOMORROW_SEQ_REQUIRED_KM),
            "route": "Home → E1 → E2 → … → EN → Home",
        },
    ),
    TripSensorEntityDescription(
        key="tomorrow_seq_duration",
        name="Tomorrow Sequential Duration",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TOMORROW_SEQ_DURATION_MIN),
    ),
    # ── Tomorrow — round-trip (Home → Ei → Home per event) ────────────
    TripSensorEntityDescription(
        key="tomorrow_rt_distance",
        name="Tomorrow Round Trip Distance",
        icon="mdi:map-marker-path",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TOMORROW_RT_DISTANCE_KM),
        extra_attr_fn=lambda d: {
            "required_range_km": d.get(KEY_TOMORROW_RT_REQUIRED_KM),
            "route": "Home → E1 → Home, Home → E2 → Home, …",
        },
    ),
    TripSensorEntityDescription(
        key="tomorrow_rt_duration",
        name="Tomorrow Round Trip Duration",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(KEY_TOMORROW_RT_DURATION_MIN),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Trip Planner sensors."""
    coordinator: SmartTripPlannerCoordinator = entry.runtime_data
    async_add_entities(
        SmartTripSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class SmartTripSensor(
    CoordinatorEntity[SmartTripPlannerCoordinator], SensorEntity
):
    """A sensor entity backed by the SmartTripPlannerCoordinator."""

    entity_description: TripSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartTripPlannerCoordinator,
        description: TripSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Smart EV Trip Planner",
            "model": "EV Trip Advisor",
        }

    @property
    def native_value(self) -> Any:
        """Return sensor value via the description's extractor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes if the description provides them."""
        if self.coordinator.data is None or self.entity_description.extra_attr_fn is None:
            return None
        return self.entity_description.extra_attr_fn(self.coordinator.data)
