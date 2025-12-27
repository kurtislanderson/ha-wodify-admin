"""Constants for the Wodify integration."""

DOMAIN = "wodify"

# Configuration keys
CONF_API_KEY = "api_key"
CONF_LOCATIONS = "locations"
CONF_PROGRAMS = "programs"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_BEFORE_CLASS_MINUTES = "before_class_minutes"
CONF_AFTER_BLOCK_MINUTES = "after_block_minutes"

# Backwards compatibility with earlier constant names
CONF_BEFORE_MINUTES = CONF_BEFORE_CLASS_MINUTES
CONF_AFTER_MINUTES = CONF_AFTER_BLOCK_MINUTES

# Default values
DEFAULT_UPDATE_INTERVAL = 5  # minutes
DEFAULT_BEFORE_CLASS_MINUTES = 15
DEFAULT_AFTER_BLOCK_MINUTES = 15
DEFAULT_BEFORE_MINUTES = DEFAULT_BEFORE_CLASS_MINUTES
DEFAULT_AFTER_MINUTES = DEFAULT_AFTER_BLOCK_MINUTES

# Valid ranges
MIN_UPDATE_INTERVAL = 1
MAX_UPDATE_INTERVAL = 60
MIN_EVENT_MINUTES = 5
MAX_EVENT_MINUTES = 60

# Behavioural tuning
BLOCK_GAP_THRESHOLD = 30  # minutes between classes to be considered the same block

# Event names
EVENT_CLASS_STARTS_SOON = "wodify_class_starts_soon"
EVENT_CLASS_BLOCK_DONE = "wodify_class_block_done"
EVENT_CLASS_CANCELLED = "wodify_class_cancelled"

# API behaviour
API_BASE_URL = "https://api.wodify.com/v1"
API_TIMEOUT = 30
API_RATE_LIMIT_CALLS = 60

# Coordinator behaviour
COORDINATOR_UPDATE_METHOD = "_async_update_data"

# Supported platforms
PLATFORMS = ["sensor", "binary_sensor", "calendar"]
