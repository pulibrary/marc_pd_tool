# tests/conftest.py

"""Pytest configuration and fixtures for test suite"""

# Standard library imports
import logging
import os
import shutil
import tempfile

# Third party imports
import pytest


@pytest.fixture(autouse=True)
def isolate_tests(monkeypatch):
    """Ensure test isolation by resetting environment and mocks between tests"""
    # Store original working directory
    original_cwd = os.getcwd()

    # Don't change directory - tests need access to config files
    # But do clear any cache directories in the project root
    cache_dirs = [".marcpd_cache", "logs"]
    for cache_dir in cache_dirs:
        cache_path = os.path.join(original_cwd, cache_dir)
        if os.path.exists(cache_path):
            shutil.rmtree(cache_path)

    # Reset logging to avoid handler conflicts
    # Get the root logger
    root_logger = logging.getLogger()
    # Remove all handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    # Reset logging level
    root_logger.setLevel(logging.WARNING)

    # Clear all logger instances
    logging.Logger.manager.loggerDict.clear()

    yield

    # No cleanup needed since we didn't change directory


@pytest.fixture
def temp_test_dir():
    """Provide a temporary directory for tests that need file operations"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_cache_dir(tmp_path):
    """Provide a mock cache directory"""
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir()
    return str(cache_dir)
