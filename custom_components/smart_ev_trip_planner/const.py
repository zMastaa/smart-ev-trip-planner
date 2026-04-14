"""Constants for Smart Trip Planner."""

DOMAIN = "smart_ev_trip_planner"
DEFAULT_NAME = "Smart Trip Planner"

# Configuration keys
CONF_CALENDAR_ENTITY = "calendar_entity"
CONF_BATTERY_ENTITY = "battery_entity"
CONF_RANGE_ENTITY = "range_entity"
CONF_BUFFER_PERCENT = "buffer_percent"
CONF_GOOGLE_MAPS_API_KEY = "google_maps_api_key"

# Google Maps Routes API (replaces legacy Distance Matrix API)
GOOGLE_ROUTES_MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
GOOGLE_ROUTES_FIELD_MASK = "originIndex,destinationIndex,distanceMeters,duration,condition"

# Defaults
DEFAULT_BUFFER_PERCENT = 15
DEFAULT_LOOKAHEAD_DAYS = 7
UPDATE_INTERVAL_MINUTES = 30

# ── Next-event data keys ───────────────────────────────────────────────
KEY_NEXT_EVENT_SUMMARY = "next_event_summary"
KEY_NEXT_EVENT_LOCATION = "next_event_location"
KEY_NEXT_EVENT_START = "next_event_start"
KEY_TRIP_DISTANCE_KM = "trip_distance_km"
KEY_TRIP_DURATION_MIN = "trip_duration_min"
KEY_EV_BATTERY_PERCENT = "ev_battery_percent"
KEY_EV_RANGE_KM = "ev_range_km"
KEY_REQUIRED_RANGE_KM = "required_range_km"
KEY_NEEDS_CHARGING = "needs_charging"
KEY_GEOCODE_SUCCESS = "geocode_success"

# ── Tomorrow — shared ──────────────────────────────────────────────────
KEY_TOMORROW_EVENT_COUNT = "tomorrow_event_count"
KEY_TOMORROW_EVENTS = "tomorrow_events"

# ── Tomorrow — sequential route (Home → E1 → E2 → … → EN → Home) ──────
KEY_TOMORROW_SEQ_DISTANCE_KM = "tomorrow_seq_distance_km"
KEY_TOMORROW_SEQ_DURATION_MIN = "tomorrow_seq_duration_min"
KEY_TOMORROW_SEQ_REQUIRED_KM = "tomorrow_seq_required_range_km"
KEY_TOMORROW_SEQ_NEEDS_CHARGING = "tomorrow_seq_needs_charging"

# ── Tomorrow — round-trip route (Home → Ei → Home per event) ──────────
KEY_TOMORROW_RT_DISTANCE_KM = "tomorrow_rt_distance_km"
KEY_TOMORROW_RT_DURATION_MIN = "tomorrow_rt_duration_min"
KEY_TOMORROW_RT_REQUIRED_KM = "tomorrow_rt_required_range_km"
KEY_TOMORROW_RT_NEEDS_CHARGING = "tomorrow_rt_needs_charging"
