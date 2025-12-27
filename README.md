# Wodify Home Assistant Integration

A Home Assistant custom integration for Wodify, providing real-time class tracking and smart notifications for your gym schedule.

## Features

- **Real-time class tracking** - Monitor upcoming classes with automatic updates every 10 minutes
- **Smart class blocks** - Automatically detects back-to-back classes (within 30 minutes)
- **Configurable notifications** - Set custom timing for before-class and after-block alerts
- **Binary sensor** - Know instantly if you're currently in a class block
- **Next class sensor** - Always see what's coming up next with full details

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/kurtislanderson/ha-wodify-admin`
6. Select "Integration" as the category
7. Click "Add"
8. Search for "Wodify" in HACS
9. Click "Install"
10. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/wodify` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "Wodify"
4. Enter your configuration:
   - **Username**: Your Wodify username
   - **Password**: Your Wodify password
   - **Gym URL**: Your gym's Wodify URL (e.g., `https://yourgym.wodify.com`)
   - **Before class notification**: Minutes before class to send notification (default: 30)
   - **After block notification**: Minutes after class block ends to send notification (default: 15)

## Entities

After configuration, the integration will create the following entities:

### Binary Sensor: In Class Block
- **Entity ID**: `binary_sensor.wodify_in_class_block`
- **State**: `on` when you're currently in a class block, `off` otherwise
- **Attributes**:
  - `block_start`: Start time of the current block
  - `block_end`: End time of the current block
  - `classes_in_block`: Number of classes in the block
  - `class_X_name`: Name of each class in the block
  - `class_X_time`: Start time of each class
  - `class_X_instructor`: Instructor for each class

### Sensor: Next Class
- **Entity ID**: `sensor.wodify_next_class`
- **State**: Name of the next upcoming class
- **Attributes**:
  - `class_name`: Name of the class
  - `class_time`: Start time of the class
  - `instructor`: Class instructor
  - `location`: Class location
  - `duration`: Class duration in minutes
  - `time_until_minutes`: Minutes until class starts
  - `time_until_formatted`: Human-readable time until class
  - `upcoming_classes_count`: Total number of upcoming classes

## Automation Examples

### Notification Before Class

```yaml
automation:
  - alias: "Wodify - Notify Before Class"
    trigger:
      - platform: template
        value_template: >
          {{ state_attr('sensor.wodify_next_class', 'time_until_minutes') | int <= 30 }}
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.wodify_next_class', 'time_until_minutes') | int > 0 }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Wodify Reminder"
          message: >
            Your class "{{ states('sensor.wodify_next_class') }}" 
            starts in {{ state_attr('sensor.wodify_next_class', 'time_until_minutes') }} minutes!
```

### Notification After Class Block

```yaml
automation:
  - alias: "Wodify - Notify After Block"
    trigger:
      - platform: state
        entity_id: binary_sensor.wodify_in_class_block
        from: "on"
        to: "off"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Wodify - Class Block Complete"
          message: "Great job! Your class block is complete."
```

## How It Works

### Update Interval
The integration updates class information every 10 minutes to ensure you have the latest schedule.

### Class Block Detection
Classes are considered part of the same block if they start within 30 minutes of the previous class ending. This allows the integration to detect back-to-back training sessions and provide appropriate notifications.

### Smart State Management
- The binary sensor turns `on` when you enter a class block and `off` when the block ends
- The next class sensor updates to show the most relevant upcoming class
- All entities update automatically based on the 10-minute polling interval

## Troubleshooting

### Integration not loading
- Ensure you've restarted Home Assistant after installation
- Check the Home Assistant logs for any error messages
- Verify your Wodify credentials are correct

### No classes showing
- Verify your Wodify account has scheduled classes
- Check that your gym URL is correct
- Ensure the integration has successfully authenticated (check logs)

### Notifications not working
- Verify the notification times are configured correctly
- Check that your automation triggers are properly set up
- Test your notification service independently

## Support

For issues, feature requests, or questions, please open an issue on [GitHub](https://github.com/kurtislanderson/ha-wodify-admin/issues).

## License

This project is licensed under the MIT License - see the LICENSE file for details.