# tests/adapters/api/test_api_core.py

"""Tests for API core functionality"""

# Standard library imports
import json
from pathlib import Path
import pickle
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.adapters.api import AnalysisResults
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer
from marc_pd_tool.application.models.config_models import AnalysisOptions
from marc_pd_tool.application.processing.matching_engine import process_batch
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.publication import Publication


class TestAnalysisResults:
    """Test the AnalysisResults class"""

    def test_init(self):
        """Test AnalysisResults initialization"""
        results = AnalysisResults()
        assert results.publications == []
        assert results.result_file_paths == []
        assert results.statistics.total_records == 0
        assert results.statistics.us_records == 0
        assert results.statistics.non_us_records == 0
        assert results.statistics.registration_matches == 0
        assert results.statistics.renewal_matches == 0
        assert results.statistics.no_matches == 0

    def test_add_publication(self):
        """Test adding publications updates statistics"""
        results = AnalysisResults()

        # Add US publication
        pub1 = Publication(
            title="Test Book 1",
            pub_date="1960",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )
        results.add_publication(pub1)

        assert len(results.publications) == 1
        assert results.statistics.total_records == 1
        assert results.statistics.us_records == 1
        assert results.statistics.non_us_records == 0

        # Add non-US publication
        pub2 = Publication(
            title="Test Book 2",
            pub_date="1960",
            source_id="002",
            country_code="xxk",
            country_classification=CountryClassification.NON_US,
        )
        results.add_publication(pub2)

        assert len(results.publications) == 2
        assert results.statistics.total_records == 2
        assert results.statistics.us_records == 1
        assert results.statistics.non_us_records == 1

    def test_add_result_file(self):
        """Test adding result files"""
        results = AnalysisResults()
        results.add_result_file("test.json")
        results.add_result_file("test.csv")

        assert len(results.result_file_paths) == 2
        assert "test.json" in results.result_file_paths
        assert "test.csv" in results.result_file_paths


class TestMarcCopyrightAnalyzer:
    """Test the MarcCopyrightAnalyzer class"""

    def test_init_defaults(self):
        """Test analyzer initialization with defaults"""
        analyzer = MarcCopyrightAnalyzer()
        assert analyzer.config is not None
        assert analyzer.cache_manager is not None
        assert analyzer.results is not None
        assert analyzer.cache_dir == ".marcpd_cache"

    def test_init_with_config(self, tmp_path):
        """Test analyzer initialization with custom config"""
        config_path = tmp_path / "test_config.json"
        config_data = {"default_thresholds": {"title": 50, "author": 40}}
        config_path.write_text(json.dumps(config_data))

        analyzer = MarcCopyrightAnalyzer(config_path=str(config_path))
        assert analyzer.config.get_threshold("title") == 50
        assert analyzer.config.get_threshold("author") == 40

    def test_init_with_force_refresh(self, tmp_path):
        """Test analyzer initialization with force refresh"""
        cache_dir = tmp_path / "test_cache"

        with patch("marc_pd_tool.adapters.api._analyzer.CacheManager") as mock_cache_class:
            mock_cache = Mock()
            mock_cache_class.return_value = mock_cache

            analyzer = MarcCopyrightAnalyzer(cache_dir=str(cache_dir), force_refresh=True)

            mock_cache.clear_all_caches.assert_called_once()

    def test_compute_config_hash(self):
        """Test config hash computation"""
        analyzer = MarcCopyrightAnalyzer()

        config1 = {"key1": "value1", "key2": 123}
        config2 = {"key1": "value1", "key2": 123}
        config3 = {"key1": "value2", "key2": 123}

        hash1 = analyzer._compute_config_hash(config1)
        hash2 = analyzer._compute_config_hash(config2)
        hash3 = analyzer._compute_config_hash(config3)

        # Same config should produce same hash
        assert hash1 == hash2
        # Different config should produce different hash
        assert hash1 != hash3

    def test_process_sequentially(self, tmp_path):
        """Test processing with single worker (sequential-like behavior)"""
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
            for i in range(5)
        ]

        # Mock dependencies - streaming is now always used
        with patch.object(analyzer, "_load_and_index_data"):
            # Need to import StreamingComponent to patch it
            # Local imports
            from marc_pd_tool.adapters.api._streaming import StreamingComponent

            with patch.object(StreamingComponent, "_analyze_marc_file_streaming") as mock_stream:
                # Mock to populate results
                def mock_streaming(self, *args, **kwargs):
                    self.results.publications = publications

                mock_stream.side_effect = mock_streaming

                # Call with num_processes=1 for sequential-like behavior
                results = analyzer.analyze_marc_records(
                    publications, options=AnalysisOptions(num_processes=1, batch_size=100)
                )

            assert len(results) == 5
            assert all(isinstance(pub, Publication) for pub in results)

    def test_analyze_marc_records(self):
        """Test analyze_marc_records method"""
        analyzer = MarcCopyrightAnalyzer()

        # Create test publications
        publications = [
            Publication(
                title="Test Book",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
        ]

        # Mock dependencies - now mocking the streaming approach
        with patch.object(analyzer, "_load_and_index_data"):
            # Local imports
            from marc_pd_tool.adapters.api._streaming import StreamingComponent

            with patch.object(StreamingComponent, "_analyze_marc_file_streaming") as mock_stream:
                # Mock the streaming to populate results
                def mock_streaming(self, *args, **kwargs):
                    self.results.publications = publications

                mock_stream.side_effect = mock_streaming

                results = analyzer.analyze_marc_records(
                    publications, options=AnalysisOptions(num_processes=1)
                )

                # Verify the streaming method was called
                assert mock_stream.called
                assert len(results) == 1
                assert (
                    results[0].original_title == "Test Book"
                )  # Check original_title, not normalized title

    def test_export_results_single_file(self, tmp_path):
        """Test export results with single file option"""
        analyzer = MarcCopyrightAnalyzer()

        # Add test publication
        pub = Publication(
            title="Export Test",
            pub_date="1960",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )
        analyzer.results.add_publication(pub)

        # Mock the exporters where they're imported
        with patch(
            "marc_pd_tool.application.models.analysis_results.AnalysisResults.export_json"
        ) as mock_json:
            with patch("marc_pd_tool.adapters.api._export.CSVExporter") as mock_csv_class:
                mock_csv = Mock()
                mock_csv_class.return_value = mock_csv

                # Export results
                output_path = str(tmp_path / "test_export")
                analyzer.export_results(output_path, formats=["json", "csv"], single_file=True)

                # Verify exporters were called
                mock_json.assert_called_once_with(f"{output_path}.json")
                mock_csv.export.assert_called_once()

                # Check CSV exporter was created with correct arguments
                csv_init_args = mock_csv_class.call_args
                # CSV output path should include the .csv extension
                assert csv_init_args[0][1] == f"{output_path}.csv"  # CSV output path with extension
                # The exporter is created with single_file=True


class TestWorkerFunctions:
    """Test worker-related functions"""

    @pytest.mark.skip(reason="Requires full multiprocessing setup with cached indexes")
    def test_process_batch(self, tmp_path):
        """Test process_batch function"""
        # Create test batch file
        batch_path = tmp_path / "test_batch.pkl"
        test_pubs = [
            Publication(
                title="Batch Test",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
        ]

        with open(batch_path, "wb") as f:
            pickle.dump(test_pubs, f)

        # Create directories
        cache_dir = tmp_path / "cache"
        copyright_dir = tmp_path / "copyright"
        renewal_dir = tmp_path / "renewal"
        result_dir = tmp_path / "results"

        cache_dir.mkdir()
        copyright_dir.mkdir()
        renewal_dir.mkdir()
        result_dir.mkdir()

        # Create minimal data files
        copyright_file = copyright_dir / "test.xml"
        copyright_file.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
        <copyrightEntries></copyrightEntries>"""
        )

        renewal_file = renewal_dir / "test.tsv"
        renewal_file.write_text("title\tauthor\toreg\todat\tid\trdat\tclaimants\n")

        # Create batch info as a tuple (BatchProcessingInfo is a tuple type)
        # Local imports

        batch_info = (
            1,  # batch_id
            str(batch_path),  # batch_path
            str(cache_dir),  # cache_dir
            str(copyright_dir),  # copyright_dir
            str(renewal_dir),  # renewal_dir
            "test_hash",  # config_hash
            {},  # detector_config
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            20,  # publisher_threshold
            1,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything_mode
            None,  # minimum_combined_score
            False,  # brute_force_missing_year
            None,  # min_year
            None,  # max_year
            str(result_dir),  # result_temp_dir
        )

        # Mock the global worker variables and DataMatcher
        with patch(
            "marc_pd_tool.application.processing.matching_engine._worker_registration_index", None
        ):
            with patch(
                "marc_pd_tool.application.processing.matching_engine._worker_renewal_index", None
            ):
                with patch(
                    "marc_pd_tool.application.processing.matching_engine._worker_generic_detector",
                    Mock(),
                ):
                    with patch(
                        "marc_pd_tool.application.processing.matching_engine._worker_config", {}
                    ):
                        with patch(
                            "marc_pd_tool.application.processing.matching_engine.DataMatcher"
                        ) as mock_dm:
                            # Setup mock DataMatcher
                            mock_matcher = Mock()
                            mock_matcher.find_best_match.return_value = (None, None)
                            mock_dm.return_value = mock_matcher

                            batch_id, result_path, stats = process_batch(batch_info)

                assert batch_id == 1
                assert Path(result_path).exists()
                # Stats is now a BatchStats object, not a dict
                # Local imports
                from marc_pd_tool.application.models.batch_stats import BatchStats

                assert isinstance(stats, BatchStats)
                # Verify stats has expected fields
                assert stats.batch_id == 1


class TestAnalysisMethods:
    """Test analysis methods"""

    def test_analyze_with_config_hash(self, tmp_path):
        """Test that config hash is properly computed and used"""
        analyzer = MarcCopyrightAnalyzer(cache_dir=str(tmp_path))

        # Create test publications
        publications = [
            Publication(
                title="Test Book",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
        ]

        # Mock both _load_and_index_data and streaming
        with patch.object(analyzer, "_load_and_index_data"):
            # Local imports
            from marc_pd_tool.adapters.api._streaming import StreamingComponent

            with patch.object(StreamingComponent, "_analyze_marc_file_streaming") as mock_stream:
                # Track the arguments and populate results
                called_args = {}

                def capture_args(self, batch_paths, marc_path, output_path, options):
                    called_args["title_threshold"] = (
                        options.title_threshold if hasattr(options, "title_threshold") else 40
                    )
                    # Add publications to results
                    for pub in publications:
                        self.results.add_publication(pub)

                mock_stream.side_effect = capture_args

                # Analyze with specific config
                results = analyzer.analyze_marc_records(
                    publications, options=AnalysisOptions(num_processes=1, title_threshold=50)
                )

                # Verify config was used
                assert called_args["title_threshold"] == 50
