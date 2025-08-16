# tests/unit/shared/utils/test_time_utils.py

"""Tests for time utility functions"""

# Third party imports

# Local imports
from marc_pd_tool.shared.utils.time_utils import format_time_duration


class TestFormatTimeDuration:
    """Test the format_time_duration function"""

    def test_seconds_only(self):
        """Test formatting when duration is less than a minute"""
        assert format_time_duration(0) == "0s"
        assert format_time_duration(1) == "1s"
        assert format_time_duration(59) == "59s"
        assert format_time_duration(30.5) == "30s"  # Fractional seconds

    def test_minutes_and_seconds(self):
        """Test formatting when duration is less than an hour"""
        assert format_time_duration(60) == "1m 0s"
        assert format_time_duration(61) == "1m 1s"
        assert format_time_duration(119) == "1m 59s"
        assert format_time_duration(3599) == "59m 59s"
        assert format_time_duration(90.7) == "1m 30s"  # 90 seconds

    def test_hours_and_minutes(self):
        """Test formatting when duration is less than a day"""
        assert format_time_duration(3600) == "1h 0m"
        assert format_time_duration(3661) == "1h 1m"  # 1h 1m 1s shows as 1h 1m
        assert format_time_duration(7200) == "2h 0m"
        assert format_time_duration(7260) == "2h 1m"
        assert format_time_duration(86399) == "23h 59m"  # Just under a day
        assert format_time_duration(5400) == "1h 30m"  # 1.5 hours

    def test_days_hours_and_minutes(self):
        """Test formatting when duration is one or more days"""
        assert format_time_duration(86400) == "1d 0h 0m"  # Exactly 1 day
        assert format_time_duration(90000) == "1d 1h 0m"  # 25 hours
        assert format_time_duration(172800) == "2d 0h 0m"  # 2 days
        assert format_time_duration(266400) == "3d 2h 0m"  # 3 days 2 hours
        assert format_time_duration(273900) == "3d 4h 5m"  # 3 days 4 hours 5 minutes

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Large numbers
        assert format_time_duration(604800) == "7d 0h 0m"  # 1 week
        assert format_time_duration(2592000) == "30d 0h 0m"  # 30 days

        # Floating point inputs
        assert format_time_duration(3.14159) == "3s"
        assert format_time_duration(60.99) == "1m 0s"
        assert format_time_duration(3600.5) == "1h 0m"

    def test_realistic_durations(self):
        """Test with realistic processing durations"""
        # Quick operation (45 seconds)
        assert format_time_duration(45) == "45s"

        # Medium operation (5 minutes 30 seconds)
        assert format_time_duration(330) == "5m 30s"

        # Long operation (2 hours 15 minutes)
        assert format_time_duration(8100) == "2h 15m"

        # Very long operation (1 day 3 hours 45 minutes)
        assert format_time_duration(99900) == "1d 3h 45m"
