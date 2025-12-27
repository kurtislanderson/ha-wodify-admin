"""Test utilities for timezone compatibility."""

from datetime import timezone

# Python 3.11+ has datetime.UTC, older versions use timezone.utc
UTC = timezone.utc
