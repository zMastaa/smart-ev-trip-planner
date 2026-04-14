"""DataUpdateCoordinator for Smart EV Trip Planner."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

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
    CONF_GOOGLE_MAPS_API_KEY,
    CONF_RANGE_ENTITY,
    DEFAULT_BUFFER_PERCENT,
    DEFAULT_LOOKAHEAD_DAYS,
    DOMAIN,
    GOOGLE_DISTANCE_MATRIX_URL,
    KEY_EV_BATTERY_PERCENT,
    KEY_EV_RANGE_KM,
    KEY_GEOCODE_SUCCESS,
    KEY_NEEDS_CHARGING,
    KEY_NEXT_EVENT_LOCATION,
    KEY_NEXT_EVENT_START,
    KEY_NEXT_EVENT_SUMMARY,
    KEY_REQUIRED_RANGE_KM,
    KEY_TRIP_DISTANCE_KM,
    KEY_TRIP_DURATION_MIN,
    UPDATE_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

MILES_TO_KM = 1.60934


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
        self._api_key: str = entry.data[CONF_GOOGLE_MAPS_API_KEY]

        # Cache: location string → (driving_distance_km, duration_min)
        self._distance_cache: dict[str, tuple[float, float]] = {}

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

    def _home_origin(self) -> str | None:
        """Return the HA home location as a 'lat,lon' string for the Distance Matrix origin."""
        lat = self.hass.config.latitude
        lon = self.hass.config.longitude
        if lat is None or lon is None:
            _LOGGER.error(
                "Home coordinates are not set in Home Assistant. "
                "Please set your home location in Settings → System → General."
            )
            return None
        return f"{lat},{lon}"

    async def _get_driving_distance(
        self, destination: str
    ) -> tuple[float, float] | None:
        """
        Return (driving_distance_km, duration_min) from home to destination via
        Google Maps Distance Matrix API, with in-memory caching.
        """
        if destination in self._distance_cache:
            return self._distance_cache[destination]

        origin = self._home_origin()
        if origin is None:
            return None

        params = {
            "origins": origin,
            "destinations": destination,
            "mode": "driving",
            "units": "metric",
            "key": self._api_key,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    GOOGLE_DISTANCE_MATRIX_URL, params=params
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

            top_status = data.get("status")
            if top_status != "OK":
                _LOGGER.warning(
                    "Distance Matrix API returned top-level status '%s' for '%s'",
                    top_status,
                    destination,
                )
                return None

            element = data["rows"][0]["elements"][0]
            el_status = element.get("status")
            if el_status != "OK":
                _LOGGER.warning(
                    "Distance Matrix element status '%s' for destination '%s'",
                    el_status,
                    destination,
                )
                return None

            distance_km = round(element["distance"]["value"] / 1000, 1)
            duration_min = round(element["duration"]["value"] / 60, 0)

            result = (distance_km, duration_min)
            self._distance_cache[destination] = result
            _LOGGER.debug(
                "Driving distance to '%s': %.1f km, %.0f min",
                destination,
                distance_km,
                duration_min,
            )
            return result

        except aiohttp.ClientError as exc:
            _LOGGER.error(
                "Network error fetching driving distance for '%s': %s", destination, exc
            )
        except Exception as exc:
            _LOGGER.error(
                "Unexpected error fetching driving distance for '%s': %s", destination, exc
            )

        return None

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

    def _read_range_as_km(self, entity_id: str) -> float | None:
        """Read a range sensor and always return its value in km, converting from miles if needed."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            value = float(state.state)
        except ValueError:
            _LOGGER.warning("Non-numeric state '%s' for %s", state.state, entity_id)
            return None

        unit = (state.attributes.get("unit_of_measurement") or "").lower()
        if unit in ("mi", "miles", "mile"):
            _LOGGER.debug(
                "Range sensor %s is in miles (%s mi) — converting to km",
                entity_id,
                value,
            )
            return round(value * MILES_TO_KM, 1)
        return value

    # ------------------------------------------------------------------
    # DataUpdateCoordinator core
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data, compute charge requirement, and return a state dict."""

        # --- EV sensors ---
        battery_pct = self._read_sensor_float(self.battery_entity_id)
        ev_range_km = self._read_range_as_km(self.range_entity_id)

        # --- Next calendar event with a location ---
        event_result = await self._get_next_event_with_location()

        if event_result is None:
            return {
                KEY_NEXT_EVENT_SUMMARY: None,
                KEY_NEXT_EVENT_LOCATION: None,
                KEY_NEXT_EVENT_START: None,
                KEY_TRIP_DISTANCE_KM: None,
                KEY_TRIP_DURATION_MIN: None,
                KEY_EV_BATTERY_PERCENT: battery_pct,
                KEY_EV_RANGE_KM: ev_range_km,
                KEY_REQUIRED_RANGE_KM: None,
                KEY_NEEDS_CHARGING: False,
                KEY_GEOCODE_SUCCESS: False,
            }

        summary, location, start_dt = event_result

        # --- Get driving distance + duration via Google Maps ---
        trip_distance_km: float | None = None
        trip_duration_min: float | None = None
        lookup_ok = False

        driving = await self._get_driving_distance(location)
        if driving is not None:
            trip_distance_km, trip_duration_min = driving
            lookup_ok = True

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
            KEY_TRIP_DISTANCE_KM: trip_distance_km,
            KEY_TRIP_DURATION_MIN: trip_duration_min,
            KEY_EV_BATTERY_PERCENT: battery_pct,
            KEY_EV_RANGE_KM: ev_range_km,
            KEY_REQUIRED_RANGE_KM: required_range_km,
            KEY_NEEDS_CHARGING: needs_charging,
            KEY_GEOCODE_SUCCESS: lookup_ok,
        }
