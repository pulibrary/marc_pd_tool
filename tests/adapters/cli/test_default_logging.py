# tests/adapters/cli/test_default_logging.py

"""Tests for default file logging functionality"""

# Standard library imports
from unittest import TestCase
from unittest.mock import patch

# Local imports
from marc_pd_tool.adapters.cli import get_default_log_path
from marc_pd_tool.adapters.cli import set_up_logging


class TestDefaultLogging(TestCase):
    """Test the default logging functionality"""

    def test_get_default_log_path_format(self):
        """Test that default log path has correct format"""
        with patch("marc_pd_tool.infrastructure.logging._setup.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20250126_143052"
            with patch("marc_pd_tool.infrastructure.logging._setup.exists", return_value=True):
                with patch(
                    "marc_pd_tool.infrastructure.logging._setup.RunIndexManager"
                ) as mock_run_manager:
                    mock_run_manager.return_value.get_next_run_index.return_value = 1
                    path = get_default_log_path()
                    self.assertEqual(path, "logs/marc_pd_20250126_143052_run001.log")

    def test_get_default_log_path_creates_directory(self):
        """Test that logs directory is created if it doesn't exist"""
        with patch(
            "marc_pd_tool.infrastructure.logging._setup.exists", return_value=False
        ) as mock_exists:
            with patch("marc_pd_tool.infrastructure.logging._setup.makedirs") as mock_makedirs:
                with patch(
                    "marc_pd_tool.infrastructure.logging._setup.RunIndexManager"
                ) as mock_run_manager:
                    mock_run_manager.return_value.get_next_run_index.return_value = 1
                    get_default_log_path()
                    mock_makedirs.assert_called_once_with("logs")

    def test_setup_logging_with_default(self):
        """Test setup_logging with default file logging enabled"""
        with patch("marc_pd_tool.infrastructure.logging._setup.FileHandler") as mock_file_handler:
            with patch(
                "marc_pd_tool.infrastructure.logging._setup.StreamHandler"
            ) as mock_stream_handler:
                with patch(
                    "marc_pd_tool.infrastructure.logging._setup.get_default_log_path",
                    return_value="logs/test.log",
                ):
                    with patch(
                        "marc_pd_tool.infrastructure.logging._setup.getLogger"
                    ) as mock_get_logger:
                        # Mock the logger and handlers properly
                        mock_logger = mock_get_logger.return_value
                        mock_logger.handlers = []
                        mock_file_instance = mock_file_handler.return_value
                        mock_file_instance.level = 10  # DEBUG level
                        mock_stream_instance = mock_stream_handler.return_value
                        mock_stream_instance.level = 20  # INFO level

                        log_path = set_up_logging(disable_file_logging=False)
                        self.assertEqual(log_path, "logs/test.log")
                        mock_file_handler.assert_called_once_with("logs/test.log")

    def test_setup_logging_with_no_log_file(self):
        """Test setup_logging with file logging disabled"""
        with patch("marc_pd_tool.infrastructure.logging._setup.FileHandler") as mock_file_handler:
            with patch(
                "marc_pd_tool.infrastructure.logging._setup.StreamHandler"
            ) as mock_stream_handler:
                log_path = set_up_logging(disable_file_logging=True)
                self.assertIsNone(log_path)
                mock_file_handler.assert_not_called()

    def test_setup_logging_with_custom_file(self):
        """Test setup_logging with custom log file specified"""
        with patch("marc_pd_tool.infrastructure.logging._setup.FileHandler") as mock_file_handler:
            with patch(
                "marc_pd_tool.infrastructure.logging._setup.StreamHandler"
            ) as mock_stream_handler:
                with patch(
                    "marc_pd_tool.infrastructure.logging._setup.getLogger"
                ) as mock_get_logger:
                    # Mock the logger and handlers properly
                    mock_logger = mock_get_logger.return_value
                    mock_logger.handlers = []
                    mock_file_instance = mock_file_handler.return_value
                    mock_file_instance.level = 10  # DEBUG level
                    mock_stream_instance = mock_stream_handler.return_value
                    mock_stream_instance.level = 20  # INFO level

                    log_path = set_up_logging(log_file="custom.log", disable_file_logging=False)
                    self.assertEqual(log_path, "custom.log")
                    mock_file_handler.assert_called_once_with("custom.log")


if __name__ == "__main__":
    # Standard library imports
    import unittest

    unittest.main()
