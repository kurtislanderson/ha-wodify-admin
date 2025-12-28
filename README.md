# Wodify Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacs-shield]][hacs]

A Home Assistant integration for Wodify class schedules. Use your Wodify schedule to power automations in your gym with Home Assistant.

> **Note**: This integration requires Wodify API access, which is only available to gym owners and Wodify administrators.

## Features

### Core Functionality
- **Real-time class tracking** - Monitor upcoming classes with automatic updates every 5 minutes (configurable 1-60 min)
- **Smart class blocks** - Automatically detects back-to-back classes (within 30 minutes)
- **Pre-Class & Post-Block Triggers** - Binary sensors for automating TVs, lights, etc.
- **Private training filter** - Optionally exclude private training sessions from class lists
- **Next Class sensor** - Always see what's coming up next with full details
- **Current Class sensor** - Shows the active class or "No active class"
- **Today's Classes sensor** - See all classes scheduled for today with count and details
- **API Status sensor** - Monitor connection status with cache information
- **Settings sensor** - View current configuration at a glance
- **Binary sensor** - Know instantly if you're currently in a class
- **Refresh button** - Manually refresh class data from the dashboard
- **Calendar integration** - View your gym schedule in Home Assistant's calendar
- **Detailed attendee info** - Full breakdown of reserved, signed-in, waitlisted, and more

### Automation Events
- `wodify_class_starts_soon` - Fires before a class starts (default: 15 min)
- `wodify_class_block_done` - Fires after a class block ends (default: 15 min)
- `wodify_class_cancelled` - Fires when a scheduled class is cancelled

### Optimized Design
- **Efficient API usage** - Fetches 7 days of upcoming class data
- **Coach information** - Automatically fetches coach names for the next 10 upcoming classes
- **Multiple coach support** - Displays all assigned coaches (e.g., "Nick Alexander & Sarah Smith")
- **Data caching** - Retains class data for 48 hours when API is unavailable
- **Active program filtering** - Only shows active programs during setup
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
   - **Pre-class trigger**: Minutes before class to turn on the Pre-Class Trigger sensor (5-60, default: 15)
   - **Post-block trigger**: Minutes after block ends to turn on the Post-Block Trigger sensor (5-60, default: 15)

### Options

You can adjust settings at any time through the integration options:
1. Go to the Wodify integration
2. Click "Configure"
3. Adjust timing preferences, locations, or programs
4. Toggle **Exclude Private Training** to hide/show private training sessions
5. Changes take effect immediately

## Entities

### Sensors

#### Next Class Sensor
- **Entity ID**: `sensor.wodify_next_class`
- **State**: Description of the next upcoming class (e.g., "CrossFit at 6:00 AM with Coach Name")
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
  - `attendees_reserved`: Number of reservations
  - `attendees_signed_in`: Number signed in
  - `attendees_drop_in`: Number of drop-in attendees
  - `attendees_waitlisted`: Number on waitlist
  - `available_slots`: Available spots remaining
  - `attendees_cancelled`: Number of cancellations
  - `attendees_no_show`: Number of no-shows
  - `percent_filled`: Percentage of class capacity filled
  - `count_towards_attendance_limits`: Whether class counts toward limits

#### Current Class Sensor
- **Entity ID**: `sensor.wodify_current_class`
- **State**: Active class name or "No active class"
- **Attributes** (when class is active):
  - `class_id`: Unique identifier
  - `class_name`: Name of the class
  - `coach`: Instructor name
  - `location`: Gym location
  - `program`: Program name
  - `start_time`, `end_time`: Class timing
  - `minutes_remaining`: Minutes until class ends
  - `duration_minutes`: Total class length
  - `capacity`: Current/max attendees
  - `is_full`: Boolean
  - `attendees_reserved`: Number of reservations
  - `attendees_signed_in`: Number signed in
  - `attendees_drop_in`: Number of drop-in attendees
  - `attendees_waitlisted`: Number on waitlist
  - `available_slots`: Available spots remaining
  - `attendees_cancelled`: Number of cancellations
  - `attendees_no_show`: Number of no-shows
  - `percent_filled`: Percentage of class capacity filled
  - `count_towards_attendance_limits`: Whether class counts toward limits

#### Today's Classes Sensor
- **Entity ID**: `sensor.wodify_todays_classes`
- **State**: Count of classes today (e.g., "3 classes today" or "No classes today")
- **Attributes**:
  - `class_count`: Number of classes scheduled
  - `classes`: List of all today's classes with full details including:
    - Basic: id, name, coach, location, program, start_time, end_time, time, duration_minutes, capacity, is_full
    - Attendee breakdown: attendees_reserved, attendees_signed_in, attendees_drop_in, attendees_waitlisted, available_slots, attendees_cancelled, attendees_no_show, percent_filled, count_towards_attendance_limits

#### API Status Sensor
- **Entity ID**: `sensor.wodify_api_status`
- **State**: "Connected" or "Disconnected"
- **Attributes**:
  - `connected`: Boolean connection status
  - `last_successful_update`: Timestamp of last successful API call
  - `last_error`: Error message (when disconnected)
  - `cached_classes`: Number of classes in cache
  - `using_cache`: True when serving cached data

#### Settings Sensor
- **Entity ID**: `sensor.wodify_settings`
- **State**: Current update interval (e.g., "Updates every 5 min")
- **Attributes**:
  - `update_interval_minutes`: Refresh frequency
  - `before_class_minutes`: Pre-class trigger timing (minutes)
  - `after_block_minutes`: Post-block trigger timing (minutes)
  - `locations`: List of tracked locations
  - `programs`: List of tracked programs

### Binary Sensors

#### Class Ongoing Binary Sensor
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

#### Pre-Class Trigger
- **Entity ID**: `binary_sensor.wodify_class_starting_soon`
- **State**: ON when a class starts within the configured trigger window, OFF otherwise
- **Device Class**: `occupancy`
- **Icon**: `mdi:television` (on) / `mdi:television-off` (off)
- **Use Case**: Trigger automations to prepare for class (turn on TVs, lights, HVAC, etc.)
- **Attributes**:
  - `trigger_window_minutes`: Configured minutes before class to trigger (5-60)
  - `next_class`: Name of upcoming class
  - `coach`: Instructor name
  - `location`: Gym location
  - `minutes_until_class`: Minutes until class starts
  - `class_start_time`: ISO formatted start time

#### Post-Block Trigger
- **Entity ID**: `binary_sensor.wodify_block_just_ended`
- **State**: ON for the configured trigger window after a class block ends, OFF otherwise
- **Device Class**: `occupancy`
- **Icon**: `mdi:television-off` (on) / `mdi:television` (off)
- **Use Case**: Trigger automations after classes end (turn off TVs, lights, equipment, etc.)
- **Note**: A "block" is a group of back-to-back classes with gaps less than 30 minutes between them
- **Attributes**:
  - `trigger_window_minutes`: Configured minutes after block to trigger (5-60)
  - `last_class`: Name of last class in block
  - `coach`: Instructor name
  - `location`: Gym location
  - `block_class_count`: Number of classes in the block
  - `block_duration_minutes`: Total duration of the block
  - `minutes_since_block_end`: Minutes since block ended
  - `block_end_time`: ISO formatted end time

### Buttons

#### Refresh Button
- **Entity ID**: `button.wodify_refresh`
- **Action**: Manually triggers a data refresh from the Wodify API

### Calendar

#### Classes Calendar
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
Update pre-class and post-block trigger timing.

| Field | Required | Description |
|-------|----------|-------------|
| `entry_id` | Yes | The config entry ID |
| `before_class_minutes` | No | Pre-class trigger window in minutes (5-60, default: 15) |
| `after_block_minutes` | No | Post-block trigger window in minutes (5-60, default: 15) |

## Automations

The integration provides two binary sensors specifically designed for triggering automations:
- **Pre-Class Trigger**: Turns ON within X minutes before a class starts
- **Post-Block Trigger**: Turns ON within X minutes after a class block ends

### Example: Turn On TVs & Lights Before Class
```yaml
automation:
  - alias: "Gym Pre-Class Setup"
    trigger:
      - platform: state
        entity_id: binary_sensor.wodify_class_starting_soon
        to: "on"
    action:
      - service: media_player.turn_on
        target:
          entity_id: media_player.gym_tv
      - service: light.turn_on
        target:
          entity_id: light.gym_lights
```

### Example: Turn Off TVs & Lights After Class Block
```yaml
automation:
  - alias: "Gym Post-Block Shutdown"
    trigger:
      - platform: state
        entity_id: binary_sensor.wodify_block_just_ended
        to: "on"
    action:
      - service: media_player.turn_off
        target:
          entity_id: media_player.gym_tv
      - service: light.turn_off
        target:
          entity_id: light.gym_lights
```

### Using Trigger Window Attributes
Both sensors expose a `trigger_window_minutes` attribute showing the configured timing:
```yaml
automation:
  - alias: "Log Trigger Info"
    trigger:
      - platform: state
        entity_id: binary_sensor.wodify_class_starting_soon
        to: "on"
    action:
      - service: logbook.log
        data:
          name: "Wodify"
          message: >
            Pre-class trigger activated {{ state_attr('binary_sensor.wodify_class_starting_soon', 'trigger_window_minutes') }}
            minutes before {{ state_attr('binary_sensor.wodify_class_starting_soon', 'next_class') }}
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
