# tests/adapters/api/test_batch_processing.py

"""Tests for batch processing component functionality"""

# Standard library imports
from os.path import join
from pathlib import Path
from pickle import HIGHEST_PROTOCOL
from pickle import dump
import shutil
from tempfile import mkdtemp
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool import MarcCopyrightAnalyzer
from marc_pd_tool.application.models.batch_stats import BatchStats
from marc_pd_tool.application.processing.indexer import DataIndexer
from marc_pd_tool.core.domain.publication import Publication


class TestBatchProcessingComponent:
    """Test batch processing component functionality"""

    def test_batch_processing_processes_batches(self):
        """Test that batch processing processes batch files"""
        analyzer = MarcCopyrightAnalyzer()

        # Create temp directory with batch file
        temp_dir = mkdtemp(prefix="test_batch_")
        batch_file = join(temp_dir, "batch_001.pkl")

        # Create a batch with test publications
        test_pubs = [Publication(title="Test Book", pub_date="1960", source_id="001")]

        with open(batch_file, "wb") as f:
            dump(test_pubs, f, protocol=HIGHEST_PROTOCOL)

        try:
            # Mock the Pool to avoid actual multiprocessing
            with patch("marc_pd_tool.adapters.api._batch_processing.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Mock the results from processing
                stats = BatchStats(batch_id=1, total_batches=1)
                stats.marc_count = 1
                mock_pool.imap_unordered.return_value = iter([(1, "result.pkl", stats)])

                # Process the batch
                result = analyzer._process_batches_parallel(
                    batch_paths=[batch_file],
                    num_processes=1,
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

                # Verify processing was called
                assert mock_pool.imap_unordered.called
                # Verify result is the publications list
                assert isinstance(result, list)
        finally:
            # Clean up
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir)

    def test_batch_processing_handles_fork_mode(self):
        """Test that streaming handles fork mode correctly"""
        analyzer = MarcCopyrightAnalyzer()

        # Set up pre-loaded indexes for fork mode
        analyzer.registration_index = Mock(spec=DataIndexer)
        analyzer.renewal_index = Mock(spec=DataIndexer)

        batch_file = "/test/batch.pkl"

        with patch("marc_pd_tool.adapters.api._batch_processing.Pool") as mock_pool_class:
            mock_pool = MagicMock()
            mock_pool_class.return_value.__enter__.return_value = mock_pool

            stats = BatchStats(batch_id=1, total_batches=1)
            mock_pool.imap_unordered.return_value = iter([(1, "result.pkl", stats)])

            with patch("marc_pd_tool.adapters.api._batch_processing.get_start_method") as mock_start:
                mock_start.return_value = "fork"

                # Process with fork mode
                analyzer._process_batches_parallel(
                    batch_paths=[batch_file],
                    num_processes=1,
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

                # Verify fork mode was detected
                mock_start.assert_called_once()

                # Verify Pool was created with initializer for fork mode
                call_kwargs = mock_pool_class.call_args[1]
                assert "initializer" in call_kwargs

    def test_batch_processing_handles_spawn_mode(self):
        """Test that streaming handles spawn mode correctly"""
        analyzer = MarcCopyrightAnalyzer()

        batch_file = "/test/batch.pkl"

        with patch("marc_pd_tool.adapters.api._batch_processing.Pool") as mock_pool_class:
            mock_pool = MagicMock()
            mock_pool_class.return_value.__enter__.return_value = mock_pool

            stats = BatchStats(batch_id=1, total_batches=1)
            mock_pool.imap_unordered.return_value = iter([(1, "result.pkl", stats)])

            with patch("marc_pd_tool.adapters.api._batch_processing.get_start_method") as mock_start:
                mock_start.return_value = "spawn"

                # Process with spawn mode
                analyzer._process_batches_parallel(
                    batch_paths=[batch_file],
                    num_processes=1,
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

                # Verify spawn mode was detected
                mock_start.assert_called_once()

                # Verify Pool was created with initializer and initargs for spawn mode
                call_kwargs = mock_pool_class.call_args[1]
                assert "initializer" in call_kwargs
                if "initargs" in call_kwargs:
                    # Spawn mode should have initargs
                    assert call_kwargs["initargs"] is not None

    def test_batch_processing_cleanup_on_error(self):
        """Test that streaming cleans up on error"""
        analyzer = MarcCopyrightAnalyzer()

        batch_file = "/test/batch.pkl"

        with patch("marc_pd_tool.adapters.api._batch_processing.Pool") as mock_pool_class:
            mock_pool = MagicMock()
            mock_pool_class.return_value.__enter__.return_value = mock_pool

            # Simulate an error during processing
            mock_pool.imap_unordered.side_effect = Exception("Test error")

            with patch("marc_pd_tool.adapters.api._batch_processing.mkdtemp") as mock_mkdtemp:
                temp_dir = mkdtemp(prefix="test_error_")
                mock_mkdtemp.return_value = temp_dir

                try:
                    # Process should handle the error
                    result = analyzer._process_batches_parallel(
                        batch_paths=[batch_file],
                        num_processes=1,
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

                    # Should return empty list on error
                    assert result == []

                    # Temp directory should still be set in finally block
                    assert analyzer.results.result_temp_dir == temp_dir

                    # Directory still exists but will be cleaned up by _cleanup_on_exit
                    assert Path(temp_dir).exists(), "Temp dir still exists until cleanup_on_exit"

                    # Now call cleanup manually to verify it works
                    analyzer._cleanup_on_exit()
                    assert not Path(
                        temp_dir
                    ).exists(), "Temp dir should be cleaned after cleanup_on_exit"
                finally:
                    # Clean up if still exists
                    if Path(temp_dir).exists():
                        shutil.rmtree(temp_dir)
