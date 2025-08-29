# tests/adapters/api/test_streaming.py

"""Comprehensive tests for the streaming processing module"""

# Standard library imports
from hashlib import md5
from json import dumps
from pickle import dump
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

# Local imports
from marc_pd_tool.adapters.api._streaming import StreamingAnalyzerProtocol
from marc_pd_tool.adapters.api._streaming import StreamingComponent
from marc_pd_tool.application.models.analysis_results import AnalysisResults
from marc_pd_tool.application.models.batch_stats import BatchStats
from marc_pd_tool.application.models.config_models import AnalysisOptions
from marc_pd_tool.application.processing.indexer import DataIndexer
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure import CacheManager
from marc_pd_tool.infrastructure.config import ConfigLoader


class MockStreamingAnalyzer(StreamingComponent):
    """Mock analyzer that implements StreamingAnalyzerProtocol for testing"""

    def __init__(self, cache_dir: str | None = None):
        self.results = AnalysisResults()
        self.config = Mock(spec=ConfigLoader)
        self.config.config = {
            "default_thresholds": {"title": 40, "author": 30},
            "generic_title_detection": {"enabled": True, "min_length": 5},
        }
        self.cache_manager = Mock(spec=CacheManager)
        self.cache_dir = cache_dir or ".test_cache"
        self.copyright_dir = "/test/copyright"
        self.renewal_dir = "/test/renewal"
        self.copyright_data = None
        self.renewal_data = None
        self.registration_index = None
        self.renewal_index = None
        self.generic_detector = None

    def _compute_config_hash(self, config_dict: dict) -> str:
        """Compute hash of configuration for cache validation"""
        config_str = dumps(config_dict, sort_keys=True)
        return md5(config_str.encode()).hexdigest()

    def _load_and_index_data(self, options: dict) -> None:
        """Mock load and index data"""
        pass

    def export_results(
        self, output_path: str, formats: list[str] | None, single_file: bool
    ) -> None:
        """Mock export results"""
        pass


class TestStreamingComponent:
    """Test the StreamingComponent class"""

    def test_analyze_marc_file_streaming_basic(self, tmp_path):
        """Test basic streaming analysis with minimal options"""
        analyzer = MockStreamingAnalyzer()

        # Create mock batch files
        batch_dir = tmp_path / "batches"
        batch_dir.mkdir()

        batch_paths = []
        for i in range(3):
            batch_path = batch_dir / f"batch_{i:05d}.pkl"
            publications = [
                Publication(
                    title=f"Book {i}-{j}",
                    pub_date="1960",
                    source_id=f"{i}-{j}",
                    country_code="xxu",
                    country_classification=CountryClassification.US,
                )
                for j in range(5)
            ]
            with open(batch_path, "wb") as f:
                dump(publications, f)
            batch_paths.append(str(batch_path))

        options = AnalysisOptions(
            year_tolerance=1, title_threshold=40, author_threshold=30, num_processes=2
        )

        with patch.object(analyzer, "_process_streaming_parallel") as mock_process:
            mock_process.return_value = []

            results = analyzer._analyze_marc_file_streaming(
                batch_paths=batch_paths,
                marc_path="/test/marc.xml",
                output_path=None,
                options=options,
            )

            # Verify results were reset
            assert isinstance(results, AnalysisResults)

            # Verify _process_streaming_parallel was called with correct arguments
            mock_process.assert_called_once()
            call_args = mock_process.call_args[0]
            assert call_args[0] == batch_paths  # batch_paths
            assert call_args[1] == 2  # num_processes
            assert call_args[2] == 1  # year_tolerance
            assert call_args[3] == 40  # title_threshold
            assert call_args[4] == 30  # author_threshold

    def test_analyze_marc_file_streaming_with_filters(self, tmp_path):
        """Test streaming analysis with US-only and year filters"""
        analyzer = MockStreamingAnalyzer()

        batch_paths = ["/test/batch_00000.pkl"]

        options = AnalysisOptions(
            us_only=True,
            min_year=1950,
            max_year=1980,
            year_tolerance=2,
            title_threshold=45,
            author_threshold=35,
            num_processes=4,
        )

        with patch.object(analyzer, "_process_streaming_parallel") as mock_process:
            mock_process.return_value = []

            with patch("marc_pd_tool.adapters.api._streaming.logger") as mock_logger:
                analyzer._analyze_marc_file_streaming(
                    batch_paths=batch_paths,
                    marc_path="/test/marc.xml",
                    output_path=None,
                    options=options,
                )

                # Verify filter logging
                mock_logger.info.assert_any_call("  Filter applied: US publications only")
                mock_logger.info.assert_any_call("  Year range filter: 1950 to 1980")

    def test_analyze_marc_file_streaming_with_export(self, tmp_path):
        """Test streaming analysis with result export"""
        analyzer = MockStreamingAnalyzer()

        batch_paths = ["/test/batch_00000.pkl"]
        output_path = str(tmp_path / "output")

        options = AnalysisOptions(
            formats=["json", "csv", "xlsx"], single_file=True, num_processes=1
        )

        with patch.object(analyzer, "_process_streaming_parallel") as mock_process:
            mock_process.return_value = []

            with patch.object(analyzer, "export_results") as mock_export:
                analyzer._analyze_marc_file_streaming(
                    batch_paths=batch_paths,
                    marc_path="/test/marc.xml",
                    output_path=output_path,
                    options=options,
                )

                # Verify export was called
                mock_export.assert_called_once_with(
                    output_path, formats=["json", "csv", "xlsx"], single_file=True
                )

    def test_analyze_marc_file_streaming_all_options(self, tmp_path):
        """Test streaming analysis with all possible options"""
        analyzer = MockStreamingAnalyzer()

        batch_paths = [f"/test/batch_{i:05d}.pkl" for i in range(5)]

        options = AnalysisOptions(
            us_only=True,
            min_year=1923,
            max_year=1977,
            year_tolerance=3,
            title_threshold=50,
            author_threshold=40,
            publisher_threshold=30,
            early_exit_title=98,
            early_exit_author=95,
            early_exit_publisher=90,
            score_everything_mode=True,
            minimum_combined_score=70,
            brute_force_missing_year=True,
            num_processes=8,
            formats=["json"],
            single_file=False,
        )

        with patch.object(analyzer, "_process_streaming_parallel") as mock_process:
            mock_process.return_value = []

            results = analyzer._analyze_marc_file_streaming(
                batch_paths=batch_paths,
                marc_path="/test/marc.xml",
                output_path=str(tmp_path / "output"),
                options=options,
            )

            # Verify all parameters were passed correctly
            call_args = mock_process.call_args[0]
            assert call_args[0] == batch_paths
            assert call_args[1] == 8  # num_processes
            assert call_args[2] == 3  # year_tolerance
            assert call_args[3] == 50  # title_threshold
            assert call_args[4] == 40  # author_threshold
            assert call_args[5] == 30  # publisher_threshold
            assert call_args[6] == 98  # early_exit_title
            assert call_args[7] == 95  # early_exit_author
            assert call_args[8] == 90  # early_exit_publisher
            assert call_args[9] is True  # score_everything_mode
            assert call_args[10] == 70  # minimum_combined_score
            assert call_args[11] is True  # brute_force_missing_year
            assert call_args[12] == 1923  # min_year
            assert call_args[13] == 1977  # max_year

    def test_process_streaming_parallel_basic(self, tmp_path):
        """Test basic parallel streaming processing"""
        analyzer = MockStreamingAnalyzer(cache_dir=str(tmp_path / "cache"))

        # Create mock batch files
        batch_dir = tmp_path / "batches"
        batch_dir.mkdir()
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        batch_paths = []
        for i in range(2):
            batch_path = batch_dir / f"batch_{i:05d}.pkl"
            publications = [
                Publication(
                    title=f"Book {i}",
                    pub_date="1960",
                    source_id=f"{i}",
                    country_code="xxu",
                    country_classification=CountryClassification.US,
                )
            ]
            with open(batch_path, "wb") as f:
                dump(publications, f)
            batch_paths.append(str(batch_path))

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Mock batch processing results
                batch_results = []
                for i, batch_path in enumerate(batch_paths):
                    stats = BatchStats(
                        batch_id=i + 1,
                        marc_count=1,
                        registration_matches_found=1 if i == 0 else 0,
                        renewal_matches_found=1 if i == 1 else 0,
                        processing_time=0.5,
                        skipped_no_year=0,
                    )
                    result_file = result_dir / f"batch_{i+1:05d}_result.pkl"
                    batch_results.append((i + 1, str(result_file), stats))

                mock_pool.imap_unordered.return_value = iter(batch_results)

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"  # macOS mode

                    publications = analyzer._process_streaming_parallel(
                        batch_paths=batch_paths,
                        num_processes=2,
                        year_tolerance=1,
                        title_threshold=40,
                        author_threshold=30,
                        publisher_threshold=20,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        score_everything_mode=False,
                        minimum_combined_score=None,
                        brute_force_missing_year=False,
                        min_year=None,
                        max_year=None,
                    )

                    # Verify Pool was created correctly
                    mock_pool_class.assert_called_once()

                    # Verify batch infos were created correctly
                    call_args = mock_pool.imap_unordered.call_args[0]
                    batch_infos = call_args[1]
                    assert len(batch_infos) == 2
                    assert batch_infos[0][0] == 1  # batch_id
                    assert batch_infos[0][1] == batch_paths[0]  # batch_path

                    # Verify statistics were aggregated
                    assert analyzer.results.statistics.get("skipped_no_year") == 0

    def test_process_streaming_parallel_fork_mode(self, tmp_path):
        """Test parallel processing with fork mode (Linux)"""
        analyzer = MockStreamingAnalyzer(cache_dir=str(tmp_path / "cache"))

        batch_paths = ["/test/batch_00000.pkl"]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Mock batch result
                stats = BatchStats(batch_id=1, marc_count=5, processing_time=1.0)
                mock_pool.imap_unordered.return_value = iter([(1, "result.pkl", stats)])

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "fork"  # Linux mode

                    with patch("marc_pd_tool.adapters.api._streaming.CacheManager") as mock_cache:
                        mock_cache_instance = MagicMock()
                        mock_cache.return_value = mock_cache_instance

                        # Mock cached indexes
                        mock_index = Mock(spec=DataIndexer)
                        mock_cache_instance.get_cached_indexes.return_value = (
                            mock_index,
                            mock_index,
                        )

                        analyzer._process_streaming_parallel(
                            batch_paths=batch_paths,
                            num_processes=1,
                            year_tolerance=1,
                            title_threshold=40,
                            author_threshold=30,
                            publisher_threshold=20,
                            early_exit_title=95,
                            early_exit_author=90,
                            early_exit_publisher=85,
                            score_everything_mode=False,
                            minimum_combined_score=None,
                            brute_force_missing_year=False,
                            min_year=1950,
                            max_year=1980,
                        )

                        # Verify cache manager was created and used
                        mock_cache.assert_called_once_with(str(tmp_path / "cache"))
                        mock_cache_instance.get_cached_indexes.assert_called_once()

    def test_process_streaming_parallel_memory_monitoring(self, tmp_path):
        """Test memory monitoring during processing"""
        analyzer = MockStreamingAnalyzer()

        # Create 50 batch paths to trigger memory monitoring
        batch_paths = [f"/test/batch_{i:05d}.pkl" for i in range(50)]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Create batch results that will trigger memory logging
                batch_results = []
                for i in range(50):
                    stats = BatchStats(batch_id=i + 1, marc_count=10, processing_time=0.1)
                    batch_results.append((i + 1, f"result_{i}.pkl", stats))

                mock_pool.imap_unordered.return_value = iter(batch_results)

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    with patch("marc_pd_tool.adapters.api._streaming.logger") as mock_logger:
                        analyzer._process_streaming_parallel(
                            batch_paths=batch_paths,
                            num_processes=4,
                            year_tolerance=1,
                            title_threshold=40,
                            author_threshold=30,
                            publisher_threshold=20,
                            early_exit_title=95,
                            early_exit_author=90,
                            early_exit_publisher=85,
                            score_everything_mode=False,
                            minimum_combined_score=None,
                            brute_force_missing_year=False,
                            min_year=None,
                            max_year=None,
                        )

                        # Check that memory is NOT logged (removed from streaming component)
                        memory_logs = [
                            call
                            for call in mock_logger.info.call_args_list
                            if "Memory usage:" in str(call)
                        ]
                        assert (
                            len(memory_logs) == 0
                        ), "Memory monitoring should be removed from streaming"

    def test_process_streaming_parallel_worker_recycling(self, tmp_path):
        """Test worker recycling logic based on workload"""
        analyzer = MockStreamingAnalyzer()

        result_dir = tmp_path / "results"
        result_dir.mkdir()

        # Test small job (< 20 batches per worker)
        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool
                mock_pool.imap_unordered.return_value = iter([])

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    # Small job: 10 batches, 4 workers = 2.5 batches per worker
                    batch_paths = [f"/test/batch_{i:05d}.pkl" for i in range(10)]

                    analyzer._process_streaming_parallel(
                        batch_paths=batch_paths,
                        num_processes=4,
                        year_tolerance=1,
                        title_threshold=40,
                        author_threshold=30,
                        publisher_threshold=20,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        score_everything_mode=False,
                        minimum_combined_score=None,
                        brute_force_missing_year=False,
                        min_year=None,
                        max_year=None,
                    )

                    # Verify no worker recycling for small job
                    call_kwargs = mock_pool_class.call_args[1]
                    assert call_kwargs.get("maxtasksperchild") is None

        # Test large job (>= 20 batches per worker)
        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool
                mock_pool.imap_unordered.return_value = iter([])

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    # Large job: 200 batches, 4 workers = 50 batches per worker
                    batch_paths = [f"/test/batch_{i:05d}.pkl" for i in range(200)]

                    analyzer._process_streaming_parallel(
                        batch_paths=batch_paths,
                        num_processes=4,
                        year_tolerance=1,
                        title_threshold=40,
                        author_threshold=30,
                        publisher_threshold=20,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        score_everything_mode=False,
                        minimum_combined_score=None,
                        brute_force_missing_year=False,
                        min_year=None,
                        max_year=None,
                    )

                    # Verify worker recycling is set for large job
                    call_kwargs = mock_pool_class.call_args[1]
                    tasks_per_child = call_kwargs.get("maxtasksperchild")
                    assert tasks_per_child is not None
                    assert 50 <= tasks_per_child <= 200

    def test_process_streaming_parallel_keyboard_interrupt(self, tmp_path):
        """Test handling of keyboard interrupt during processing"""
        analyzer = MockStreamingAnalyzer()

        batch_paths = ["/test/batch_00000.pkl"]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Simulate keyboard interrupt
                mock_pool.imap_unordered.side_effect = KeyboardInterrupt()

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    with patch("marc_pd_tool.adapters.api._streaming.logger") as mock_logger:
                        result = analyzer._process_streaming_parallel(
                            batch_paths=batch_paths,
                            num_processes=2,
                            year_tolerance=1,
                            title_threshold=40,
                            author_threshold=30,
                            publisher_threshold=20,
                            early_exit_title=95,
                            early_exit_author=90,
                            early_exit_publisher=85,
                            score_everything_mode=False,
                            minimum_combined_score=None,
                            brute_force_missing_year=False,
                            min_year=None,
                            max_year=None,
                        )

                        # Verify interrupt was handled gracefully
                        mock_logger.warning.assert_called_with(
                            "Interrupted by user. Cleaning up..."
                        )
                        assert result == analyzer.results.publications

    def test_process_streaming_parallel_general_exception(self, tmp_path):
        """Test handling of general exceptions during processing"""
        analyzer = MockStreamingAnalyzer()

        batch_paths = ["/test/batch_00000.pkl"]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Simulate general exception
                mock_pool.imap_unordered.side_effect = RuntimeError("Test error")

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    with patch("marc_pd_tool.adapters.api._streaming.logger") as mock_logger:
                        result = analyzer._process_streaming_parallel(
                            batch_paths=batch_paths,
                            num_processes=2,
                            year_tolerance=1,
                            title_threshold=40,
                            author_threshold=30,
                            publisher_threshold=20,
                            early_exit_title=95,
                            early_exit_author=90,
                            early_exit_publisher=85,
                            score_everything_mode=False,
                            minimum_combined_score=None,
                            brute_force_missing_year=False,
                            min_year=None,
                            max_year=None,
                        )

                        # Verify error was logged
                        mock_logger.error.assert_called_with(
                            "Error in parallel processing: Test error"
                        )
                        assert result == analyzer.results.publications

    def test_process_streaming_parallel_progress_logging(self, tmp_path):
        """Test progress logging during batch processing"""
        analyzer = MockStreamingAnalyzer()

        batch_paths = [f"/test/batch_{i:05d}.pkl" for i in range(3)]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Create batch results with different processing times
                batch_results = [
                    (1, "result1.pkl", BatchStats(batch_id=1, marc_count=10, processing_time=1.5)),
                    (2, "result2.pkl", BatchStats(batch_id=2, marc_count=15, processing_time=2.0)),
                    (3, "result3.pkl", BatchStats(batch_id=3, marc_count=20, processing_time=2.5)),
                ]

                mock_pool.imap_unordered.return_value = iter(batch_results)

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    with patch("marc_pd_tool.adapters.api._streaming.time") as mock_time:
                        # Mock time progression - need one extra for final time() call
                        mock_time.side_effect = [
                            0,
                            1.5,
                            3.5,
                            6.0,
                            6.0,
                        ]  # start, after each batch, and final

                        with patch("marc_pd_tool.adapters.api._streaming.logger") as mock_logger:
                            analyzer._process_streaming_parallel(
                                batch_paths=batch_paths,
                                num_processes=2,
                                year_tolerance=1,
                                title_threshold=40,
                                author_threshold=30,
                                publisher_threshold=20,
                                early_exit_title=95,
                                early_exit_author=90,
                                early_exit_publisher=85,
                                score_everything_mode=False,
                                minimum_combined_score=None,
                                brute_force_missing_year=False,
                                min_year=None,
                                max_year=None,
                            )

                            # Verify progress logs were generated
                            progress_logs = [
                                call
                                for call in mock_logger.info.call_args_list
                                if "Batch" in str(call) and "complete" in str(call)
                            ]
                            assert len(progress_logs) == 3

                            # Verify final stats log
                            final_logs = [
                                call
                                for call in mock_logger.info.call_args_list
                                if "Streaming parallel processing complete" in str(call)
                            ]
                            assert len(final_logs) == 1

    def test_process_streaming_parallel_no_cached_indexes(self, tmp_path):
        """Test fork mode when no cached indexes are available"""
        analyzer = MockStreamingAnalyzer(cache_dir=str(tmp_path / "cache"))

        batch_paths = ["/test/batch_00000.pkl"]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Mock batch result
                stats = BatchStats(batch_id=1, marc_count=5, processing_time=1.0)
                mock_pool.imap_unordered.return_value = iter([(1, "result.pkl", stats)])

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "fork"  # Linux mode

                    with patch("marc_pd_tool.adapters.api._streaming.CacheManager") as mock_cache:
                        mock_cache_instance = MagicMock()
                        mock_cache.return_value = mock_cache_instance

                        # No cached indexes available
                        mock_cache_instance.get_cached_indexes.return_value = None

                        with patch("marc_pd_tool.adapters.api._streaming.logger") as mock_logger:
                            analyzer._process_streaming_parallel(
                                batch_paths=batch_paths,
                                num_processes=1,
                                year_tolerance=1,
                                title_threshold=40,
                                author_threshold=30,
                                publisher_threshold=20,
                                early_exit_title=95,
                                early_exit_author=90,
                                early_exit_publisher=85,
                                score_everything_mode=False,
                                minimum_combined_score=None,
                                brute_force_missing_year=False,
                                min_year=None,
                                max_year=None,
                            )

                            # Verify appropriate log message
                            mock_logger.info.assert_any_call(
                                "No cached indexes found - workers will load independently"
                            )

    def test_process_streaming_parallel_memory_monitoring_error(self, tmp_path):
        """Test that memory monitoring errors are handled gracefully"""
        analyzer = MockStreamingAnalyzer()

        # Create 10 batch paths to trigger memory monitoring
        batch_paths = [f"/test/batch_{i:05d}.pkl" for i in range(10)]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Create batch results
                batch_results = []
                for i in range(10):
                    stats = BatchStats(batch_id=i + 1, marc_count=10, processing_time=0.1)
                    batch_results.append((i + 1, f"result_{i}.pkl", stats))

                mock_pool.imap_unordered.return_value = iter(batch_results)

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    # Memory monitoring removed - no psutil needed
                    analyzer._process_streaming_parallel(
                        batch_paths=batch_paths,
                        num_processes=2,
                        year_tolerance=1,
                        title_threshold=40,
                        author_threshold=30,
                        publisher_threshold=20,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        score_everything_mode=False,
                        minimum_combined_score=None,
                        brute_force_missing_year=False,
                        min_year=None,
                        max_year=None,
                    )

                    # Verify processing completed (memory monitoring removed)
                    assert analyzer.results.result_temp_dir == str(result_dir)

    def test_streaming_analyzer_protocol(self):
        """Test that StreamingAnalyzerProtocol is properly defined"""
        # This test verifies the protocol structure
        # Standard library imports
        from typing import get_type_hints

        # Local imports
        # Import necessary types for get_type_hints to work
        from marc_pd_tool.application.models.analysis_results import (  # noqa: F401
            AnalysisResults,
        )
        from marc_pd_tool.application.models.config_models import (  # noqa: F401
            AnalysisOptions,
        )
        from marc_pd_tool.application.processing.indexer import (  # noqa: F401
            DataIndexer,
        )
        from marc_pd_tool.application.processing.text_processing import (  # noqa: F401
            GenericTitleDetector,
        )
        from marc_pd_tool.core.types.json import JSONType  # noqa: F401
        from marc_pd_tool.infrastructure import CacheManager  # noqa: F401
        from marc_pd_tool.infrastructure.config import ConfigLoader  # noqa: F401

        hints = get_type_hints(StreamingAnalyzerProtocol, localns=locals())

        # Verify required attributes
        assert "results" in hints
        assert "config" in hints
        assert "cache_manager" in hints
        assert "cache_dir" in hints
        assert "copyright_dir" in hints
        assert "renewal_dir" in hints
        assert "copyright_data" in hints
        assert "renewal_data" in hints
        assert "registration_index" in hints
        assert "renewal_index" in hints
        assert "generic_detector" in hints

        # Verify required methods
        assert hasattr(StreamingAnalyzerProtocol, "_compute_config_hash")
        assert hasattr(StreamingAnalyzerProtocol, "_load_and_index_data")
        assert hasattr(StreamingAnalyzerProtocol, "export_results")

    def test_batch_info_tuple_creation(self, tmp_path):
        """Test that batch info tuples are created correctly"""
        analyzer = MockStreamingAnalyzer(cache_dir=str(tmp_path / "cache"))
        analyzer.config.config["generic_title_detection"] = {
            "enabled": True,
            "min_length": 10,
            "max_generic_words": 3,
        }

        batch_paths = ["/test/batch_00000.pkl", "/test/batch_00001.pkl"]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool
                mock_pool.imap_unordered.return_value = iter([])

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    analyzer._process_streaming_parallel(
                        batch_paths=batch_paths,
                        num_processes=2,
                        year_tolerance=2,
                        title_threshold=45,
                        author_threshold=35,
                        publisher_threshold=25,
                        early_exit_title=96,
                        early_exit_author=91,
                        early_exit_publisher=86,
                        score_everything_mode=True,
                        minimum_combined_score=60,
                        brute_force_missing_year=True,
                        min_year=1950,
                        max_year=1980,
                    )

                    # Get the batch infos from the call
                    call_args = mock_pool.imap_unordered.call_args[0]
                    batch_infos = call_args[1]

                    # Verify batch info structure
                    assert len(batch_infos) == 2

                    # Check first batch info
                    batch_info = batch_infos[0]
                    assert batch_info[0] == 1  # batch_id
                    assert batch_info[1] == "/test/batch_00000.pkl"  # batch_path
                    assert batch_info[2] == str(tmp_path / "cache")  # cache_dir
                    assert batch_info[3] == "/test/copyright"  # copyright_dir
                    assert batch_info[4] == "/test/renewal"  # renewal_dir
                    assert len(batch_info[5]) == 32  # config_hash (MD5)
                    # detector_config filters to only int and bool values
                    assert batch_info[6]["enabled"] is True
                    assert batch_info[6]["min_length"] == 10
                    # max_generic_words is an int, so it should be included
                    assert "max_generic_words" in batch_info[6]
                    assert batch_info[7] == 2  # total_batches
                    assert batch_info[8] == 45  # title_threshold
                    assert batch_info[9] == 35  # author_threshold
                    assert batch_info[10] == 25  # publisher_threshold
                    assert batch_info[11] == 2  # year_tolerance
                    assert batch_info[12] == 96  # early_exit_title
                    assert batch_info[13] == 91  # early_exit_author
                    assert batch_info[14] == 86  # early_exit_publisher
                    assert batch_info[15] is True  # score_everything_mode
                    assert batch_info[16] == 60  # minimum_combined_score
                    assert batch_info[17] is True  # brute_force_missing_year
                    assert batch_info[18] == 1950  # min_year
                    assert batch_info[19] == 1980  # max_year
                    assert batch_info[20] == str(result_dir)  # result_temp_dir

    def test_default_option_values(self, tmp_path):
        """Test that default option values are used correctly"""
        analyzer = MockStreamingAnalyzer()

        batch_paths = ["/test/batch_00000.pkl"]

        # Minimal options - test defaults
        options = AnalysisOptions()

        with patch.object(analyzer, "_process_streaming_parallel") as mock_process:
            mock_process.return_value = []

            analyzer._analyze_marc_file_streaming(
                batch_paths=batch_paths,
                marc_path="/test/marc.xml",
                output_path=None,
                options=options,
            )

            # Verify default values were used
            call_args = mock_process.call_args[0]
            assert call_args[2] == 1  # year_tolerance default
            assert call_args[3] == 40  # title_threshold default
            assert call_args[4] == 30  # author_threshold default
            assert call_args[5] == 0  # publisher_threshold default
            assert call_args[6] == 95  # early_exit_title default
            assert call_args[7] == 90  # early_exit_author default
            assert call_args[8] == 85  # early_exit_publisher default
            assert call_args[9] is False  # score_everything_mode default
            assert call_args[10] is None  # minimum_combined_score default
            assert call_args[11] is False  # brute_force_missing_year default

    def test_detector_config_filtering(self, tmp_path):
        """Test that detector_config properly filters non-int/bool values"""
        analyzer = MockStreamingAnalyzer(cache_dir=str(tmp_path / "cache"))

        # Set up config with various types
        analyzer.config.config["generic_title_detection"] = {
            "enabled": True,  # bool - should be included
            "min_length": 10,  # int - should be included
            "max_words": 5,  # int - should be included
            "pattern": "test.*",  # str - should be excluded
            "threshold": 0.75,  # float - should be excluded
            "rules": ["rule1", "rule2"],  # list - should be excluded
            "options": {"key": "value"},  # dict - should be excluded
        }

        batch_paths = ["/test/batch_00000.pkl"]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool
                mock_pool.imap_unordered.return_value = iter([])

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    analyzer._process_streaming_parallel(
                        batch_paths=batch_paths,
                        num_processes=1,
                        year_tolerance=1,
                        title_threshold=40,
                        author_threshold=30,
                        publisher_threshold=20,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        score_everything_mode=False,
                        minimum_combined_score=None,
                        brute_force_missing_year=False,
                        min_year=None,
                        max_year=None,
                    )

                    # Get the batch infos from the call
                    call_args = mock_pool.imap_unordered.call_args[0]
                    batch_infos = call_args[1]

                    # Check that only int and bool values were included
                    detector_config = batch_infos[0][6]
                    assert detector_config["enabled"] is True
                    assert detector_config["min_length"] == 10
                    assert detector_config["max_words"] == 5
                    assert "pattern" not in detector_config  # str excluded
                    assert "threshold" not in detector_config  # float excluded
                    assert "rules" not in detector_config  # list excluded
                    assert "options" not in detector_config  # dict excluded

    def test_detector_config_not_dict(self, tmp_path):
        """Test handling when generic_title_detection is not a dict"""
        analyzer = MockStreamingAnalyzer(cache_dir=str(tmp_path / "cache"))

        # Set generic_title_detection to a non-dict value
        analyzer.config.config["generic_title_detection"] = "not_a_dict"

        batch_paths = ["/test/batch_00000.pkl"]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool
                mock_pool.imap_unordered.return_value = iter([])

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    analyzer._process_streaming_parallel(
                        batch_paths=batch_paths,
                        num_processes=1,
                        year_tolerance=1,
                        title_threshold=40,
                        author_threshold=30,
                        publisher_threshold=20,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        score_everything_mode=False,
                        minimum_combined_score=None,
                        brute_force_missing_year=False,
                        min_year=None,
                        max_year=None,
                    )

                    # Get the batch infos from the call
                    call_args = mock_pool.imap_unordered.call_args[0]
                    batch_infos = call_args[1]

                    # When not a dict, detector_config should be empty
                    detector_config = batch_infos[0][6]
                    assert detector_config == {}

    def test_memory_monitoring_low_memory(self, tmp_path):
        """Test that low memory usage doesn't trigger logging"""
        analyzer = MockStreamingAnalyzer()

        # Create exactly 50 batch paths to check memory at batch 50
        batch_paths = [f"/test/batch_{i:05d}.pkl" for i in range(50)]
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        with patch("marc_pd_tool.adapters.api._streaming.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = str(result_dir)

            with patch("marc_pd_tool.adapters.api._streaming.Pool") as mock_pool_class:
                mock_pool = MagicMock()
                mock_pool_class.return_value.__enter__.return_value = mock_pool

                # Create batch results
                batch_results = []
                for i in range(50):
                    stats = BatchStats(batch_id=i + 1, marc_count=10, processing_time=0.1)
                    batch_results.append((i + 1, f"result_{i}.pkl", stats))

                mock_pool.imap_unordered.return_value = iter(batch_results)

                with patch("marc_pd_tool.adapters.api._streaming.get_start_method") as mock_start:
                    mock_start.return_value = "spawn"

                    with patch("marc_pd_tool.adapters.api._streaming.logger") as mock_logger:
                        analyzer._process_streaming_parallel(
                            batch_paths=batch_paths,
                            num_processes=4,
                            year_tolerance=1,
                            title_threshold=40,
                            author_threshold=30,
                            publisher_threshold=20,
                            early_exit_title=95,
                            early_exit_author=90,
                            early_exit_publisher=85,
                            score_everything_mode=False,
                            minimum_combined_score=None,
                            brute_force_missing_year=False,
                            min_year=None,
                            max_year=None,
                        )

                        # Check that memory is NOT logged (removed from streaming component)
                        memory_logs = [
                            call
                            for call in mock_logger.info.call_args_list
                            if "Memory usage:" in str(call)
                        ]
                        assert (
                            len(memory_logs) == 0
                        ), "Memory monitoring should be removed from streaming"

    def test_minimum_combined_score_type_handling(self):
        """Test that minimum_combined_score handles different types correctly"""
        analyzer = MockStreamingAnalyzer()

        batch_paths = ["/test/batch_00000.pkl"]

        # Test with integer value
        options = AnalysisOptions(minimum_combined_score=75)

        with patch.object(analyzer, "_process_streaming_parallel") as mock_process:
            mock_process.return_value = []

            analyzer._analyze_marc_file_streaming(
                batch_paths=batch_paths,
                marc_path="/test/marc.xml",
                output_path=None,
                options=options,
            )

            call_args = mock_process.call_args[0]
            assert call_args[10] == 75

        # Test with None value
        options = AnalysisOptions(minimum_combined_score=None)

        with patch.object(analyzer, "_process_streaming_parallel") as mock_process:
            mock_process.return_value = []

            analyzer._analyze_marc_file_streaming(
                batch_paths=batch_paths,
                marc_path="/test/marc.xml",
                output_path=None,
                options=options,
            )

            call_args = mock_process.call_args[0]
            assert call_args[10] is None

        # Test with invalid type (should default to None)
        options = AnalysisOptions()  # Can't set invalid type in Pydantic model

        with patch.object(analyzer, "_process_streaming_parallel") as mock_process:
            mock_process.return_value = []

            analyzer._analyze_marc_file_streaming(
                batch_paths=batch_paths,
                marc_path="/test/marc.xml",
                output_path=None,
                options=options,
            )

            call_args = mock_process.call_args[0]
            assert call_args[10] is None
