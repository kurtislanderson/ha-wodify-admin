"""Constants for the Wodify integration."""

DOMAIN = "wodify"

# Configuration keys
CONF_API_KEY = "api_key"
CONF_LOCATIONS = "locations"
CONF_PROGRAMS = "programs"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_BEFORE_CLASS_MINUTES = "before_class_minutes"
CONF_AFTER_BLOCK_MINUTES = "after_block_minutes"
CONF_EXCLUDE_PRIVATE_TRAINING = "exclude_private_training"

# Default values
DEFAULT_UPDATE_INTERVAL = 5  # minutes
DEFAULT_BEFORE_CLASS_MINUTES = 15  # minutes before class to trigger pre-class automation
DEFAULT_AFTER_BLOCK_MINUTES = 15  # minutes after block ends to trigger post-block automation
DEFAULT_EXCLUDE_PRIVATE_TRAINING = True  # Exclude by default

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
CACHE_MAX_AGE_HOURS = 48  # How long to use cached data when API is down (2 days)

# Supported platforms
PLATFORMS = ["sensor", "binary_sensor", "calendar", "button"]
