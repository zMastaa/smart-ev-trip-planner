"""Constants for Smart Trip Planner."""

DOMAIN = "smart_ev_trip_planner"
DEFAULT_NAME = "Smart Trip Planner"

# Configuration keys
CONF_CALENDAR_ENTITY = "calendar_entity"
CONF_BATTERY_ENTITY = "battery_entity"
CONF_RANGE_ENTITY = "range_entity"
CONF_BUFFER_PERCENT = "buffer_percent"
CONF_GOOGLE_MAPS_API_KEY = "google_maps_api_key"
CONF_ROUTING_MODE = "routing_mode"

# Routing modes for tomorrow's events
ROUTING_MODE_SEQUENTIAL = "sequential"   # Home → E1 → E2 → ... → EN → Home
ROUTING_MODE_ROUND_TRIP = "round_trip"   # Home → E1 → Home, Home → E2 → Home, …
DEFAULT_ROUTING_MODE = ROUTING_MODE_SEQUENTIAL

# Google Maps
GOOGLE_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

# Data keys returned by coordinator
KEY_TRIP_DURATION_MIN = "trip_duration_min"

# Defaults
DEFAULT_BUFFER_PERCENT = 15
DEFAULT_LOOKAHEAD_DAYS = 7
UPDATE_INTERVAL_MINUTES = 30

# Data keys returned by coordinator
KEY_NEXT_EVENT_SUMMARY = "next_event_summary"
KEY_NEXT_EVENT_LOCATION = "next_event_location"
KEY_NEXT_EVENT_START = "next_event_start"
KEY_TRIP_DISTANCE_KM = "trip_distance_km"
KEY_EV_BATTERY_PERCENT = "ev_battery_percent"
KEY_EV_RANGE_KM = "ev_range_km"
KEY_REQUIRED_RANGE_KM = "required_range_km"
KEY_NEEDS_CHARGING = "needs_charging"
KEY_GEOCODE_SUCCESS = "geocode_success"

# Tomorrow's events data keys
KEY_TOMORROW_EVENT_COUNT = "tomorrow_event_count"
KEY_TOMORROW_EVENTS = "tomorrow_events"
KEY_TOMORROW_TOTAL_DISTANCE_KM = "tomorrow_total_distance_km"
KEY_TOMORROW_TOTAL_DURATION_MIN = "tomorrow_total_duration_min"
KEY_TOMORROW_REQUIRED_RANGE_KM = "tomorrow_required_range_km"
KEY_TOMORROW_NEEDS_CHARGING = "tomorrow_needs_charging"
KEY_TOMORROW_ROUTE_DESCRIPTION = "tomorrow_route_description"
