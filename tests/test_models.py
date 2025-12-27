"""Test data models."""

from datetime import datetime, timezone

import pytest

from custom_components.wodify.models import WodifyClass


class TestWodifyClass:
    """Test WodifyClass model."""

    def test_wodify_class_creation(self):
        """Test WodifyClass model creation."""
        class_data = WodifyClass(
            id="123",
            name="CrossFit",
            start_time=datetime(2024, 1, 1, 17, 30, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 18, 30, tzinfo=timezone.utc),
            coach_name="Coach Mike",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=15,
        )

        assert class_data.id == "123"
        assert class_data.name == "CrossFit"
        assert class_data.coach_name == "Coach Mike"
        assert class_data.location_name == "Downtown"
        assert class_data.program_name == "CrossFit"
        assert class_data.max_attendees == 20
        assert class_data.current_attendees == 15
        assert class_data.is_cancelled is False

    def test_wodify_class_validation(self):
        """Test dataclass validation."""
        # Test with invalid max_attendees (negative)
        with pytest.raises(ValueError, match="max_attendees must be non-negative"):
            WodifyClass(
                id="123",
                name="CrossFit",
                start_time=datetime(2024, 1, 1, 17, 30, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 18, 30, tzinfo=timezone.utc),
                coach_name="Coach",
                location_name="Gym",
                program_name="CrossFit",
                max_attendees=-1,
                current_attendees=15,
            )

        # Test with invalid current_attendees (negative)
        with pytest.raises(ValueError, match="current_attendees must be non-negative"):
            WodifyClass(
                id="123",
                name="CrossFit",
                start_time=datetime(2024, 1, 1, 17, 30, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 18, 30, tzinfo=timezone.utc),
                coach_name="Coach",
                location_name="Gym",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=-1,
            )

        # Test with end_time before start_time
        with pytest.raises(ValueError, match="end_time must be after start_time"):
            WodifyClass(
                id="123",
                name="CrossFit",
                start_time=datetime(2024, 1, 1, 18, 30, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 17, 30, tzinfo=timezone.utc),
                coach_name="Coach",
                location_name="Gym",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=15,
            )

    def test_wodify_class_from_api_response(self):
        """Test creating from API response."""
        api_data = {
            "id": "123",
            "name": "CrossFit",
            "start_date_time": "2024-01-01T17:30:00Z",
            "end_date_time": "2024-01-01T18:30:00Z",
            "location": "Downtown",
            "program_name": "CrossFit",
            "class_limit": 20,
            "reserved": 15,
            "is_cancelled": False,
        }

        class_data = WodifyClass.from_api_response(api_data)
        assert class_data.id == "123"
        assert class_data.name == "CrossFit"
        assert class_data.is_cancelled is False
        assert (
            class_data.coach_name == "Not Available"
        )  # API doesn't provide coach info
        assert class_data.max_attendees == 20

    def test_wodify_class_cancelled_detection(self):
        """Test cancelled class detection from various formats."""
        # Test is_cancelled flag
        api_data = {
            "id": "123",
            "name": "CrossFit",
            "start_date_time": "2024-01-01T17:30:00Z",
            "end_date_time": "2024-01-01T18:30:00Z",
            "location": "Downtown",
            "program_name": "CrossFit",
            "class_limit": 20,
            "reserved": 0,
            "is_cancelled": True,
        }

        class_data = WodifyClass.from_api_response(api_data)
        assert class_data.is_cancelled is True

        # Test status field
        api_data["is_cancelled"] = False
        api_data["status"] = "Cancelled"

        class_data = WodifyClass.from_api_response(api_data)
        assert class_data.is_cancelled is True

        # Test normal class (not cancelled)
        api_data["status"] = "Active"
        class_data = WodifyClass.from_api_response(api_data)
        assert class_data.is_cancelled is False

    def test_wodify_class_is_full(self):
        """Test is_full property."""
        # Not full
        class_data = WodifyClass(
            id="1",
            name="CrossFit",
            start_time=datetime(2024, 1, 1, 17, 30, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 18, 30, tzinfo=timezone.utc),
            coach_name="Coach",
            location_name="Gym",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=15,
        )
        assert class_data.is_full is False

        # Full
        class_data = WodifyClass(
            id="1",
            name="CrossFit",
            start_time=datetime(2024, 1, 1, 17, 30, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 18, 30, tzinfo=timezone.utc),
            coach_name="Coach",
            location_name="Gym",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=20,
        )
        assert class_data.is_full is True

        # Over capacity
        class_data = WodifyClass(
            id="1",
            name="CrossFit",
            start_time=datetime(2024, 1, 1, 17, 30, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 18, 30, tzinfo=timezone.utc),
            coach_name="Coach",
            location_name="Gym",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=22,
        )
        assert class_data.is_full is True

    def test_wodify_class_duration(self):
        """Test duration_minutes property."""
        class_data = WodifyClass(
            id="1",
            name="CrossFit",
            start_time=datetime(2024, 1, 1, 17, 30, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 18, 30, tzinfo=timezone.utc),
            coach_name="Coach",
            location_name="Gym",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=15,
        )
        assert class_data.duration_minutes == 60

        # Test 45-minute class
        class_data = WodifyClass(
            id="1",
            name="Express",
            start_time=datetime(2024, 1, 1, 17, 30, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 18, 15, tzinfo=timezone.utc),
            coach_name="Coach",
            location_name="Gym",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=15,
        )
        assert class_data.duration_minutes == 45

    def test_wodify_class_defaults(self):
        """Test handling of missing optional fields."""
        api_data = {
            "id": "123",
            "name": "CrossFit",
            "start_date_time": "2024-01-01T17:30:00Z",
            "end_date_time": "2024-01-01T18:30:00Z",
            # Optional fields missing
        }

        class_data = WodifyClass.from_api_response(api_data)
        assert class_data.coach_name == "Not Available"
        assert class_data.location_name == "Unknown"
        assert class_data.program_name == "Unknown"
        assert class_data.max_attendees == 0
        assert class_data.current_attendees == 0
        assert class_data.is_cancelled is False

    def test_wodify_class_timezone_handling(self):
        """Test timezone handling in datetime parsing."""
        # Test with Z suffix
        api_data = {
            "id": "123",
            "name": "CrossFit",
            "start_date_time": "2024-01-01T17:30:00Z",
            "end_date_time": "2024-01-01T18:30:00Z",
            "location": "Downtown",
            "program_name": "CrossFit",
            "class_limit": 20,
            "reserved": 15,
        }

        class_data = WodifyClass.from_api_response(api_data)
        assert class_data.start_time.tzinfo is not None
        assert class_data.end_time.tzinfo is not None

        # Test with offset
        api_data["start_date_time"] = "2024-01-01T17:30:00+00:00"
        api_data["end_date_time"] = "2024-01-01T18:30:00+00:00"

        class_data = WodifyClass.from_api_response(api_data)
        assert class_data.start_time.tzinfo is not None
        assert class_data.end_time.tzinfo is not None
