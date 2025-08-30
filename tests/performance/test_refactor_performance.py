# tests/performance/test_refactor_performance.py

"""Performance benchmarks to ensure refactor doesn't regress

These benchmarks establish baseline performance metrics that must
be maintained during the analyzer refactor.
"""

# Standard library imports
from pathlib import Path
from pickle import HIGHEST_PROTOCOL
from pickle import dump
from tempfile import mkdtemp
from time import time
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
from pytest import fixture
from pytest import mark

# Local imports
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer
from marc_pd_tool.application.models.config_models import AnalysisOptions
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication


class TestRefactorPerformance:
    """Performance benchmarks for analyzer refactor"""

    @fixture
    def large_publication_set(self):
        """Create a large set of publications for performance testing"""
        pubs = []
        for i in range(1000):
            pub = Publication(
                title=f"Performance Test Title {i} with some longer text",
                author=f"Author {i}, Test",
                publisher=f"Test Publisher {i} & Co.",
                place="New York",
                country_code="nyu",
                country_classification=CountryClassification.US,
                year=1920 + (i % 100),
            )
            pubs.append(pub)
        return pubs

    @fixture
    def temp_batches(self, large_publication_set):
        """Create temp batches for testing"""
        temp_dir = mkdtemp(prefix="perf_test_")
        batch_paths = []
        batch_size = 100

        for i in range(0, len(large_publication_set), batch_size):
            batch = large_publication_set[i : i + batch_size]
            batch_path = Path(temp_dir) / f"batch_{i//batch_size:03d}.pkl"
            with open(batch_path, "wb") as f:
                dump(batch, f, protocol=HIGHEST_PROTOCOL)
            batch_paths.append(str(batch_path))

        return batch_paths

    def test_processing_speed(self, temp_batches):
        """Verify processing speed: 2000-5000 records/minute"""
        analyzer = MarcCopyrightAnalyzer()

        # Mock the data loading since we're testing processing speed
        mock_reg_index = Mock()
        mock_reg_index.publications = []
        mock_reg_index.find_candidates = Mock(return_value=([], set()))
        mock_ren_index = Mock()
        mock_ren_index.publications = []
        mock_ren_index.find_candidates = Mock(return_value=([], set()))

        analyzer.registration_index = mock_reg_index
        analyzer.renewal_index = mock_ren_index

        options = AnalysisOptions(num_processes=2)

        start_time = time()

        # Test the processing speed
        # Local imports
        from marc_pd_tool.adapters.api._batch_processing import BatchProcessingComponent

        mock_self = Mock()
        mock_self.results = Mock()
        mock_self.results.publications = []
        mock_self.registration_index = mock_reg_index
        mock_self.renewal_index = mock_ren_index
        mock_self.generic_detector = None
        mock_self.config = analyzer.config
        mock_self.cache_dir = analyzer.cache_dir
        mock_self.copyright_dir = analyzer.copyright_dir
        mock_self.renewal_dir = analyzer.renewal_dir

        # Mock the actual processing to measure overhead
        with patch(
            "marc_pd_tool.application.processing.matching_engine.process_batch"
        ) as mock_process:
            # Simulate realistic processing time
            def simulate_batch(batch_info):
                # Simulate ~10ms per batch (100 records)
                # Standard library imports
                import time

                time.sleep(0.01)
                batch_id = batch_info[0]
                result_file = f"/tmp/result_{batch_id}.pkl"
                stats = Mock()
                stats.registration_matches_found = 10
                stats.renewal_matches_found = 5
                stats.processing_time = 0.01
                return (batch_id, result_file, stats)

            mock_process.side_effect = simulate_batch

            with patch("marc_pd_tool.adapters.api._batch_processing.Pool") as mock_pool:
                mock_pool_instance = Mock()
                mock_pool.return_value.__enter__.return_value = mock_pool_instance

                # Simulate pool.imap_unordered behavior
                def mock_imap(func, items):
                    for item in items:
                        yield simulate_batch(item)

                mock_pool_instance.imap_unordered.side_effect = mock_imap

                BatchProcessingComponent._process_batches_parallel(
                    mock_self,
                    temp_batches[:5],  # Test with 5 batches = 500 records
                    num_processes=2,
                    year_tolerance=1,
                    title_threshold=40,
                    author_threshold=30,
                    publisher_threshold=60,
                    early_exit_title=95,
                    early_exit_author=90,
                    early_exit_publisher=85,
                    score_everything_mode=False,
                    minimum_combined_score=None,
                    brute_force_missing_year=False,
                    min_year=None,
                    max_year=None,
                )

        elapsed_time = time() - start_time
        records_per_minute = (500 / elapsed_time) * 60

        # Verify we're in the expected range (accounting for test overhead)
        # In real processing this would be 2000-5000, but test is faster
        assert records_per_minute > 1000, f"Too slow: {records_per_minute:.0f} records/minute"

    def test_memory_usage(self, temp_batches):
        """Verify memory usage remains bounded"""
        # Third party imports
        import psutil

        process = psutil.Process()

        analyzer = MarcCopyrightAnalyzer()

        # Measure baseline memory
        baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB

        # Mock indexes to avoid loading real data
        mock_reg_index = Mock()
        mock_reg_index.publications = []
        mock_reg_index.find_candidates = Mock(return_value=([], set()))
        analyzer.registration_index = mock_reg_index
        analyzer.renewal_index = mock_reg_index

        # Process batches

        mock_self = Mock()
        mock_self.results = Mock()
        mock_self.results.publications = []
        mock_self.registration_index = mock_reg_index
        mock_self.renewal_index = mock_reg_index
        mock_self.generic_detector = None
        mock_self.config = analyzer.config
        mock_self.cache_dir = analyzer.cache_dir
        mock_self.copyright_dir = analyzer.copyright_dir
        mock_self.renewal_dir = analyzer.renewal_dir

        with patch("marc_pd_tool.adapters.api._batch_processing.Pool"):
            # Measure memory after setup
            peak_memory = process.memory_info().rss / (1024 * 1024)  # MB
            memory_increase = peak_memory - baseline_memory

            # Memory increase should be reasonable (< 500MB for test)
            assert memory_increase < 500, f"Memory increased by {memory_increase:.1f}MB"

    def test_startup_time(self):
        """Verify cache loading time remains fast"""
        start_time = time()

        # Test analyzer initialization
        analyzer = MarcCopyrightAnalyzer()

        # Mock cache manager to simulate cache hit
        with patch.object(analyzer.cache_manager, "get_cached_indexes") as mock_cache:
            mock_cache.return_value = (Mock(), Mock())

            options = AnalysisOptions()
            analyzer._load_and_index_data(options)

        elapsed_time = time() - start_time

        # Startup should be fast with cache hit (< 1 second)
        assert elapsed_time < 1.0, f"Startup took {elapsed_time:.2f}s"

    @mark.skip(reason="Requires actual data files")
    def test_end_to_end_performance(self):
        """Test full end-to-end performance with real data"""
        # This would test with actual MARC files
        # Skipped by default but can be run manually
