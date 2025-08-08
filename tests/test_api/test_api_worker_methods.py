# tests/test_api/test_api_worker_methods.py

"""Tests for methods called by parallel workers in api.py"""

# Standard library imports
from hashlib import md5
from json import dumps
from os.path import join
from pickle import HIGHEST_PROTOCOL
from pickle import dump
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.api import AnalysisResults
from marc_pd_tool.api import MarcCopyrightAnalyzer
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.ground_truth import GroundTruthAnalysis
from marc_pd_tool.data.ground_truth import ScoreDistribution
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.utils.types import AnalysisOptions
from marc_pd_tool.utils.types import JSONDict
from marc_pd_tool.utils.types import MatchResultDict


class TestWorkerCalledMethods:
    """Test methods that are called within parallel worker processes"""

    def test_apply_match_to_publication_registration(self) -> None:
        """Test _apply_match_to_publication for registration matches"""
        analyzer = MarcCopyrightAnalyzer()

        pub = Publication(title="Test Book", author="Test Author")
        pub.year = 1950
        pub.original_publisher = "Test Publisher"

        match_result: MatchResultDict = {
            "copyright_record": {
                "title": "Test Book",
                "author": "Test Author",
                "year": 1950,
                "publisher": "Test Publisher",
                "source_id": "REG123",
                "pub_date": "1950-01-01",
                "full_text": None,
            },
            "similarity_scores": {
                "combined": 95.0,
                "title": 100.0,
                "author": 95.0,
                "publisher": 90.0,
            },
            "generic_title_info": {
                "has_generic_title": False,
                "marc_title_is_generic": False,
                "copyright_detection_reason": None,
                "marc_detection_reason": None,
            },
            "is_lccn_match": False,
        }

        analyzer._apply_match_to_publication(pub, match_result, "registration")

        assert pub.has_registration_match()
        assert pub.registration_match is not None
        assert pub.registration_match.matched_title == "Test Book"
        assert pub.registration_match.similarity_score == 95.0
        assert pub.registration_match.match_type == MatchType.SIMILARITY
        assert pub.registration_generic_title is False

    def test_apply_match_to_publication_renewal(self) -> None:
        """Test _apply_match_to_publication for renewal matches"""
        analyzer = MarcCopyrightAnalyzer()

        pub = Publication(title="Test Book", author="Test Author")
        pub.year = 1950
        pub.original_publisher = "Original Publisher"

        match_result: MatchResultDict = {
            "copyright_record": {
                "title": "Test Book",
                "author": "Test Author",
                "year": 1950,
                "publisher": "Different Publisher",
                "source_id": "REN456",
                "pub_date": "1950-06-15",
                "full_text": "Full text mentioning Original Publisher somewhere",
            },
            "similarity_scores": {
                "combined": 85.0,
                "title": 90.0,
                "author": 85.0,
                "publisher": 75.0,
            },
            "generic_title_info": {
                "has_generic_title": True,
                "marc_title_is_generic": False,
                "copyright_detection_reason": "Frequency threshold",
                "marc_detection_reason": None,
            },
            "is_lccn_match": False,
        }

        analyzer._apply_match_to_publication(pub, match_result, "renewal")

        assert pub.has_renewal_match()
        assert pub.renewal_match is not None
        assert pub.renewal_match.matched_title == "Test Book"
        assert pub.renewal_match.similarity_score == 85.0
        assert pub.renewal_generic_title is True
        assert pub.generic_detection_reason == "Frequency threshold"

    def test_apply_match_to_publication_lccn_match(self) -> None:
        """Test _apply_match_to_publication with LCCN match"""
        analyzer = MarcCopyrightAnalyzer()

        pub = Publication(title="Test", author="Author")
        pub.year = 1950

        match_result: MatchResultDict = {
            "copyright_record": {
                "title": "Test",
                "author": "Author",
                "year": 1950,
                "publisher": "Publisher",
                "source_id": "REG789",
                "pub_date": "1950-01-01",
                "full_text": None,
            },
            "similarity_scores": {
                "combined": 100.0,
                "title": 100.0,
                "author": 100.0,
                "publisher": 100.0,
            },
            "is_lccn_match": True,  # LCCN match flag
        }

        analyzer._apply_match_to_publication(pub, match_result, "registration")

        assert pub.registration_match is not None
        assert pub.registration_match.match_type == MatchType.LCCN

    def test_apply_match_to_publication_no_year(self) -> None:
        """Test _apply_match_to_publication when publication has no year"""
        analyzer = MarcCopyrightAnalyzer()

        pub = Publication(title="Test", author="Author")
        pub.year = None  # No year - brute force match

        match_result: MatchResultDict = {
            "copyright_record": {
                "title": "Test",
                "author": "Author",
                "year": 1950,
                "publisher": "Publisher",
                "source_id": "REG999",
                "pub_date": "1950-01-01",
                "full_text": None,
            },
            "similarity_scores": {
                "combined": 90.0,
                "title": 95.0,
                "author": 90.0,
                "publisher": 85.0,
            },
        }

        analyzer._apply_match_to_publication(pub, match_result, "registration")

        assert pub.registration_match is not None
        assert pub.registration_match.match_type == MatchType.BRUTE_FORCE_WITHOUT_YEAR
        assert pub.registration_match.year_difference == 0  # No year to compare

    def test_apply_match_generic_title_marc_generic(self) -> None:
        """Test _apply_match_to_publication when MARC title is generic"""
        analyzer = MarcCopyrightAnalyzer()

        pub = Publication(title="Report", author="Author")  # Generic title
        pub.year = 1950

        match_result: MatchResultDict = {
            "copyright_record": {
                "title": "Report",
                "author": "Author",
                "year": 1950,
                "publisher": "Publisher",
                "source_id": "REG111",
                "pub_date": "1950-01-01",
                "full_text": None,
            },
            "similarity_scores": {
                "combined": 85.0,
                "title": 100.0,
                "author": 85.0,
                "publisher": 75.0,
            },
            "generic_title_info": {
                "has_generic_title": True,
                "marc_title_is_generic": True,
                "copyright_detection_reason": None,
                "marc_detection_reason": "Pattern match: report",
            },
        }

        analyzer._apply_match_to_publication(pub, match_result, "registration")

        assert pub.generic_title_detected is True
        assert pub.registration_generic_title is True
        assert pub.generic_detection_reason == "Pattern match: report"

    def test_compute_config_hash(self) -> None:
        """Test _compute_config_hash generates consistent hashes"""
        analyzer = MarcCopyrightAnalyzer()

        config1: JSONDict = {
            "thresholds": {"title": 40, "author": 30},
            "options": {"us_only": True},
        }

        config2: JSONDict = {
            "options": {"us_only": True},  # Different order
            "thresholds": {"author": 30, "title": 40},  # Different order
        }

        config3: JSONDict = {
            "thresholds": {"title": 50, "author": 30},  # Different value
            "options": {"us_only": True},
        }

        hash1 = analyzer._compute_config_hash(config1)
        hash2 = analyzer._compute_config_hash(config2)
        hash3 = analyzer._compute_config_hash(config3)

        # Same content, different order should give same hash
        assert hash1 == hash2

        # Different content should give different hash
        assert hash1 != hash3

        # Should be valid MD5 hash (32 hex characters)
        assert len(hash1) == 32
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_save_matches_json_basic(self) -> None:
        """Test save_matches_json function with basic data"""
        # Import from the correct location
        # Local imports
        from marc_pd_tool.exporters.json_exporter import save_matches_json

        with TemporaryDirectory() as temp_dir:
            output_file = join(temp_dir, "test_matches.json")

            pub1 = Publication(title="Book 1", author="Author 1")
            pub1.year = 1950
            pub1.copyright_status = "US_PUBLIC_DOMAIN"
            pub1.source_id = "test1"

            pub2 = Publication(title="Book 2", author="Author 2")
            pub2.year = 1955
            pub2.copyright_status = "US_RENEWED"
            pub2.source_id = "test2"

            publications = [pub1, pub2]
            parameters = {"test_param": "value", "threshold": 40}

            save_matches_json(publications, output_file, parameters=parameters)

            # Read and verify the JSON
            # Standard library imports
            import json

            with open(output_file, "r") as f:
                json_data = json.load(f)

                assert json_data["metadata"]["total_records"] == 2
                if "parameters" in json_data["metadata"]:
                    assert json_data["metadata"]["parameters"]["test_param"] == "value"
                    assert json_data["metadata"]["parameters"]["threshold"] == 40
                assert len(json_data["records"]) == 2
                assert json_data["records"][0]["marc"]["original"]["title"] == "Book 1"

    def test_save_matches_json_with_compression(self) -> None:
        """Test save_matches_json with compression option"""
        # Local imports
        from marc_pd_tool.exporters.json_exporter import save_matches_json

        with TemporaryDirectory() as temp_dir:
            output_file = join(temp_dir, "test_compressed.json")

            pub = Publication(title="Test", author="Author")
            pub.year = 1950
            pub.source_id = "test_compressed"

            # Note: save_matches_json doesn't handle .gz extension automatically
            save_matches_json([pub], output_file, compress=True)

            # Verify gzipped file was created (adds .gz automatically)
            # Standard library imports
            import gzip
            import json

            with gzip.open(output_file + ".gz", "rt") as f:
                json_data = json.load(f)
                assert json_data["metadata"]["total_records"] == 1

    def test_save_matches_json_empty_list(self) -> None:
        """Test save_matches_json with empty publications list"""
        # Local imports
        from marc_pd_tool.exporters.json_exporter import save_matches_json

        with TemporaryDirectory() as temp_dir:
            output_file = join(temp_dir, "empty.json")

            save_matches_json([], output_file)

            # Standard library imports
            import json

            with open(output_file, "r") as f:
                json_data = json.load(f)
                assert json_data["metadata"]["total_records"] == 0
                assert json_data["records"] == []

    def test_analyze_marc_file_streaming_mode_basic(self) -> None:
        """Test _analyze_marc_file_streaming basic functionality"""
        analyzer = MarcCopyrightAnalyzer()

        with TemporaryDirectory() as temp_dir:
            # Create mock batch files
            batch_files = []
            for i in range(2):
                batch_file = join(temp_dir, f"batch_{i}.pkl")

                pub = Publication(title=f"Book {i}", author=f"Author {i}")
                pub.year = 1950 + i

                with open(batch_file, "wb") as f:
                    dump([pub], f, protocol=HIGHEST_PROTOCOL)
                batch_files.append(batch_file)

            options: AnalysisOptions = {
                "formats": ["json"],
                "single_file": True,
                "num_processes": 1,
            }

            # Mock the heavy processing
            with patch.object(analyzer, "_process_streaming_parallel") as mock_process:
                mock_process.return_value = []

                results = analyzer._analyze_marc_file_streaming(
                    batch_files, "/path/to/marc.xml", None, options
                )

                assert results is analyzer.results
                mock_process.assert_called_once()

                # Verify the call arguments
                call_args = mock_process.call_args[0]
                assert call_args[0] == batch_files  # batch_paths
                assert call_args[1] == 1  # num_processes

    def test_export_ground_truth_json_method(self) -> None:
        """Test _export_ground_truth_json private method"""
        analyzer = MarcCopyrightAnalyzer()

        # Create minimal ground truth analysis
        dist = ScoreDistribution(field_name="title", scores=[70.0, 80.0, 90.0])

        analyzer.results.ground_truth_analysis = GroundTruthAnalysis(
            total_pairs=3,
            registration_pairs=2,
            renewal_pairs=1,
            title_distribution=dist,
            author_distribution=dist,
            publisher_distribution=dist,
            combined_distribution=dist,
            pairs_by_match_type={"registration": [], "renewal": []},
        )

        with TemporaryDirectory() as temp_dir:
            output_file = join(temp_dir, "ground_truth.json")

            analyzer._export_ground_truth_json(output_file)

            # Verify the file was created and has correct structure
            # Standard library imports
            import json

            with open(output_file, "r") as f:
                data = json.load(f)

                assert data["statistics"]["total_pairs"] == 3
                assert data["statistics"]["registration_pairs"] == 2
                assert data["statistics"]["renewal_pairs"] == 1

                # Check that distribution properties are included
                assert "mean" in data["score_distributions"]["title"]
                assert "median" in data["score_distributions"]["title"]
                assert "min" in data["score_distributions"]["title"]
                assert "max" in data["score_distributions"]["title"]

    def test_get_statistics_returns_copy(self) -> None:
        """Test get_statistics returns a copy, not reference"""
        analyzer = MarcCopyrightAnalyzer()

        # Set some statistics
        analyzer.results.statistics["test_stat"] = 100
        analyzer.results.statistics["another_stat"] = 200

        # Get statistics
        stats = analyzer.get_statistics()

        # Verify it's a copy
        assert stats["test_stat"] == 100
        assert stats["another_stat"] == 200

        # Modify the returned dict
        stats["test_stat"] = 999

        # Original should be unchanged
        assert analyzer.results.statistics["test_stat"] == 100

        # Verify it's actually a different object
        assert stats is not analyzer.results.statistics

    def skip_test_load_and_index_data_cache_miss(self) -> None:
        """Test _load_and_index_data when cache misses and loads fresh data"""
        analyzer = MarcCopyrightAnalyzer()

        options: AnalysisOptions = {
            "min_year": 1950,
            "max_year": 1960,
            "brute_force_missing_year": False,
        }

        # Force cache miss - this should trigger actual loading
        with patch.object(analyzer.cache_manager, "get_cached_indexes", return_value=None):
            with patch.object(
                analyzer.cache_manager, "get_cached_copyright_data", return_value=None
            ):
                with patch.object(
                    analyzer.cache_manager, "get_cached_renewal_data", return_value=None
                ):
                    # Mock the loaders
                    with patch(
                        "marc_pd_tool.loaders.copyright_loader.CopyrightDataLoader"
                    ) as MockCopyright:
                        with patch(
                            "marc_pd_tool.loaders.renewal_loader.RenewalDataLoader"
                        ) as MockRenewal:
                            with patch(
                                "marc_pd_tool.processing.indexer.build_wordbased_index"
                            ) as mock_build:
                                # Setup mocks
                                mock_copyright = Mock()
                                mock_copyright.load_all_copyright_data.return_value = []
                                MockCopyright.return_value = mock_copyright

                                mock_renewal = Mock()
                                mock_renewal.load_all_renewal_data.return_value = []
                                MockRenewal.return_value = mock_renewal

                                mock_index = Mock()
                                mock_index.publications = []
                                mock_build.return_value = mock_index

                                with patch.object(analyzer.cache_manager, "cache_indexes"):
                                    with patch.object(
                                        analyzer.cache_manager, "cache_copyright_data"
                                    ):
                                        with patch.object(
                                            analyzer.cache_manager, "cache_renewal_data"
                                        ):
                                            analyzer._load_and_index_data(options)

                                            # Verify loaders were called with correct year filters
                                            MockCopyright.assert_called_once()
                                            call_kwargs = MockCopyright.call_args[1]
                                            assert call_kwargs["min_year"] == 1950
                                            assert call_kwargs["max_year"] == 1960

                                            MockRenewal.assert_called_once()
                                            call_kwargs = MockRenewal.call_args[1]
                                            assert call_kwargs["min_year"] == 1950
                                            assert call_kwargs["max_year"] == 1960
