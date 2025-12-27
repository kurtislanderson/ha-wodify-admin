"""Constants for the Wodify integration."""

DOMAIN = "wodify"

# Update interval (10 minutes as per requirements)
UPDATE_INTERVAL = 600  # seconds

# Time threshold for detecting back-to-back classes (30 minutes)
CLASS_BLOCK_THRESHOLD = 1800  # seconds

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_GYM_URL = "gym_url"
CONF_BEFORE_CLASS_NOTIFICATION = "before_class_notification"
CONF_AFTER_BLOCK_NOTIFICATION = "after_block_notification"

# Default notification times (in minutes)
DEFAULT_BEFORE_CLASS_NOTIFICATION = 30
DEFAULT_AFTER_BLOCK_NOTIFICATION = 15

# Sensor attributes
ATTR_CLASS_NAME = "class_name"
ATTR_CLASS_TIME = "class_time"
ATTR_CLASS_INSTRUCTOR = "instructor"
ATTR_CLASS_LOCATION = "location"
ATTR_CLASS_DURATION = "duration"
ATTR_BLOCK_START = "block_start"
ATTR_BLOCK_END = "block_end"
ATTR_NEXT_CLASS = "next_class"
ATTR_CLASSES_IN_BLOCK = "classes_in_block"
