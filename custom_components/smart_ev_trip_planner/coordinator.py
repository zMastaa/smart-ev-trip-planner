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
    GOOGLE_ROUTES_FIELD_MASK,
    GOOGLE_ROUTES_MATRIX_URL,
    KEY_EV_BATTERY_PERCENT,
    KEY_EV_RANGE_KM,
    KEY_GEOCODE_SUCCESS,
    KEY_NEEDS_CHARGING,
    KEY_NEXT_EVENT_LOCATION,
    KEY_NEXT_EVENT_START,
    KEY_NEXT_EVENT_SUMMARY,
    KEY_REQUIRED_RANGE_KM,
    KEY_TODAY_EVENT_COUNT,
    KEY_TODAY_EVENTS,
    KEY_TODAY_RT_DISTANCE_KM,
    KEY_TODAY_RT_DURATION_MIN,
    KEY_TODAY_RT_NEEDS_CHARGING,
    KEY_TODAY_RT_REQUIRED_KM,
    KEY_TODAY_SEQ_DISTANCE_KM,
    KEY_TODAY_SEQ_DURATION_MIN,
    KEY_TODAY_SEQ_NEEDS_CHARGING,
    KEY_TODAY_SEQ_REQUIRED_KM,
    KEY_TOMORROW_EVENT_COUNT,
    KEY_TOMORROW_EVENTS,
    KEY_TOMORROW_RT_DISTANCE_KM,
    KEY_TOMORROW_RT_DURATION_MIN,
    KEY_TOMORROW_RT_NEEDS_CHARGING,
    KEY_TOMORROW_RT_REQUIRED_KM,
    KEY_TOMORROW_SEQ_DISTANCE_KM,
    KEY_TOMORROW_SEQ_DURATION_MIN,
    KEY_TOMORROW_SEQ_NEEDS_CHARGING,
    KEY_TOMORROW_SEQ_REQUIRED_KM,
    KEY_TRIP_DISTANCE_KM,
    KEY_TRIP_DURATION_MIN,
    UPDATE_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

MILES_TO_KM = 1.60934


def _parse_waypoint(location: str) -> dict:
    """
    Return a Routes API waypoint dict.
    If the string looks like 'lat,lon' it becomes a latLng; otherwise treated as an address.
    """
    parts = location.split(",", 1)
    if len(parts) == 2:
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            return {"location": {"latLng": {"latitude": lat, "longitude": lon}}}
        except ValueError:
            pass
    return {"address": location}


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

        # Cache: (origin, destination) → (driving_distance_km, duration_min)
        self._distance_cache: dict[tuple[str, str], tuple[float, float]] = {}

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

    def _home_origin(self) -> str | None:
        """Return the HA home location as a 'lat,lon' string for use as a route origin."""
        lat = self.hass.config.latitude
        lon = self.hass.config.longitude
        if lat is None or lon is None:
            _LOGGER.error(
                "Home coordinates are not set in Home Assistant. "
                "Please set your home location in Settings → System → General."
            )
            return None
        return f"{lat},{lon}"

    async def _get_calendar_events(
        self, start: datetime, end: datetime
    ) -> list[Any]:
        """Fetch raw events from the configured calendar entity."""
        component = self.hass.data.get(CALENDAR_DOMAIN)
        if component is None:
            _LOGGER.warning("Calendar component not found in hass.data")
            return []

        entity: CalendarEntity | None = component.get_entity(self.calendar_entity_id)
        if entity is None:
            _LOGGER.warning("Calendar entity %s not found", self.calendar_entity_id)
            return []

        try:
            return await entity.async_get_events(self.hass, start, end)
        except Exception as exc:
            _LOGGER.error("Error fetching calendar events: %s", exc)
            return []

    async def _get_next_event_with_location(
        self,
    ) -> tuple[str, str, datetime] | None:
        """Return (summary, location, start_dt) for the next upcoming event with a location."""
        now = dt_util.now()
        events = await self._get_calendar_events(
            now, now + timedelta(days=DEFAULT_LOOKAHEAD_DAYS)
        )

        for event in sorted(events, key=lambda e: e.start_datetime_local):
            location = getattr(event, "location", None) or ""
            if location.strip():
                return event.summary, location.strip(), event.start_datetime_local

        return None

    async def _get_today_remaining_events_with_locations(
        self,
    ) -> list[tuple[str, str, datetime]]:
        """Return today's not-yet-started events that have a location, sorted by start time."""
        now = dt_util.now()
        today_end = dt_util.start_of_local_day(now) + timedelta(days=1)

        events = await self._get_calendar_events(now, today_end)

        result = []
        for event in sorted(events, key=lambda e: e.start_datetime_local):
            location = getattr(event, "location", None) or ""
            if location.strip():
                result.append(
                    (event.summary, location.strip(), event.start_datetime_local)
                )
        return result

    async def _get_tomorrow_events_with_locations(
        self,
    ) -> list[tuple[str, str, datetime]]:
        """Return all tomorrow events that have a location, sorted by start time."""
        now = dt_util.now()
        tomorrow_start = dt_util.start_of_local_day(now + timedelta(days=1))
        tomorrow_end = tomorrow_start + timedelta(days=1)

        events = await self._get_calendar_events(tomorrow_start, tomorrow_end)

        result = []
        for event in sorted(events, key=lambda e: e.start_datetime_local):
            location = getattr(event, "location", None) or ""
            if location.strip():
                result.append(
                    (event.summary, location.strip(), event.start_datetime_local)
                )
        return result

    async def _get_driving_distance(
        self, origin: str, destination: str
    ) -> tuple[float, float] | None:
        """
        Return (driving_distance_km, duration_min) between any two points via
        the Google Maps Routes API (computeRouteMatrix), with in-memory caching.
        """
        cache_key = (origin, destination)
        if cache_key in self._distance_cache:
            return self._distance_cache[cache_key]

        body = {
            "origins": [{"waypoint": _parse_waypoint(origin)}],
            "destinations": [{"waypoint": _parse_waypoint(destination)}],
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_UNAWARE",
        }
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": GOOGLE_ROUTES_FIELD_MASK,
            "Content-Type": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    GOOGLE_ROUTES_MATRIX_URL, json=body, headers=headers
                ) as resp:
                    resp.raise_for_status()
                    results = await resp.json()

            if not results:
                _LOGGER.warning(
                    "Routes API returned empty response for '%s' → '%s'",
                    origin,
                    destination,
                )
                return None

            element = results[0]
            condition = element.get("condition", "")
            if condition != "ROUTE_EXISTS":
                _LOGGER.warning(
                    "Routes API condition '%s' for '%s' → '%s'",
                    condition,
                    origin,
                    destination,
                )
                return None

            distance_km = round(element["distanceMeters"] / 1000, 1)
            # duration is returned as a string like "672s"
            duration_min = round(int(element["duration"].rstrip("s")) / 60, 0)

            result = (distance_km, duration_min)
            self._distance_cache[cache_key] = result
            _LOGGER.debug(
                "Routes API '%s' → '%s': %.1f km, %.0f min",
                origin,
                destination,
                distance_km,
                duration_min,
            )
            return result

        except aiohttp.ClientResponseError as exc:
            if exc.status in (401, 403):
                _LOGGER.error(
                    "Routes API authentication failed for '%s' → '%s' (HTTP %d). "
                    "Check your API key and that the Routes API is enabled.",
                    origin,
                    destination,
                    exc.status,
                )
            else:
                _LOGGER.error(
                    "Routes API HTTP %d for '%s' → '%s': %s",
                    exc.status,
                    origin,
                    destination,
                    exc,
                )
        except aiohttp.ClientError as exc:
            _LOGGER.error(
                "Network error calling Routes API '%s' → '%s': %s",
                origin,
                destination,
                exc,
            )
        except Exception as exc:
            _LOGGER.error(
                "Unexpected error calling Routes API '%s' → '%s': %s",
                origin,
                destination,
                exc,
            )

        return None

    async def _get_sequential_route_distance(
        self, home: str, locations: list[str]
    ) -> tuple[float, float] | None:
        """
        Home → E1 → E2 → ... → EN → Home  (events visited in chronological order).
        Returns (total_km, total_min), or None if any leg cannot be resolved.
        """
        stops = [home, *locations, home]
        total_km = 0.0
        total_min = 0.0

        for i in range(len(stops) - 1):
            leg = await self._get_driving_distance(stops[i], stops[i + 1])
            if leg is None:
                _LOGGER.warning(
                    "Could not calculate leg %d of tomorrow's sequential route "
                    "('%s' → '%s'). Sequential totals will be unavailable.",
                    i + 1,
                    stops[i],
                    stops[i + 1],
                )
                return None
            total_km += leg[0]
            total_min += leg[1]

        return round(total_km, 1), round(total_min, 0)

    async def _get_round_trip_route_distance(
        self, home: str, locations: list[str]
    ) -> tuple[float, float] | None:
        """
        Home → E1 → Home, Home → E2 → Home, …  (independent round trip per event).
        The return leg reuses the cached outbound distance (roads are symmetric).
        Returns (total_km, total_min), or None if any outbound leg cannot be resolved.
        """
        total_km = 0.0
        total_min = 0.0

        for i, loc in enumerate(locations):
            leg = await self._get_driving_distance(home, loc)
            if leg is None:
                _LOGGER.warning(
                    "Could not calculate outbound leg %d of tomorrow's round-trip route "
                    "('%s' → '%s'). Round-trip totals will be unavailable.",
                    i + 1,
                    home,
                    loc,
                )
                return None
            # Count outbound + return (both legs assumed equal distance)
            total_km += leg[0] * 2
            total_min += leg[1] * 2

        return round(total_km, 1), round(total_min, 0)

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
        """Fetch all data, compute charge requirements, and return a state dict."""

        # --- EV sensors ---
        battery_pct = self._read_sensor_float(self.battery_entity_id)
        ev_range_km = self._read_range_as_km(self.range_entity_id)
        buffer_factor = 1.0 + (self.buffer_percent / 100.0)

        # ── Next upcoming event ────────────────────────────────────────
        event_result = await self._get_next_event_with_location()

        trip_distance_km: float | None = None
        trip_duration_min: float | None = None
        required_range_km: float | None = None
        needs_charging = False
        lookup_ok = False
        summary = location = start_dt = None

        if event_result is not None:
            summary, location, start_dt = event_result
            home = self._home_origin()
            if home is not None:
                driving = await self._get_driving_distance(home, location)
                if driving is not None:
                    trip_distance_km, trip_duration_min = driving
                    lookup_ok = True

            if trip_distance_km is not None and ev_range_km is not None:
                required_range_km = round(trip_distance_km * buffer_factor, 1)
                needs_charging = ev_range_km < required_range_km

        # ── Today's remaining events ───────────────────────────────────
        today_events_raw = await self._get_today_remaining_events_with_locations()
        today_locations = [loc for _, loc, _ in today_events_raw]
        today_home = self._home_origin()

        today_seq_total_km: float | None = None
        today_seq_total_min: float | None = None
        today_seq_required_km: float | None = None
        today_seq_needs_charging = False

        today_rt_total_km: float | None = None
        today_rt_total_min: float | None = None
        today_rt_required_km: float | None = None
        today_rt_needs_charging = False

        if today_events_raw and today_home is not None:
            today_seq = await self._get_sequential_route_distance(today_home, today_locations)
            if today_seq is not None:
                today_seq_total_km, today_seq_total_min = today_seq
                if ev_range_km is not None:
                    today_seq_required_km = round(today_seq_total_km * buffer_factor, 1)
                    today_seq_needs_charging = ev_range_km < today_seq_required_km

            today_rt = await self._get_round_trip_route_distance(today_home, today_locations)
            if today_rt is not None:
                today_rt_total_km, today_rt_total_min = today_rt
                if ev_range_km is not None:
                    today_rt_required_km = round(today_rt_total_km * buffer_factor, 1)
                    today_rt_needs_charging = ev_range_km < today_rt_required_km

        today_events_list = [
            {"summary": s, "location": loc, "start": t.isoformat()}
            for s, loc, t in today_events_raw
        ]

        # ── Tomorrow's events ──────────────────────────────────────────
        tomorrow_events_raw = await self._get_tomorrow_events_with_locations()
        tomorrow_locations = [loc for _, loc, _ in tomorrow_events_raw]
        tomorrow_home = self._home_origin()

        # Sequential: Home → E1 → E2 → … → EN → Home
        seq_total_km: float | None = None
        seq_total_min: float | None = None
        seq_required_km: float | None = None
        seq_needs_charging = False

        # Round-trip: (Home → E1 → Home) + (Home → E2 → Home) + …
        rt_total_km: float | None = None
        rt_total_min: float | None = None
        rt_required_km: float | None = None
        rt_needs_charging = False

        if tomorrow_events_raw and tomorrow_home is not None:
            seq = await self._get_sequential_route_distance(tomorrow_home, tomorrow_locations)
            if seq is not None:
                seq_total_km, seq_total_min = seq
                if ev_range_km is not None:
                    seq_required_km = round(seq_total_km * buffer_factor, 1)
                    seq_needs_charging = ev_range_km < seq_required_km

            rt = await self._get_round_trip_route_distance(tomorrow_home, tomorrow_locations)
            if rt is not None:
                rt_total_km, rt_total_min = rt
                if ev_range_km is not None:
                    rt_required_km = round(rt_total_km * buffer_factor, 1)
                    rt_needs_charging = ev_range_km < rt_required_km

        tomorrow_events_list = [
            {"summary": s, "location": loc, "start": t.isoformat()}
            for s, loc, t in tomorrow_events_raw
        ]

        return {
            # Today remaining
            KEY_TODAY_EVENT_COUNT: len(today_events_raw),
            KEY_TODAY_EVENTS: today_events_list,
            KEY_TODAY_SEQ_DISTANCE_KM: today_seq_total_km,
            KEY_TODAY_SEQ_DURATION_MIN: today_seq_total_min,
            KEY_TODAY_SEQ_REQUIRED_KM: today_seq_required_km,
            KEY_TODAY_SEQ_NEEDS_CHARGING: today_seq_needs_charging,
            KEY_TODAY_RT_DISTANCE_KM: today_rt_total_km,
            KEY_TODAY_RT_DURATION_MIN: today_rt_total_min,
            KEY_TODAY_RT_REQUIRED_KM: today_rt_required_km,
            KEY_TODAY_RT_NEEDS_CHARGING: today_rt_needs_charging,
            # Next event
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
            # Tomorrow shared
            KEY_TOMORROW_EVENT_COUNT: len(tomorrow_events_raw),
            KEY_TOMORROW_EVENTS: tomorrow_events_list,
            # Tomorrow sequential
            KEY_TOMORROW_SEQ_DISTANCE_KM: seq_total_km,
            KEY_TOMORROW_SEQ_DURATION_MIN: seq_total_min,
            KEY_TOMORROW_SEQ_REQUIRED_KM: seq_required_km,
            KEY_TOMORROW_SEQ_NEEDS_CHARGING: seq_needs_charging,
            # Tomorrow round-trip
            KEY_TOMORROW_RT_DISTANCE_KM: rt_total_km,
            KEY_TOMORROW_RT_DURATION_MIN: rt_total_min,
            KEY_TOMORROW_RT_REQUIRED_KM: rt_required_km,
            KEY_TOMORROW_RT_NEEDS_CHARGING: rt_needs_charging,
        }
