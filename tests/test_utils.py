"""Test utilities for timezone compatibility."""

from datetime import UTC

# Python 3.11+ has datetime.UTC, older versions use timezone.utc
UTC = UTC
