# Smart EV Trip Planner — Home Assistant Integration

A HACS custom integration that monitors your Home Assistant Calendar for upcoming events with locations and alerts you when your EV needs charging to reach the destination.

## How it works

1. The integration reads your chosen HA Calendar for the next event that has a **location** field set.
2. It geocodes that location (via OpenStreetMap/Nominatim — no API key required).
3. It calculates the straight-line distance from your HA home location to the event.
4. It compares that distance (plus your configured buffer) against your EV's current estimated range.
5. A **binary sensor** turns `on` when your EV cannot make the trip on its current charge.

## Requirements

- Home Assistant 2024.1.0 or newer
- HACS installed
- A calendar integration (Google Calendar, CalDAV, etc.) with events that include a location
- Two EV sensors already in HA:
  - Battery level sensor (in %)
  - Estimated range sensor (in km or miles)

## Installation via HACS

1. Open HACS → Integrations → Custom repositories
2. Add `https://github.com/zmastaa/smart-ev-trip-planner` as type **Integration**
3. Install **Smart Trip Planner**
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration** and search for **Smart Trip Planner**

## Configuration

During setup you will be asked to select:

| Field | Description |
|---|---|
| Calendar | The HA calendar entity to monitor |
| EV Battery Level Sensor | Sensor reporting battery % |
| EV Estimated Range Sensor | Sensor reporting range remaining |
| Charge Buffer (%) | Extra margin added on top of the trip distance (default 10 %) |

## Entities created

| Entity | Type | Description |
|---|---|---|
| `sensor.smart_ev_trip_planner_next_trip_event` | Sensor | Name of the next event with a location |
| `sensor.smart_ev_trip_planner_trip_distance` | Sensor (km) | Distance to the event location |
| `sensor.smart_ev_trip_planner_ev_current_range` | Sensor (km) | Current EV range from your sensor |
| `sensor.smart_ev_trip_planner_required_range` | Sensor (km) | Trip distance + buffer |
| `sensor.smart_ev_trip_planner_ev_battery_level` | Sensor (%) | Current battery % from your sensor |
| `binary_sensor.smart_ev_trip_planner_needs_charging` | Binary Sensor | `on` when EV cannot reach next event |

## Example automation

```yaml
alias: Alert EV needs charging before trip
trigger:
  - platform: state
    entity_id: binary_sensor.smart_ev_trip_planner_needs_charging
    to: "on"
action:
  - service: notify.mobile_app
    data:
      title: "EV needs charging!"
      message: >
        Your EV range is {{ states('sensor.smart_ev_trip_planner_ev_current_range') }} km
        but the trip to {{ state_attr('sensor.smart_ev_trip_planner_next_trip_event', 'location') }}
        requires {{ states('sensor.smart_ev_trip_planner_required_range') }} km.
```

## Notes

- Geocoding uses [Nominatim](https://nominatim.openstreetmap.org/) (OpenStreetMap). Results are cached in memory so the same location is only looked up once per HA session.
- Distance is a straight-line (haversine) estimate, not a routed driving distance. Add a generous buffer for real-world trips.
- The integration refreshes every 30 minutes.
