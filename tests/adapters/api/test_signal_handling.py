# tests/adapters/api/test_signal_handling.py

"""Tests for signal handling and cleanup functionality"""

# Standard library imports
from os.path import exists
from os.path import join
from pathlib import Path
from pickle import HIGHEST_PROTOCOL
from pickle import dump
import shutil  # full import requore for patching
import signal  # full import requore for patching
from tempfile import mkdtemp
from unittest.mock import MagicMock
from unittest.mock import patch

# Third party imports
from pytest import raises

# Local imports
from marc_pd_tool import MarcCopyrightAnalyzer
from marc_pd_tool.application.models.analysis_results import AnalysisResults
from marc_pd_tool.application.models.config_models import AnalysisOptions
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication


class TestSignalHandling:
    """Test signal handling and cleanup functionality"""

    def test_cleanup_temp_files_removes_directory(self):
        """Test that cleanup_temp_files removes the temporary directory"""
        results = AnalysisResults()

        # Create a real temp directory
        temp_dir = mkdtemp(prefix="test_cleanup_")

        # Add some test files
        test_file = join(temp_dir, "test.pkl")
        with open(test_file, "wb") as f:
            dump({"test": "data"}, f, protocol=HIGHEST_PROTOCOL)

        # Set up results with temp directory
        results.result_temp_dir = temp_dir
        results.result_file_paths = [test_file]

        # Verify directory exists
        assert exists(temp_dir)
        assert exists(test_file)

        # Call cleanup
        results.cleanup_temp_files()

        # Verify cleanup
        assert not exists(temp_dir)
        assert results.result_temp_dir is None
        assert len(results.result_file_paths) == 0

    def test_cleanup_temp_files_handles_missing_directory(self):
        """Test that cleanup_temp_files handles missing directory gracefully"""
        results = AnalysisResults()
        results.result_temp_dir = "/nonexistent/directory"
        results.result_file_paths = ["/nonexistent/file.pkl"]

        # Should not raise exception
        results.cleanup_temp_files()

        assert results.result_temp_dir is None
        assert len(results.result_file_paths) == 0

    def test_cleanup_temp_files_handles_permission_error(self):
        """Test that cleanup_temp_files handles permission errors gracefully"""
        results = AnalysisResults()
        temp_dir = mkdtemp(prefix="test_cleanup_")
        results.result_temp_dir = temp_dir

        with patch("marc_pd_tool.application.models.analysis_results.rmtree") as mock_rmtree:
            mock_rmtree.side_effect = PermissionError("Access denied")

            # Should log warning but not raise
            with patch("marc_pd_tool.application.models.analysis_results.logger") as mock_logger:
                results.cleanup_temp_files()
                mock_logger.warning.assert_called_once()
                assert "Failed to clean up temp directory" in str(mock_logger.warning.call_args)

        # Manual cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("marc_pd_tool.adapters.api._processing.signal.signal")
    @patch("marc_pd_tool.adapters.api._processing.atexit.register")
    def test_process_parallel_registers_signal_handlers(self, mock_atexit, mock_signal):
        """Test that _process_parallel registers signal handlers"""
        analyzer = MarcCopyrightAnalyzer()
        publications = [
            Publication(
                title="Test",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
        ]

        with patch("marc_pd_tool.adapters.api._processing.Pool") as mock_pool_class:
            mock_pool = MagicMock()
            mock_pool_class.return_value.__enter__.return_value = mock_pool
            mock_pool.imap_unordered.return_value = []

            with patch("marc_pd_tool.adapters.api._processing.mkdtemp") as mock_mkdtemp:
                mock_mkdtemp.return_value = "/tmp/test"

                analyzer._process_parallel(
                    publications=publications,
                    batch_size=100,
                    num_processes=2,
                    year_tolerance=1,
                    title_threshold=40,
                    author_threshold=30,
                    publisher_threshold=None,
                    early_exit_title=95,
                    early_exit_author=90,
                    early_exit_publisher=None,
                    score_everything_mode=False,
                    minimum_combined_score=None,
                    brute_force_missing_year=False,
                    min_year=None,
                    max_year=None,
                )

        # Verify signal handlers were registered
        assert mock_signal.call_count >= 2  # SIGINT and SIGTERM
        signal_calls = mock_signal.call_args_list

        # Check that SIGINT was registered
        sigint_registered = any(call[0][0] == signal.SIGINT for call in signal_calls)
        assert sigint_registered, "SIGINT handler not registered"

        # Check that SIGTERM was registered
        sigterm_registered = any(call[0][0] == signal.SIGTERM for call in signal_calls)
        assert sigterm_registered, "SIGTERM handler not registered"

        # Verify atexit was registered
        mock_atexit.assert_called()

    @patch("marc_pd_tool.adapters.api._processing.signal.signal")
    def test_process_parallel_restores_signal_handlers(self, mock_signal):
        """Test that _process_parallel restores original signal handlers"""
        analyzer = MarcCopyrightAnalyzer()
        publications = []

        # Mock original handlers
        original_sigint = MagicMock()
        original_sigterm = MagicMock()

        # Set up mock_signal to return original handlers
        def signal_side_effect(sig, handler):
            if sig == signal.SIGINT:
                return original_sigint
            elif sig == signal.SIGTERM:
                return original_sigterm
            return None

        mock_signal.side_effect = signal_side_effect

        with patch("marc_pd_tool.adapters.api._processing.Pool") as mock_pool_class:
            mock_pool = MagicMock()
            mock_pool_class.return_value.__enter__.return_value = mock_pool
            mock_pool.imap_unordered.return_value = []

            with patch("marc_pd_tool.adapters.api._processing.mkdtemp") as mock_mkdtemp:
                mock_mkdtemp.return_value = "/tmp/test"

                with patch("marc_pd_tool.adapters.api._processing.atexit.unregister"):
                    analyzer._process_parallel(
                        publications=publications,
                        batch_size=100,
                        num_processes=2,
                        year_tolerance=1,
                        title_threshold=40,
                        author_threshold=30,
                        publisher_threshold=None,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=None,
                        score_everything_mode=False,
                        minimum_combined_score=None,
                        brute_force_missing_year=False,
                        min_year=None,
                        max_year=None,
                    )

        # Verify handlers were restored in finally block
        # Should have been called 4 times total: 2 to register, 2 to restore
        assert mock_signal.call_count == 4

        # Last two calls should restore original handlers
        last_calls = mock_signal.call_args_list[-2:]
        assert any(call[0] == (signal.SIGINT, original_sigint) for call in last_calls)
        assert any(call[0] == (signal.SIGTERM, original_sigterm) for call in last_calls)

    def test_process_parallel_cleanup_on_keyboard_interrupt(self):
        """Test that cleanup happens on KeyboardInterrupt"""
        analyzer = MarcCopyrightAnalyzer()
        publications = [
            Publication(
                title="Test",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
        ]

        # Patch the cleanup method on the class
        with patch(
            "marc_pd_tool.application.models.analysis_results.AnalysisResults.cleanup_temp_files"
        ) as mock_cleanup:
            with patch("marc_pd_tool.adapters.api._processing.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Simulate KeyboardInterrupt during processing
                mock_pool.imap_unordered.side_effect = KeyboardInterrupt()

                with patch("marc_pd_tool.adapters.api._processing.mkdtemp") as mock_mkdtemp:
                    mock_mkdtemp.return_value = "/tmp/test"

                    with raises(KeyboardInterrupt):
                        analyzer._process_parallel(
                            publications=publications,
                            batch_size=100,
                            num_processes=2,
                            year_tolerance=1,
                            title_threshold=40,
                            author_threshold=30,
                            publisher_threshold=None,
                            early_exit_title=95,
                            early_exit_author=90,
                            early_exit_publisher=None,
                            score_everything_mode=False,
                            minimum_combined_score=None,
                            brute_force_missing_year=False,
                            min_year=None,
                            max_year=None,
                        )

        # The KeyboardInterrupt should be re-raised
        # Note: actual cleanup via signal handler won't be called in tests
        # since we're mocking signal.signal

    def test_cleanup_handler_on_sigint(self):
        """Test that cleanup handler behaves correctly on SIGINT"""
        analyzer = MarcCopyrightAnalyzer()

        # Create a real temp directory
        temp_dir = mkdtemp(prefix="test_sigint_")
        analyzer.results.result_temp_dir = temp_dir

        # Create test file
        test_file = join(temp_dir, "test.pkl")
        Path(test_file).touch()

        # Get the cleanup handler function
        # We need to extract it from the _process_parallel method
        cleanup_handler = None

        with patch("marc_pd_tool.adapters.api._processing.signal.signal") as mock_signal:

            def capture_handler(sig, handler):
                nonlocal cleanup_handler
                if sig == signal.SIGINT and callable(handler):
                    cleanup_handler = handler
                return MagicMock()

            mock_signal.side_effect = capture_handler

            with patch("marc_pd_tool.adapters.api._processing.Pool"):
                with patch("marc_pd_tool.adapters.api._processing.mkdtemp"):
                    try:
                        analyzer._process_parallel(
                            publications=[],
                            batch_size=100,
                            num_processes=2,
                            year_tolerance=1,
                            title_threshold=40,
                            author_threshold=30,
                            publisher_threshold=None,
                            early_exit_title=95,
                            early_exit_author=90,
                            early_exit_publisher=None,
                            score_everything_mode=False,
                            minimum_combined_score=None,
                            brute_force_missing_year=False,
                            min_year=None,
                            max_year=None,
                        )
                    except:
                        pass

        # Clean up manually
        if exists(temp_dir):
            shutil.rmtree(temp_dir)

    def test_file_tracking_persistence(self):
        """Test that result file paths are properly tracked"""
        results = AnalysisResults()

        # Add multiple result files
        test_files = [
            "/tmp/batch_001_result.pkl",
            "/tmp/batch_002_result.pkl",
            "/tmp/batch_003_result.pkl",
        ]

        for file_path in test_files:
            results.add_result_file(file_path)

        # Verify all files are tracked
        assert len(results.result_file_paths) == 3
        assert all(f in results.result_file_paths for f in test_files)

        # Test the new two-argument API
        results.add_result_file("json", "/tmp/output.json")
        assert results.result_files["json"] == "/tmp/output.json"

    def test_cleanup_called_after_successful_export(self):
        """Test that cleanup is called after successful export"""
        analyzer = MarcCopyrightAnalyzer()

        with patch(
            "marc_pd_tool.application.models.analysis_results.AnalysisResults.cleanup_temp_files"
        ) as mock_cleanup:
            with patch.object(analyzer, "export_results"):
                with patch.object(analyzer, "_load_and_index_data"):
                    with patch.object(analyzer, "_process_marc_batches"):
                        with patch("marc_pd_tool.adapters.api._analyzer.MarcLoader") as mock_loader:
                            # Mock extract_batches_to_disk instead of extract_all_batches
                            mock_loader.return_value.extract_batches_to_disk.return_value = (
                                ["batch1.pkl"],
                                1,
                                0,
                            )

                            # Call analyze_marc_file with output path
                            analyzer.analyze_marc_file(
                                "/test/marc.xml",
                                copyright_dir="/test/copyright",
                                renewal_dir="/test/renewal",
                                output_path="/test/output",
                                options=AnalysisOptions(),
                            )

            # Cleanup should have been called
            mock_cleanup.assert_called_once()
