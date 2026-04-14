"""DataUpdateCoordinator for Smart Trip Planner."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any

from homeassistant.components.calendar import CalendarEntity
from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_ENTITY,
    CONF_BUFFER_PERCENT,
    CONF_CALENDAR_ENTITY,
    CONF_RANGE_ENTITY,
    DEFAULT_BUFFER_PERCENT,
    DEFAULT_LOOKAHEAD_DAYS,
    DOMAIN,
    KEY_EV_BATTERY_PERCENT,
    KEY_EV_RANGE_KM,
    KEY_GEOCODE_SUCCESS,
    KEY_NEEDS_CHARGING,
    KEY_NEXT_EVENT_LOCATION,
    KEY_NEXT_EVENT_START,
    KEY_NEXT_EVENT_SUMMARY,
    KEY_REQUIRED_RANGE_KM,
    KEY_TRIP_DISTANCE_KM,
    UPDATE_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometres between two points."""
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


class SmartTripPlannerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that checks whether the EV can reach the next calendar event."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.entry = entry
        self.calendar_entity_id: str = entry.data[CONF_CALENDAR_ENTITY]
        self.battery_entity_id: str = entry.data[CONF_BATTERY_ENTITY]
        self.range_entity_id: str = entry.data[CONF_RANGE_ENTITY]
        self.buffer_percent: float = entry.data.get(
            CONF_BUFFER_PERCENT, DEFAULT_BUFFER_PERCENT
        )

        # Simple in-memory geocode cache: location string → (lat, lon)
        self._geocode_cache: dict[str, tuple[float, float]] = {}

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def async_shutdown(self) -> None:
        """Perform any cleanup on unload."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_next_event_with_location(
        self,
    ) -> tuple[str, str, datetime] | None:
        """Return (summary, location, start_dt) for the next event that has a location."""
        now = dt_util.now()
        end = now + timedelta(days=DEFAULT_LOOKAHEAD_DAYS)

        try:
            component = self.hass.data.get(CALENDAR_DOMAIN)
            if component is None:
                _LOGGER.warning("Calendar component not found in hass.data")
                return None

            entity: CalendarEntity | None = component.get_entity(
                self.calendar_entity_id
            )
            if entity is None:
                _LOGGER.warning(
                    "Calendar entity %s not found", self.calendar_entity_id
                )
                return None

            events = await entity.async_get_events(self.hass, now, end)
        except Exception as exc:
            _LOGGER.error("Error fetching calendar events: %s", exc)
            return None

        for event in sorted(events, key=lambda e: e.start_datetime_local):
            location = getattr(event, "location", None) or ""
            if location.strip():
                return event.summary, location.strip(), event.start_datetime_local

        return None

    async def _geocode(self, location: str) -> tuple[float, float] | None:
        """Geocode a location string to (lat, lon), using cache to avoid repeat calls."""
        if location in self._geocode_cache:
            return self._geocode_cache[location]

        try:
            from geopy.geocoders import Nominatim
            from geopy.adapters import AioHTTPAdapter

            async with Nominatim(
                user_agent=f"ha_{DOMAIN}",
                adapter_factory=AioHTTPAdapter,
            ) as geolocator:
                result = await geolocator.geocode(location, timeout=10)

            if result is None:
                _LOGGER.warning("Could not geocode location: %s", location)
                return None

            coords = (result.latitude, result.longitude)
            self._geocode_cache[location] = coords
            return coords

        except Exception as exc:
            _LOGGER.error("Geocoding error for '%s': %s", location, exc)
            return None

    def _home_coordinates(self) -> tuple[float, float] | None:
        """Return HA home (lat, lon) from the config, or None."""
        lat = self.hass.config.latitude
        lon = self.hass.config.longitude
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)

    def _read_sensor_float(self, entity_id: str) -> float | None:
        """Read a numeric sensor state as float, returning None on failure."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            return float(state.state)
        except ValueError:
            _LOGGER.warning("Non-numeric state '%s' for %s", state.state, entity_id)
            return None

    # ------------------------------------------------------------------
    # DataUpdateCoordinator core
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data, compute charge requirement, and return a state dict."""

        # --- EV sensors ---
        battery_pct = self._read_sensor_float(self.battery_entity_id)
        ev_range_km = self._read_sensor_float(self.range_entity_id)

        # --- Next calendar event with a location ---
        event_result = await self._get_next_event_with_location()

        if event_result is None:
            return {
                KEY_NEXT_EVENT_SUMMARY: None,
                KEY_NEXT_EVENT_LOCATION: None,
                KEY_NEXT_EVENT_START: None,
                KEY_TRIP_DISTANCE_KM: None,
                KEY_EV_BATTERY_PERCENT: battery_pct,
                KEY_EV_RANGE_KM: ev_range_km,
                KEY_REQUIRED_RANGE_KM: None,
                KEY_NEEDS_CHARGING: False,
                KEY_GEOCODE_SUCCESS: False,
            }

        summary, location, start_dt = event_result

        # --- Geocode the event location ---
        home = self._home_coordinates()
        trip_distance_km: float | None = None
        geocode_ok = False

        if home is not None:
            coords = await self._geocode(location)
            if coords is not None:
                trip_distance_km = _haversine_km(home[0], home[1], coords[0], coords[1])
                geocode_ok = True

        # --- Compute required range (trip + buffer) ---
        required_range_km: float | None = None
        needs_charging = False

        if trip_distance_km is not None and ev_range_km is not None:
            buffer_factor = 1.0 + (self.buffer_percent / 100.0)
            required_range_km = round(trip_distance_km * buffer_factor, 1)
            needs_charging = ev_range_km < required_range_km

        return {
            KEY_NEXT_EVENT_SUMMARY: summary,
            KEY_NEXT_EVENT_LOCATION: location,
            KEY_NEXT_EVENT_START: start_dt,
            KEY_TRIP_DISTANCE_KM: round(trip_distance_km, 1) if trip_distance_km is not None else None,
            KEY_EV_BATTERY_PERCENT: battery_pct,
            KEY_EV_RANGE_KM: ev_range_km,
            KEY_REQUIRED_RANGE_KM: required_range_km,
            KEY_NEEDS_CHARGING: needs_charging,
            KEY_GEOCODE_SUCCESS: geocode_ok,
        }
