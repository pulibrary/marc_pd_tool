# tests/conftest.py

"""Pytest configuration and fixtures for test suite"""

# Standard library imports
from logging import Logger
from logging import getLogger
from os import getcwd
from os.path import exists
from os.path import join
from shutil import rmtree
from tempfile import mkdtemp

# Third party imports
import pytest


# Custom markers
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "full_isolation: mark test as needing complete isolation")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# Test collection configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers"""
    pass  # No automatic marking needed anymore


@pytest.fixture(autouse=True, scope="function")
def basic_isolation():
    """Minimal isolation for most tests - just reset logging"""
    # Reset logging to avoid handler conflicts
    root_logger = getLogger()
    # Remove all handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    # Reset logging level
    root_logger.setLevel(30)  # WARNING level

    # Clear all logger instances
    Logger.manager.loggerDict.clear()

    yield


@pytest.fixture(scope="class")
def class_isolation(request):
    """Class-level isolation for groups of related tests"""
    # Store original working directory
    getcwd()

    # Create a class-specific temp directory for caches
    class_temp_dir = mkdtemp(prefix=f"test_{request.cls.__name__}_")

    yield class_temp_dir

    # Cleanup
    rmtree(class_temp_dir, ignore_errors=True)


@pytest.fixture
def full_isolation(monkeypatch):
    """Full test isolation - only for tests that really need it"""
    # Store original working directory
    original_cwd = getcwd()

    # Clear any cache directories in the project root
    cache_dirs = [".marcpd_cache", "logs", ".cache"]
    for cache_dir in cache_dirs:
        cache_path = join(original_cwd, cache_dir)
        if exists(cache_path):
            rmtree(cache_path)

    yield

    # No cleanup needed since we didn't change directory


@pytest.fixture
def temp_test_dir():
    """Provide a temporary directory for tests that need file operations"""
    temp_dir = mkdtemp()
    yield temp_dir
    rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_cache_dir(tmp_path):
    """Provide a mock cache directory"""
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir()
    return str(cache_dir)
