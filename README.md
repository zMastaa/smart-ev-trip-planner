# Smart EV Trip Planner — Home Assistant Integration

A HACS custom integration that monitors your Home Assistant Calendar for upcoming events with locations and alerts you when your EV needs charging to reach the destination.

## How it works

1. The integration reads your chosen HA Calendar for the next event that has a **location** field set.
2. It calls the **Google Maps Distance Matrix API** to calculate the real driving distance and estimated journey time from your HA home location to the event.
3. It compares that distance (plus your configured buffer) against your EV's current estimated range.
4. A **binary sensor** turns `on` when your EV cannot make the trip on its current charge.

## Requirements

- Home Assistant 2024.1.0 or newer
- HACS installed
- A calendar integration (Google Calendar, CalDAV, etc.) with events that include a **location** field
- Two EV sensors already in HA:
  - Battery level sensor (%)
  - Estimated range sensor (km or mi — both are handled automatically)
- A **Google Maps API key** with the **Distance Matrix API** enabled

## Getting a Google Maps API key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Go to **APIs & Services → Library** and enable the **Distance Matrix API**
4. Go to **APIs & Services → Credentials** and create an API key
5. Optionally restrict the key to the Distance Matrix API for security

## Installation via HACS

1. Open HACS → Integrations → Custom repositories
2. Add `https://github.com/zmastaa/smart-ev-trip-planner` as type **Integration**
3. Install **Smart EV Trip Planner**
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration** and search for **Smart EV Trip Planner**

## Configuration

During setup you will be asked to select:

| Field | Description |
|---|---|
| Calendar | The HA calendar entity to monitor |
| EV Battery Level Sensor | Sensor reporting battery % |
| EV Estimated Range Sensor | Sensor reporting range remaining (km or mi) |
| Charge Buffer (%) | Extra margin added on top of the driving distance (default 15%) |
| Google Maps API Key | Your Distance Matrix API key (stored securely, masked in the UI) |

Your API key is validated against the Distance Matrix API during setup — you'll see an error immediately if the key is invalid or the API isn't enabled.

## Entities created

| Entity | Type | Description |
|---|---|---|
| `binary_sensor.smart_ev_trip_planner_needs_charging` | Binary Sensor | `on` when EV cannot reach next event |
| `sensor.smart_ev_trip_planner_next_trip_event` | Sensor | Name of the next event with a location |
| `sensor.smart_ev_trip_planner_trip_distance` | Sensor (km/mi) | Real driving distance to the event |
| `sensor.smart_ev_trip_planner_driving_duration` | Sensor (min) | Estimated driving time |
| `sensor.smart_ev_trip_planner_required_range` | Sensor (km/mi) | Driving distance + buffer |
| `sensor.smart_ev_trip_planner_ev_current_range` | Sensor (km/mi) | Current EV range from your sensor |
| `sensor.smart_ev_trip_planner_ev_battery_level` | Sensor (%) | Current battery % from your sensor |

Distance sensors use `SensorDeviceClass.DISTANCE` so Home Assistant automatically displays them in miles if your profile is set to imperial units.

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
        Your EV range is {{ states('sensor.smart_ev_trip_planner_ev_current_range') }}
        but the drive to {{ state_attr('sensor.smart_ev_trip_planner_next_trip_event', 'location') }}
        requires {{ states('sensor.smart_ev_trip_planner_required_range') }}
        (approx. {{ states('sensor.smart_ev_trip_planner_driving_duration') }} min drive).
```

## Notes

- Driving distances and durations are fetched from the **Google Maps Distance Matrix API** — these reflect real road distances, not straight-line estimates.
- Distance results are cached in memory for the duration of the HA session. If the event location changes, the cache will be refreshed on the next update cycle.
- The integration refreshes every 30 minutes.
- Make sure your **Home location is set** in Settings → System → General — this is used as the origin for all distance calculations.
