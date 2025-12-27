# Wodify Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacs-shield]][hacs]

A Home Assistant integration for Wodify gym management system. Track classes, receive notifications, and automate your home based on your gym schedule.

## Features

### Core Functionality
- **Real-time class tracking** - Monitor upcoming classes with automatic updates every 5 minutes (configurable 1-60 min)
- **Smart class blocks** - Automatically detects back-to-back classes (within 30 minutes)
- **Configurable notifications** - Set custom timing for before-class and after-block alerts
- **Binary sensor** - Know instantly if you're currently in a class
- **Next class sensor** - Always see what's coming up next with full details
- **Calendar integration** - View your gym schedule in Home Assistant's calendar

### Automation Events
- `wodify_class_starts_soon` - Fires before a class starts (default: 15 min)
- `wodify_class_block_done` - Fires after a class block ends (default: 15 min)
- `wodify_class_cancelled` - Fires when a scheduled class is cancelled

### Optimized Design
- **Efficient API usage** - Fetches 7 days of upcoming class data
- **Coach information** - Automatically fetches coach names for the next 10 upcoming classes
- **Multiple coach support** - Displays all assigned coaches (e.g., "Nick Alexander & Sarah Smith")
- **No external dependencies** - Uses only Home Assistant built-in libraries
- **Multi-step config flow** - Select specific locations and programs to track
- **Re-authentication support** - Easily update API keys when needed

## Requirements

- Home Assistant 2024.1.0 or newer
- Wodify API key (requires gym owner/administrator access)
- Active internet connection

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kurtislanderson&repository=ha-wodify-admin&category=integration)

1. Click the button above or manually add this repository to HACS
2. Search for "Wodify" in HACS
3. Click "Download"
4. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy the `custom_components/wodify` folder to your `config/custom_components/`
3. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Wodify"
3. Enter your Wodify API key
4. Select the gym locations to track
5. Select the programs to include
6. Configure timing options:
   - **Update interval**: How often to refresh data (1-60 min, default: 5)
   - **Before class minutes**: How early to notify before classes (5-60 min, default: 15)
   - **After block minutes**: How long after blocks to notify (5-60 min, default: 15)

### Options

You can adjust settings at any time through the integration options:
1. Go to the Wodify integration
2. Click "Configure"
3. Adjust timing preferences, locations, or programs
4. Changes take effect immediately

## Entities

### Next Class Sensor
- **Entity ID**: `sensor.wodify_next_class`
- **State**: Description of the next upcoming class (e.g., "6:00 AM WOD at 6:00 AM with Coach Name")
- **Attributes**:
  - `class_id`: Unique identifier for the class
  - `class_name`: Name of the class
  - `coach`: Instructor name
  - `location`: Gym location
  - `program`: Program name
  - `start_time`: When the class starts
  - `end_time`: When the class ends
  - `duration_minutes`: Length of the class in minutes
  - `capacity`: Current/max attendees (e.g., "12/20")
  - `is_full`: Boolean indicating if class is at capacity

### Class Ongoing Binary Sensor
- **Entity ID**: `binary_sensor.wodify_class_ongoing`
- **State**: ON during a class, OFF otherwise
- **Device Class**: `running`
- **Attributes** (when ON):
  - `current_class`: Name of current class
  - `coach`: Instructor name
  - `location`: Gym location
  - `minutes_remaining`: Minutes until class ends
  - `start_time`: When the class started
  - `end_time`: When the class ends

### Classes Calendar
- **Entity ID**: `calendar.wodify_classes`
- **Description**: Shows all scheduled classes in Home Assistant's calendar view
- **Event Details**:
  - Summary: Class name and coach
  - Description: Program, location, and attendee count
  - Location: Gym location

## Services

### wodify.refresh_now
Force an immediate refresh of class data from the Wodify API.

| Field | Required | Description |
|-------|----------|-------------|
| `entry_id` | Yes | The config entry ID of the Wodify integration |

### wodify.set_filter
Update location and program filters.

| Field | Required | Description |
|-------|----------|-------------|
| `entry_id` | Yes | The config entry ID |
| `locations` | Yes | List of locations to track |
| `programs` | Yes | List of programs to include |

### wodify.set_event_timing
Update event notification timing.

| Field | Required | Description |
|-------|----------|-------------|
| `entry_id` | Yes | The config entry ID |
| `before_class_minutes` | No | Minutes before class (5-60, default: 15) |
| `after_block_minutes` | No | Minutes after block ends (5-60, default: 15) |

## Automations

### Example: Class Starting Soon
```yaml
automation:
  - alias: "Wodify Class Reminder"
    trigger:
      - platform: event
        event_type: wodify_class_starts_soon
    action:
      - service: notify.mobile_app
        data:
          title: "Class Starting Soon"
          message: >
            {{ trigger.event.data.class_name }} starts in
            {{ trigger.event.data.minutes_until_start }} minutes
            at {{ trigger.event.data.location }}
```

### Example: Post-Workout Recovery
```yaml
automation:
  - alias: "Post Workout Recovery"
    trigger:
      - platform: event
        event_type: wodify_class_block_done
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.home
        data:
          temperature: 68
      - service: notify.mobile_app
        data:
          message: >
            Great job! {{ trigger.event.data.block_class_count }} class(es) complete.
            Total workout time: {{ trigger.event.data.block_duration_minutes }} minutes
```

### Example: Class Cancelled Alert
```yaml
automation:
  - alias: "Class Cancelled Alert"
    trigger:
      - platform: event
        event_type: wodify_class_cancelled
    action:
      - service: notify.mobile_app
        data:
          title: "Class Cancelled"
          message: >
            {{ trigger.event.data.class_name }} with {{ trigger.event.data.coach }}
            has been cancelled.
```

### Example: Workout Mode
```yaml
automation:
  - alias: "Enable Workout Mode"
    trigger:
      - platform: state
        entity_id: binary_sensor.wodify_class_ongoing
        to: "on"
    action:
      - service: scene.turn_on
        target:
          entity_id: scene.workout_mode
      - service: switch.turn_on
        target:
          entity_id: switch.do_not_disturb
```

## Event Data

### wodify_class_starts_soon
```json
{
  "class_id": "167917250",
  "class_name": "6:00 AM WOD",
  "coach": "Coach Name",
  "location": "CrossFit Inner Loop",
  "program": "DAILY WOD",
  "start_time": "2024-01-15T06:00:00+00:00",
  "minutes_until_start": 15
}
```

### wodify_class_block_done
```json
{
  "block_class_count": 2,
  "block_duration_minutes": 120,
  "last_class_id": "167917251",
  "last_class_name": "7:00 AM WOD",
  "location": "CrossFit Inner Loop",
  "minutes_after_end": 15
}
```

### wodify_class_cancelled
```json
{
  "class_id": "167917250",
  "class_name": "6:00 AM WOD",
  "coach": "Coach Name",
  "location": "CrossFit Inner Loop",
  "original_start_time": "2024-01-15T06:00:00+00:00",
  "cancellation_time": "2024-01-14T18:30:00+00:00"
}
```

## API Information

This integration uses the official Wodify API v1:
- Base URL: `https://api.wodify.com/v1`
- Authentication: API key via `x-api-key` header
- Endpoints used:
  - `GET /programs` - Fetch available programs
  - `GET /classes/search` - Search for class schedule
  - `GET /classes/{id}` - Fetch individual class details (for coach information)

**Note**: API access requires Wodify administrator/owner privileges. Regular gym members cannot generate API keys.

## Troubleshooting

### No classes showing
- Verify your API key is valid
- Check that classes are scheduled in Wodify
- Ensure the selected locations and programs have scheduled classes
- Check logs for API errors

### Events not firing
- Verify timing settings in integration options
- Ensure classes are in the future
- Check that automation triggers are properly configured

### Integration won't load
- Check Home Assistant logs for errors
- Verify internet connection
- Confirm API key has proper permissions
- Try removing and re-adding the integration

## Support

- **Issues**: [GitHub Issues](https://github.com/kurtislanderson/ha-wodify-admin/issues)
- **Discussions**: [Home Assistant Community](https://community.home-assistant.io/)

## License

This project is licensed under the MIT License.

---

**Disclaimer**: This is an unofficial integration and is not affiliated with or endorsed by Wodify.

[commits-shield]: https://img.shields.io/github/commit-activity/y/kurtislanderson/ha-wodify-admin.svg?style=for-the-badge
[commits]: https://github.com/kurtislanderson/ha-wodify-admin/commits/main
[hacs]: https://github.com/hacs/integration
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/kurtislanderson/ha-wodify-admin.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/kurtislanderson/ha-wodify-admin.svg?style=for-the-badge
[releases]: https://github.com/kurtislanderson/ha-wodify-admin/releases
