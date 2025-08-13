# tests/test_processing/test_skip_no_year_records.py

"""Tests for skipping MARC records without year data"""

# Standard library imports
import pickle

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.application.processing.matching_engine import process_batch
from marc_pd_tool.core.domain.enums import MatchType
from marc_pd_tool.core.domain.publication import Publication


class TestSkipNoYearRecords:
    """Test that MARC records without year data are handled correctly"""

    def _setup_mock_worker_data(self, monkeypatch, mock_index_class=None):
        """Helper to set up mock worker data for tests"""
        if mock_index_class is None:

            class MockIndex:
                def find_candidates(self, pub):
                    return []  # Return empty list of indices

                publications = []  # Empty publications list

                def get_stats(self):
                    return {"title_keys": 0, "author_keys": 0}

                def size(self):
                    return 0

            mock_index_class = MockIndex

        # Import matching_engine module to access global variables
        # Local imports
        from marc_pd_tool.application.processing import matching_engine
        from marc_pd_tool.infrastructure.config import get_config

        # Set up the mock worker globals
        mock_index = mock_index_class()
        matching_engine._worker_registration_index = mock_index
        matching_engine._worker_renewal_index = mock_index
        matching_engine._worker_generic_detector = None
        matching_engine._worker_config = get_config()  # Use actual Config object
        matching_engine._worker_options = None  # Add worker options

    @fixture
    def mock_batch_info_with_year(self, tmp_path):
        """Create batch info with MARC records that have year data"""
        # Create minimal cache directory structure
        cache_dir = tmp_path / "test_cache"
        cache_dir.mkdir()

        marc_pub_with_year = Publication(
            title="Test Book With Year",
            author="Smith, John",
            pub_date="2023",
            source="MARC",
            source_id="test001",
        )

        # Create pickle file for the batch
        batch_path = tmp_path / "batch_with_year.pkl"
        with open(batch_path, "wb") as f:
            pickle.dump([marc_pub_with_year], f)

        batch_info = (
            1,  # batch_id
            str(batch_path),  # batch_path
            str(cache_dir),  # cache_dir
            "copyright_dir",  # copyright_dir
            "renewal_dir",  # renewal_dir
            "config_hash",  # config_hash
            {"disabled": True},  # detector_config - disable generic detector for tests
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            60,  # publisher_threshold
            1,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything
            40,  # minimum_combined_score
            False,  # brute_force_missing_year (default: skip no-year records)
            None,  # min_year
            None,  # max_year
            "/tmp/test_results",  # result_temp_dir
        )
        return batch_info

    @fixture
    def mock_batch_info_no_year(self, tmp_path):
        """Create batch info with MARC records that lack year data"""
        # Create minimal cache directory structure
        cache_dir = tmp_path / "test_cache"
        cache_dir.mkdir()

        marc_pub_no_year = Publication(
            title="Test Book Without Year",
            author="Jones, Jane",
            pub_date=None,  # No year
            source="MARC",
            source_id="test002",
        )

        # Create pickle file for the batch
        batch_path = tmp_path / "batch_no_year.pkl"
        with open(batch_path, "wb") as f:
            pickle.dump([marc_pub_no_year], f)

        batch_info = (
            1,  # batch_id
            str(batch_path),  # batch_path
            str(cache_dir),  # cache_dir
            "copyright_dir",  # copyright_dir
            "renewal_dir",  # renewal_dir
            "config_hash",  # config_hash
            {"disabled": True},  # detector_config - disable generic detector for tests
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            60,  # publisher_threshold
            1,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything
            40,  # minimum_combined_score
            False,  # brute_force_missing_year (default: skip no-year records)
            None,  # min_year
            None,  # max_year
            "/tmp/test_results",  # result_temp_dir
        )
        return batch_info

    @fixture
    def mock_batch_info_mixed(self, tmp_path):
        """Create batch info with both year and no-year MARC records"""
        # Create minimal cache directory structure
        cache_dir = tmp_path / "test_cache"
        cache_dir.mkdir()

        marc_pub_with_year = Publication(
            title="Book With Year",
            author="Smith, John",
            pub_date="2023",
            source="MARC",
            source_id="test001",
        )

        marc_pub_no_year = Publication(
            title="Book Without Year",
            author="Jones, Jane",
            pub_date=None,  # No year
            source="MARC",
            source_id="test002",
        )

        # Create pickle file for the batch
        batch_path = tmp_path / "batch_mixed.pkl"
        with open(batch_path, "wb") as f:
            pickle.dump([marc_pub_with_year, marc_pub_no_year], f)

        batch_info = (
            1,  # batch_id
            str(batch_path),  # batch_path
            str(cache_dir),  # cache_dir
            "copyright_dir",  # copyright_dir
            "renewal_dir",  # renewal_dir
            "config_hash",  # config_hash
            {"disabled": True},  # detector_config - disable generic detector for tests
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            60,  # publisher_threshold
            1,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything
            40,  # minimum_combined_score
            False,  # brute_force_missing_year (default: skip no-year records)
            None,  # min_year
            None,  # max_year
            "/tmp/test_results",  # result_temp_dir
        )
        return batch_info

    def test_skip_records_without_year_by_default(
        self, mock_batch_info_no_year, monkeypatch, tmp_path
    ):
        """Test that records without year are skipped by default"""

        # Set up mock worker data
        self._setup_mock_worker_data(monkeypatch)

        # Create temp directory for results
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        # Update batch info with real temp directory
        batch_info_list = list(mock_batch_info_no_year)
        batch_info_list[-1] = str(result_dir)
        mock_batch_info_no_year = tuple(batch_info_list)

        # Process the batch
        batch_id, result_file_path, stats = process_batch(mock_batch_info_no_year)

        # Load the results from the pickle file
        with open(result_file_path, "rb") as f:
            processed_pubs = pickle.load(f)

        # The record should be skipped, so no publications should be processed
        assert len(processed_pubs) == 0
        assert stats.marc_count == 0
        assert stats.registration_matches_found == 0
        assert stats.renewal_matches_found == 0
        assert stats.skipped_no_year == 1  # Should track the skipped record

    def test_process_records_without_year_with_brute_force(
        self, mock_batch_info_no_year, monkeypatch, tmp_path
    ):
        """Test that records without year are processed when brute-force option is enabled"""
        # Create temp directory for results
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        # Enable brute force mode and update temp directory
        batch_info_list = list(mock_batch_info_no_year)
        # The batch info tuple has brute_force_missing_year at index 17 (after adding early_exit_publisher)
        batch_info_list[17] = True  # Set brute_force_missing_year to True
        batch_info_list[-1] = str(result_dir)  # Update result_temp_dir
        batch_info_brute_force = tuple(batch_info_list)

        # Set up mock worker data
        self._setup_mock_worker_data(monkeypatch)

        # Process the batch
        batch_id, result_file_path, stats = process_batch(batch_info_brute_force)

        # Load the results from the pickle file
        with open(result_file_path, "rb") as f:
            processed_pubs = pickle.load(f)

        # The record should be processed even without a year
        assert len(processed_pubs) == 1
        assert stats.marc_count == 1
        assert processed_pubs[0].original_title == "Test Book Without Year"

    def test_mixed_batch_skips_only_no_year_records(
        self, mock_batch_info_mixed, monkeypatch, tmp_path
    ):
        """Test that only records without year are skipped in a mixed batch"""

        # Create temp directory for results
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        # Update batch info with real temp directory
        batch_info_list = list(mock_batch_info_mixed)
        batch_info_list[-1] = str(result_dir)
        mock_batch_info_mixed = tuple(batch_info_list)

        # Set up mock worker data
        self._setup_mock_worker_data(monkeypatch)

        # Process the batch
        batch_id, result_file_path, stats = process_batch(mock_batch_info_mixed)

        # Load the results from the pickle file
        with open(result_file_path, "rb") as f:
            processed_pubs = pickle.load(f)

        # Only the record with a year should be processed
        assert len(processed_pubs) == 1
        assert stats.marc_count == 1
        assert stats.skipped_no_year == 1  # Should track the one skipped record
        assert processed_pubs[0].original_title == "Book With Year"
        assert processed_pubs[0].year == 2023

    def test_brute_force_match_type_for_no_year_records(
        self, mock_batch_info_no_year, monkeypatch, tmp_path
    ):
        """Test that matches for no-year records get 'brute_force_without_year' match type"""
        # Create temp directory for results
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        # Enable brute force mode and update temp directory
        batch_info_list = list(mock_batch_info_no_year)
        # The batch info tuple has brute_force_missing_year at index 17 (after adding early_exit_publisher)
        batch_info_list[17] = True  # Set brute_force_missing_year to True
        batch_info_list[-1] = str(result_dir)  # Update result_temp_dir
        batch_info_brute_force = tuple(batch_info_list)

        # Mock the indexes to return a match
        class MockIndexWithMatch:
            def __init__(self):
                # Store the mock publication
                self.publications = [
                    Publication(
                        title="Test Book Without Year",
                        author="Jones, Jane",
                        pub_date="1950",
                        source="Registration",
                        source_id="reg001",
                    )
                ]

            def find_candidates(self, pub):
                # Return index 0 to match the publication
                return [0]

            def get_stats(self):
                return {"title_keys": 0, "author_keys": 0}

            def size(self):
                return 1

        # Set up mock worker data with the custom index
        self._setup_mock_worker_data(monkeypatch, MockIndexWithMatch)

        # Also need to mock the matching engine's find_best_match to return a match
        def mock_find_best_match(self, marc_pub, candidates, *args, **kwargs):
            if candidates:
                return {
                    "copyright_record": {
                        "title": candidates[0].original_title,
                        "author": candidates[0].original_author,
                        "publisher": candidates[0].original_publisher,
                        "pub_date": candidates[0].pub_date,
                        "source_id": candidates[0].source_id,
                        "year": candidates[0].year,
                        "full_text": (
                            f"{candidates[0].original_title} by {candidates[0].original_author}"  # For renewal matching
                        ),
                        # Add normalized versions
                        "normalized_title": candidates[0].title,
                        "normalized_author": candidates[0].author,
                        "normalized_publisher": candidates[0].publisher,
                    },
                    "similarity_scores": {
                        "title": 100.0,
                        "author": 100.0,
                        "publisher": 50.0,
                        "combined": 100.0,
                    },
                    "is_lccn_match": False,
                    "match_type": MatchType.SIMILARITY,  # Default match type
                }
            return None

        monkeypatch.setattr(
            "marc_pd_tool.application.processing.matching_engine.DataMatcher.find_best_match",
            mock_find_best_match,
        )

        # Process the batch
        batch_id, result_file_path, stats = process_batch(batch_info_brute_force)

        # Load the results from the pickle file
        with open(result_file_path, "rb") as f:
            processed_pubs = pickle.load(f)

        # Check that the match was found
        assert len(processed_pubs) == 1
        assert processed_pubs[0].registration_match is not None
        # Check for BRUTE_FORCE_WITHOUT_YEAR match type
        assert processed_pubs[0].registration_match.match_type == MatchType.BRUTE_FORCE_WITHOUT_YEAR
        assert processed_pubs[0].registration_match.similarity_score == 100.0
