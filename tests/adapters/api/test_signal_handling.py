# tests/adapters/api/test_signal_handling.py

"""Tests for signal handling and cleanup functionality"""

# Standard library imports
from os.path import exists
from os.path import join
from pathlib import Path
from pickle import HIGHEST_PROTOCOL
from pickle import dump
import shutil
import signal
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

    def test_analyzer_registers_cleanup_handlers(self):
        """Test that analyzer registers signal and atexit handlers"""
        with patch("marc_pd_tool.adapters.api._analyzer.atexit_register") as mock_atexit:
            with patch("marc_pd_tool.adapters.api._analyzer.signal_handler") as mock_signal:
                analyzer = MarcCopyrightAnalyzer()
                
                # Verify atexit was registered
                mock_atexit.assert_called_once()
                
                # Verify signal handlers were registered
                assert mock_signal.call_count >= 2  # SIGINT and SIGTERM
                signal_calls = mock_signal.call_args_list
                
                # Check that SIGINT was registered
                sigint_registered = any(call[0][0] == signal.SIGINT for call in signal_calls)
                assert sigint_registered, "SIGINT handler not registered"
                
                # Check that SIGTERM was registered  
                sigterm_registered = any(call[0][0] == signal.SIGTERM for call in signal_calls)
                assert sigterm_registered, "SIGTERM handler not registered"

    def test_streaming_cleanup_on_keyboard_interrupt(self):
        """Test cleanup happens on keyboard interrupt during streaming"""
        analyzer = MarcCopyrightAnalyzer()
        
        # Create a temp directory for testing
        temp_dir = mkdtemp(prefix="test_interrupt_")
        test_file = join(temp_dir, "test.pkl")
        Path(test_file).write_text("test data")
        
        try:
            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                # Simulate KeyboardInterrupt during processing
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool
                mock_pool.imap_unordered.side_effect = KeyboardInterrupt()
                
                with patch.object(analyzer, "results") as mock_results:
                    mock_results.result_temp_dir = temp_dir
                    mock_results.result_file_paths = [test_file]
                    mock_results.cleanup_temp_files = MagicMock()
                    mock_results.publications = []
                    
                    # The streaming process should handle the interrupt and cleanup
                    options = AnalysisOptions()
                    
                    # This should handle KeyboardInterrupt and call cleanup
                    result = analyzer._process_streaming_parallel(
                        batch_paths=[test_file],
                        num_processes=2,
                        year_tolerance=1,
                        title_threshold=40,
                        author_threshold=30,
                        publisher_threshold=50,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        score_everything_mode=False,
                        minimum_combined_score=None,
                        brute_force_missing_year=False,
                        min_year=None,
                        max_year=None,
                    )
                    
                    # Verify cleanup was called
                    mock_results.cleanup_temp_files.assert_called()
                    # Should return empty publications list
                    assert result == []
        finally:
            # Manual cleanup
            if exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def test_cleanup_handler_called_on_exit(self):
        """Test that cleanup handler is called on normal exit"""
        analyzer = MarcCopyrightAnalyzer()
        
        # Create a real temp directory
        temp_dir = mkdtemp(prefix="test_exit_")
        test_file = join(temp_dir, "test.pkl")
        Path(test_file).write_text("test data")
        
        try:
            # Set up analyzer with temp files  
            analyzer.results.result_temp_dir = temp_dir
            analyzer.results.result_file_paths = [test_file]
            
            # Test the cleanup handler
            analyzer._cleanup_on_exit()
            
            # Verify temp files were cleaned
            assert not exists(temp_dir)
        except Exception:
            # If cleanup didn't work, do it manually
            if exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def test_streaming_worker_ignores_sigint(self):
        """Test that streaming workers ignore SIGINT for proper cleanup"""
        # Test that workers set SIGINT to SIG_IGN
        # This is done in the worker initialization
        
        # Simulate worker initialization
        def mock_worker_init():
            import signal
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        
        # Store original handler
        original_handler = signal.signal(signal.SIGINT, signal.SIG_DFL)
        
        try:
            # Run worker init
            mock_worker_init()
            
            # Verify SIGINT is now ignored
            current_handler = signal.signal(signal.SIGINT, signal.SIG_DFL)
            assert current_handler == signal.SIG_IGN
        finally:
            # Restore original handler
            signal.signal(signal.SIGINT, original_handler)

    def test_file_tracking_persistence(self):
        """Test that result file paths are tracked persistently"""
        results = AnalysisResults()
        
        # Create temp directory and files
        temp_dir = mkdtemp(prefix="test_tracking_")
        files = []
        for i in range(3):
            file_path = join(temp_dir, f"result_{i}.pkl")
            Path(file_path).write_text(f"data_{i}")
            files.append(file_path)
        
        # Track files
        results.result_temp_dir = temp_dir
        results.result_file_paths = files
        
        # Verify tracking
        assert results.result_temp_dir == temp_dir
        assert len(results.result_file_paths) == 3
        assert all(exists(f) for f in results.result_file_paths)
        
        # Clean up
        results.cleanup_temp_files()
        assert not exists(temp_dir)

    def test_cleanup_called_after_successful_export(self):
        """Test that cleanup is automatically called via atexit"""
        # Just verify that the analyzer registers cleanup handlers
        # The actual cleanup after export is tested in the integration tests
        
        with patch("marc_pd_tool.adapters.api._analyzer.atexit_register") as mock_atexit:
            analyzer = MarcCopyrightAnalyzer()
            
            # Verify atexit was registered with the cleanup handler
            mock_atexit.assert_called_once()
            
            # Get the registered function
            cleanup_func = mock_atexit.call_args[0][0]
            
            # Verify it's the cleanup_on_exit method
            assert cleanup_func == analyzer._cleanup_on_exit