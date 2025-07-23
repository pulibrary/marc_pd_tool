# tests/test_cli/test_default_logging.py

"""Tests for default file logging functionality"""

# Standard library imports
from os.path import join
import unittest
from unittest.mock import patch

# Local imports
from marc_pd_tool.cli.main import get_default_log_path
from marc_pd_tool.cli.main import set_up_logging


class TestDefaultLogging(unittest.TestCase):
    """Test the default logging functionality"""

    def test_get_default_log_path_format(self):
        """Test that default log path has correct format"""
        with patch("marc_pd_tool.cli.main.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20250126_143052"
            with patch("marc_pd_tool.cli.main.exists", return_value=True):
                path = get_default_log_path()
                self.assertEqual(path, join("logs", "marc_pd_20250126_143052.log"))

    def test_get_default_log_path_creates_directory(self):
        """Test that logs directory is created if it doesn't exist"""
        with patch("marc_pd_tool.cli.main.exists", return_value=False) as mock_exists:
            with patch("marc_pd_tool.cli.main.makedirs") as mock_makedirs:
                get_default_log_path()
                mock_makedirs.assert_called_once_with("logs")

    def test_setup_logging_with_default(self):
        """Test setup_logging with default file logging enabled"""
        with patch("marc_pd_tool.cli.main.FileHandler") as mock_file_handler:
            with patch("marc_pd_tool.cli.main.StreamHandler") as mock_stream_handler:
                with patch(
                    "marc_pd_tool.cli.main.get_default_log_path", return_value="logs/test.log"
                ):
                    log_path = set_up_logging(use_default_log=True)
                    self.assertEqual(log_path, "logs/test.log")
                    mock_file_handler.assert_called_once_with("logs/test.log")

    def test_setup_logging_with_no_log_file(self):
        """Test setup_logging with file logging disabled"""
        with patch("marc_pd_tool.cli.main.FileHandler") as mock_file_handler:
            with patch("marc_pd_tool.cli.main.StreamHandler") as mock_stream_handler:
                log_path = set_up_logging(use_default_log=False)
                self.assertEqual(log_path, "")
                mock_file_handler.assert_not_called()

    def test_setup_logging_with_custom_file(self):
        """Test setup_logging with custom log file specified"""
        with patch("marc_pd_tool.cli.main.FileHandler") as mock_file_handler:
            with patch("marc_pd_tool.cli.main.StreamHandler") as mock_stream_handler:
                log_path = set_up_logging(log_file="custom.log", use_default_log=False)
                self.assertEqual(log_path, "custom.log")
                mock_file_handler.assert_called_once_with("custom.log")


if __name__ == "__main__":
    unittest.main()
