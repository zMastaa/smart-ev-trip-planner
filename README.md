# Smart EV Trip Planner — Home Assistant Integration

A HACS custom integration that monitors your Home Assistant Calendar for upcoming events with locations and alerts you when your EV needs charging to reach the destination — both for the next single trip and for all of tomorrow's events.

## How it works

### Next trip
1. The integration reads your chosen HA Calendar for the next upcoming event that has a **location** field set.
2. It calls the **Google Maps Distance Matrix API** to calculate the real driving distance and estimated journey time from your HA home location to the event.
3. It compares that distance (plus your configured buffer) against your EV's current estimated range.
4. A **binary sensor** turns `on` when your EV cannot make the trip on its current charge.

### Tomorrow's events
The integration also looks ahead at all of tomorrow's calendar events that have a location and calculates two independent distance totals, always running both simultaneously:

| Mode | Route | Best represents |
|---|---|---|
| **Sequential** | Home → E1 → E2 → E3 → Home | A day out where you drive between events without going home in between |
| **Round trip** | Home → E1 → Home, Home → E2 → Home, … | A day of separate trips where you return home between each event |

A dedicated binary sensor and pair of distance/duration sensors are exposed for each mode, so you can decide which is most relevant for your day.

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

### Next trip

| Entity | Type | Description |
|---|---|---|
| `binary_sensor.…_needs_charging` | Binary Sensor | `on` when EV cannot reach the next event |
| `sensor.…_next_trip_event` | Sensor | Name and location of the next event |
| `sensor.…_trip_distance` | Sensor (km/mi) | Driving distance to the next event |
| `sensor.…_driving_duration` | Sensor (min) | Estimated driving time to the next event |
| `sensor.…_required_range` | Sensor (km/mi) | Trip distance + buffer |
| `sensor.…_ev_current_range` | Sensor (km/mi) | Current EV range from your sensor |
| `sensor.…_ev_battery_level` | Sensor (%) | Current battery % from your sensor |

### Tomorrow's events

| Entity | Type | Description |
|---|---|---|
| `binary_sensor.…_tomorrow_sequential_needs_charging` | Binary Sensor | `on` when EV can't cover the sequential route |
| `binary_sensor.…_tomorrow_round_trip_needs_charging` | Binary Sensor | `on` when EV can't cover all individual round trips |
| `sensor.…_tomorrows_events_with_location` | Sensor | Count of tomorrow's events with a location (full list in attributes) |
| `sensor.…_tomorrow_sequential_distance` | Sensor (km/mi) | Total distance: Home → E1 → E2 → … → Home |
| `sensor.…_tomorrow_sequential_duration` | Sensor (min) | Total driving time for the sequential route |
| `sensor.…_tomorrow_round_trip_distance` | Sensor (km/mi) | Total distance: all individual round trips combined |
| `sensor.…_tomorrow_round_trip_duration` | Sensor (min) | Total driving time for all round trips |

All distance sensors use `SensorDeviceClass.DISTANCE` so Home Assistant automatically displays them in miles if your profile is set to imperial units.

## Google Maps API usage

Every unique origin→destination pair is fetched once per HA session and then cached in memory, so the same location is never looked up twice while HA is running. Calls are only made on a refresh cycle (every 30 minutes) when a new, uncached location is encountered.

### How many API calls per refresh?

**Next trip:** always 1 call (Home → next event).

**Tomorrow's events:** depends on the number of events with locations.

> **Example: 3 events tomorrow** (e.g. gym, dentist, dinner)
>
> Sequential route legs: Home→Gym, Gym→Dentist, Dentist→Dinner, Dinner→Home = **4 calls**
> Round-trip outbound legs: Home→Gym, Home→Dentist, Home→Dinner = **3 calls** *(but Home→Gym and Home→Dentist were already cached from the sequential pass, so only 1 new call)*
>
> **Total new API calls on first refresh: 1 (next trip) + 4 (sequential) + 1 (uncached round-trip leg) = 6**

> **Example: 5 events tomorrow** (e.g. school run, coffee, physio, supermarket, football)
>
> Sequential legs: Home→E1, E1→E2, E2→E3, E3→E4, E4→E5, E5→Home = **6 calls**
> Round-trip outbound legs: Home→E1 through Home→E5 = **5 calls** *(Home→E1 already cached, so 4 new calls)*
>
> **Total new API calls on first refresh: 1 (next trip) + 6 (sequential) + 4 (uncached round-trip legs) = 11**

On subsequent refreshes the cache is hit for all known locations, so **0 additional API calls** are made unless an event's location string changes.

The [Distance Matrix API free tier](https://mapsplatform.google.com/pricing/) covers 40,000 elements per month at no cost, which is far more than this integration will consume in normal use.

## Example automations

### Alert when the next trip needs charging

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
        (approx. {{ states('sensor.smart_ev_trip_planner_driving_duration') }} min).
```

### Alert the evening before a busy day

```yaml
alias: Evening alert for tomorrow's trips
trigger:
  - platform: time
    at: "20:00:00"
condition:
  - condition: state
    entity_id: binary_sensor.smart_ev_trip_planner_tomorrow_sequential_needs_charging
    state: "on"
action:
  - service: notify.mobile_app
    data:
      title: "Charge your EV tonight!"
      message: >
        Tomorrow you have {{ states('sensor.smart_ev_trip_planner_tomorrows_events_with_location') }}
        events. The full day's driving is
        {{ states('sensor.smart_ev_trip_planner_tomorrow_sequential_distance') }} km
        but your current range is only
        {{ states('sensor.smart_ev_trip_planner_ev_current_range') }} km.
```

## Notes

- Driving distances and durations reflect real road distances via the Google Maps Distance Matrix API, not straight-line estimates.
- Results are cached in memory per session. If an event location string changes, the new location is fetched on the next refresh cycle.
- The integration refreshes every 30 minutes.
- Make sure your **Home location is set** in Settings → System → General — this is used as the origin for all distance calculations.
