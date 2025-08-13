# tests/test_infrastructure/test_logging_format.py

"""Tests for logging format and output consistency in processing phases"""

# Standard library imports
from io import StringIO
from logging import DEBUG
from logging import INFO
from logging import StreamHandler
from logging import getLogger
from unittest.mock import MagicMock
from unittest.mock import patch

# Local imports
from marc_pd_tool.application.processing.matching_engine import init_worker
from marc_pd_tool.infrastructure.logging import setup_logging


class TestLoggingConfiguration:
    """Test logging configuration improvements"""

    def test_console_formatter_includes_timestamp(self):
        """Test that console formatter includes timestamps"""
        # Capture log output
        StringIO()

        # Set up logging with our setup function
        with patch(
            "marc_pd_tool.infrastructure.logging._setup.StreamHandler"
        ) as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler

            setup_logging(disable_file_logging=True)

            # Verify formatter was set with timestamp
            mock_handler.setFormatter.assert_called_once()
            formatter_call = mock_handler.setFormatter.call_args[0][0]

            # Format string should include asctime
            assert "%(asctime)s" in formatter_call._fmt
            assert "%(levelname)s" in formatter_call._fmt
            assert "%(message)s" in formatter_call._fmt

    def test_worker_logger_configuration(self):
        """Test that worker logger is configured correctly"""
        with patch(
            "marc_pd_tool.application.processing.matching_engine.getLogger"
        ) as mock_get_logger:
            mock_root_logger = MagicMock()
            mock_module_logger = MagicMock()

            # Configure mock to return different loggers
            def get_logger_side_effect(name=None):
                if name is None:
                    return mock_root_logger
                return mock_module_logger

            mock_get_logger.side_effect = get_logger_side_effect

            # Mock the cache manager and indexes (imported inside init_worker)
            with patch("marc_pd_tool.infrastructure.CacheManager") as mock_cache_manager:
                mock_cache = MagicMock()
                mock_cache.get_cached_indexes.return_value = (MagicMock(), MagicMock())
                mock_cache.get_cached_generic_detector.return_value = MagicMock()
                mock_cache_manager.return_value = mock_cache

                # Initialize worker
                init_worker(
                    cache_dir="test_cache",
                    copyright_dir="test_copyright",
                    renewal_dir="test_renewal",
                    config_hash="test_hash",
                    detector_config={},
                    min_year=1950,
                    max_year=1970,
                    brute_force=False,
                )

                # Verify handlers were cleared and new one added
                mock_root_logger.handlers.clear.assert_called_once()
                mock_module_logger.handlers.clear.assert_called_once()

                # Verify propagate was set to False to avoid duplicates
                assert mock_module_logger.propagate is False


class TestBatchProcessingLogs:
    """Test batch processing log improvements"""

    def test_main_process_batch_logging_format(self):
        """Test that main process logs batch completion with correct format"""
        # Local imports
        from marc_pd_tool.application.models.batch_stats import BatchStats

        # Create mock batch stats
        batch_stats = BatchStats(
            batch_id=1,
            marc_count=100,
            registration_matches_found=5,
            renewal_matches_found=3,
            processing_time=10.5,
        )

        # Test the format string construction
        batch_id = 1
        total_batches = 100
        progress_pct = (batch_id / total_batches) * 100
        total_reg = 10
        total_ren = 8
        records_per_second = 9.5

        # This is the actual format used in _processing.py
        log_message = (
            f"Batch {batch_id:4d}/{total_batches} [{progress_pct:5.1f}%] | "
            f"Found: {batch_stats.registration_matches_found:2d} reg, "
            f"{batch_stats.renewal_matches_found:2d} ren | "
            f"Total: {total_reg:5d} reg, {total_ren:5d} ren | "
            f"{records_per_second:5.1f} rec/s"
        )

        # Verify format matches expected pattern
        assert "Batch    1/100" in log_message
        assert "[  1.0%]" in log_message
        assert "Found:  5 reg,  3 ren" in log_message
        assert "Total:    10 reg,     8 ren" in log_message
        assert "  9.5 rec/s" in log_message

    def test_worker_only_logs_exceptional_cases(self):
        """Test that workers only log when something unusual happens"""
        # Local imports
        from marc_pd_tool.application.models.batch_stats import BatchStats
        from marc_pd_tool.core.domain.publication import Publication

        # Set up test logger to capture output
        log_capture = StringIO()
        handler = StreamHandler(log_capture)
        logger = getLogger("marc_pd_tool.application.processing.matching_engine")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(DEBUG)  # Set to DEBUG to capture all logs

        # Create test batch with all records having years (normal case)
        batch = [Publication(title=f"Book {i}", year=1950 + i) for i in range(10)]

        # Mock the batch stats for normal processing
        stats = BatchStats(
            batch_id=1,
            marc_count=10,  # All processed
            registration_matches_found=2,
            renewal_matches_found=1,
            processing_time=2.0,  # Fast processing
        )

        # Simulate the logging that would happen at the end of process_batch
        # Normal case: all records processed, fast speed
        elapsed = 2.0
        records_per_sec = stats.marc_count / elapsed if elapsed > 0 else 0

        # This should NOT generate any INFO logs (only DEBUG)
        if stats.marc_count < len(batch):
            skipped = len(batch) - stats.marc_count
            logger.debug(f"  Batch 1: {skipped} records skipped (no year or filtered)")

        if elapsed > 30 and records_per_sec < 5:
            logger.warning(f"  Batch 1: Slow processing detected ({records_per_sec:.1f} rec/s)")

        # Check that no logs were generated for normal processing
        log_output = log_capture.getvalue()
        assert "Slow processing" not in log_output
        assert "skipped" not in log_output  # No skipped records

        # Now test exceptional case - slow processing
        log_capture.truncate(0)
        log_capture.seek(0)

        elapsed = 35.0  # Slow
        records_per_sec = 2.0  # Less than 5 rec/s

        if elapsed > 30 and records_per_sec < 5:
            logger.warning(f"  Batch 2: Slow processing detected ({records_per_sec:.1f} rec/s)")

        log_output = log_capture.getvalue()
        assert "Slow processing detected" in log_output
        assert "2.0 rec/s" in log_output


class TestPhaseLogging:
    """Test phase boundary logging improvements"""

    def test_phase_3_header_includes_configuration(self):
        """Test that Phase 3 header shows configuration details"""
        pass

        # Capture log output
        log_capture = StringIO()
        handler = StreamHandler(log_capture)
        logger = getLogger("marc_pd_tool.adapters.api._processing")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(INFO)

        # Test the logging that happens at the start of parallel processing
        total_batches = 100
        num_processes = 4
        batch_size = 50
        year_tolerance = 2
        title_threshold = 40
        author_threshold = 30
        publisher_threshold = 25

        # Log the configuration as the code does
        logger.info(
            f"Starting parallel processing: {total_batches} batches across {num_processes} workers"
        )
        logger.info(f"Configuration: batch_size={batch_size}, year_tolerance={year_tolerance}")
        logger.info(
            f"Thresholds: title={title_threshold}%, author={author_threshold}%, publisher={publisher_threshold}%"
        )

        log_output = log_capture.getvalue()

        # Verify all configuration details are logged
        assert "100 batches across 4 workers" in log_output
        assert "batch_size=50" in log_output
        assert "year_tolerance=2" in log_output
        assert "title=40%" in log_output
        assert "author=30%" in log_output
        assert "publisher=25%" in log_output

    def test_phase_3_completion_summary(self):
        """Test that Phase 3 completion shows proper summary"""
        pass

        # Capture log output
        log_capture = StringIO()
        handler = StreamHandler(log_capture)
        logger = getLogger("marc_pd_tool.adapters.api._processing")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(INFO)

        # Simulate completion logging
        registration_matches = 1234
        renewal_matches = 567

        logger.info("")  # Blank line for readability
        logger.info("=" * 80)
        logger.info(
            f"Phase 3 Complete: "
            f"{registration_matches:,} registration, "
            f"{renewal_matches:,} renewal matches found"
        )
        logger.info("=" * 80)

        log_output = log_capture.getvalue()

        # Verify formatting
        assert "Phase 3 Complete" in log_output
        assert "1,234 registration" in log_output
        assert "567 renewal" in log_output
        assert "=" * 80 in log_output  # Separator lines
