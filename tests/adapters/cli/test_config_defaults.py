# tests/adapters/cli/test_config_defaults.py

"""Tests for CLI config default behavior"""

# Standard library imports
from typing import Any
from typing import Dict
from unittest.mock import MagicMock
from unittest.mock import patch

# Local imports
from marc_pd_tool.adapters.cli import create_argument_parser


class MockConfigLoader:
    """Mock ConfigLoader for testing with Pydantic-like models"""

    def __init__(self, config_dict: Dict[str, Any]):
        self.config = config_dict

        # Create mock Pydantic models for each section
        self.processing = MagicMock()
        self.processing.batch_size = config_dict.get("processing", {}).get("batch_size", 100)
        self.processing.max_workers = config_dict.get("processing", {}).get("max_workers", None)
        self.processing.score_everything_mode = config_dict.get("processing", {}).get(
            "score_everything_mode", False
        )

        self.filtering = MagicMock()
        self.filtering.us_only = config_dict.get("filtering", {}).get("us_only", False)
        self.filtering.min_year = config_dict.get("filtering", {}).get("min_year", None)
        self.filtering.max_year = config_dict.get("filtering", {}).get("max_year", None)
        self.filtering.brute_force_missing_year = config_dict.get("filtering", {}).get(
            "brute_force_missing_year", False
        )

        self.output = MagicMock()
        self.output.single_file = config_dict.get("output", {}).get("single_file", False)

        self.caching = MagicMock()
        self.caching.cache_dir = config_dict.get("caching", {}).get("cache_dir", ".marcpd_cache")
        self.caching.force_refresh = config_dict.get("caching", {}).get("force_refresh", False)
        self.caching.no_cache = config_dict.get("caching", {}).get("no_cache", False)

        self.logging = MagicMock()
        self.logging.debug = config_dict.get("logging", {}).get("debug", False)
        self.logging.log_file = config_dict.get("logging", {}).get("log_file", None)

        self.generic_detector = MagicMock()
        self.generic_detector.frequency_threshold = config_dict.get(
            "generic_title_detector", {}
        ).get("frequency_threshold", 10)

    def get_threshold(self, name: str) -> int:
        return self.config.get("default_thresholds", {}).get(name, 80)


def test_config_defaults_applied():
    """Test that config defaults are applied to arguments"""
    # Mock config with non-default values
    mock_config_dict = {
        "processing": {"batch_size": 500, "max_workers": 8, "score_everything_mode": True},
        "filtering": {
            "us_only": True,
            "min_year": 1950,
            "max_year": 2000,
            "brute_force_missing_year": True,
        },
        "output": {"single_file": True},
        "caching": {"cache_dir": "/tmp/test_cache", "force_refresh": True, "no_cache": True},
        "logging": {"debug": True, "log_file": "/tmp/test.log"},
        "default_thresholds": {"title": 90, "author": 85},
    }

    mock_config = MockConfigLoader(mock_config_dict)

    with (
        patch("marc_pd_tool.infrastructure.config.get_config", return_value=mock_config),
        patch("marc_pd_tool.adapters.cli.parser.get_config", return_value=mock_config),
    ):
        parser = create_argument_parser()
        args = parser.parse_args(["--marcxml", "test.xml"])

        # Verify config defaults applied
        assert args.batch_size == 500
        assert args.max_workers == 8
        assert args.score_everything is True
        assert args.brute_force_missing_year is True
        assert args.us_only is True
        assert args.min_year == 1950
        assert args.max_year == 2000
        assert args.single_file is True
        assert args.cache_dir == "/tmp/test_cache"
        assert args.force_refresh is True
        assert args.disable_cache is True
        assert args.debug is True
        assert args.log_file == "/tmp/test.log"
        assert args.title_threshold == 90
        assert args.author_threshold == 85


def test_cli_overrides_config():
    """Test that CLI arguments override config file defaults"""
    # Mock config with specific values that would be True by default
    mock_config_dict = {
        "processing": {"batch_size": 500, "score_everything_mode": False},  # Default is False
        "filtering": {"us_only": False, "brute_force_missing_year": False},  # Defaults are False
        "caching": {"force_refresh": False},  # Default is False
        "logging": {"debug": False},  # Default is False
    }

    mock_config = MockConfigLoader(mock_config_dict)

    with (
        patch("marc_pd_tool.infrastructure.config.get_config", return_value=mock_config),
        patch("marc_pd_tool.adapters.cli.parser.get_config", return_value=mock_config),
    ):
        parser = create_argument_parser()
        # Test overriding with explicit flags (enabling features that default to False)
        args = parser.parse_args(
            [
                "--marcxml",
                "test.xml",
                "--batch-size",
                "100",
                "--score-everything",  # Enable (overrides False default)
                "--brute-force-missing-year",  # Enable (overrides False default)
                "--us-only",  # Enable (overrides False default)
                "--force-refresh",  # Enable (overrides False default)
                "--debug",  # Enable (overrides False default)
            ]
        )

        # Verify CLI overrides config defaults
        assert args.batch_size == 100
        assert args.score_everything is True  # CLI enabled it
        assert args.brute_force_missing_year is True  # CLI enabled it
        assert args.us_only is True  # CLI enabled it
        assert args.force_refresh is True  # CLI enabled it
        assert args.debug is True  # CLI enabled it


def test_boolean_flag_behavior():
    """Test that boolean flags work correctly with store_true action"""
    mock_config_dict = {
        "processing": {"score_everything_mode": False},
        "filtering": {"us_only": False},
        "caching": {"force_refresh": False},
        "logging": {"debug": False},
    }

    mock_config = MockConfigLoader(mock_config_dict)

    with (
        patch("marc_pd_tool.infrastructure.config.get_config", return_value=mock_config),
        patch("marc_pd_tool.adapters.cli.parser.get_config", return_value=mock_config),
    ):
        parser = create_argument_parser()

        # Test enabling flags that default to False
        args = parser.parse_args(
            [
                "--marcxml",
                "test.xml",
                "--score-everything",
                "--us-only",
                "--force-refresh",
                "--debug",
            ]
        )

        assert args.score_everything is True
        assert args.us_only is True
        assert args.force_refresh is True
        assert args.debug is True

        # Test that without flags, they remain False
        args2 = parser.parse_args(["--marcxml", "test.xml"])
        assert args2.score_everything is False
        assert args2.us_only is False
        assert args2.force_refresh is False
        assert args2.debug is False


def test_partial_config():
    """Test that missing config sections use code defaults"""
    # Config with only some sections
    mock_config_dict = {
        "processing": {"batch_size": 300},
        # Missing other sections
    }

    mock_config = MockConfigLoader(mock_config_dict)

    with (
        patch("marc_pd_tool.infrastructure.config.get_config", return_value=mock_config),
        patch("marc_pd_tool.adapters.cli.parser.get_config", return_value=mock_config),
    ):
        parser = create_argument_parser()
        args = parser.parse_args(["--marcxml", "test.xml"])

        # Processing config is present
        assert args.batch_size == 300

        # Other configs should use code defaults
        assert args.cache_dir == ".marcpd_cache"  # Default from get()
        assert args.us_only is False  # Default from get()
        assert args.single_file is False  # Default from get()


def test_none_values_in_config():
    """Test that None values in config are handled correctly"""
    mock_config_dict = {
        "processing": {"max_workers": None},
        "filtering": {"min_year": None, "max_year": None},
        "logging": {"log_file": None},
    }

    mock_config = MockConfigLoader(mock_config_dict)

    with (
        patch("marc_pd_tool.infrastructure.config.get_config", return_value=mock_config),
        patch("marc_pd_tool.adapters.cli.parser.get_config", return_value=mock_config),
    ):
        parser = create_argument_parser()
        args = parser.parse_args(["--marcxml", "test.xml"])

        assert args.max_workers is None
        # When min_year is None in config, it remains None (no special default)
        assert args.min_year is None
        assert args.max_year is None
        assert args.log_file is None
