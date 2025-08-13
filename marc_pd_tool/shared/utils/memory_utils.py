# marc_pd_tool/shared/utils/memory_utils.py

"""Memory monitoring utilities for tracking resource usage during processing"""

# Standard library imports
from logging import getLogger
from time import time

# Third party imports
from psutil import Process
from psutil import virtual_memory

logger = getLogger(__name__)


class MemoryMonitor:
    """Monitor and log memory usage during processing

    This class provides functionality to track memory usage over time,
    log statistics at regular intervals, and provide peak usage tracking.
    Useful for validating that streaming mode keeps memory usage bounded
    during processing of large datasets.
    """

    def __init__(self, log_interval: int = 60) -> None:
        """Initialize memory monitor

        Args:
            log_interval: Seconds between memory usage logs (default: 60)
        """
        self.process = Process()  # type: ignore[misc]
        self.log_interval = log_interval
        self.last_log_time = 0.0
        self.logger = getLogger(__name__)
        self.peak_memory = 0.0
        self.start_time = time()

        # Log initial memory state
        initial_stats = self.get_memory_usage()
        self.logger.info(
            f"Memory monitoring initialized: {initial_stats['process_gb']:.1f}GB process memory"
        )

    def log_if_needed(self) -> None:
        """Log memory stats if interval has passed since last log"""
        current_time = time()
        if current_time - self.last_log_time >= self.log_interval:
            stats = self.get_memory_usage()
            elapsed_minutes = (current_time - self.start_time) / 60

            self.logger.info(
                f"Memory [{elapsed_minutes:.1f}min]: {stats['process_gb']:.1f}GB process, "
                f"{stats['system_percent']:.1f}% system used, "
                f"Peak: {self.peak_memory:.1f}GB"
            )
            self.last_log_time = current_time

    def force_log(self, context: str = "") -> None:
        """Force immediate memory logging regardless of interval

        Args:
            context: Optional context description for the log
        """
        stats = self.get_memory_usage()
        elapsed_minutes = (time() - self.start_time) / 60

        context_str = f" ({context})" if context else ""
        self.logger.info(
            f"Memory [{elapsed_minutes:.1f}min]{context_str}: {stats['process_gb']:.1f}GB process, "
            f"{stats['system_percent']:.1f}% system used, "
            f"Peak: {self.peak_memory:.1f}GB"
        )

    def get_memory_usage(self) -> dict[str, float]:
        """Get current memory usage statistics

        Returns:
            Dictionary with memory statistics including:
            - process_gb: Current process memory in GB
            - system_percent: System memory usage percentage
            - available_gb: Available system memory in GB
            - peak_gb: Peak process memory usage in GB
        """
        try:
            mem_info = self.process.memory_info()  # type: ignore[misc]
            process_gb = mem_info.rss / (1024**3)  # type: ignore[misc]
            self.peak_memory = max(self.peak_memory, process_gb)  # type: ignore[misc]

            system_mem = virtual_memory()  # type: ignore[misc]
            return {
                "process_gb": process_gb,  # type: ignore[misc]
                "system_percent": system_mem.percent,  # type: ignore[misc]
                "available_gb": system_mem.available / (1024**3),  # type: ignore[misc]
                "peak_gb": self.peak_memory,
            }
        except Exception as e:
            self.logger.warning(f"Error getting memory usage: {e}")
            return {
                "process_gb": 0.0,
                "system_percent": 0.0,
                "available_gb": 0.0,
                "peak_gb": self.peak_memory,
            }

    def get_final_summary(self) -> str:
        """Get a final memory usage summary

        Returns:
            Formatted string with final memory statistics
        """
        final_stats = self.get_memory_usage()
        elapsed_time = time() - self.start_time

        return (
            f"Memory Summary: Peak {final_stats['peak_gb']:.1f}GB, "
            f"Final {final_stats['process_gb']:.1f}GB, "
            f"Runtime {elapsed_time/60:.1f} minutes"
        )

    def check_memory_threshold(self, threshold_gb: float) -> bool:
        """Check if current memory usage exceeds threshold

        Args:
            threshold_gb: Memory threshold in GB

        Returns:
            True if memory usage exceeds threshold
        """
        stats = self.get_memory_usage()
        return stats["process_gb"] > threshold_gb

    def log_memory_warning_if_high(self, warning_threshold_gb: float = 8.0) -> None:
        """Log a warning if memory usage is high

        Args:
            warning_threshold_gb: Threshold in GB for warning (default: 8GB)
        """
        if self.check_memory_threshold(warning_threshold_gb):
            stats = self.get_memory_usage()
            self.logger.warning(
                f"High memory usage detected: {stats['process_gb']:.1f}GB "
                f"(threshold: {warning_threshold_gb}GB). Consider using streaming mode."
            )
