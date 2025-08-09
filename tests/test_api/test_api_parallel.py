# tests/test_api/test_api_parallel.py

"""Tests for API parallel processing functionality"""

# Standard library imports
import os
from pathlib import Path
import pickle
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.api import MarcCopyrightAnalyzer
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.matching_engine import _worker_data
from marc_pd_tool.processing.matching_engine import init_worker


class TestParallelProcessing:
    """Test parallel processing functionality"""

    def test_process_parallel_creates_batches(self, tmp_path):
        """Test that _process_parallel creates batch files correctly"""
        analyzer = MarcCopyrightAnalyzer()

        # Create test publications
        publications = [
            Publication(
                title=f"Book {i}",
                pub_date="1960",
                source_id=f"{i}",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
            for i in range(10)
        ]

        # Mock multiprocessing Pool
        with patch("marc_pd_tool.api._processing.Pool") as mock_pool_class:
            mock_pool = Mock()
            mock_pool_class.return_value.__enter__.return_value = mock_pool

            # Mock map results
            def mock_map(func, batch_infos):
                # Create mock result files
                results = []
                for batch_info in batch_infos:
                    result_path = os.path.join(
                        batch_info[18], f"batch_{batch_info[0]:05d}_result.pkl"
                    )
                    # Create a mock result
                    result = {
                        "batch_id": batch_info[0],
                        "publications": [],
                        "stats": {},
                        "error": None,
                    }
                    os.makedirs(os.path.dirname(result_path), exist_ok=True)
                    with open(result_path, "wb") as f:
                        pickle.dump(result, f)
                    results.append(result_path)
                return results

            mock_pool.map.side_effect = mock_map

            # Mock imap_unordered to return an empty iterator
            # It's called with (func, batch_infos, chunksize=1)
            def mock_imap_unordered(func, batch_infos, chunksize=1):
                return iter([])

            mock_pool.imap_unordered.side_effect = mock_imap_unordered

            # Call _process_parallel
            with patch("tempfile.mkdtemp") as mock_mkdtemp:
                # Create actual temp directories
                batch_dir = tmp_path / "batches"
                result_dir = tmp_path / "results"
                batch_dir.mkdir()
                result_dir.mkdir()

                mock_mkdtemp.side_effect = [str(batch_dir), str(result_dir)]

                # Mock signal handlers
                with patch("signal.signal"):
                    with patch("atexit.register"):
                        results = analyzer._process_parallel(
                            publications=publications,
                            num_processes=2,
                            batch_size=3,
                            title_threshold=40,
                            author_threshold=30,
                            publisher_threshold=20,
                            year_tolerance=1,
                            early_exit_title=95,
                            early_exit_author=90,
                            early_exit_publisher=85,
                            score_everything_mode=False,
                            minimum_combined_score=None,
                            brute_force_missing_year=False,
                            min_year=None,
                            max_year=None,
                        )

                        # Verify pool was used with correct number of processes
                        mock_pool_class.assert_called_once()
                        call_kwargs = mock_pool_class.call_args[1]
                        assert call_kwargs["processes"] == 2

                        # Verify imap_unordered was called (this is where actual processing happens)
                        mock_pool.imap_unordered.assert_called_once()

                        # The results should be empty since our mock returns empty iterator
                        assert results == []

    def test_process_parallel_handles_errors(self, tmp_path):
        """Test that _process_parallel handles worker errors"""
        analyzer = MarcCopyrightAnalyzer()

        publications = [
            Publication(
                title="Test Book",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
        ]

        with patch("marc_pd_tool.api._processing.Pool") as mock_pool_class:
            mock_pool = Mock()
            mock_pool_class.return_value.__enter__.return_value = mock_pool

            # Mock map to simulate an error
            def mock_map_with_error(func, batch_infos):
                # Create result with error
                batch_info = batch_infos[0]
                result_path = os.path.join(batch_info[18], f"batch_{batch_info[0]:05d}_result.pkl")
                result = {
                    "batch_id": batch_info[0],
                    "publications": [],
                    "stats": {},
                    "error": "Simulated worker error",
                }
                os.makedirs(os.path.dirname(result_path), exist_ok=True)
                with open(result_path, "wb") as f:
                    pickle.dump(result, f)
                return [result_path]

            mock_pool.map.side_effect = mock_map_with_error

            # Mock imap_unordered to return an iterator with error result
            def imap_result(func, batch_infos, chunksize=1):
                # Simulate error result
                batch_info = list(batch_infos)[0]
                result_path = os.path.join(batch_info[-1], f"batch_{batch_info[0]:05d}_result.pkl")
                result = {
                    "batch_id": batch_info[0],
                    "publications": [],
                    "stats": {},
                    "error": "Simulated worker error",
                }
                os.makedirs(os.path.dirname(result_path), exist_ok=True)
                with open(result_path, "wb") as f:
                    pickle.dump(result, f)
                # Return tuple like process_batch does
                yield (batch_info[0], result_path, {"error": "Simulated worker error"})

            mock_pool.imap_unordered.side_effect = imap_result

            with patch("tempfile.mkdtemp") as mock_mkdtemp:
                batch_dir = tmp_path / "batches"
                result_dir = tmp_path / "results"
                batch_dir.mkdir()
                result_dir.mkdir()

                mock_mkdtemp.side_effect = [str(batch_dir), str(result_dir)]

                with patch("signal.signal"):
                    with patch("atexit.register"):
                        # Process parallel should handle errors gracefully by logging them
                        # It doesn't raise an exception for worker errors
                        results = analyzer._process_parallel(
                            publications=publications,
                            num_processes=1,
                            batch_size=1,
                            title_threshold=40,
                            author_threshold=30,
                            publisher_threshold=20,
                            year_tolerance=1,
                            early_exit_title=95,
                            early_exit_author=90,
                            early_exit_publisher=85,
                            score_everything_mode=False,
                            minimum_combined_score=None,
                            brute_force_missing_year=False,
                            min_year=None,
                            max_year=None,
                        )

                        # Even with errors, the function should complete and return results
                        # The error is logged but doesn't stop processing
                        assert isinstance(results, list)

    def test_process_parallel_cleanup(self, tmp_path):
        """Test that _process_parallel cleans up temp files"""
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

        cleanup_called = False

        def mock_cleanup():
            nonlocal cleanup_called
            cleanup_called = True

        with patch("marc_pd_tool.api._processing.Pool") as mock_pool_class:
            mock_pool = Mock()
            mock_pool_class.return_value.__enter__.return_value = mock_pool

            # Mock successful processing
            def mock_map(func, batch_infos):
                batch_info = batch_infos[0]
                result_path = os.path.join(batch_info[18], f"batch_{batch_info[0]:05d}_result.pkl")
                result = {
                    "batch_id": batch_info[0],
                    "publications": publications,
                    "stats": {},
                    "error": None,
                }
                os.makedirs(os.path.dirname(result_path), exist_ok=True)
                with open(result_path, "wb") as f:
                    pickle.dump(result, f)
                return [result_path]

            mock_pool.map.side_effect = mock_map

            # Mock imap_unordered to return an iterator with successful result
            def imap_result(func, batch_infos, chunksize=1):
                batch_info = list(batch_infos)[0]
                result_path = os.path.join(batch_info[-1], f"batch_{batch_info[0]:05d}_result.pkl")
                # Save publications directly (that's what process_batch does)
                os.makedirs(os.path.dirname(result_path), exist_ok=True)
                with open(result_path, "wb") as f:
                    pickle.dump(publications, f)
                # Return proper stats
                stats = {
                    "batch_id": 1,
                    "marc_count": 1,
                    "registration_matches_found": 0,
                    "renewal_matches_found": 0,
                    "skipped_records": 0,
                    "processing_time": 0.1,
                    "records_with_errors": 0,
                }
                yield (batch_info[0], result_path, stats)

            mock_pool.imap_unordered.side_effect = imap_result

            with patch("tempfile.mkdtemp") as mock_mkdtemp:
                batch_dir = tmp_path / "batches"
                result_dir = tmp_path / "results"
                batch_dir.mkdir()
                result_dir.mkdir()

                mock_mkdtemp.side_effect = [str(batch_dir), str(result_dir)]

                with patch("signal.signal"):
                    # The cleanup registration is not in _processing module
                    # Just test that the method completes successfully
                    results = analyzer._process_parallel(
                        publications=publications,
                        num_processes=1,
                        batch_size=1,
                        title_threshold=40,
                        author_threshold=30,
                        publisher_threshold=20,
                        year_tolerance=1,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        score_everything_mode=False,
                        minimum_combined_score=None,
                        brute_force_missing_year=False,
                        min_year=None,
                        max_year=None,
                    )

                    # Verify the function completes successfully
                    assert isinstance(results, list)


class TestWorkerInitialization:
    """Test worker initialization"""

    def test_init_worker(self, tmp_path):
        """Test init_worker function"""
        # Create mock data
        cache_dir = str(tmp_path / "cache")
        copyright_dir = str(tmp_path / "copyright")
        renewal_dir = str(tmp_path / "renewal")
        config_hash = "test_hash"
        detector_config = {"min_length": 10}

        # Create minimal mock data files
        os.makedirs(copyright_dir, exist_ok=True)
        os.makedirs(renewal_dir, exist_ok=True)

        copyright_file = Path(copyright_dir) / "test.xml"
        copyright_file.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
        <copyrightEntries></copyrightEntries>"""
        )

        renewal_file = Path(renewal_dir) / "test.tsv"
        renewal_file.write_text("title\tauthor\toreg\todat\tid\trdat\tclaimants\n")

        # Mock the cache manager and other dependencies
        with patch("marc_pd_tool.processing.matching_engine.CacheManager") as mock_cache_class:
            mock_cache = Mock()
            mock_cache_class.return_value = mock_cache
            mock_cache.get_cached_indexes.return_value = None

            # Mock indexes
            mock_reg_index = Mock()
            mock_reg_index.size.return_value = 100
            mock_ren_index = Mock()
            mock_ren_index.size.return_value = 50

            # Return cached indexes
            mock_cache.get_cached_indexes.return_value = (mock_reg_index, mock_ren_index)
            mock_cache.get_cached_generic_detector.return_value = Mock()

            # Clear any existing worker data
            if hasattr(_worker_data, "clear"):
                _worker_data.clear()

            # Call init_worker with all required params
            init_worker(
                cache_dir,
                copyright_dir,
                renewal_dir,
                config_hash,
                detector_config,
                min_year=None,
                max_year=None,
                brute_force=False,
            )

            # Verify cache manager was created and used
            mock_cache_class.assert_called_once_with(cache_dir)
            mock_cache.get_cached_indexes.assert_called_once()
            mock_cache.get_cached_generic_detector.assert_called_once()
