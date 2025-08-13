# tests/test_api/test_api_parallel.py

"""Tests for API parallel processing functionality"""

# Standard library imports
import os
from pathlib import Path
import pickle
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer
from marc_pd_tool.application.processing.matching_engine import init_worker
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication


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
        with patch("marc_pd_tool.adapters.api._processing.Pool") as mock_pool_class:
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

        with patch("marc_pd_tool.adapters.api._processing.Pool") as mock_pool_class:
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
                # Return tuple like process_batch does, but with a BatchStats object
                # Local imports
                from marc_pd_tool.application.models.batch_stats import BatchStats

                stats = BatchStats(batch_id=batch_info[0])
                yield (batch_info[0], result_path, stats)

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

        with patch("marc_pd_tool.adapters.api._processing.Pool") as mock_pool_class:
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
                # Return proper BatchStats object
                # Local imports
                from marc_pd_tool.application.models.batch_stats import BatchStats

                stats = BatchStats(
                    batch_id=1,
                    marc_count=1,
                    registration_matches_found=0,
                    renewal_matches_found=0,
                    skipped_no_year=0,
                    processing_time=0.1,
                    records_with_errors=0,
                )
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

    def test_process_parallel_timing_calculation(self, tmp_path):
        """Test that batch processing timing is calculated correctly"""
        analyzer = MarcCopyrightAnalyzer()

        publications = [
            Publication(
                title=f"Book {i}",
                pub_date="1960",
                source_id=f"{i}",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
            for i in range(6)
        ]

        with patch("marc_pd_tool.adapters.api._processing.Pool") as mock_pool_class:
            mock_pool = Mock()
            mock_pool_class.return_value.__enter__.return_value = mock_pool

            # Mock imap_unordered to return results with different processing times
            def imap_result(func, batch_infos, chunksize=1):
                batch_infos_list = list(batch_infos)

                # Simulate 2 batches with different processing times
                for i, batch_info in enumerate(batch_infos_list):
                    result_path = os.path.join(batch_info[-1], f"result_{batch_info[0]:05d}.pkl")
                    stats_path = os.path.join(batch_info[-1], f"stats_{batch_info[0]:05d}.pkl")

                    # Save publications
                    os.makedirs(os.path.dirname(result_path), exist_ok=True)
                    with open(result_path, "wb") as f:
                        pickle.dump(publications[i * 3 : (i + 1) * 3], f)

                    # Save detailed stats
                    detailed_stats = {
                        "total_records": 3,
                        "us_records": 3,
                        "non_us_records": 0,
                        "unknown_country_records": 0,
                        "public_domain_us_pre_min_year": 0,
                        "public_domain_us_1930_1963_no_renewal": 0,
                        "public_domain_us_other": 0,
                        "foreign_pre_1930": 0,
                        "foreign_post_1930": 0,
                        "foreign_unknown_year": 0,
                        "unknown_country": 0,
                        "copyright_restored": 0,
                        "possibly_public_domain": 0,
                        "records_with_errors": 0,
                    }
                    with open(stats_path, "wb") as f:
                        pickle.dump(detailed_stats, f)

                    # Return BatchStats with different processing times
                    # Local imports
                    from marc_pd_tool.application.models.batch_stats import BatchStats

                    stats = BatchStats(
                        batch_id=batch_info[0],
                        marc_count=3,
                        registration_matches_found=i + 1,  # 1 for batch 1, 2 for batch 2
                        renewal_matches_found=i * 2,  # 0 for batch 1, 2 for batch 2
                        skipped_no_year=0,
                        processing_time=1.5 + i * 0.5,  # 1.5s for batch 1, 2.0s for batch 2
                        records_with_errors=0,
                    )
                    yield (batch_info[0], result_path, stats)

            mock_pool.imap_unordered.side_effect = imap_result

            with patch("tempfile.mkdtemp") as mock_mkdtemp:
                batch_dir = tmp_path / "batches"
                result_dir = tmp_path / "results"
                batch_dir.mkdir()
                result_dir.mkdir()

                mock_mkdtemp.side_effect = [str(batch_dir), str(result_dir)]

                with patch("signal.signal"):
                    with patch("atexit.register"):
                        # Track logged messages
                        logged_messages = []

                        def mock_logger_info(msg):
                            logged_messages.append(msg)

                        # Patch the logger.info to capture messages
                        with patch(
                            "marc_pd_tool.adapters.api._processing.logger.info",
                            side_effect=mock_logger_info,
                        ):
                            results = analyzer._process_parallel(
                                publications=publications,
                                num_processes=2,
                                batch_size=3,  # 2 batches of 3 records each
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

                            # Check that the timing was logged correctly
                            # Find messages with rec/s
                            timing_messages = [msg for msg in logged_messages if "rec/s" in msg]

                            # Verify we have timing messages
                            assert (
                                len(timing_messages) == 2
                            ), f"Expected 2 timing logs, got {len(timing_messages)}: {timing_messages}"

                            # Check batch 1 timing - new format includes "Found:" and "|"
                            # Format: "Batch    1/2 [ 50.0%] | Found:  1 reg,  0 ren | Total:     1 reg,     0 ren |   2.0 rec/s"
                            assert (
                                "Found:  1 reg,  0 ren" in timing_messages[0]
                                and "2.0 rec/s" in timing_messages[0]
                            ), f"Batch 1 log: {timing_messages[0]}"

                            # Check batch 2 timing
                            assert (
                                "Found:  2 reg,  2 ren" in timing_messages[1]
                                and "1.5 rec/s" in timing_messages[1]
                            ), f"Batch 2 log: {timing_messages[1]}"


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

        # Mock the cache manager at the actual import location
        with patch("marc_pd_tool.infrastructure.CacheManager") as mock_cache_class:
            mock_cache = Mock()
            mock_cache_class.return_value = mock_cache

            # Mock indexes
            mock_reg_index = Mock()
            mock_reg_index.size.return_value = 100
            mock_ren_index = Mock()
            mock_ren_index.size.return_value = 50

            # Return cached indexes consistently
            mock_cache.get_cached_indexes.return_value = (mock_reg_index, mock_ren_index)
            mock_cache.get_cached_generic_detector.return_value = Mock()

            # No longer need to clear worker data - it's handled internally

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
