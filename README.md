# Smart EV Trip Planner — Home Assistant Integration

A HACS custom integration that monitors your Home Assistant Calendar for upcoming events with locations and alerts you when your EV needs charging to reach the destination — both for the next single trip and for all of tomorrow's events.

## How it works

### Next trip
1. The integration reads your chosen HA Calendar for the next upcoming event that has a **location** field set.
2. It calls the **Google Maps Routes API** to calculate the real driving distance and estimated journey time from your HA home location to the event.
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
- A **Google Maps API key** with the **Routes API** enabled

## Getting a Google Maps API key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Go to **APIs & Services → Library** and enable the **Routes API**
4. Go to **APIs & Services → Credentials** and create an API key
5. Optionally restrict the key to the Routes API for security

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
| Google Maps API Key | Your Routes API key (stored securely, masked in the UI) |

Your API key is validated against the Routes API during setup — you'll see an error immediately if the key is invalid or the API isn't enabled.

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

## Google Maps API Usage & Cost Management

### Billing Model: Routes API (`computeRouteMatrix`)
This application utilizes the Google Routes API, specifically the `computeRouteMatrix` method. 

**Cost Calculation:**
Google bills this API based on **elements** (where $Elements = Origins \times Destinations$). To ensure maximum cost-efficiency and predictability, this integration is architected to always send exactly **one origin and one destination per request**. Consequently, each API call consumes exactly **1 element**.

Google provides a recurring **\$200 monthly credit** to all billing accounts. At the standard rate (~$5–$10 per 1,000 elements), this allows for tens of thousands of free elements per month. This application is designed to stay well below this threshold.

### Caching Strategy
To minimize API latency and prevent redundant billing, the application implements a multi-layer caching strategy:
1. **In-Memory Cache:** Every unique origin $\to$ destination pair is cached in memory for the duration of the session. If a leg has been calculated once, it is never re-fetched until the cache expires.
2. **30-Minute Refresh Cycle:** The application performs a periodic check. Only "new" or "unvisited" legs (legs not present in the current cache) trigger a new `computeRouteMatrix` call.

### Usage Estimation (Worst-Case Scenario)
The table below estimates the "Cold Start" cost (the first refresh of the day when the cache is empty). We assume the application must calculate both the **sequential path** ($Home \to E_1 \to E_2$) and the **round-trip capability** ($Home \to E_n$).

| Events Tomorrow | Sequential Legs (Elements) | Round-Trip New Legs* | Total Elements (First Refresh) |
| :--- | :---: | :---: | :---: |
| 1 Event | 2 | 0 | **2** |
| 2 Events | 3 | 1 | **4** |
| 3 Events | 4 | 2 | **6** |
| 4 Events | 5 | 3 | **8** |
| 5 Events | 6 | 4 | **10** |

*\*The round-trip pass reuses the $Home \to E_1$ element from the sequential pass. Each subsequent $Home \to E_n$ is a new element.*

#### Example Breakdown (3 Events: Gym, Dentist, Dinner)
**Initial Refresh (Cold Cache):**
* **Sequential Pass (4 elements):** `Home→Gym`, `Gym→Dentist`, `Dintist→Dinner`, `Dinner→Home`
* **Round-trip Pass (2 elements):** `Home→Dentist`, `Home→Dinner` (Note: `Home→Gym` is skipped as it is already cached).
* **Next-trip Lookup (1 element):** `Home→[Next Event]` 
* **Total:** **7 Elements**

**Subsequent Refreshes (Warm Cache):**
* All legs are already present in memory.
* **Total: 0 Elements**

### Conclusion
Even with a heavy schedule of 5+ events per day, the application consumes approximately **11 elements per day**. This results in roughly **330 elements per month**, which is less than **2%** of the estimated free monthly credit provided by Google.

### Capping API usage for peace of mind

Even though normal usage stays well inside the free tier, you can set a hard quota cap on the Routes API so it stops accepting requests once a limit you choose is reached. This guarantees you can never be charged beyond what you are comfortable with.

1. In the [Google Cloud Console](https://console.cloud.google.com/), go to **APIs & Services → Dashboard** and select your project.
2. Click on the **Routes API** in your enabled APIs list.
3. Open the **Quotas** tab.
4. Use the filter to find the quota you want to cap (e.g. *Requests per day*).
5. Check the checkbox next to it and click **Edit quotas**.
6. Enter your desired limit and submit the request.

> **Note:** Quota enforcement has a small lag, so Google recommends setting your cap slightly below your true limit if you are using it to control billing. See the [Google documentation on capping API usage](https://docs.cloud.google.com/apis/docs/capping-api-usage) for full details.

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

- Driving distances and durations reflect real road distances via the Google Maps Routes API, not straight-line estimates.
- Results are cached in memory per session. If an event location string changes, the new location is fetched on the next refresh cycle.
- The integration refreshes every 30 minutes.
- Make sure your **Home location is set** in Settings → System → General — this is used as the origin for all distance calculations.
