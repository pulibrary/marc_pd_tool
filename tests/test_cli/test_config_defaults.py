# tests/test_cli/test_config_defaults.py

"""Tests for CLI config default behavior"""

# Standard library imports
from typing import Any
from typing import Dict
from unittest.mock import patch

# Local imports
from marc_pd_tool.cli.main import create_argument_parser


class MockConfigLoader:
    """Mock ConfigLoader for testing"""

    def __init__(self, config_dict: Dict[str, Any]):
        self.config = config_dict

    def get_processing_config(self) -> Dict[str, Any]:
        return self.config.get("processing", {})

    def get_filtering_config(self) -> Dict[str, Any]:
        return self.config.get("filtering", {})

    def get_output_config(self) -> Dict[str, Any]:
        return self.config.get("output", {})

    def get_caching_config(self) -> Dict[str, Any]:
        return self.config.get("caching", {})

    def get_logging_config(self) -> Dict[str, Any]:
        return self.config.get("logging", {})

    def get_threshold(self, name: str) -> int:
        return self.config.get("default_thresholds", {}).get(name, 80)

    def get_generic_detector_config(self) -> Dict[str, int]:
        return self.config.get("generic_title_detector", {"frequency_threshold": 10})


def test_config_defaults_applied():
    """Test that config defaults are applied to arguments"""
    # Mock config with non-default values
    mock_config_dict = {
        "processing": {
            "batch_size": 500,
            "max_workers": 8,
            "score_everything_mode": True,
            "brute_force_missing_year": True,
        },
        "filtering": {"us_only": True, "min_year": 1950, "max_year": 2000},
        "output": {"single_file": True},
        "caching": {"cache_dir": "/tmp/test_cache", "force_refresh": True, "no_cache": True},
        "logging": {"debug": True, "log_file": "/tmp/test.log"},
        "default_thresholds": {"title": 90, "author": 85},
    }

    mock_config = MockConfigLoader(mock_config_dict)

    with patch("marc_pd_tool.cli.main.get_config", return_value=mock_config):
        parser = create_argument_parser()
        args = parser.parse_args(["--marcxml", "test.xml"])

        # Verify config defaults applied
        assert args.batch_size == 500
        assert args.max_workers == 8
        assert args.score_everything_mode is True
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
    # Mock config with specific values
    mock_config_dict = {
        "processing": {
            "batch_size": 500,
            "score_everything_mode": True,
            "brute_force_missing_year": True,
        },
        "filtering": {"us_only": True},
        "caching": {"force_refresh": True},
        "logging": {"debug": True},
    }

    mock_config = MockConfigLoader(mock_config_dict)

    with patch("marc_pd_tool.cli.main.get_config", return_value=mock_config):
        parser = create_argument_parser()
        args = parser.parse_args(
            [
                "--marcxml",
                "test.xml",
                "--batch-size",
                "100",
                "--no-score-everything-mode",
                "--no-brute-force-missing-year",
                "--no-us-only",
                "--no-force-refresh",
                "--no-debug",
            ]
        )

        # Verify CLI overrides
        assert args.batch_size == 100
        assert args.score_everything_mode is False
        assert args.brute_force_missing_year is False
        assert args.us_only is False
        assert args.force_refresh is False
        assert args.debug is False


def test_boolean_flag_negation():
    """Test that boolean flags can be negated with --no- prefix"""
    mock_config_dict = {
        "processing": {"score_everything_mode": False},
        "filtering": {"us_only": False},
        "caching": {"force_refresh": False},
        "logging": {"debug": False},
    }

    mock_config = MockConfigLoader(mock_config_dict)

    with patch("marc_pd_tool.cli.main.get_config", return_value=mock_config):
        parser = create_argument_parser()

        # Test enabling flags that default to False
        args = parser.parse_args(
            [
                "--marcxml",
                "test.xml",
                "--score-everything-mode",
                "--us-only",
                "--force-refresh",
                "--debug",
            ]
        )

        assert args.score_everything_mode is True
        assert args.us_only is True
        assert args.force_refresh is True
        assert args.debug is True


def test_partial_config():
    """Test that missing config sections use code defaults"""
    # Config with only some sections
    mock_config_dict = {
        "processing": {"batch_size": 300},
        # Missing other sections
    }

    mock_config = MockConfigLoader(mock_config_dict)

    with patch("marc_pd_tool.cli.main.get_config", return_value=mock_config):
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

    with patch("marc_pd_tool.cli.main.get_config", return_value=mock_config):
        parser = create_argument_parser()
        args = parser.parse_args(["--marcxml", "test.xml"])

        assert args.max_workers is None
        # When min_year is None in config, it defaults to current_year - 96
        # Standard library imports
        from datetime import datetime

        expected_min_year = datetime.now().year - 96
        assert args.min_year == expected_min_year
        assert args.max_year is None
        assert args.log_file is None
