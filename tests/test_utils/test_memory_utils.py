# tests/test_utils/test_memory_utils.py

"""Tests for memory monitoring utilities"""

# Standard library imports
from time import sleep
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.utils.memory_utils import MemoryMonitor


class TestMemoryMonitor:
    """Test memory monitoring functionality"""

    @patch("marc_pd_tool.utils.memory_utils.Process")
    @patch("marc_pd_tool.utils.memory_utils.virtual_memory")
    def test_memory_monitor_initialization(
        self, mock_virtual_memory: Mock, mock_process_class: Mock
    ):
        """Test MemoryMonitor initializes correctly"""
        # Mock process and memory info
        mock_process = Mock()
        mock_process_class.return_value = mock_process

        mock_memory_info = Mock()
        mock_memory_info.rss = 1024 * 1024 * 1024  # 1GB in bytes
        mock_process.memory_info.return_value = mock_memory_info

        mock_system_mem = Mock()
        mock_system_mem.percent = 50.0
        mock_system_mem.available = 8 * 1024 * 1024 * 1024  # 8GB
        mock_virtual_memory.return_value = mock_system_mem

        monitor = MemoryMonitor(log_interval=30)

        assert monitor.log_interval == 30
        assert monitor.peak_memory > 0
        assert monitor.start_time > 0

    @patch("marc_pd_tool.utils.memory_utils.Process")
    @patch("marc_pd_tool.utils.memory_utils.virtual_memory")
    def test_get_memory_usage(self, mock_virtual_memory: Mock, mock_process_class: Mock):
        """Test get_memory_usage returns correct statistics"""
        # Mock process and memory info
        mock_process = Mock()
        mock_process_class.return_value = mock_process

        mock_memory_info = Mock()
        mock_memory_info.rss = 2 * 1024 * 1024 * 1024  # 2GB in bytes
        mock_process.memory_info.return_value = mock_memory_info

        mock_system_mem = Mock()
        mock_system_mem.percent = 75.5
        mock_system_mem.available = 4 * 1024 * 1024 * 1024  # 4GB
        mock_virtual_memory.return_value = mock_system_mem

        monitor = MemoryMonitor()
        stats = monitor.get_memory_usage()

        assert abs(stats["process_gb"] - 2.0) < 0.01  # Should be ~2GB
        assert stats["system_percent"] == 75.5
        assert abs(stats["available_gb"] - 4.0) < 0.01  # Should be ~4GB
        assert stats["peak_gb"] >= stats["process_gb"]

    @patch("marc_pd_tool.utils.memory_utils.Process")
    @patch("marc_pd_tool.utils.memory_utils.virtual_memory")
    def test_peak_memory_tracking(self, mock_virtual_memory: Mock, mock_process_class: Mock):
        """Test peak memory tracking works correctly"""
        # Mock process and memory info
        mock_process = Mock()
        mock_process_class.return_value = mock_process

        # Simulate increasing memory usage
        memory_values = [
            1 * 1024 * 1024 * 1024,  # 1GB
            3 * 1024 * 1024 * 1024,  # 3GB
            2 * 1024 * 1024 * 1024,  # 2GB (decrease)
        ]

        mock_memory_info = Mock()
        mock_process.memory_info.return_value = mock_memory_info

        mock_system_mem = Mock()
        mock_system_mem.percent = 50.0
        mock_system_mem.available = 8 * 1024 * 1024 * 1024
        mock_virtual_memory.return_value = mock_system_mem

        monitor = MemoryMonitor()

        # Simulate memory usage changes
        for memory_bytes in memory_values:
            mock_memory_info.rss = memory_bytes
            stats = monitor.get_memory_usage()

        # Peak should be 3GB
        final_stats = monitor.get_memory_usage()
        assert abs(final_stats["peak_gb"] - 3.0) < 0.01

    @patch("marc_pd_tool.utils.memory_utils.Process")
    @patch("marc_pd_tool.utils.memory_utils.virtual_memory")
    def test_check_memory_threshold(self, mock_virtual_memory: Mock, mock_process_class: Mock):
        """Test memory threshold checking"""
        # Mock process and memory info
        mock_process = Mock()
        mock_process_class.return_value = mock_process

        mock_memory_info = Mock()
        mock_memory_info.rss = 5 * 1024 * 1024 * 1024  # 5GB
        mock_process.memory_info.return_value = mock_memory_info

        mock_system_mem = Mock()
        mock_system_mem.percent = 50.0
        mock_system_mem.available = 8 * 1024 * 1024 * 1024
        mock_virtual_memory.return_value = mock_system_mem

        monitor = MemoryMonitor()

        # Should exceed 4GB threshold
        assert monitor.check_memory_threshold(4.0) is True

        # Should not exceed 6GB threshold
        assert monitor.check_memory_threshold(6.0) is False

    @patch("marc_pd_tool.utils.memory_utils.Process")
    @patch("marc_pd_tool.utils.memory_utils.virtual_memory")
    def test_log_if_needed_respects_interval(
        self, mock_virtual_memory: Mock, mock_process_class: Mock
    ):
        """Test log_if_needed respects the logging interval"""
        # Mock process and memory info
        mock_process = Mock()
        mock_process_class.return_value = mock_process

        mock_memory_info = Mock()
        mock_memory_info.rss = 1024 * 1024 * 1024  # 1GB
        mock_process.memory_info.return_value = mock_memory_info

        mock_system_mem = Mock()
        mock_system_mem.percent = 50.0
        mock_system_mem.available = 8 * 1024 * 1024 * 1024
        mock_virtual_memory.return_value = mock_system_mem

        monitor = MemoryMonitor(log_interval=1)  # 1 second interval

        with patch.object(monitor.logger, "info") as mock_info:
            # First call should log
            monitor.log_if_needed()
            assert mock_info.call_count >= 1

            # Immediate second call should not log
            mock_info.reset_mock()
            monitor.log_if_needed()
            assert mock_info.call_count == 0

            # Wait for interval to pass and try again
            sleep(1.1)
            monitor.log_if_needed()
            assert mock_info.call_count >= 1

    @patch("marc_pd_tool.utils.memory_utils.Process")
    @patch("marc_pd_tool.utils.memory_utils.virtual_memory")
    def test_force_log_always_logs(self, mock_virtual_memory: Mock, mock_process_class: Mock):
        """Test force_log always logs regardless of interval"""
        # Mock process and memory info
        mock_process = Mock()
        mock_process_class.return_value = mock_process

        mock_memory_info = Mock()
        mock_memory_info.rss = 1024 * 1024 * 1024  # 1GB
        mock_process.memory_info.return_value = mock_memory_info

        mock_system_mem = Mock()
        mock_system_mem.percent = 50.0
        mock_system_mem.available = 8 * 1024 * 1024 * 1024
        mock_virtual_memory.return_value = mock_system_mem

        monitor = MemoryMonitor(log_interval=3600)  # Very long interval

        with patch.object(monitor.logger, "info") as mock_info:
            # Multiple force_log calls should all log
            monitor.force_log("test context 1")
            monitor.force_log("test context 2")
            monitor.force_log()

            assert mock_info.call_count == 3

            # Verify context is included in log messages
            log_calls = mock_info.call_args_list
            assert "test context 1" in str(log_calls[0])
            assert "test context 2" in str(log_calls[1])

    @patch("marc_pd_tool.utils.memory_utils.Process")
    @patch("marc_pd_tool.utils.memory_utils.virtual_memory")
    def test_get_final_summary(self, mock_virtual_memory: Mock, mock_process_class: Mock):
        """Test get_final_summary returns formatted summary"""
        # Mock process and memory info
        mock_process = Mock()
        mock_process_class.return_value = mock_process

        mock_memory_info = Mock()
        mock_memory_info.rss = 2 * 1024 * 1024 * 1024  # 2GB
        mock_process.memory_info.return_value = mock_memory_info

        mock_system_mem = Mock()
        mock_system_mem.percent = 50.0
        mock_system_mem.available = 8 * 1024 * 1024 * 1024
        mock_virtual_memory.return_value = mock_system_mem

        monitor = MemoryMonitor()

        # Simulate some peak usage
        mock_memory_info.rss = 3 * 1024 * 1024 * 1024  # 3GB peak
        monitor.get_memory_usage()  # Update peak
        mock_memory_info.rss = 2 * 1024 * 1024 * 1024  # Back to 2GB

        summary = monitor.get_final_summary()

        assert "Memory Summary:" in summary
        assert "Peak" in summary and "3.0GB" in summary
        assert "Final" in summary and "2.0GB" in summary
        assert "Runtime" in summary and "minutes" in summary

    @patch("marc_pd_tool.utils.memory_utils.Process")
    @patch("marc_pd_tool.utils.memory_utils.virtual_memory")
    def test_log_memory_warning_if_high(self, mock_virtual_memory: Mock, mock_process_class: Mock):
        """Test log_memory_warning_if_high warns when threshold exceeded"""
        # Mock process and memory info
        mock_process = Mock()
        mock_process_class.return_value = mock_process

        mock_memory_info = Mock()
        mock_memory_info.rss = 10 * 1024 * 1024 * 1024  # 10GB
        mock_process.memory_info.return_value = mock_memory_info

        mock_system_mem = Mock()
        mock_system_mem.percent = 80.0
        mock_system_mem.available = 2 * 1024 * 1024 * 1024
        mock_virtual_memory.return_value = mock_system_mem

        monitor = MemoryMonitor()

        with patch.object(monitor.logger, "warning") as mock_warning:
            # Should warn when above 8GB default threshold
            monitor.log_memory_warning_if_high()
            assert mock_warning.call_count == 1
            assert "High memory usage detected" in str(mock_warning.call_args)

            # Should not warn with higher threshold
            mock_warning.reset_mock()
            monitor.log_memory_warning_if_high(warning_threshold_gb=15.0)
            assert mock_warning.call_count == 0

    @patch("marc_pd_tool.utils.memory_utils.Process")
    @patch("marc_pd_tool.utils.memory_utils.virtual_memory")
    def test_error_handling(self, mock_virtual_memory: Mock, mock_process_class: Mock):
        """Test error handling when psutil calls fail"""
        # Mock process that raises exceptions
        mock_process = Mock()
        mock_process_class.return_value = mock_process
        mock_process.memory_info.side_effect = Exception("Mock error")

        mock_virtual_memory.side_effect = Exception("Mock system error")

        monitor = MemoryMonitor()

        # Should handle errors gracefully and return default values
        stats = monitor.get_memory_usage()

        assert stats["process_gb"] == 0.0
        assert stats["system_percent"] == 0.0
        assert stats["available_gb"] == 0.0
        assert stats["peak_gb"] >= 0.0  # Peak should be preserved

        # Should still work for threshold checking
        assert monitor.check_memory_threshold(1.0) is False

        # Should still generate summary
        summary = monitor.get_final_summary()
        assert "Memory Summary:" in summary


class TestMemoryMonitorIntegration:
    """Integration tests for memory monitoring with realistic scenarios"""

    @patch("marc_pd_tool.utils.memory_utils.Process")
    @patch("marc_pd_tool.utils.memory_utils.virtual_memory")
    def test_realistic_monitoring_scenario(
        self, mock_virtual_memory: Mock, mock_process_class: Mock
    ):
        """Test a realistic monitoring scenario with changing memory usage"""
        # Mock process and system memory
        mock_process = Mock()
        mock_process_class.return_value = mock_process

        mock_memory_info = Mock()
        mock_process.memory_info.return_value = mock_memory_info

        mock_system_mem = Mock()
        mock_virtual_memory.return_value = mock_system_mem

        monitor = MemoryMonitor(log_interval=0.1)  # Very short interval for testing

        # Simulate a processing scenario with increasing then decreasing memory
        memory_progression = [
            (1.0, 60.0, 8.0),  # 1GB process, 60% system, 8GB available
            (2.5, 65.0, 7.5),  # Increase during processing
            (4.0, 70.0, 6.0),  # Peak usage
            (3.5, 68.0, 6.5),  # Slight decrease
            (1.5, 62.0, 7.8),  # Back to baseline
        ]

        peak_seen = 0.0
        with patch.object(monitor.logger, "info") as mock_info:
            for process_gb, system_percent, available_gb in memory_progression:
                mock_memory_info.rss = int(process_gb * 1024 * 1024 * 1024)
                mock_system_mem.percent = system_percent
                mock_system_mem.available = int(available_gb * 1024 * 1024 * 1024)

                stats = monitor.get_memory_usage()
                peak_seen = max(peak_seen, stats["process_gb"])

                # Force log each measurement
                monitor.force_log(f"step at {process_gb}GB")

        # Verify peak tracking
        assert abs(monitor.peak_memory - 4.0) < 0.01

        # Verify logging occurred
        assert mock_info.call_count == len(memory_progression)

        # Verify final summary includes correct peak
        summary = monitor.get_final_summary()
        assert "4.0GB" in summary

    def test_monitor_context_usage_pattern(self):
        """Test memory monitor usage pattern that would be used in real processing"""
        with patch("marc_pd_tool.utils.memory_utils.Process") as mock_process_class:
            with patch("marc_pd_tool.utils.memory_utils.virtual_memory") as mock_virtual_memory:
                # Setup mocks
                mock_process = Mock()
                mock_process_class.return_value = mock_process

                mock_memory_info = Mock()
                mock_memory_info.rss = 2 * 1024 * 1024 * 1024  # 2GB
                mock_process.memory_info.return_value = mock_memory_info

                mock_system_mem = Mock()
                mock_system_mem.percent = 50.0
                mock_system_mem.available = 8 * 1024 * 1024 * 1024
                mock_virtual_memory.return_value = mock_system_mem

                # Simulate realistic usage pattern
                monitor = MemoryMonitor(log_interval=1)

                # Initial state
                monitor.force_log("initialization")

                # Simulate processing batches
                for i in range(5):
                    # Simulate memory increase during batch processing
                    mock_memory_info.rss = (2 + i * 0.5) * 1024 * 1024 * 1024

                    # Check if we should log
                    monitor.log_if_needed()

                    # Check if memory is getting too high
                    if monitor.check_memory_threshold(3.0):
                        monitor.log_memory_warning_if_high(3.0)

                # Final summary
                summary = monitor.get_final_summary()
                assert isinstance(summary, str)
                assert len(summary) > 0
