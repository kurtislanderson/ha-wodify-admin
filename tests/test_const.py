"""Test constants module."""


def test_constants_defined():
    """Test all required constants are defined."""
    from custom_components.wodify import const

    # Domain
    assert hasattr(const, "DOMAIN")
    assert const.DOMAIN == "wodify"

    # Configuration keys
    assert hasattr(const, "CONF_API_KEY")
    assert hasattr(const, "CONF_LOCATIONS")
    assert hasattr(const, "CONF_PROGRAMS")
    assert hasattr(const, "CONF_UPDATE_INTERVAL")
    assert hasattr(const, "CONF_BEFORE_CLASS_MINUTES")
    assert hasattr(const, "CONF_AFTER_BLOCK_MINUTES")

    # Defaults
    assert hasattr(const, "DEFAULT_UPDATE_INTERVAL")
    assert const.DEFAULT_UPDATE_INTERVAL == 5
    assert hasattr(const, "DEFAULT_BEFORE_CLASS_MINUTES")
    assert const.DEFAULT_BEFORE_CLASS_MINUTES == 15
    assert hasattr(const, "DEFAULT_AFTER_BLOCK_MINUTES")
    assert const.DEFAULT_AFTER_BLOCK_MINUTES == 15

    # Ranges
    assert hasattr(const, "MIN_UPDATE_INTERVAL")
    assert const.MIN_UPDATE_INTERVAL == 1
    assert hasattr(const, "MAX_UPDATE_INTERVAL")
    assert const.MAX_UPDATE_INTERVAL == 60
    assert hasattr(const, "MIN_EVENT_MINUTES")
    assert const.MIN_EVENT_MINUTES == 5
    assert hasattr(const, "MAX_EVENT_MINUTES")
    assert const.MAX_EVENT_MINUTES == 60

    # Events
    assert hasattr(const, "EVENT_CLASS_STARTS_SOON")
    assert const.EVENT_CLASS_STARTS_SOON == "wodify_class_starts_soon"
    assert hasattr(const, "EVENT_CLASS_BLOCK_DONE")
    assert const.EVENT_CLASS_BLOCK_DONE == "wodify_class_block_done"
    assert hasattr(const, "EVENT_CLASS_CANCELLED")
    assert const.EVENT_CLASS_CANCELLED == "wodify_class_cancelled"

    # API
    assert hasattr(const, "API_BASE_URL")
    assert const.API_BASE_URL == "https://api.wodify.com/v1"
    assert hasattr(const, "API_TIMEOUT")
    assert const.API_TIMEOUT == 30
    assert hasattr(const, "API_RATE_LIMIT_CALLS")
    assert const.API_RATE_LIMIT_CALLS == 60

    # Coordinator
    assert hasattr(const, "COORDINATOR_UPDATE_METHOD")
    assert const.COORDINATOR_UPDATE_METHOD == "_async_update_data"

    # Platforms
    assert hasattr(const, "PLATFORMS")
    assert const.PLATFORMS == ["sensor", "binary_sensor", "calendar"]


def test_constants_types():
    """Test constant types are correct."""
    from custom_components.wodify import const

    # Strings
    assert isinstance(const.DOMAIN, str)
    assert isinstance(const.CONF_API_KEY, str)
    assert isinstance(const.EVENT_CLASS_STARTS_SOON, str)
    assert isinstance(const.API_BASE_URL, str)

    # Integers
    assert isinstance(const.DEFAULT_UPDATE_INTERVAL, int)
    assert isinstance(const.MIN_UPDATE_INTERVAL, int)
    assert isinstance(const.API_TIMEOUT, int)

    # Lists
    assert isinstance(const.PLATFORMS, list)
    assert all(isinstance(p, str) for p in const.PLATFORMS)


def test_constants_values_reasonable():
    """Test constant values are reasonable."""
    from custom_components.wodify import const

    # Update interval constraints
    assert const.MIN_UPDATE_INTERVAL < const.DEFAULT_UPDATE_INTERVAL < const.MAX_UPDATE_INTERVAL

    # Event timing constraints
    assert const.MIN_EVENT_MINUTES < const.DEFAULT_BEFORE_CLASS_MINUTES < const.MAX_EVENT_MINUTES
    assert const.MIN_EVENT_MINUTES < const.DEFAULT_AFTER_BLOCK_MINUTES < const.MAX_EVENT_MINUTES

    # API constraints
    assert const.API_TIMEOUT > 0
    assert const.API_RATE_LIMIT_CALLS > 0
