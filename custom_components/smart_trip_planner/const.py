"""Constants for Smart Trip Planner."""

DOMAIN = "smart_ev_trip_planner"
DEFAULT_NAME = "Smart Trip Planner"

# Configuration keys
CONF_CALENDAR_ENTITY = "calendar_entity"
CONF_BATTERY_ENTITY = "battery_entity"
CONF_RANGE_ENTITY = "range_entity"
CONF_BUFFER_PERCENT = "buffer_percent"

# Defaults
DEFAULT_BUFFER_PERCENT = 10
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
