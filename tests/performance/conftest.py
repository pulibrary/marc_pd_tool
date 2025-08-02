# tests/performance/conftest.py

"""Performance testing fixtures and configuration"""

# Third party imports
import pytest


# Configure pytest-benchmark if available
try:
    import pytest_benchmark
    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False


@pytest.fixture
def skip_if_no_benchmark():
    """Skip test if pytest-benchmark is not installed"""
    if not BENCHMARK_AVAILABLE:
        pytest.skip("pytest-benchmark not installed")


# Performance test markers
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "performance: mark test as a performance benchmark"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )